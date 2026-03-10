# TactiReader - 战术阅读器

专为长篇 PDF、工程手册、标准文档、教材查阅设计的键盘优先阅读器，重点解决高频跳转、对照阅读、批注记录和跨章节关联的问题。

## 快速开始

1. 安装依赖

```bash
pip install PyMuPDF PyQt5 markdown
```

不要安装 `fitz` 这个同名包，TactiReader 依赖的是 `PyMuPDF`。

2. 克隆仓库

```bash
git clone https://gitee.com/Mr_newbee666/tacti-reader.git
cd tacti-reader
```

3. 启动程序

```bash
python tactireader.py
```

4. 直接打开文件

```bash
python tactireader.py your_file.pdf
python tactireader.py your_notebook.tactinote
```

## 功能特点

- 双页对照阅读，左页可锁定为参考页
- `Q` 到 `P` 十键瞬时书签，适合盲操切换
- 支持逻辑页码校准、快速跳页、全文搜索
- 支持批注、导出 PDF、导出 `.tactinote` 笔记本
- 支持多标签页和新窗口并行阅读

## 文档索引

- 文档目录：[`docs/README.md`](docs/README.md)
- 中文使用指南：[`docs/help_zh.md`](docs/help_zh.md)
- English user guide: [`docs/help.md`](docs/help.md)
- 中文关于页：[`docs/about_zh.md`](docs/about_zh.md)
- English about page: [`docs/about.md`](docs/about.md)
- English overview: [`docs/README.en.md`](docs/README.en.md)
- 架构优化计划：[`docs/PLAN.md`](docs/PLAN.md)

## 打包

支持 Windows / macOS / Linux，要求 Python 3.14+。

Windows:

```powershell
pip install pyinstaller
pyinstaller --windowed --name "TactiReader" --icon=tactireader.ico ^
  --add-data "tactireader.png;." ^
  --add-data "docs/help.md;docs" ^
  --add-data "docs/about.md;docs" ^
  --add-data "docs/help_zh.md;docs" ^
  --add-data "docs/about_zh.md;docs" ^
  tactireader.py
```

macOS:

```bash
pip install pyinstaller
pyinstaller --windowed --name "TactiReader" \
  --add-data "tactireader.png:." \
  --add-data "docs/help.md:docs" \
  --add-data "docs/about.md:docs" \
  --add-data "docs/help_zh.md:docs" \
  --add-data "docs/about_zh.md:docs" \
  tactireader.py
```

Linux:

```bash
pip install pyinstaller
pyinstaller --windowed --name "TactiReader" \
  --add-data "tactireader.png:." \
  --add-data "docs/help.md:docs" \
  --add-data "docs/about.md:docs" \
  --add-data "docs/help_zh.md:docs" \
  --add-data "docs/about_zh.md:docs" \
  tactireader.py
```

macOS/Linux 使用 `:` 分隔路径，Windows 使用 `;`。

## 项目结构

- `tactireader.py`: 当前主程序入口
- `main.py`: 包模式入口
- `tacti_reader/`: 已拆分出的模块化代码
- `docs/`: 帮助文档、关于页、英文说明和规划文档
- `tactireader.png`: 应用图标
- `tactireader.ico`: Windows 图标

## 说明

TactiReader 的目标不是替代通用 PDF 阅读器，而是为高密度知识跳转和对照阅读提供更低摩擦的工作流。
