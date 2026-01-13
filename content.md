好的，我们现在进入持久化层，这是本次架构演进的核心战场。我们将执行一次“心脏移植”手术：将 `SignatureManager` 迁移到一个更合适的位置，并用符合 `stitcher.lock` 分布式模式的新实现替换它。

## [WIP] feat(sidecar): 迁移并重写 SignatureManager 以支持 stitcher.lock

### 用户需求

根据“`stitcher.lock` 模式与全局 SURI 架构”路线图，实施 3.3 阶段任务：
1.  将 `SignatureManager` 从 `stitcher-application` 迁移至 `stitcher-lang-sidecar`。
2.  彻底重写 `SignatureManager`，使其从管理碎片化的 `.stitcher/signatures/` 目录，转变为管理分布在各个包根目录下的 `stitcher.lock` 文件。
3.  实现新的“注册表”模式，对 `stitcher.lock` 文件进行缓存、内存操作和原子化写回。
4.  更新相关包的依赖关系。

### 评论

这是对系统“真理单一来源 (SSoT)”原则的一次重大强化。将 `SignatureManager` 迁移到 `stitcher-lang-sidecar` 包是本体论上的正确选择，因为它与 `DocumentManager`（管理 `.stitcher.yaml`）共同构成了对“边车文件”的完整抽象。

新的实现在架构上是优越的：
*   **性能**: 通过全量加载和内存缓存，避免了对大量小文件的重复 I/O 操作。
*   **原子性**: `flush` 机制确保了对 `stitcher.lock` 的写入是事务性的，减少了状态不一致的风险。
*   **确定性**: 通过强制依赖 `Workspace` 服务进行路径计算，确保了 SURI 的全局唯一性，杜绝了路径歧义。

### 目标

1.  物理移动 `signature_manager.py` 文件到 `stitcher-lang-sidecar` 包。
2.  更新源包和目标包的 `__init__.py` 以正确导出/移除 `SignatureManager`。
3.  重写 `SignatureManager`，实现基于 `stitcher.lock` 的新逻辑，包括缓存、`flush` 机制和对旧 `.stitcher/signatures` 目录的自动迁移能力。
4.  在 `stitcher-lang-sidecar` 的 `pyproject.toml` 中添加对 `stitcher-workspace` 的依赖。
5.  在 `stitcher-application` 的 `pyproject.toml` 中添加对 `stitcher-lang-sidecar` 的依赖。

### 基本原理

我们将采用“注册表”设计模式来管理 `stitcher.lock` 文件。`SignatureManager` 在首次需要访问某个包的指纹时，会找到对应的 `stitcher.lock`，将其内容完整加载到内存缓存中。后续的所有读写操作都只针对这个内存缓存进行。当一个工作单元（如 `pump` 或 `init` 命令）结束后，调用 `flush()` 方法会将所有被标记为“脏”的缓存一次性、原子地写回到对应的 `stitcher.lock` 文件中。

为了确保平滑过渡，`SignatureManager` 在加载时会检查 `stitcher.lock` 是否存在。如果不存在，但检测到了旧的 `.stitcher/signatures` 目录，它将自动触发一次性的迁移流程。该流程会扫描所有旧的指纹文件，根据其路径计算出正确的全局 SURI 和所属的包，然后将这些数据合并到内存缓存中，并标记为“脏”。在下一次 `flush` 成功后，旧的 `.stitcher/signatures` 目录将被自动删除，完成迁移。

### 标签

#intent/refine #intent/architect #flow/ready #priority/critical #scope/core #scope/api #ai/instruct #task/domain/architecture #task/object/lock-file #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 物理迁移 SignatureManager

首先，我们将 `signature_manager.py` 文件从 `stitcher-application` 移动到 `stitcher-lang-sidecar`。

~~~~~act
move_file
packages/stitcher-application/src/stitcher/app/services/signature_manager.py
packages/stitcher-lang-sidecar/src/stitcher/lang/sidecar/signature_manager.py
~~~~~

#### Acts 2: 更新模块导出

现在，我们更新两个包的 `__init__.py` 文件，以反映这次迁移。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/services/__init__.py
~~~~~
~~~~~python.old
from .doc_manager import DocumentManager
from .signature_manager import SignatureManager
from .scanner import ScannerService
from .merger import DocstringMerger

__all__ = [
    "DocumentManager",
    "SignatureManager",
    "ScannerService",
    "DocstringMerger",
]
~~~~~
~~~~~python.new
from .doc_manager import DocumentManager
from .scanner import ScannerService
from .merger import DocstringMerger

__all__ = [
    "DocumentManager",
    "ScannerService",
    "DocstringMerger",
]
~~~~~

~~~~~act
patch_file
packages/stitcher-lang-sidecar/src/stitcher/lang/sidecar/__init__.py
~~~~~
~~~~~python.old
__path__ = __import__("pkgutil").extend_path(__path__, __name__)

from .adapter import SidecarAdapter
from .parser import parse_doc_references, parse_signature_references
from .transform import SidecarTransformContext, SidecarTransformer

__all__ = [
    "SidecarAdapter",
    "parse_doc_references",
    "parse_signature_references",
    "SidecarTransformContext",
    "SidecarTransformer",
]
~~~~~
~~~~~python.new
__path__ = __import__("pkgutil").extend_path(__path__, __name__)

from .adapter import SidecarAdapter
from .parser import parse_doc_references, parse_signature_references
from .transform import SidecarTransformContext, SidecarTransformer
from .signature_manager import SignatureManager

__all__ = [
    "SidecarAdapter",
    "parse_doc_references",
    "parse_signature_references",
    "SidecarTransformContext",
    "SidecarTransformer",
    "SignatureManager",
]
~~~~~

#### Acts 3: 重写 SignatureManager 实现

这是本次任务的核心。我将用全新的实现覆盖 `signature_manager.py` 的内容，使其支持 `stitcher.lock`。

~~~~~act
write_file
packages/stitcher-lang-sidecar/src/stitcher/lang/sidecar/signature_manager.py
~~~~~
~~~~~python
import json
import logging
import shutil
from collections import defaultdict
from pathlib import Path
from typing import Dict, Set

from stitcher.spec import Fingerprint, InvalidFingerprintKeyError
from stitcher.workspace import Workspace, find_package_root
from stitcher.lang.python.uri import SURIGenerator

log = logging.getLogger(__name__)

LOCK_FILE_VERSION = "1.0"
LOCK_FILE_NAME = "stitcher.lock"
LEGACY_SIG_DIR = ".stitcher/signatures"


class SignatureManager:
    def __init__(self, workspace: Workspace):
        self.workspace = workspace
        # Cache: lock_file_path -> {suri: Fingerprint}
        self._fingerprints_cache: Dict[Path, Dict[str, Fingerprint]] = {}
        self._dirty_locks: Set[Path] = set()
        self._migration_done = False
        self._legacy_dir_to_delete: Path | None = None

    def _get_lock_path(self, package_root: Path) -> Path:
        return package_root / LOCK_FILE_NAME

    def _ensure_loaded(self, abs_file_path: Path) -> Path:
        package_root = find_package_root(abs_file_path)
        if not package_root:
            raise FileNotFoundError(f"Could not find package root for: {abs_file_path}")

        lock_path = self._get_lock_path(package_root)
        if lock_path in self._fingerprints_cache:
            return lock_path

        if not self._migration_done:
            self._run_migration_if_needed()

        if lock_path in self._fingerprints_cache:
            return lock_path

        if lock_path.exists():
            log.debug(f"Loading lock file: {lock_path}")
            try:
                with lock_path.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                if data.get("version") == LOCK_FILE_VERSION and "fingerprints" in data:
                    self._fingerprints_cache[lock_path] = {
                        suri: Fingerprint.from_dict(fp_data)
                        for suri, fp_data in data["fingerprints"].items()
                    }
                else:
                    self._fingerprints_cache[lock_path] = {}
            except (json.JSONDecodeError, OSError):
                self._fingerprints_cache[lock_path] = {}
        else:
            self._fingerprints_cache[lock_path] = {}

        return lock_path

    def _run_migration_if_needed(self):
        legacy_dir = self.workspace.root_path / LEGACY_SIG_DIR
        if not legacy_dir.is_dir():
            self._migration_done = True
            return

        log.info("Legacy '.stitcher/signatures' directory found. Starting migration...")
        fingerprints_by_pkg: Dict[Path, Dict[str, Fingerprint]] = defaultdict(dict)

        for sig_file in legacy_dir.rglob("*.json"):
            try:
                rel_source_path = str(sig_file.relative_to(legacy_dir))[:-5]
                abs_source_path = self.workspace.root_path / rel_source_path
                package_root = find_package_root(abs_source_path)
                if not package_root:
                    continue

                with sig_file.open("r", encoding="utf-8") as f:
                    data = json.load(f)

                for key, fp_data in data.items():
                    suri = (
                        key
                        if key.startswith("py://")
                        else SURIGenerator.for_symbol(rel_source_path, key)
                    )
                    fingerprints_by_pkg[package_root][suri] = Fingerprint.from_dict(
                        fp_data
                    )
            except (json.JSONDecodeError, InvalidFingerprintKeyError, ValueError):
                continue

        for pkg_root, fingerprints in fingerprints_by_pkg.items():
            lock_path = self._get_lock_path(pkg_root)
            self._fingerprints_cache[lock_path] = fingerprints
            self._dirty_locks.add(lock_path)

        self._migration_done = True
        self._legacy_dir_to_delete = legacy_dir

    def load_composite_hashes(self, file_path_str: str) -> Dict[str, Fingerprint]:
        abs_file_path = (self.workspace.root_path / file_path_str).resolve()
        lock_path = self._ensure_loaded(abs_file_path)

        workspace_rel_path = self.workspace.get_suri_path(abs_file_path)
        prefix = f"py://{workspace_rel_path}"
        all_lock_fps = self._fingerprints_cache.get(lock_path, {})
        file_fingerprints: Dict[str, Fingerprint] = {}

        for suri, fp in all_lock_fps.items():
            if suri.startswith(prefix):
                _, fragment = SURIGenerator.parse(suri)
                if fragment:
                    file_fingerprints[fragment] = fp
        return file_fingerprints

    def save_composite_hashes(
        self, file_path_str: str, hashes: Dict[str, Fingerprint]
    ) -> None:
        abs_file_path = (self.workspace.root_path / file_path_str).resolve()
        lock_path = self._ensure_loaded(abs_file_path)
        self._dirty_locks.add(lock_path)
        lock_cache = self._fingerprints_cache.setdefault(lock_path, {})

        workspace_rel_path = self.workspace.get_suri_path(abs_file_path)
        updated_suris = {
            SURIGenerator.for_symbol(workspace_rel_path, fragment)
            for fragment in hashes
        }

        prefix = f"py://{workspace_rel_path}"
        stale_suris = [
            suri
            for suri in lock_cache
            if suri.startswith(prefix) and suri not in updated_suris
        ]
        for suri in stale_suris:
            del lock_cache[suri]

        for fragment, fp in hashes.items():
            suri = SURIGenerator.for_symbol(workspace_rel_path, fragment)
            lock_cache[suri] = fp

    def flush(self) -> None:
        if not self._dirty_locks:
            return

        log.debug(f"Flushing {len(self._dirty_locks)} dirty lock files.")
        for lock_path in self._dirty_locks:
            fingerprints = self._fingerprints_cache.get(lock_path, {})
            if not fingerprints:
                if lock_path.exists():
                    lock_path.unlink()
                continue

            lock_data = {
                "version": LOCK_FILE_VERSION,
                "fingerprints": {
                    suri: fp.to_dict() for suri, fp in sorted(fingerprints.items())
                },
            }
            lock_path.parent.mkdir(parents=True, exist_ok=True)
            with lock_path.open("w", encoding="utf-8") as f:
                json.dump(lock_data, f, indent=2)
                f.write("\n")

        self._dirty_locks.clear()

        if self._legacy_dir_to_delete:
            log.info(
                "Migration successful. "
                f"Deleting legacy signature directory: {self._legacy_dir_to_delete}"
            )
            shutil.rmtree(self._legacy_dir_to_delete)
            self._legacy_dir_to_delete = None

    def get_signature_path(self, file_path: str) -> Path:
        abs_file_path = (self.workspace.root_path / file_path).resolve()
        package_root = find_package_root(abs_file_path)
        if not package_root:
            raise FileNotFoundError(f"Cannot find package root for {file_path}")
        return self._get_lock_path(package_root)
~~~~~

#### Acts 4: 更新包依赖关系

最后，我们更新 `pyproject.toml` 文件来正式化新的架构依赖。

~~~~~act
patch_file
packages/stitcher-lang-sidecar/pyproject.toml
~~~~~
~~~~~python.old
dependencies = [
    "stitcher-spec",
    "stitcher-common",
    "stitcher-lang-python",
    "ruamel.yaml>=0.17.0",
]
~~~~~
~~~~~python.new
dependencies = [
    "stitcher-spec",
    "stitcher-common",
    "stitcher-lang-python",
    "stitcher-workspace",
    "ruamel.yaml>=0.17.0",
]
~~~~~

~~~~~act
patch_file
packages/stitcher-application/pyproject.toml
~~~~~
~~~~~python.old
dependencies = [
    "stitcher-spec",
    "stitcher-common",
    "stitcher-config",
    "stitcher-lang-python",
    "stitcher-stubgen",
    "stitcher-workspace",
    "stitcher-index",
    "stitcher-analysis",
    "pyneedle",
]
~~~~~
~~~~~python.new
dependencies = [
    "stitcher-spec",
    "stitcher-common",
    "stitcher-config",
    "stitcher-lang-python",
    "stitcher-lang-sidecar",
    "stitcher-stubgen",
    "stitcher-workspace",
    "stitcher-index",
    "stitcher-analysis",
    "pyneedle",
]
~~~~~

### 下一步建议

持久化层的核心改造已经完成。我们拥有了一个全新的、支持分布式 `stitcher.lock` 并能自动迁移旧数据的 `SignatureManager`。

现在，整个系统的应用层（`StitcherApp` 及其 Runners）与新的持久化层处于“失联”状态。下一步是**实施路线图的 3.5 阶段：应用层适配**。我们需要修改 `StitcherApp` 的初始化逻辑，使其从新的 `stitcher-lang-sidecar` 包中实例化 `SignatureManager`，并调整所有相关的 Runner（如 `InitRunner`, `PumpRunner`）以适应新的 API，特别是要在操作结束时调用 `sig_manager.flush()` 来确保数据持久化。
