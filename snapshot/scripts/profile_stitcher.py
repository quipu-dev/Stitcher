import sys
import argparse
import subprocess
from pathlib import Path

# --- 1. Project Root Determination ---
# This is now only used to set the CWD for the subprocess, which is correct.
project_root = Path(__file__).parent.parent.resolve()

# --- 2. Pyinstrument Check ---
try:
    import pyinstrument
except ImportError:
    print(
        "❌ Error: 'pyinstrument' not found. Please install it with: pip install pyinstrument"
    )
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Stitcher Performance Profiler")
    parser.add_argument(
        "command",
        choices=[
            "cov",
            "check",
            "init",
            "pump",
            "generate",
            "inject",
            "strip",
            "index",
            "refactor",
        ],
        help="The stitcher command to profile.",
    )
    parser.add_argument(
        "subcommand_args",
        nargs=argparse.REMAINDER,
        help="Additional arguments for the command (e.g., 'apply my-migration.py' for refactor).",
    )
    parser.add_argument(
        "--html",
        action="store_true",
        help="Output results as HTML instead of printing to console.",
    )
    args = parser.parse_args()

    # --- 3. Command Construction ---
    # Use pyinstrument's CLI interface for robust subprocess profiling.
    # We use sys.executable to ensure we're using the python from the current env.

    output_renderer = "html" if args.html else "console"
    output_file_name = f"profile_{args.command}.html"

    cmd = [
        sys.executable,
        "-m",
        "pyinstrument",
        "--renderer",
        output_renderer,
    ]

    if args.html:
        cmd.extend(["--outfile", output_file_name])

    # Add the stitcher command to be profiled
    cmd.extend(
        [
            "-m",
            "stitcher.cli.main",
            args.command,
        ]
    )

    # Add any remaining arguments
    if args.subcommand_args:
        cmd.extend(args.subcommand_args)

    # --- 4. Execution ---
    print(f"🚀 Profiling: {' '.join(cmd)}")
    print(f"📂 Working Directory: {project_root}")
    print("-" * 27)

    try:
        # We run the command from the project root to ensure correct workspace discovery.
        result = subprocess.run(
            cmd,
            cwd=project_root,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

        # Print stitcher's own output if not rendering to console
        if args.html or output_renderer != "console":
            print("--- Stitcher Output ---")
            print(result.stdout)
            if result.stderr:
                print("--- Stitcher Stderr ---")
                print(result.stderr)
            print("-" * 23)

    except subprocess.CalledProcessError as e:
        print(f"\n❌ Profiling failed. Command exited with status {e.returncode}.")
        print("--- Stderr ---")
        print(e.stderr)
        print("--- Stdout ---")
        print(e.stdout)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n🛑 Profiling interrupted by user.")
        sys.exit(1)

    # --- 5. Report ---
    if args.html:
        print(f"✨ HTML report saved to: {project_root / output_file_name}")
    else:
        # Pyinstrument with 'console' renderer prints directly to stdout.
        # We captured it, so let's print it.
        print(result.stdout)


if __name__ == "__main__":
    main()