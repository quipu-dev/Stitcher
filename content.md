您的分析完全正确。

问题出在性能分析脚本 `scripts/profile_stitcher.py` 上。它通过硬编码的相对路径 `Path(__file__).parent.parent.resolve()` 来确定项目根目录。当从 `scripts` 目录运行时，这会将根目录错误地设置为 `stitcher-python` 的父目录（即 `Projects`），导致 `Workspace` 组件扫描该目录下的所有项目，引发了您观察到的长时间解析行为。

该脚本还直接导入并实例化了 `StitcherApp`，这绕过了 CLI 使用的、更为健壮的 `find_workspace_root` 工作区发现逻辑。

解决方案是重构这个脚本，使其不再直接调用内部 API，而是通过 `subprocess` 模块来执行 `stitcher` 的命令行接口。这不仅能解决路径问题，还能提供一个更高保真度的性能测试环境，因为它能模拟真实用户的使用场景，包含所有启动开销。

我将生成一个计划来执行这个重构。

## [WIP] refactor(tooling): 改进性能分析脚本以使用 CLI 子进程

### 错误分析
`profile_stitcher.py` 脚本存在两个核心问题：
1.  **错误的根目录计算**: 脚本使用 `Path(__file__).parent.parent.resolve()` 来定义 `root_path`。当从 `scripts/` 目录执行时，这会将工作区根目录设定为 `stitcher-python` 的父文件夹，导致 `Workspace` 扫描所有无关的项目。
2.  **绕过工作区发现**: 通过直接实例化 `StitcherApp(root_path=...)`，脚本绕过了 CLI 使用的、从当前目录向上查找项目根的 `find_workspace_root` 标准流程。这掩盖了路径错误，本应快速失败的场景变成了一个非常缓慢的全局扫描。

### 用户需求
用户希望性能分析脚本能够正确地识别项目边界。如果在错误的位置运行，它应该像 CLI 一样快速失败，而不是对无关目录进行耗时的解析。

### 评论
这是一个重要的开发者体验 (DX) 改进。性能分析工具必须在与真实使用场景一致的环境下运行，才能提供有意义的数据。当前的实现是脆弱的，并且会产生误导性的性能结果。

将其重构为通过子进程调用 CLI，可以将其与 `Stitcher` 的内部实现解耦，使其成为一个更健壮、更高保真的测试工具。

### 目标
1.  重构 `scripts/profile_stitcher.py` 脚本。
2.  移除对 `StitcherApp` 的直接导入和实例化。
3.  利用 `subprocess` 和 `pyinstrument` 的命令行接口来执行和分析 `stitcher` 命令。
4.  确保子进程在正确的项目根目录下执行，以利用应用本身的工作区发现机制。
5.  移除不再需要的 `sys.path` 注入逻辑，简化脚本。

### 基本原理
通过将 `pyinstrument` 和 `stitcher` 作为子进程命令来调用 (`python -m pyinstrument ... python -m stitcher.cli.main ...`)，我们实现了以下目标：
-   **高保真**: 性能数据将包含 CLI 的所有启动开销，完全模拟用户体验。
-   **正确性**: `stitcher` 进程将通过其标准入口点启动，该入口点会调用 `find_workspace_root`，从而确保它总是在正确的工作区内运行。
-   **解耦**: 脚本不再依赖 `StitcherApp` 的内部结构，降低了未来重构带来的维护成本。

### 标签
#intent/refine #intent/tooling #flow/ready #priority/medium #comp/build #scope/dx #task/domain/testing #task/object/profiler-script #task/action/refactor #task/state/begin

---

### Script

#### Acts 1: 重写性能分析脚本

我们将完全替换 `profile_stitcher.py` 的内容，使其成为一个健壮的、基于子进程的 CLI 调用器。

~~~~~act
write_file
scripts/profile_stitcher.py
~~~~~
~~~~~python
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
~~~~~

### 下一步建议
脚本重构完成后，您可以运行 `python scripts/profile_stitcher.py check` 来验证其行为是否符合预期。它应该会快速执行，并且只分析 `stitcher-python` 项目内的文件。

同时，可以考虑将这个脚本的调用方式加入到项目的贡献指南或开发者文档中，作为一个标准的性能测试工具。
