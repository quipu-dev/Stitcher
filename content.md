这是一个非常正确的直觉。在没有数据支撑的情况下进行优化往往会产生“负优化”。

我将为你创建一个基于 **`pyinstrument`** 的高性能分析脚本。`pyinstrument` 是目前 Python 社区中非常推崇的采样分析器（Sampling Profiler），它能生成非常清晰的、层级化的调用树，并且运行开销极低。

## [WIP] feat: 增加性能分析脚本以诊断全流程瓶颈

### 用户需求

用户需要一个位于 `scripts/` 目录下的性能测试脚本，用于精确诊断 `stitcher cov` 运行缓慢（~570ms）的具体原因，并要求使用较新的技术栈。

### 评论

半秒钟的延迟对于一个本地开发工具来说确实处于“令人烦躁”的边缘。通过 `pyinstrument`，我们可以看清究竟是 SQLite 的 I/O 慢、AST 解析的残留开销，还是 Python 导入系统的启动负担。这将为我们后续的“新鲜度快路径”或“批量加载”提供确凿的证据。

### 目标

1.  在项目根目录下创建 `scripts/` 文件夹。
2.  编写 `profile_cov.py` 脚本，集成 `pyinstrument` 对 `StitcherApp` 的关键方法进行采样。
3.  输出易于阅读的层级化性能报告。

### 基本原理

该脚本将执行以下操作：
-   使用 `pyinstrument.Profiler` 包装 `app.run_cov()` 的执行过程。
-   在执行前后手动记录时间点，以区分“启动加载（Imports）”和“业务逻辑执行”的时间占比。
-   将结果以文本形式直接输出到终端。如果需要更细致的分析，`pyinstrument` 还支持导出 HTML 交互式图表。

### 标签

#intent/tooling #flow/ready #priority/medium #comp/build #comp/tests #scope/dx #ai/instruct #task/domain/testing #task/object/profiler #task/action/implementation #task/state/begin

---

### Script

#### Acts 1: 创建性能分析脚本

我们将创建 `scripts/profile_cov.py`。请确保你的环境中已安装 `pyinstrument`（可以通过 `pip install pyinstrument` 安装）。

~~~~~act
run_command
~~~~~
~~~~~
mkdir -p scripts
~~~~~

~~~~~act
write_file
scripts/profile_cov.py
~~~~~
~~~~~python
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
~~~~~

### 下一步建议

1.  **安装依赖**: 请运行 `pip install pyinstrument` 以支持该脚本。
2.  **运行脚本**: 在项目根目录下运行 `python3 scripts/profile_cov.py`。
3.  **分析结果**: 
    *   看 **"Startup Diagnostics"**: 如果这部分加起来就占了 300ms，说明瓶颈在 Python 启动和导入（对于 440 个文件这种规模，这是很常见的）。
    *   看 **`pyinstrument` 输出的树**: 寻找百分比最高的节点。如果是 `sqlite3` 的 `execute`，说明 N+1 查询是元凶；如果是 `os.stat`，说明文件扫描太重。
4.  **根据报告决策**: 我们将根据这份报告决定是先优化数据库查询，还是先做 Git 快路径。
