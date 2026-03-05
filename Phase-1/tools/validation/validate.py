#!/usr/bin/env python3
"""
Trace Validation Suite for Wormhole SIT Engine
Tests residency detection, state conservation, and SIT metric ranges

Usage:
    python3 validate_trace.py --trace-dir runs/cpu/fm_mm/tiny
    python3 validate_trace.py --trace-dir runs/spike/fm_mm/tiny --verbose
    python3 validate_trace.py --all-runs runs/  # Check all subdirectories
"""

import argparse
import pandas as pd
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import sys
from collections import defaultdict

# ANSI colors for output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'

def print_header(text: str):
    """Print formatted header"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*70}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text:^70}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*70}{Colors.END}\n")

def print_pass(text: str):
    """Print passing test"""
    print(f"{Colors.GREEN}✓ PASS:{Colors.END} {text}")

def print_fail(text: str):
    """Print failing test"""
    print(f"{Colors.RED}✗ FAIL:{Colors.END} {text}")

def print_warn(text: str):
    """Print warning"""
    print(f"{Colors.YELLOW}⚠ WARN:{Colors.END} {text}")

def print_info(text: str):
    """Print info"""
    print(f"{Colors.BLUE}ℹ INFO:{Colors.END} {text}")


class TraceValidator:
    """Validates trace files for correctness and physical plausibility"""
    
    def __init__(self, trace_dir: Path, verbose: bool = False):
        self.trace_dir = Path(trace_dir)
        self.verbose = verbose
        self.state_csv = self.trace_dir / "inputs" / "state_intervals.csv"
        self.resid_csv = self.trace_dir / "inputs" / "residency_intervals.csv"
        self.export_csv = self.trace_dir / "export" / "windows_v1.csv"
        
        self.results = {
            'marker_detection': False,
            'state_conservation': False,
            'sit_validation': False,
            'errors': [],
            'warnings': []
        }
    
    def validate_files_exist(self) -> bool:
        """Check if required files exist"""
        print_info(f"Checking directory: {self.trace_dir}")
        
        files_ok = True
        for filepath, name in [
            (self.state_csv, "state_intervals.csv"),
            (self.resid_csv, "residency_intervals.csv"),
        ]:
            if filepath.exists():
                print_pass(f"Found {name}")
            else:
                print_fail(f"Missing {name}")
                self.results['errors'].append(f"Missing file: {name}")
                files_ok = False
        
        # Export is optional
        if self.export_csv.exists():
            print_pass(f"Found exports/windows_v1.csv")
        else:
            print_warn(f"No exports/run_windows_v1.csv (run classify step to generate)")
        
        return files_ok
    
    # ========================================================================
    # TEST 1.1: MARKER DETECTION
    # ========================================================================
    
    def test_marker_detection(self) -> bool:
        """
        Test 1.1: Verify residency regions are detected correctly
        
        Checks:
        - Residency intervals exist
        - Residency regions are non-empty
        - Residency doesn't exceed total time
        - Multiple cores handled correctly
        """
        print_header("TEST 1.1: MARKER DETECTION")
        
        try:
            resid_df = pd.read_csv(self.resid_csv)
        except Exception as e:
            print_fail(f"Cannot read residency CSV: {e}")
            self.results['errors'].append(f"Residency read error: {e}")
            return False
        
        # Check required columns
        required_cols = ['start_us', 'end_us', 'core']
        missing = set(required_cols) - set(resid_df.columns)
        if missing:
            print_fail(f"Missing columns in residency CSV: {missing}")
            self.results['errors'].append(f"Missing residency columns: {missing}")
            return False
        
        print_pass(f"Residency CSV has required columns: {list(resid_df.columns)}")
        
        # Check for residency intervals
        if len(resid_df) == 0:
            print_fail("No residency intervals detected!")
            print_info("  Possible causes:")
            print_info("    1. Markers (101/102) not in compiled code")
            print_info("    2. Spike adapter not detecting markers")
            print_info("    3. Using PC threshold fallback (check resident_pc_ge)")
            self.results['errors'].append("No residency intervals")
            return False
        
        print_pass(f"Found {len(resid_df)} residency interval(s)")
        
        # Analyze per-core residency
        cores = sorted(resid_df['core'].unique())
        print_info(f"Cores with residency: {cores}")
        
        all_cores_ok = True
        for core in cores:
            core_resid = resid_df[resid_df['core'] == core]
            
            # Calculate total residency time
            total_resident = (core_resid['end_us'] - core_resid['start_us']).sum()
            max_time = core_resid['end_us'].max()
            
            if total_resident <= 0:
                print_fail(f"  Core {core}: Zero residency time!")
                self.results['errors'].append(f"Core {core}: No resident time")
                all_cores_ok = False
                continue
            
            residency_pct = (total_resident / max_time * 100) if max_time > 0 else 0
            
            print_info(f"  Core {core}:")
            print_info(f"    Regions: {len(core_resid)}")
            print_info(f"    Total resident: {total_resident:.1f} us ({residency_pct:.1f}%)")
            print_info(f"    Trace duration: {max_time:.1f} us")
            
            # Check for physical plausibility
            if residency_pct > 100.1:  # Allow small floating point error
                print_fail(f"    Core {core}: Residency > 100% (impossible!)")
                self.results['errors'].append(f"Core {core}: residency {residency_pct:.1f}% > 100%")
                all_cores_ok = False
            elif residency_pct < 1:
                print_warn(f"    Core {core}: Very low residency ({residency_pct:.1f}%)")
                self.results['warnings'].append(f"Core {core}: Low residency {residency_pct:.1f}%")
            else:
                print_pass(f"    Core {core}: Residency percentage OK")
            
            # Show first few intervals if verbose
            if self.verbose and len(core_resid) > 0:
                print_info("    First residency intervals:")
                for idx, row in core_resid.head(3).iterrows():
                    duration = row['end_us'] - row['start_us']
                    print_info(f"      [{idx}] {row['start_us']:.1f} -> {row['end_us']:.1f} us (duration: {duration:.1f} us)")
        
        if all_cores_ok:
            print_pass("All cores have valid residency")
            self.results['marker_detection'] = True
            return True
        else:
            print_fail("Some cores have residency issues")
            return False
    
    # ========================================================================
    # TEST 1.2: STATE CONSERVATION
    # ========================================================================
    
    def test_state_conservation(self) -> bool:
        """
        Test 1.2: Verify state percentages sum to 100%
        
        Checks:
        - All time is accounted for (no gaps)
        - States don't overlap
        - State percentages sum to ~100%
        - Each state has reasonable percentage
        """
        print_header("TEST 1.2: STATE CONSERVATION")
        
        try:
            state_df = pd.read_csv(self.state_csv)
        except Exception as e:
            print_fail(f"Cannot read state CSV: {e}")
            self.results['errors'].append(f"State read error: {e}")
            return False
        
        # Check required columns
        required_cols = ['start_us', 'end_us', 'core', 'state']
        missing = set(required_cols) - set(state_df.columns)
        if missing:
            print_fail(f"Missing columns in state CSV: {missing}")
            self.results['errors'].append(f"Missing state columns: {missing}")
            return False
        
        print_pass(f"State CSV has required columns: {list(state_df.columns)}")
        
        if len(state_df) == 0:
            print_fail("No state intervals found!")
            self.results['errors'].append("No state intervals")
            return False
        
        print_pass(f"Found {len(state_df)} state interval(s)")
        
        # Check valid states
        valid_states = {'active', 'idle', 'stall'}
        actual_states = set(state_df['state'].unique())
        invalid_states = actual_states - valid_states
        
        if invalid_states:
            print_fail(f"Invalid states found: {invalid_states}")
            self.results['errors'].append(f"Invalid states: {invalid_states}")
            return False
        
        print_pass(f"All states valid: {sorted(actual_states)}")
        
        # Analyze per-core conservation
        cores = sorted(state_df['core'].unique())
        print_info(f"Cores with state data: {cores}")
        
        all_cores_ok = True
        for core in cores:
            core_states = state_df[state_df['core'] == core].sort_values('start_us')
            
            print_info(f"\n  Core {core}:")
            
            # Calculate state durations
            state_times = {}
            for state in valid_states:
                state_intervals = core_states[core_states['state'] == state]
                state_time = (state_intervals['end_us'] - state_intervals['start_us']).sum()
                state_times[state] = state_time
            
            total_time = sum(state_times.values())
            
            if total_time <= 0:
                print_fail(f"    Total time is zero!")
                self.results['errors'].append(f"Core {core}: Zero total time")
                all_cores_ok = False
                continue
            
            print_info(f"    Total time: {total_time:.1f} us")
            
            # Calculate percentages
            state_pcts = {}
            for state in valid_states:
                pct = (state_times[state] / total_time * 100) if total_time > 0 else 0
                state_pcts[state] = pct
                print_info(f"    {state:>6}: {state_times[state]:>10.1f} us ({pct:>5.1f}%)")
            
            # Check conservation (sum should be ~100%)
            total_pct = sum(state_pcts.values())
            
            if abs(total_pct - 100.0) < 0.1:
                print_pass(f"    Conservation OK: {total_pct:.2f}% ≈ 100%")
            elif abs(total_pct - 100.0) < 1.0:
                print_warn(f"    Small gap: {total_pct:.2f}% (within 1% tolerance)")
                self.results['warnings'].append(f"Core {core}: {total_pct:.2f}% (not exactly 100%)")
            else:
                print_fail(f"    Conservation FAIL: {total_pct:.2f}% ≠ 100%")
                self.results['errors'].append(f"Core {core}: {total_pct:.2f}% ≠ 100%")
                all_cores_ok = False
            
            # Check for gaps or overlaps
            gaps_found = False
            overlaps_found = False
            
            for i in range(len(core_states) - 1):
                curr_end = core_states.iloc[i]['end_us']
                next_start = core_states.iloc[i + 1]['start_us']
                
                if next_start > curr_end + 0.001:  # Gap
                    if not gaps_found and self.verbose:
                        print_warn(f"    Gap detected: {curr_end:.1f} -> {next_start:.1f} us")
                    gaps_found = True
                elif next_start < curr_end - 0.001:  # Overlap
                    if not overlaps_found and self.verbose:
                        print_warn(f"    Overlap detected at {next_start:.1f} us")
                    overlaps_found = True
            
            if gaps_found:
                print_warn(f"    Gaps found in timeline (time not accounted for)")
                self.results['warnings'].append(f"Core {core}: Timeline gaps")
            
            if overlaps_found:
                print_fail(f"    Overlaps found in timeline (impossible!)")
                self.results['errors'].append(f"Core {core}: Timeline overlaps")
                all_cores_ok = False
            
            if not gaps_found and not overlaps_found:
                print_pass(f"    Timeline continuity OK")
            
            # Check for physically plausible ratios
            # Wormhole baseline: ~60% active, ~30% idle, ~5-10% stall
            if 'active' in state_pcts:
                if state_pcts['active'] < 20:
                    print_warn(f"    Very low active time ({state_pcts['active']:.1f}%)")
                    self.results['warnings'].append(f"Core {core}: Low active {state_pcts['active']:.1f}%")
                elif state_pcts['active'] > 90:
                    print_warn(f"    Unusually high active time ({state_pcts['active']:.1f}%)")
                    self.results['warnings'].append(f"Core {core}: High active {state_pcts['active']:.1f}%")
            
            if 'stall' in state_pcts:
                if state_pcts['stall'] > 50:
                    print_warn(f"    Very high stall time ({state_pcts['stall']:.1f}%)")
                    print_warn(f"      Check if spike adapter has 'is_stall = False'")
                    self.results['warnings'].append(f"Core {core}: High stall {state_pcts['stall']:.1f}%")
        
        if all_cores_ok:
            print_pass("\nAll cores pass state conservation")
            self.results['state_conservation'] = True
            return True
        else:
            print_fail("\nSome cores fail state conservation")
            return False
    
    # ========================================================================
    # TEST 1.3: SIT RANGE VALIDATION
    # ========================================================================
    
    def test_sit_validation(self) -> bool:
        """
        Test 1.3: Ensure SIT falls in physically plausible ranges
        
        Checks:
        - SIT metric exists in exports
        - SIT is in valid range [0.0, 1.0]
        - SIT matches expected range for configuration
        - Wormhole targets: 0.50-0.60 baseline, 0.45-0.50 with overflow
        """
        print_header("TEST 1.3: SIT RANGE VALIDATION")
        
        if not self.export_csv.exists():
            print_warn("No exports/windows_v1.csv found")
            print_info("  Run classify step to generate SIT metrics:")
            print_info("    python cli.py classify --in <trace_dir> --window-us 128")
            self.results['warnings'].append("No SIT export file")
            return False
        
        try:
            export_df = pd.read_csv(self.export_csv)
        except Exception as e:
            print_fail(f"Cannot read export CSV: {e}")
            self.results['errors'].append(f"Export read error: {e}")
            return False
        
        # Check for SIT column
        sit_col = None
        for col in ['sit', 'SIT', 'sit_metric', 'SIT_metric']:
            if col in export_df.columns:
                sit_col = col
                break
        
        if sit_col is None:
            print_fail("No SIT metric column found in exports")
            print_info(f"  Available columns: {list(export_df.columns)}")
            self.results['errors'].append("No SIT column in exports")
            return False
        
        print_pass(f"Found SIT metric column: '{sit_col}'")
        
        # Calculate SIT statistics
        sit_values = export_df[sit_col].dropna()
        
        if len(sit_values) == 0:
            print_fail("No SIT values found!")
            self.results['errors'].append("No SIT values")
            return False
        
        sit_min = sit_values.min()
        sit_max = sit_values.max()
        sit_mean = sit_values.mean()
        sit_median = sit_values.median()
        sit_std = sit_values.std()
        
        print_info(f"SIT Statistics ({len(sit_values)} windows):")
        print_info(f"  Min:    {sit_min:.4f}")
        print_info(f"  Max:    {sit_max:.4f}")
        print_info(f"  Mean:   {sit_mean:.4f}")
        print_info(f"  Median: {sit_median:.4f}")
        print_info(f"  StdDev: {sit_std:.4f}")
        
        # Physical validity checks
        all_valid = True
        
        # Check: SIT must be in [0, 1]
        if sit_min < 0.0:
            print_fail(f"SIT below 0.0 (minimum: {sit_min:.4f}) - impossible!")
            self.results['errors'].append(f"SIT < 0: {sit_min:.4f}")
            all_valid = False
        
        if sit_max > 1.0:
            print_fail(f"SIT above 1.0 (maximum: {sit_max:.4f}) - impossible!")
            self.results['errors'].append(f"SIT > 1: {sit_max:.4f}")
            all_valid = False
        
        if 0.0 <= sit_min and sit_max <= 1.0:
            print_pass(f"SIT in valid range [0.0, 1.0]")
        
        # Wormhole-specific target ranges
        print_info("\nWormhole Target Ranges:")
        print_info("  Baseline (data in SRAM):        0.50 - 0.60")
        print_info("  Memory overflow (GDDR6 access): 0.45 - 0.50")
        print_info("  Branch mispredicts:             0.50 - 0.55")
        
        # Classify result
        if sit_mean >= 0.55 and sit_mean <= 0.65:
            print_pass(f"Mean SIT {sit_mean:.4f} in BASELINE range ✓")
            print_info("  → Indicates data fits in SRAM, minimal stalls")
        elif sit_mean >= 0.45 and sit_mean <= 0.54:
            print_pass(f"Mean SIT {sit_mean:.4f} in OVERFLOW/MISPREDICT range ✓")
            print_info("  → Indicates GDDR6 access or branch stalls")
        #elif sit_mean >= 0.40 and sit_mean < 0.45:
            #print_warn(f"Mean SIT {sit_mean:.4f} below expected range")
            #print_info("  → Check for excessive stalls or misconfiguration")
            #self.results['warnings'].append(f"Low SIT: {sit_mean:.4f}")
        elif sit_mean > 0.65:
            print_warn(f"Mean SIT {sit_mean:.4f} above expected range")
            print_info("  → Unusually high efficiency (check workload)")
            self.results['warnings'].append(f"High SIT: {sit_mean:.4f}")
        elif sit_mean < 0.40:
            print_fail(f"Mean SIT {sit_mean:.4f} too low!")
            print_info("  Possible causes:")
            print_info("    1. spike_adapter.py still has 'is_stall = True' for memory ops")
            print_info("    2. Excessive idle time in workload")
            print_info("    3. Configuration error")
            self.results['errors'].append(f"SIT too low: {sit_mean:.4f}")
            all_valid = False
        
        # Check for stability (low variance is good)
        if sit_std < 0.05:
            print_pass(f"Low variance ({sit_std:.4f}) - stable performance ✓")
        elif sit_std < 0.10:
            print_info(f"Moderate variance ({sit_std:.4f}) - acceptable")
        else:
            print_warn(f"High variance ({sit_std:.4f}) - inconsistent performance")
            self.results['warnings'].append(f"High SIT variance: {sit_std:.4f}")
        
        # Distribution analysis (if verbose)
        if self.verbose and len(sit_values) > 10:
            print_info("\nSIT Distribution:")
            bins = [0.0, 0.3, 0.4, 0.5, 0.6, 0.7, 1.0]
            for i in range(len(bins) - 1):
                count = ((sit_values >= bins[i]) & (sit_values < bins[i+1])).sum()
                pct = (count / len(sit_values)) * 100
                print_info(f"  [{bins[i]:.1f}, {bins[i+1]:.1f}): {count:4d} windows ({pct:5.1f}%)")
        
        if all_valid:
            print_pass("\nSIT metrics are physically valid")
            self.results['sit_validation'] = True
            return True
        else:
            print_fail("\nSIT metrics have issues")
            return False
    
    # ========================================================================
    # SUMMARY
    # ========================================================================
    
    def print_summary(self):
        """Print validation summary"""
        print_header("VALIDATION SUMMARY")
        
        total_tests = 3
        passed_tests = sum([
            self.results['marker_detection'],
            self.results['state_conservation'],
            self.results['sit_validation']
        ])
        
        print(f"Tests Passed: {passed_tests}/{total_tests}\n")
        
        # Individual test results
        tests = [
            ("Marker Detection", self.results['marker_detection']),
            ("State Conservation", self.results['state_conservation']),
            ("SIT Validation", self.results['sit_validation'])
        ]
        
        for test_name, passed in tests:
            if passed:
                print_pass(f"{test_name}")
            else:
                print_fail(f"{test_name}")
        
        # Errors
        if self.results['errors']:
            # CORRECT - Colors.END inside f-string
            print(f"\n{Colors.RED}Errors ({len(self.results['errors'])}){Colors.END}:")
            for error in self.results['errors']:
                print(f"  • {error}")
        
        # Warnings
        if self.results['warnings']:
            print(f"\n{Colors.YELLOW}Warnings ({len(self.results['warnings'])}){Colors.END}:")
            for warning in self.results['warnings']:
                print(f"  • {warning}")
        
        # Overall result
        print()
        if passed_tests == total_tests and not self.results['errors']:
            print_pass(f"{Colors.BOLD}ALL TESTS PASSED ✓{Colors.END}")
            return 0
        elif passed_tests > 0 and not self.results['errors']:
            print_warn(f"{Colors.BOLD}SOME TESTS PASSED (with warnings){Colors.END}")
            return 1
        else:
            print_fail(f"{Colors.BOLD}VALIDATION FAILED ✗{Colors.END}")
            return 2
    
    def run_all_tests(self) -> int:
        """Run all validation tests"""
        if not self.validate_files_exist():
            return 2
        
        print()  # Spacing
        
        # Run tests
        self.test_marker_detection()
        self.test_state_conservation()
        self.test_sit_validation()
        
        # Summary
        return self.print_summary()


def validate_directory(trace_dir: Path, verbose: bool = False) -> int:
    """Validate a single trace directory"""
    validator = TraceValidator(trace_dir, verbose)
    return validator.run_all_tests()


def find_all_trace_dirs(root_dir: Path) -> List[Path]:
    """Find all directories with trace files"""
    trace_dirs = []
    
    for path in root_dir.rglob("inputs/state_intervals.csv"):
        trace_dir = path.parent.parent
        trace_dirs.append(trace_dir)
    
    return sorted(trace_dirs)


def main():
    parser = argparse.ArgumentParser(
        description="Validate Wormhole SIT engine trace files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Validate single trace directory
  %(prog)s --trace-dir runs/cpu/fm_mm/tiny
  
  # Validate with verbose output
  %(prog)s --trace-dir runs/spike/fm_mm/tiny --verbose
  
  # Validate all traces in directory tree
  %(prog)s --all-runs runs/
  
  # Validate specific trace with detailed output
  %(prog)s -d runs/cpu/fm_mm/tiny -v
        """
    )
    
    parser.add_argument(
        "-d", "--trace-dir",
        type=Path,
        help="Path to trace directory (contains inputs/ and exports/)"
    )
    
    parser.add_argument(
        "-a", "--all-runs",
        type=Path,
        help="Validate all trace directories under this path"
    )
    
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Show detailed output"
    )
    
    args = parser.parse_args()
    
    if not args.trace_dir and not args.all_runs:
        parser.print_help()
        print(f"\n{Colors.RED}Error: Must specify --trace-dir or --all-runs{Colors.END}")
        return 1
    
    if args.all_runs:
        # Find and validate all trace directories
        trace_dirs = find_all_trace_dirs(args.all_runs)
        
        if not trace_dirs:
            print_fail(f"No trace directories found under {args.all_runs}")
            return 1
        
        print_header(f"FOUND {len(trace_dirs)} TRACE DIRECTORIES")
        for td in trace_dirs:
            print(f"  • {td.relative_to(args.all_runs)}")
        print()
        
        # Validate each
        results = {}
        for trace_dir in trace_dirs:
            print(f"\n{Colors.BOLD}{'='*70}{Colors.END}")
            print(f"{Colors.BOLD}Validating: {trace_dir.relative_to(args.all_runs)}{Colors.END}")
            print(f"{Colors.BOLD}{'='*70}{Colors.END}")
            
            exit_code = validate_directory(trace_dir, args.verbose)
            results[trace_dir] = exit_code
        
        # Summary of all
        print_header("OVERALL SUMMARY")
        passed = sum(1 for code in results.values() if code == 0)
        warned = sum(1 for code in results.values() if code == 1)
        failed = sum(1 for code in results.values() if code == 2)
        
        print(f"Total: {len(results)} directories")
        print_pass(f"Passed: {passed}")
        if warned > 0:
            print_warn(f"Warned: {warned}")
        if failed > 0:
            print_fail(f"Failed: {failed}")
        
        return 0 if failed == 0 else 1
    
    else:
        # Single directory validation
        return validate_directory(args.trace_dir, args.verbose)


if __name__ == "__main__":
    sys.exit(main())