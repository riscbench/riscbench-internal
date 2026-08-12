import sys
import termios
import tty

# ANSI Escape Sequences
CLEAR_LINE = "\x1b[2K"
CURSOR_UP = "\x1b[1A"
HIDE_CURSOR = "\x1b[?25l"
SHOW_CURSOR = "\x1b[?25h"
COLOR_CYAN = "\x1b[36m"
COLOR_GRAY = "\x1b[90m"
COLOR_RESET = "\x1b[0m"
BOLD = "\x1b[1m"

# AIHF
def get_key():
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(sys.stdin.fileno())
        ch = sys.stdin.read(1)
        if ch == "\x1b":  # Arrow keys start with escape characters
            ch += sys.stdin.read(2)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    return ch

# AIHF
def select_menu(question, options):
    selected_index = 0
    num_options = len(options)

    sys.stdout.write(HIDE_CURSOR)
    sys.stdout.flush()

    try:
        while True:
            # Print Question
            sys.stdout.write(f"{COLOR_CYAN}?{COLOR_RESET} {BOLD}{question}{COLOR_RESET}\n")

            # Print Options
            for i, option in enumerate(options):
                if i == selected_index:
                    sys.stdout.write(f" {COLOR_CYAN}❯ {option}{COLOR_RESET}\n")
                else:
                    sys.stdout.write(f"   {COLOR_GRAY}{option}{COLOR_RESET}\n")

            sys.stdout.flush()

            # Wait for user input
            key = get_key()

            # Clear the menu lines to prepare for re-rendering
            # Total lines = 1 (question) + number of options
            total_lines = 1 + num_options
            sys.stdout.write((CURSOR_UP + CLEAR_LINE) * total_lines)

            # Handle Actions
            if key in ("\x1b[A", "k"):  # Up Arrow or 'k'
                selected_index = (selected_index - 1) % num_options
            elif key in ("\x1b[B", "j"):  # Down Arrow or 'j'
                selected_index = (selected_index + 1) % num_options
            elif key in ("\r", "\n"):  # Enter key
                # Print the final chosen answer styled nicely like questionary
                sys.stdout.write(
                    f"{COLOR_CYAN}?{COLOR_RESET} {BOLD}{question}{COLOR_RESET} {COLOR_CYAN}{options[selected_index]}{COLOR_RESET}\n"
                )
                return options[selected_index], selected_index
            elif key == "\x03":  # Ctrl+C
                raise KeyboardInterrupt

    finally:
        # Always restore the cursor
        sys.stdout.write(SHOW_CURSOR)
        sys.stdout.flush()