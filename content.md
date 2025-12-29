## [WIP] feat(common): 增强语言自动检测逻辑 (LANG 支持)

### 摘要头
## [WIP] feat(common): 支持从系统 LANG 环境变量推断语言

### 用户需求
1.  **废除单一依赖**: 不再仅依赖 `STITCHER_LANG`，而是支持标准的 `LANG` 环境变量。
2.  **智能解析**: 能够从 `zh_CN.UTF-8` 格式中提取出 `zh`。
3.  **优先级控制**: 保持 `STITCHER_LANG` 作为最高优先级覆盖，`LANG` 次之，默认回退到 `en`。

### 评论
这是一个提升用户体验（UX）的改进，使得工具能够“开箱即用”地适配用户的系统语言环境，无需额外配置。

### 目标
1.  在 `stitcher-common` 中实现 `_detect_lang` 辅助函数。
2.  解析优先级：`STITCHER_LANG` > `LANG` (strip region/encoding) > `en`。
3.  更新 `get_current_renderer` 使用该检测逻辑。

### 基本原理
通过解析标准的 POSIX `LANG` 环境变量（格式通常为 `language[_territory][.codeset]`），我们可以获取用户的首选语言代码。简单的字符串分割（先按 `.` 分割去编码，再按 `_` 分割去地区）足以满足大多数常见场景（如 `zh_CN` -> `zh`）。

### 标签
#intent/build #flow/ready #priority/medium #comp/common #concept/config #scope/ux #ai/instruct #task/domain/i18n #task/object/lang-detection #task/action/implement #task/state/begin

---

### Script

#### Acts 1: 实现语言检测逻辑

在 `stitcher/common/__init__.py` 中添加 `_detect_lang` 函数并更新渲染器获取逻辑。

~~~~~act
patch_file
packages/stitcher-common/src/stitcher/common/__init__.py
~~~~~
~~~~~python
# 3. Dynamic Pipeline with Caching
_operator_cache: Dict[str, OverlayOperator] = {}

def get_current_renderer() -> OverlayOperator:
    """
    Returns the OverlayOperator for the current configured language.
    This implements the 'Lazy Pipeline Construction' pattern.
    """
    lang_code = os.getenv("STITCHER_LANG", "en")
    
    if lang_code in _operator_cache:
        return _operator_cache[lang_code]
    
    # Construct the pipeline on demand
    # L.en or L.zh based on env string
    # We use a simple pointer construction here.
    lang_ptr = getattr(L, lang_code)
~~~~~
~~~~~python
# 3. Dynamic Pipeline with Caching
_operator_cache: Dict[str, OverlayOperator] = {}


def _detect_lang() -> str:
    # 1. Explicit override
    stitcher_lang = os.getenv("STITCHER_LANG")
    if stitcher_lang:
        return stitcher_lang

    # 2. System LANG (e.g. "zh_CN.UTF-8" -> "zh")
    sys_lang = os.getenv("LANG")
    if sys_lang:
        # Extract "zh" from "zh_CN.UTF-8" or "en_US"
        # Split by '.' first to remove encoding, then '_' to remove territory
        base_lang = sys_lang.split(".")[0].split("_")[0]
        if base_lang:
            return base_lang

    # 3. Default fallback
    return "en"


def get_current_renderer() -> OverlayOperator:
    """
    Returns the OverlayOperator for the current configured language.
    This implements the 'Lazy Pipeline Construction' pattern.
    """
    lang_code = _detect_lang()
    
    if lang_code in _operator_cache:
        return _operator_cache[lang_code]
    
    # Construct the pipeline on demand
    # L.en or L.zh based on env string
    # We use a simple pointer construction here.
    lang_ptr = getattr(L, lang_code)
~~~~~

### 下一步建议
现在您可以在不设置 `STITCHER_LANG` 的情况下，仅依赖系统环境运行 `stitcher --help` 来验证中文支持（前提是您的系统 `LANG` 为 `zh_CN` 或类似）。如果需要强制英文，可以使用 `STITCHER_LANG=en` 进行覆盖。
