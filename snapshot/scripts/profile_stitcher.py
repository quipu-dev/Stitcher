import sys
from pathlib import Path

# --- 1. 环境准备 (Monorepo 开发环境) ---
# 确保在开发环境下，即使没有执行 pip install -e，也能找到 packages 目录下的源码。
project_root = Path(__file__).parent.parent.resolve()
packages_dir = project_root / "packages"

if packages_dir.exists():
    # 将所有 package 的 src 目录加入 sys.path
    # 按照字母顺序排序以确保加载顺序的确定性
    for pkg in sorted(packages_dir.iterdir()):
        if pkg.is_dir():
            src_path = pkg / "src"
            if src_path.exists():
                sys.path.insert(0, str(src_path))

# --- 2. 性能分析器检查 ---
try:
    from pyinstrument import Profiler
except ImportError:
    print(
        "❌ 错误: 未找到 'pyinstrument'。请通过以下命令安装: pip install pyinstrument"
    )
    sys.exit(1)

# --- 3. 导入 CLI 入口 ---
# 注意：必须在设置完 sys.path 后导入，否则无法找到内部 package。
try:
    from stitcher.cli.main import app
except ImportError as e:
    print(f"❌ 错误: 无法加载 Stitcher CLI。请检查 packages 目录结构。({e})")
    sys.exit(1)


def main():
    # 拦截并提取分析器专用的标志
    html_mode = "--html" in sys.argv
    if html_mode:
        sys.argv.remove("--html")

    # 提取命令名称用于报告文件名
    # sys.argv[0] 是脚本路径，sys.argv[1] 通常是 CLI 的子命令（如 cov, check）
    cmd_name = "stitcher"
    if len(sys.argv) > 1:
        cmd_name = sys.argv[1]

    profiler = Profiler(interval=0.001)

    print(f"🚀 正在分析 'stitcher {' '.join(sys.argv[1:])}'...")
    profiler.start()

    try:
        # 委托给真实的 Typer 应用执行。
        # Typer 会解析剩余的 sys.argv 参数，行为与直接运行 stitcher 完全一致。
        app()
    except SystemExit:
        # Typer 或 Click 可能会通过 SystemExit 正常退出，此处不应将其视为错误
        pass
    except Exception as e:
        print(f"\n❌ 执行过程中发生意外错误: {e}")
        import traceback

        traceback.print_exc()
    finally:
        profiler.stop()

        # --- 4. 生成报告 ---
        if html_mode:
            output_file = project_root / f"profile_{cmd_name}.html"
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(profiler.output_html())
            print(f"✨ HTML 性能报告已保存至: {output_file}")
        else:
            profiler.print()


if __name__ == "__main__":
    main()
