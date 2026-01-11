import sys
import time
from pathlib import Path

# 尝试导入 pyinstrument，如果不存在则提示安装
try:
    from pyinstrument import Profiler
except ImportError:
    print("❌ Error: 'pyinstrument' not found. Please install it with: pip install pyinstrument")
    sys.exit(1)

# 将 packages 目录加入路径，确保可以导入本地包
project_root = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(project_root / "packages" / "stitcher-application" / "src"))
sys.path.insert(0, str(project_root / "packages" / "stitcher-common" / "src"))
sys.path.insert(0, str(project_root / "packages" / "stitcher-spec" / "src"))
sys.path.insert(0, str(project_root / "packages" / "stitcher-config" / "src"))
sys.path.insert(0, str(project_root / "packages" / "stitcher-index" / "src"))
sys.path.insert(0, str(project_root / "packages" / "stitcher-workspace" / "src"))

# 定义导入
t_start_imports = time.perf_counter()
from stitcher.app import StitcherApp
from stitcher.adapter.python.griffe_parser import GriffePythonParser
from stitcher.adapter.python import PythonTransformer, PythonFingerprintStrategy
t_end_imports = time.perf_counter()

def run_profile():
    app_init_start = time.perf_counter()
    
    # 构造应用实例
    parser = GriffePythonParser()
    transformer = PythonTransformer()
    strategy = PythonFingerprintStrategy()
    
    app = StitcherApp(
        root_path=project_root,
        parser=parser,
        transformer=transformer,
        fingerprint_strategy=strategy
    )
    
    app_init_end = time.perf_counter()

    print(f"--- Startup Diagnostics ---")
    print(f"Imports took:      {(t_end_imports - t_start_imports)*1000:.2f} ms")
    print(f"App Instance took: {(app_init_end - app_init_start)*1000:.2f} ms")
    print("-" * 27)

    # 开始性能分析
    profiler = Profiler(interval=0.001)  # 1ms 采样频率
    profiler.start()

    print("🚀 Running stitcher cov...")
    app.run_cov()

    profiler.stop()

    # 输出报告
    profiler.print()

if __name__ == "__main__":
    run_profile()