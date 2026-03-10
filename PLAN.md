# TactiReader 代码架构优化计划

> 当前状态：全部 4100+ 行代码在单文件 `tactireader.py` 中，存在大量重复代码、硬编码、职责混杂等问题。

---

## Phase 1: 项目结构拆分（单文件 → 模块化）

- [x] 建立包结构 `tacti_reader/`，入口改为 `main.py`
- [x] 拆分 `constants.py` — 提取 `CONFIG_DIR`、`GLOBAL_CONFIG_FILE`、`RENDER_SCALE`、颜色预设列表等全局常量
- [x] 拆分 `utils.py` — 提取 `resource_path()`、`get_config_path()`、`serialize_annotations()` 等工具函数
- [x] 拆分 `config.py` — 封装 `ConfigManager` 类，统一管理 `load_config()`、`save_config()`、`save_global_config()`、`load_global_config()` 逻辑
- [ ] 拆分 `i18n.py` — 将内联的 200+ 行翻译字典提取为独立模块（或 JSON 文件 `locales/en.json`、`locales/zh.json`），提供 `Translator` 类
- [ ] 拆分 `widgets/pane.py` — `TacticalPane` 类（~1000 行）
- [ ] 拆分 `widgets/dialogs.py` — `SearchDialog`、`LanguageSelectDialog`、`MarkdownViewer` 等对话框
- [ ] 拆分 `widgets/bookmark.py` — `BookmarkButton`、`InlineTextEdit` 等自定义控件
- [ ] 拆分 `main_window.py` — `TactiReader(QMainWindow)` 主窗口类
- [ ] 更新 `__main__.py` 或 `main.py`，保持 `python -m tacti_reader` 可运行

## Phase 2: 消除重复代码

- [ ] `import_notebook()` 与 `import_notebook_from_path()` 逻辑高度重复（~60 行），合并为单一方法
- [ ] `search_text_with_highlight()` 与 `SearchDialog.perform_search()` 中的搜索逻辑重复，抽取共用的 PDF 文本搜索函数
- [ ] `GLOBAL_CONFIG_FILE` 在 `__init__` 中被读取 3 次（语言、最近文件、已打开文档），合并为单次读取
- [ ] `_on_bookmark_clicked` / `jump_to_page` / `_jump_to_page_internal` 调用链过长，简化导航逻辑
- [ ] 左右窗格的颜色同步（`set_pen_color` / `set_rect_color` / `set_text_color`）可用循环代替 6 行重复调用

## Phase 3: 代码规范化

- [ ] 移除所有 `print()` 调试语句（`[DEBUG]`、`[KEY DEBUG]`、`[INFO]`、`[ERROR]`），替换为 `logging` 模块
- [ ] 清理重复 import（如 `QVBoxLayout`、`QHBoxLayout`、`QTextEdit` 在顶部 import 了两次；`zipfile`、`hashlib` 在方法内部重复 import）
- [ ] 统一代码风格：删除多余空行、对齐缩进、移除 `# === NEW CODE START ===` / `# === 修复 ===` 等临时注释
- [ ] 补充类型注解（至少为公有方法添加参数和返回值类型）
- [ ] 修复 `paintEvent` 结尾缺少空行直接接 `draw_annotation` 等格式问题
- [ ] `keyPressEvent` 方法超过 280 行，拆分为 `_handle_navigation_keys()`、`_handle_annotation_keys()`、`_handle_bookmark_keys()` 等子方法

## Phase 4: 架构设计改进

- [ ] **配置与数据分离**：当前 `save_config()` 将书签、批注、视图状态、颜色偏好全部混在同一个 JSON 顶层。重构为分层结构 `{ "config": {...}, "bookmarks": {...}, "annotations": {...}, "view_state": {...} }`
- [ ] **事件系统解耦**：菜单项通过 `_trigger_shortcut()` 模拟按键事件是反模式。改为将快捷键和菜单项都连接到同一个 slot 方法
- [ ] **跨平台配置路径**：当前仅处理 Windows `APPDATA`，Linux/macOS fallback 为当前目录。使用 `QStandardPaths` 或 `platformdirs` 库
- [ ] **文档管理分离**：将多文档/标签页管理逻辑从 `TactiReader` 中提取为 `DocumentManager` 类
- [ ] **批注系统封装**：将分散在 `TacticalPane` 和 `TactiReader` 中的批注逻辑（创建、保存、撤销、渲染）封装为 `AnnotationManager`

## Phase 5: 依赖与构建

- [ ] 添加 `pyproject.toml`（或 `setup.py`），声明 `PyMuPDF`、`PyQt5`、`markdown` 等依赖
- [ ] 添加 `.gitignore`（排除 `__pycache__/`、`dist/`、`build/`、`*.spec` 等）
- [ ] 更新 `README.md` 中的项目结构说明
- [ ] 更新 PyInstaller 打包脚本以适配新的模块结构

## Phase 6: 可选改进

- [ ] 为核心逻辑（配置读写、页码计算、搜索）添加单元测试
- [ ] 将硬编码的 QSS 样式表提取为 `styles/` 目录下的 `.qss` 文件
- [ ] 考虑将 `QLabel` 子类的 `BookmarkButton` 改为标准 `QPushButton` 以获得更好的可访问性
