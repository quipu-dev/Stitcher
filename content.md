# 📸 Snapshot Capture

检测到工作区发生变更。

### 📝 变更文件摘要:
```
.../src/stitcher/lang/python/adapter.json          |  31 ++++++
 .../src/stitcher/lang/python/analysis/models.json  |  24 +++++
 .../src/stitcher/lang/python/analysis/scope.json   |  11 +++
 .../lang/python/analysis/usage_visitor.json        |  70 ++++++++++++++
 .../src/stitcher/lang/python/analysis/utils.json   |   7 ++
 .../stitcher/lang/python/analysis/visitors.json    |  77 +++++++++++++++
 .../stitcher/lang/python/docstring/__init__.json   |   3 +
 .../stitcher/lang/python/docstring/factory.json    |  21 +++++
 .../stitcher/lang/python/docstring/parsers.json    |  29 ++++++
 .../stitcher/lang/python/docstring/renderers.json  |  50 ++++++++++
 .../lang/python/docstring/serializers.json         |  71 ++++++++++++++
 .../src/stitcher/lang/python/fingerprint.json      |  68 +++++++++++++
 .../src/stitcher/lang/python/inspector.json        |  18 ++++
 .../src/stitcher/lang/python/parser/cst.json       |  10 ++
 .../src/stitcher/lang/python/parser/griffe.json    |  55 +++++++++++
 .../lang/python/transform/cst_visitors.json        | 105 +++++++++++++++++++++
 .../src/stitcher/lang/python/transform/facade.json |  14 +++
 .../src/stitcher/lang/python/transform/rename.json |  67 +++++++++++++
 .../src/stitcher/lang/python/uri.json              |  22 +++++
 .../adapter/python/docstring/__init__.json         |   3 -
 .../stitcher/adapter/python/docstring/factory.json |  21 -----
 .../stitcher/adapter/python/docstring/parsers.json |  29 ------
 .../adapter/python/docstring/renderers.json        |  50 ----------
 .../adapter/python/docstring/serializers.json      |  71 --------------
 .../src/stitcher/adapter/python/fingerprint.json   |  68 -------------
 .../src/stitcher/adapter/python/griffe_parser.json |  55 -----------
 .../src/stitcher/adapter/python/index_adapter.json |  31 ------
 .../src/stitcher/adapter/python/inspector.json     |  18 ----
 .../src/stitcher/adapter/python/parser.json        |  10 --
 .../src/stitcher/adapter/python/transformer.json   |  14 ---
 ...
 131 files changed, 3191 insertions(+), 3207 deletions(-)
```