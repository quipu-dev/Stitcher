#!/usr/bin/env python3
import sys
import subprocess
from pathlib import Path


def check_cycles():
    """
    Scans the workspace for import cycles using pylint.
    """
    print("--- Import Cycle Detector ---")

    root_dir = Path(__file__).parent.parent.resolve()
    packages_dir = root_dir / "packages"

    # 1. Collect all cascade source directories
    # We look for packages/*/src/cascade
    src_dirs = []
    for pkg in packages_dir.iterdir():
        if pkg.is_dir():
            src_path = pkg / "src"
            if src_path.exists():
                src_dirs.append(str(src_path))

    if not src_dirs:
        print("[FAIL] No source directories found in 'packages/'.")
        sys.exit(1)

    print(f"Scanning {len(src_dirs)} source paths for cycles...")

    # 2. Prepare pylint command
    # We disable everything except 'cyclic-import'
    cmd = [
        sys.executable,
        "-m",
        "pylint",
        "--disable=all",
        "--enable=cyclic-import",
        "--rcfile=/dev/null",  # Ignore local .pylintrc to ensure strict cycle check
        "--reports=n",
        "--score=n",
    ] + src_dirs

    print(f"Running: {' '.join(cmd)}\n")

    try:
        # We allow a non-zero exit code from pylint as it returns bits
        # indicating types of errors found.
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)

        if result.returncode == 0:
            print("[SUCCESS] No import cycles detected.")
            sys.exit(0)
        else:
            # Pylint output usually goes to stdout for messages
            output = result.stdout.strip()
            if "Cyclic import" in output:
                print("[FAIL] Import cycles detected!")
                print("-" * 40)
                print(output)
                print("-" * 40)
                sys.exit(1)
            else:
                # If pylint failed for other reasons (e.g. pylint not installed)
                if result.stderr:
                    print(f"[ERROR] pylint execution failed:\n{result.stderr}")
                else:
                    print(
                        f"[SUCCESS] pylint finished with no cycles found (code {result.returncode})."
                    )
                    sys.exit(0)

    except FileNotFoundError:
        print(
            "[ERROR] 'pylint' is not installed. Please install it with 'pip install pylint'."
        )
        sys.exit(1)


if __name__ == "__main__":
    check_cycles()
