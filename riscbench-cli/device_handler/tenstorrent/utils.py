import subprocess
import os

#from dh_helper import shared

env_d = dict(os.environ)

def run_executable(script_name, target_dir, venv_path=None, env_arg=None):
    commands = []

    if venv_path:
        activate_script = os.path.join(venv_path, "bin", "activate")
        commands.append(f"source {activate_script}")

    if env_arg:
        for arg in env_arg:
            iarg = arg.split("=")
            env_d[iarg[0]] = iarg[1]

    env_d["TT_METAL_HOME"] = "" #shared.HOME

    commands.append(f"./{script_name}")
    full_command = " && ".join(commands)

    try:
        print(f"--- Executing: {script_name} (Venv: {bool(venv_path)}) ---")
        
        result = subprocess.Popen(
            full_command,
            cwd=target_dir,
            shell=True,
            executable="/bin/bash",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, # Redirect stderr to stdout to catch everything in one stream
            text=True,
            bufsize=1, # Line-buffered for real-time responsiveness
            env = env_d
        )

        for line in result.stdout:
            print(line, end="")

        result.wait()

        if result.returncode == 0:
            print("Program Executed without Errors")
        else:
            print(f"Error (Exit Code {result.returncode}):\n", result.stderr)

    except Exception as e:
        print(f"Failed to execute: {e}")

def run_command(command, target_dir):
    try:
        print(f"--- Executing: {command} ---")
        
        result = subprocess.Popen(
            command,
            cwd=target_dir,
            shell=True,
            executable="/bin/bash",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, # Redirect stderr to stdout to catch everything in one stream
            text=True,
            bufsize=1 # Line-buffered for real-time responsiveness
        )

        for line in result.stdout:
            print(line, end="")

        result.wait()

        if result.returncode == 0:
            print("Program Executed without Errors")
        else:
            print(f"Error (Exit Code {result.returncode}):\n", result.stderr)

    except Exception as e:
        print(f"Failed to execute: {e}")
