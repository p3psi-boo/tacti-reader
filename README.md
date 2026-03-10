TactiReader - 战术阅读器

专为快速跳转翻页、工程手册阅读等场景设计的 PDF 阅读器。

▶️ 快速运行

1. 安装依赖  
      pip install PyMuPDF PyQt5 markdown
   千万不要pip install fitz，否则会变得不幸！

2. 克隆仓库  
      git clone https://gitee.com/Mr_newbee666/tacti-reader.git
   cd tacti-reader
   

3. 启动程序  
      python tactireader.py
   

4. （可选）直接打开文件  
      python tactireader.py your_file.pdf
   python tactireader.py your_notebook.tactinote
   

✅ 支持 Windows / macOS / Linux  
📌 要求：Python 3.14+

📦 打包为可执行文件

Windows
pip install pyinstaller
pyinstaller --windowed --name "TactiReader" --icon=tactireader.ico ^
  --add-data "tactireader.png;." ^
  --add-data "help.md;." ^
  --add-data "about.md;." ^
  --add-data "help_zh.md;." ^
  --add-data "about_zh.md;." ^
  tactireader.py

生成的 dist/TactiReader/TactiReader.exe 即可分发使用。

macOS
pip install pyinstaller
pyinstaller --windowed --name "TactiReader" \
  --add-data "tactireader.png:." \
  --add-data "help.md:." \
  --add-data "about.md:." \
  --add-data "help_zh.md:." \
  --add-data "about_zh.md:." \
  tactireader.py

生成 dist/TactiReader.app，双击即可运行。

Linux
pip install pyinstaller
pyinstaller --windowed --name "TactiReader" \
  --add-data "tactireader.png:." \
  --add-data "help.md:." \
  --add-data "about.md:." \
  --add-data "help_zh.md:." \
  --add-data "about_zh.md:." \
  tactireader.py

生成 dist/TactiReader/TactiReader 可执行文件。

💡 注意：macOS/Linux 使用 : 分隔路径，Windows 使用 ;。命令中已分别处理。

📂 文件说明
文件   说明
tactireader.py   主程序入口

tactireader.ico   程序图标（仅 Windows 使用）

tactireader.png   应用图标（用于界面）

help.md, help_zh.md   英文/中文帮助文档

about.md, about_zh.md   关于页面内容

💡 TactiReader —— 让每一次阅读都成为战术行动。
