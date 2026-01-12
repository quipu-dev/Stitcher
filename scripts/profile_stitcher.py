import sys
import time
import argparse
from pathlib import Path
from stitcher.app import StitcherApp
from stitcher.adapter.python.griffe_parser import GriffePythonParser
from stitcher.adapter.python import PythonTransformer, PythonFingerprintStrategy

# --- 1. 自动路径注入 (Automation of sys.path) ---
project_root = Path(__file__).parent.parent.resolve()
packages_dir = project_root / "packages"


def setup_paths():
    added_count = 0
    if packages_dir.exists():
        for pkg in packages_dir.iterdir():
            if pkg.is_dir():
                src_path = pkg / "src"
                if src_path.exists():
                    sys.path.insert(0, str(src_path))
                    added_count += 1
    return added_count


# 在任何可能触发导入的操作前执行路径设置
pkgs_added = setup_paths()

# --- 2. 采样分析器检查 ---
try:
    from pyinstrument import Profiler
except ImportError:
    print(
        "❌ Error: 'pyinstrument' not found. Please install it with: pip install pyinstrument"
    )
    sys.exit(1)

# --- 3. 记录导入耗时 (Startup latency) ---
t_start_imports = time.perf_counter()
# 核心组件导入

t_end_imports = time.perf_counter()


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
        ],
        help="The stitcher command to profile",
    )
    parser.add_argument("--html", action="store_true", help="Output results as HTML")
    args = parser.parse_args()

    # --- 4. 应用初始化 ---
    app_init_start = time.perf_counter()

    st_parser = GriffePythonParser()
    transformer = PythonTransformer()
    strategy = PythonFingerprintStrategy()

    app = StitcherApp(
        root_path=project_root,
        parser=st_parser,
        transformer=transformer,
        fingerprint_strategy=strategy,
    )

    # 建立命令映射
    commands = {
        "cov": lambda: app.run_cov(),
        "check": lambda: app.run_check(),
        "init": lambda: app.run_init(),
        "pump": lambda: app.run_pump(strip=False),
        "generate": lambda: app.run_from_config(),
        "inject": lambda: app.run_inject(),
        "strip": lambda: app.run_strip(),
        "index": lambda: app.run_index_build(),
    }

    target_action = commands[args.command]
    app_init_end = time.perf_counter()

    # --- 5. 执行分析 ---
    print("--- Stitcher Diagnostics ---")
    print(f"Packages auto-loaded: {pkgs_added}")
    print(f"Imports latency:      {(t_end_imports - t_start_imports) * 1000:.2f} ms")
    print(f"App Init latency:     {(app_init_end - app_init_start) * 1000:.2f} ms")
    print("-" * 27)

    profiler = Profiler(interval=0.001)
    profiler.start()

    print(f"🚀 Profiling 'stitcher {args.command}'...")
    try:
        target_action()
    except Exception as e:
        print(f"❌ Command failed during profiling: {e}")
    finally:
        profiler.stop()

    # --- 6. 报告输出 ---
    if args.html:
        output_file = project_root / f"profile_{args.command}.html"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(profiler.output_html())
        print(f"✨ HTML report saved to: {output_file}")
    else:
        profiler.print()


if __name__ == "__main__":
    main()
