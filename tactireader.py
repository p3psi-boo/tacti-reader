
import sys
import fitz  # PyMuPDF
import json
import os
import hashlib
import zipfile
import subprocess


import markdown
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QLabel, QWidget, QHBoxLayout, QVBoxLayout, QFrame,
    QFileDialog, QMenuBar, QAction, QInputDialog, QMessageBox, QPushButton,
    QColorDialog, QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QTextEdit, 
    QDialogButtonBox, QToolBar, QComboBox, QTextEdit, QScrollArea,
    QListWidget, QListWidgetItem, QGroupBox, QSplitter, QAbstractItemView,QTextBrowser,QTreeWidget,QTreeWidgetItem,QTabBar, QMenu
)
from PyQt5.QtCore import Qt, QMimeData, QPointF,QEvent, QPoint, QRect, QRectF, pyqtSignal, pyqtSlot,QUrl,QTimer,QSize
from PyQt5.QtGui import (
    QPixmap, QPainter, QImage, QDragEnterEvent, QDropEvent, QPen, QBrush, 
    QPainterPath, QColor, QFont, QCursor, QLinearGradient, QIcon, QFontMetrics, QTransform,QKeyEvent,
)


appdata = os.getenv("APPDATA")
if appdata:
    CONFIG_DIR = os.path.join(appdata, "TactiReader", "tactireader_bookmarks")
else:
    # Fallback for rare cases (e.g., non-Windows)
    CONFIG_DIR = "tactireader_bookmarks"
os.makedirs(CONFIG_DIR, exist_ok=True)

GLOBAL_CONFIG_FILE = os.path.join(CONFIG_DIR, "global_settings.json")
RENDER_SCALE = 2.0  # 必须与 render_page 中的 Matrix 缩放一致
def resource_path(relative_path):
    """ 获取资源文件的真实路径（兼容开发环境和 PyInstaller 打包后） """
    try:
        # PyInstaller 打包后
        base_path = sys._MEIPASS
    except Exception:
        # 开发时：使用脚本所在目录
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)


def get_config_path(pdf_path):
    abs_path = os.path.abspath(pdf_path)
    hash_id = hashlib.md5(abs_path.encode('utf-8')).hexdigest()[:12]
    base_name = os.path.basename(pdf_path).replace('.', '_').replace(' ', '_')
    config_name = f"{base_name}_{hash_id}.json"
    return os.path.join(CONFIG_DIR, config_name)


class BookmarkButton(QLabel):
    bookmarkClicked = pyqtSignal(str)
    
    def __init__(self, key, page, name, parent=None):
        super().__init__(parent)
        self.key = key
        self.page = page
        
        display_name = name.strip() or f"P.{page}"
        full_text = f"[{key}] {display_name} (P.{page})"
        self.setText(full_text)
        # 设置字体：中英分离
        font = QFont()
        font.setFamily("Microsoft YaHei, Consolas, Courier New, monospace")
        font.setPointSize(9)
        self.setFont(font)
        # === 支持自动换行 ===
        self.setWordWrap(True)
        self.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        # ==================
        
        # === 按钮样式 ===
        self.setStyleSheet("""
            QLabel {
                background-color: #f0f0f0;
                border: 1px solid #ccc;
                border-radius: 4px;
                padding: 6px;
                margin: 2px;
            }
            QLabel:hover {
                background-color: #e0e0e0;
                border: 1px solid #999;
            }
        """)
        self.setCursor(Qt.PointingHandCursor)
        # ==============
        
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.bookmarkClicked.emit(self.key)
        super().mousePressEvent(event)

class InlineTextEdit(QTextEdit):
    """内联文本编辑器"""
    textConfirmed = pyqtSignal(str)
    editingCancelled = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptRichText(False)
        self.setLineWrapMode(QTextEdit.WidgetWidth)
        self.setWordWrapMode(True)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.editingCancelled.emit()
        elif event.key() == Qt.Key_Return and event.modifiers() == Qt.ControlModifier:
            # Ctrl+Enter 确认
            self.textConfirmed.emit(self.toPlainText())
        elif event.key() == Qt.Key_Return and event.modifiers() == Qt.NoModifier:
            # Enter 键换行
            self.insertPlainText('\n')
        elif event.key() == Qt.Key_Enter and event.modifiers() == Qt.NoModifier:
            # 小键盘 Enter 键换行
            self.insertPlainText('\n')
        else:
            super().keyPressEvent(event)
    
    def focusOutEvent(self, event):
        # 失去焦点时也确认
        self.textConfirmed.emit(self.toPlainText())
        super().focusOutEvent(event)

# === 首次运行语言选择对话框 ===
class LanguageSelectDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("TactiReader - Choose Language")
        self.setFixedSize(320, 130)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Please choose your language:\n请选择您的语言："))
        self.btn_en = QPushButton("English")
        self.btn_zh = QPushButton("简体中文")
        layout.addWidget(self.btn_en)
        layout.addWidget(self.btn_zh)

        self.selected_lang = "en"
        self.btn_en.clicked.connect(lambda: self.accept_with("en"))
        self.btn_zh.clicked.connect(lambda: self.accept_with("zh"))

    def accept_with(self, lang):
        self.selected_lang = lang
        self.accept()
# ==============================
class SearchDialog(QDialog):
    """增强的搜索对话框"""
    searchResultSelected = pyqtSignal(int, str)  # page_num, matched_text
    
    def __init__(self, parent=None, pdf_doc=None):
        super().__init__(parent)
        self.doc = pdf_doc
        self.results = []
        self.current_search_index = 0
        
        self.setWindowTitle(QApplication.instance().activeWindow().tr("Search in PDF"))
        
        self.setMinimumSize(500, 400)
        
        layout = QVBoxLayout(self)
        
        # 搜索框
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel(QApplication.instance().activeWindow().tr("Search:")))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(QApplication.instance().activeWindow().tr("Enter search term..."))
        self.search_input.returnPressed.connect(self.perform_search)
        search_layout.addWidget(self.search_input)
        
        self.search_button = QPushButton(QApplication.instance().activeWindow().tr("Search"))
        self.search_button.clicked.connect(self.perform_search)
        search_layout.addWidget(self.search_button)
        
        self.case_sensitive_check = QPushButton("Aa")
        self.case_sensitive_check.setCheckable(True)
        self.case_sensitive_check.setToolTip("Case Sensitive")
        self.case_sensitive_check.setFixedWidth(30)
        search_layout.addWidget(self.case_sensitive_check)
        
        layout.addLayout(search_layout)
        
        # 结果统计
        self.result_count_label = QLabel(QApplication.instance().activeWindow().tr("No results"))
        layout.addWidget(self.result_count_label)
        
        # 结果列表
        self.results_list = QListWidget()
        self.results_list.itemClicked.connect(self.on_result_clicked)
        self.results_list.itemDoubleClicked.connect(self.on_result_double_clicked)
        layout.addWidget(self.results_list)
        
        # 导航按钮
        nav_layout = QHBoxLayout()
        self.prev_button = QPushButton(QApplication.instance().activeWindow().tr("◀ Previous"))
        self.prev_button.clicked.connect(self.go_to_previous)
        self.prev_button.setEnabled(False)
        nav_layout.addWidget(self.prev_button)
        
        self.next_button = QPushButton(QApplication.instance().activeWindow().tr("Next ▶"))
        self.next_button.clicked.connect(self.go_to_next)
        self.next_button.setEnabled(False)
        nav_layout.addWidget(self.next_button)
        
        nav_layout.addStretch()
        
        self.close_button = QPushButton(QApplication.instance().activeWindow().tr("Close"))
        self.close_button.clicked.connect(self.close)
        nav_layout.addWidget(self.close_button)
        
        layout.addLayout(nav_layout)
    
    def perform_search(self):
        """执行搜索"""
        if not self.doc:
            return
        
        search_term = self.search_input.text().strip()
        if not search_term:
            return
        
        self.results_list.clear()
        self.results = []
        self.current_search_index = 0
        
        # 搜索所有页面
        for page_num in range(len(self.doc)):
            page = self.doc[page_num]
            try:
                # 获取页面文本
                text = page.get_text()
                
                # 搜索
                if self.case_sensitive_check.isChecked():
                    indices = []
                    start = 0
                    while True:
                        idx = text.find(search_term, start)
                        if idx == -1:
                            break
                        indices.append(idx)
                        start = idx + 1
                else:
                    search_term_lower = search_term.lower()
                    text_lower = text.lower()
                    indices = []
                    start = 0
                    while True:
                        idx = text_lower.find(search_term_lower, start)
                        if idx == -1:
                            break
                        indices.append(idx)
                        start = idx + 1
                
                # 为每个匹配创建结果
                for idx in indices:
                    # 获取上下文
                    context_start = max(0, idx - 40)
                    context_end = min(len(text), idx + len(search_term) + 40)
                    context = text[context_start:context_end]
                    
                    # 高亮搜索词
                    highlight_start = idx - context_start
                    highlight_end = highlight_start + len(search_term)
                    context = context[:highlight_start] + "**" + context[highlight_start:highlight_end] + "**" + context[highlight_end:]
                    
                    result = {
                        'page': page_num + 1,
                        'context': context.strip(),
                        'position': idx
                    }
                    self.results.append(result)
                    
            except Exception as e:
                print(f"Error searching page {page_num}: {e}")
        
        # 更新UI
        self.update_results_list()
                # === 新增：通知主窗口执行高亮 ===
        if hasattr(self.parent(), 'search_text_with_highlight'):
            self.parent().search_text_with_highlight(search_term, self.case_sensitive_check.isChecked())
        # =================================
    def on_result_clicked(self, item):
        """单击：仅跳转"""
        index = item.data(Qt.UserRole)
        if 0 <= index < len(self.results):
            result = self.results[index]
            self.searchResultSelected.emit(result['page'], result['context'])
            # 注意：这里不调用 self.accept()

    def on_result_double_clicked(self, item):
        """双击：跳转并关闭对话框"""
        index = item.data(Qt.UserRole)
        if 0 <= index < len(self.results):
            result = self.results[index]
            self.searchResultSelected.emit(result['page'], result['context'])
            self.accept()  # 关闭对话框    
    def update_results_list(self):
        """更新结果列表"""
        self.results_list.clear()
        
        for i, result in enumerate(self.results):
            item_text = f"Page {result['page']}: {result['context']}"
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, i)  # 存储索引
            self.results_list.addItem(item)
        
        # 更新统计
        count = len(self.results)
        self.result_count_label.setText(QApplication.instance().activeWindow().tr("Found {count} result(s)"))

        # 更新按钮状态
        self.prev_button.setEnabled(count > 0)
        self.next_button.setEnabled(count > 0)
    

    
    def go_to_previous(self):
        """跳转到上一个结果"""
        if not self.results:
            return
        
        self.current_search_index = (self.current_search_index - 1) % len(self.results)
        result = self.results[self.current_search_index]
        self.searchResultSelected.emit(result['page'], result['context'])
        
        # 高亮当前项
        for i in range(self.results_list.count()):
            if self.results_list.item(i).data(Qt.UserRole) == self.current_search_index:
                self.results_list.setCurrentRow(i)
                break
    
    def go_to_next(self):
        """跳转到下一个结果"""
        if not self.results:
            return
        
        self.current_search_index = (self.current_search_index + 1) % len(self.results)
        result = self.results[self.current_search_index]
        self.searchResultSelected.emit(result['page'], result['context'])
        
        # 高亮当前项
        for i in range(self.results_list.count()):
            if self.results_list.item(i).data(Qt.UserRole) == self.current_search_index:
                self.results_list.setCurrentRow(i)
                break


class TacticalPane(QLabel):

    focused = pyqtSignal(bool)
    def __init__(self, parent=None):
        
        super().__init__(parent)
        self.page_pixmap = None
        self.scaled_pixmap = None
        self.offset = QPointF(0, 0)
        self.scale_factor = 1.0
        self.drag_start = None
        self.page_num = -1
        self.is_left = False
        
        # 旋转相关
        self.rotation = 0
        self.original_pixmap = None
        
        # 批注相关
        self.annotations = []  # 当前页面的批注
        self.current_annotation = None
        self.annotation_mode = None  # None, "pen", "rect", "text"
        self.annotation_start = QPointF()
        self.temp_annotation = None
        self.pen_path = None
        self.pen_points = []
        self.text_input_widget = None
        self.drawing = False
        
        # 默认颜色 - 每个功能独立
        self.pen_color = QColor(255, 0, 0)  # 红色 - 画笔
        self.rect_color = QColor(255, 255, 0, 128)  # 半透明黄色 - 矩形高亮
        self.text_color = QColor(0, 0, 0)  # 黑色 - 文本
        self.pen_width = 3
        self.rect_border_width = 2
        self.font_size = 12
        
        # 文本编辑相关
        self.editing_text_annotation = None
        self.text_edit_start_pos = QPointF()
        
        # 搜索高亮
        self.search_highlights = []  # [{'rect': QRectF, 'color': QColor}, ...]
        self.search_text = ""  # 当前搜索词
        self.search_color = QColor(255, 255, 0, 100)  # 半透明黄色高亮
        
        self.setFrameShape(QFrame.Box)
        self.setFrameShadow(QFrame.Sunken)
        self.setAlignment(Qt.AlignCenter)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMouseTracking(True)
        self.setCursor(Qt.ArrowCursor)
        # === 文字选取相关 ===
        self.text_selection_mode = False
        self.selection_start = None      # QPointF (widget coordinates)
        self.selection_end = None        # QPointF (widget coordinates)
        self.text_selection_highlights = []  # [{'rect': [x,y,w,h], 'color': QColor}, ...]
        self.page_text_dict = None       # 存储 fitz.get_text("dict") 结果
        self.doc_page = None             # PyMuPDF page object
        # ====================       
        # 新增：用于控制拖动状态
        self.is_selecting_text = False         
    def _transform_point_for_rotation(self, x, y, creation_rotation, current_rotation, pixmap_width, pixmap_height):
        """将原始PDF坐标点根据旋转角度转换为当前屏幕坐标"""
        if creation_rotation == current_rotation:
            return x, y

        relative_rotation = (current_rotation - creation_rotation) % 360

        if relative_rotation == 90:
            return pixmap_height-y, x
        elif relative_rotation == 180:
            return pixmap_width - x, pixmap_height - y
        elif relative_rotation == 270:
            return  y,pixmap_width- x
        else:
            return x, y
    def _pixmap_coord_to_pdf_0deg(self, px, py):
        """将当前旋转视图下的 pixmap 像素坐标，转换为 0° PDF 坐标"""
        if not self.original_pixmap:
            return px, py
        orig_w = self.original_pixmap.width()
        orig_h = self.original_pixmap.height()
        rot = self.rotation
        if rot == 0:
            return px, py
        elif rot == 90:
            return py, orig_h - px
        elif rot == 180:
            return orig_w - px, orig_h - py
        elif rot == 270:
            return orig_w - py, px
        else:
            return px, py

    def _pixmap_rect_to_pdf_0deg_rect(self, x, y, w, h):
        """将当前旋转视图下的 pixmap 矩形，转换为 0° PDF 坐标下的包围盒"""
        x1, y1 = self._pixmap_coord_to_pdf_0deg(x, y)
        x2, y2 = self._pixmap_coord_to_pdf_0deg(x + w, y + h)
        pdf_x = min(x1, x2)
        pdf_y = min(y1, y2)
        pdf_w = abs(x1 - x2)
        pdf_h = abs(y1 - y2)
        return pdf_x, pdf_y, pdf_w, pdf_h    
    
    
    def focusInEvent(self, event):
        """当窗格获得键盘焦点时触发"""
        super().focusInEvent(event)
        # 发射信号，告诉主窗口：“我获得了焦点，我是左窗格吗？”
        self.focused.emit(self.is_left_pane)
    def set_page(self, pixmap, page_num, is_left=False, reset_view=False, annotations=None):
        # 保存原始pixmap
        self.original_pixmap = pixmap
        self.page_pixmap = pixmap
        self.page_num = page_num
        self.is_left = is_left
        
        if reset_view:
            self.reset_view()
        # else: 保持现有的 self.rotation 值（由 render_facing 或用户操作设置）
            
        if annotations is not None:
            self.annotations = annotations
        elif hasattr(self.window(), 'get_annotations_for_page'):
            self.annotations = self.window().get_annotations_for_page(page_num)
        else:
            self.annotations = []
        # 移除任何现有的文本编辑部件
        if self.text_input_widget:
            self.text_input_widget.deleteLater()
        self.text_input_widget = None
        self.editing_text_annotation = None
        # 应用旋转
        if self.rotation != 0:
            transform = QTransform().rotate(self.rotation)
            self.page_pixmap = self.original_pixmap.transformed(transform, Qt.SmoothTransformation)
        
        # 加载页面文本用于选取
        if hasattr(self.window(), 'doc') and self.window().doc and page_num > 0:
            try:
                self.doc_page = self.window().doc[page_num - 1]
                self.page_text_dict = self.doc_page.get_text("dict")
                print(f"[DEBUG] Loaded text dict for page {page_num}")
            except Exception as e:
                print(f"[ERROR] Failed to load text for page {page_num}: {e}")
                self.doc_page = None
                self.page_text_dict = None
        else:
            self.doc_page = None
            self.page_text_dict = None        
        self.update()
    
    def reset_view(self):
        self.rotation = 0
        self.offset = QPointF(0, 0)
        if self.original_pixmap:
            # 计算适配窗格宽度的缩放比例
            pane_width = self.width()
            if pane_width > 0:
                self.scale_factor = pane_width / self.original_pixmap.width()
                # 限制缩放范围
                self.scale_factor = max(0.2, min(self.scale_factor, 10.0))
            else:
                self.scale_factor = 1.0
            # 应用旋转（虽然 rotation=0，但保持逻辑一致）
            transform = QTransform().rotate(self.rotation)
            self.page_pixmap = self.original_pixmap.transformed(transform, Qt.SmoothTransformation)
        else:
            self.scale_factor = 1.0
        self.update()

    def rotate_clockwise(self):
        self.rotation = (self.rotation + 90) % 360
        if self.original_pixmap:
            transform = QTransform().rotate(self.rotation)
            self.page_pixmap = self.original_pixmap.transformed(transform, Qt.SmoothTransformation)
        self.update()

    def paintEvent(self, event):
        if not self.page_pixmap or self.page_pixmap.isNull():
            super().paintEvent(event)
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

        scaled_size = self.page_pixmap.size() * self.scale_factor
        self.scaled_pixmap = self.page_pixmap.scaled(
            scaled_size,
            Qt.IgnoreAspectRatio,
            Qt.SmoothTransformation
        )

        draw_x = self.offset.x()
        draw_y = self.offset.y()
        painter.drawPixmap(int(draw_x), int(draw_y), self.scaled_pixmap)
        
        # 绘制搜索高亮（支持页面旋转）
        for highlight in self.search_highlights:
            x0, y0, w, h = highlight['rect']
            color = highlight['color']
            
            # 获取原始 PDF 坐标下的四个角（0°）
            corners_0deg = [(x0, y0), (x0+w, y0), (x0+w, y0+h), (x0, y0+h)]
            
            # 转换到当前旋转下的 PDF 坐标
            corners_current = []
            for (px, py) in corners_0deg:
                xc, yc = self._transform_point_for_rotation(px, py, 0, self.rotation, 
                                                            self.original_pixmap.width(), 
                                                            self.original_pixmap.height())
                corners_current.append((xc, yc))
            
            # 转换到屏幕坐标并创建包围盒
            screen_points = [
                QPointF(cx * self.scale_factor + draw_x, cy * self.scale_factor + draw_y)
                for (cx, cy) in corners_current
            ]
            xs = [p.x() for p in screen_points]
            ys = [p.y() for p in screen_points]
            screen_rect = QRectF(min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))
            
            painter.fillRect(screen_rect, color)
            # =======================================
        
        # 绘制批注
        for annotation in self.annotations:
            self.draw_annotation(painter, annotation, draw_x, draw_y)
        # === 新增：绘制文字选取高亮 ===
        for highlight in self.text_selection_highlights:
            x0, y0, w, h = highlight['rect']
            color = highlight['color']
            # 复用搜索高亮的坐标变换逻辑
            corners_0deg = [(x0, y0), (x0+w, y0), (x0+w, y0+h), (x0, y0+h)]
            corners_current = []
            for (px, py) in corners_0deg:
                xc, yc = self._transform_point_for_rotation(px, py, 0, self.rotation, self.original_pixmap.width(), self.original_pixmap.height())
                corners_current.append((xc, yc))
            screen_points = [
                QPointF(cx * self.scale_factor + draw_x, cy * self.scale_factor + draw_y)
                for (cx, cy) in corners_current
            ]
            xs = [p.x() for p in screen_points]
            ys = [p.y() for p in screen_points]
            screen_rect = QRectF(min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))
            painter.fillRect(screen_rect, color)
        # === 文字选取高亮绘制结束 ===        
        # 绘制临时批注（正在绘制中的）
        # === 修复：所见即所得的临时批注预览 (矩形、画笔、文本) ===
        # 1. 预览临时矩形/高亮
        if self.temp_annotation and self.temp_annotation["type"] == "rect":
            x, y, w, h = self.temp_annotation["rect"]
            screen_x = x * self.scale_factor + draw_x
            screen_y = y * self.scale_factor + draw_y
            screen_w = w * self.scale_factor
            screen_h = h * self.scale_factor
            painter.save()
            color = QColor(self.temp_annotation["color"])
            color.setAlpha(128)
            painter.setBrush(QBrush(color))
            painter.setPen(QPen(color, self.rect_border_width))
            painter.drawRect(int(screen_x), int(screen_y), int(screen_w), int(screen_h))
            painter.restore()

        # 2. 预览临时画笔路径
        if self.pen_path and len(self.pen_points) > 0:
            painter.save()
            pen = QPen(self.pen_color, self.pen_width)
            pen.setCapStyle(Qt.RoundCap)
            pen.setJoinStyle(Qt.RoundJoin)
            painter.setPen(pen)
            # 关键：直接使用当前视图的 scale+offset 转换点
            scaled_path = QPainterPath()
            for i, point in enumerate(self.pen_points):
                if isinstance(point, (list, tuple)) and len(point) >= 2:
                    px, py = point[0], point[1]
                else:  # 如果是 QPointF
                    px, py = point.x(), point.y()
                screen_px = px * self.scale_factor + draw_x
                screen_py = py * self.scale_factor + draw_y
                if i == 0:
                    scaled_path.moveTo(screen_px, screen_py)
                else:
                    scaled_path.lineTo(screen_px, screen_py)
            painter.drawPath(scaled_path)
            painter.restore()

        # 3. 文本批注的预览由 InlineTextEdit 自身处理，无需在此绘制
        # === 修复结束 ===
        # === 极简方案：直接问主窗口我是不是当前阅读区域 ===
        main_window = self.window()
        if hasattr(main_window, 'last_focused_pane_is_left') and hasattr(main_window, 'single_page_mode'):
            # 判断自己是不是左窗格（通过对象身份）
            is_left_pane = (self is main_window.left_pane)
            is_right_pane = (self is main_window.right_pane)

            # 当前阅读区域逻辑：
            # - 单页模式：只有右窗格是活跃的
            # - 双页模式：左窗格活跃当且仅当 last_focused_pane_is_left 为 True
            is_active = False
            if main_window.single_page_mode:
                if is_right_pane:
                    is_active = True
            else:
                if is_left_pane and main_window.last_focused_pane_is_left:
                    is_active = True
                elif is_right_pane and not main_window.last_focused_pane_is_left:
                    is_active = True

            if is_active:
                border_pen = QPen(QColor(80, 110, 130), 2)
                border_pen.setJoinStyle(Qt.MiterJoin)
                painter.setPen(border_pen)
                painter.setBrush(Qt.NoBrush)
                painter.drawRect(1, 1, self.width() - 2, self.height() - 2)
    def draw_annotation(self, painter, annotation, offset_x, offset_y):
        if not self.original_pixmap:
            return

        anno_type = annotation.get("type", "")
        color = QColor(annotation.get("color", "#FF0000"))
        orig_w = self.original_pixmap.width()
        orig_h = self.original_pixmap.height()
        creation_rot = annotation.get("creation_rotation", 0)  # 批注创建时的页面旋转
        current_rot = self.rotation                              # 当前页面旋转

        # === 核心：将批注从 creation_rot 坐标系 转换到 current_rot 坐标系 ===
        def transform_coords_from_creation_to_current(points_0deg):
            """将一组在 creation_rot 下定义的点，转换到 current_rot 下的坐标"""
            points_current = []
            for (px, py) in points_0deg:
                # Step 1: 从 creation_rot 逆变换回 0°
                x0, y0 = self._transform_point_for_rotation(px, py, creation_rot, 0, orig_w, orig_h)
                # Step 2: 从 0° 正变换到 current_rot
                xc, yc = self._transform_point_for_rotation(x0, y0, 0, current_rot, orig_w, orig_h)
                points_current.append((xc, yc))
            return points_current
        # ===================================================================

        if anno_type == "rect":
            x, y, w, h = annotation["rect"]
            corners_0deg = [(x, y), (x+w, y), (x+w, y+h), (x, y+h)]
            corners_current = transform_coords_from_creation_to_current(corners_0deg)
            
            # 计算包围盒（用于绘制）
            xs = [p[0] for p in corners_current]
            ys = [p[1] for p in corners_current]
            final_x, final_y = min(xs), min(ys)
            final_w, final_h = max(xs) - final_x, max(ys) - final_y

            screen_x = final_x * self.scale_factor + offset_x
            screen_y = final_y * self.scale_factor + offset_y
            screen_w = final_w * self.scale_factor
            screen_h = final_h * self.scale_factor

            painter.save()
            highlight_color = QColor(color)
            highlight_color.setAlpha(96)
            painter.setBrush(QBrush(highlight_color))
            painter.setPen(QPen(color, self.rect_border_width))
            painter.drawRect(int(screen_x), int(screen_y), int(screen_w), int(screen_h))
            painter.restore()

        elif anno_type == "pen":
            points = annotation.get("points", [])
            if len(points) < 2:
                return
            # 将所有笔迹点从 creation_rot 转换到 current_rot
            transformed_points = transform_coords_from_creation_to_current(points)
            # 转换到屏幕坐标
            screen_points = [
                QPointF(px * self.scale_factor + offset_x, py * self.scale_factor + offset_y)
                for (px, py) in transformed_points
            ]
            painter.save()
            pen = QPen(color, self.pen_width * self.scale_factor)
            pen.setCapStyle(Qt.RoundCap)
            pen.setJoinStyle(Qt.RoundJoin)
            painter.setPen(pen)
            path = QPainterPath()
            for i, pt in enumerate(screen_points):
                if i == 0:
                    path.moveTo(pt)
                else:
                    path.lineTo(pt)
            painter.drawPath(path)
            painter.restore()

        elif anno_type == "text":
            x, y, w, h = annotation["rect"]  # 这已经是精准的 0° PDF 坐标下的文字包围盒！
            text = annotation.get("text", "")
            font_size = annotation.get("font_size", 12)
            
            if not text.strip():
                return
                
            # === 直接使用保存的矩形（四个角）===
            corners_0deg = [(x, y), (x+w, y), (x+w, y+h), (x, y+h)]
            
            # === 将四个角从 0° 转换到 current_rot ===
            corners_current = []
            for (px, py) in corners_0deg:
                xc, yc = self._transform_point_for_rotation(px, py, 0, current_rot, orig_w, orig_h)
                corners_current.append((xc, yc))
            
            # === 转换到屏幕坐标并绘制 ===
            screen_path = QPainterPath()
            for i, (cx, cy) in enumerate(corners_current):
                sx = cx * self.scale_factor + offset_x
                sy = cy * self.scale_factor + offset_y
                if i == 0:
                    screen_path.moveTo(sx, sy)
                else:
                    screen_path.lineTo(sx, sy)
            screen_path.closeSubpath()
            
            # 绘制背景（透明）
            painter.save()
            highlight_color = QColor(color)
            highlight_color.setAlpha(0)  # 完全透明
            painter.setBrush(QBrush(highlight_color))
            painter.setPen(Qt.NoPen)  # ← 完全移除边框
            painter.drawPath(screen_path)
            painter.restore()
            
            # === 绘制文字（在旋转后的包围盒内）===
            # 计算四边形的屏幕包围盒（用于文字定位）
            xs = [p[0] for p in corners_current]
            ys = [p[1] for p in corners_current]
            min_x, max_x = min(xs), max(xs)
            min_y, max_y = min(ys), max(ys)
            text_rect_screen = QRectF(
                min_x * self.scale_factor + offset_x,
                min_y * self.scale_factor + offset_y,
                (max_x - min_x) * self.scale_factor,
                (max_y - min_y) * self.scale_factor
            )
            
            painter.save()
            font = QFont("Arial", int(font_size * self.scale_factor))
            painter.setFont(font)
            painter.setPen(QPen(color))
            painter.drawText(text_rect_screen, Qt.TextWordWrap, text)
            painter.restore()
    def set_search_highlights(self, highlights, search_text=""):
        """设置搜索高亮"""
        self.search_highlights = highlights
        self.search_text = search_text
        self.update()

    def wheelEvent(self, event):
        if event.modifiers() == Qt.ControlModifier:
            delta = event.angleDelta().y()
            zoom_factor = 1.1 if delta > 0 else 1 / 1.1
            self.scale_factor *= zoom_factor
            self.scale_factor = max(0.2, min(self.scale_factor, 10.0))
            self.update()
        else:
            scroll_amount = event.angleDelta().y() // 3
            self.offset.setY(self.offset.y() + scroll_amount)
            self.update()
        event.accept()

    def mousePressEvent(self, event):
        if self.text_selection_mode and event.button() == Qt.LeftButton:
            # J模式下，左键按下开始选取（但不立即绘制，等待拖动）
            self.is_selecting_text = True
            self.selection_start = event.pos()
            self.selection_end = event.pos()
            # 不立即调用 update_selected_text，避免单击产生空选区
        elif self.annotation_mode and event.button() == Qt.LeftButton:
            # 开始绘制批注
            self.drawing = True
            # 计算在PDF图片上的坐标（考虑缩放和偏移）
            img_x = (event.pos().x() - self.offset.x()) / self.scale_factor
            img_y = (event.pos().y() - self.offset.y()) / self.scale_factor
            self.annotation_start = QPointF(event.pos())
            if self.annotation_mode == "rect":
                self.temp_annotation = {
                    "type": "rect",
                    "rect": [img_x, img_y, 0, 0],
                    "color": self.rect_color.name()
                }
            elif self.annotation_mode == "pen":
                self.pen_path = QPainterPath()
                self.pen_points = [(img_x, img_y)] # 修复：初始化路径起点
                self.pen_path.moveTo(event.pos())
            elif self.annotation_mode == "text":
                # 对于文本，直接创建文本框
                screen_x = event.pos().x()
                screen_y = event.pos().y()
                # 创建文本编辑部件
                self.text_input_widget = InlineTextEdit(self)
                self.text_input_widget.setGeometry(int(screen_x), int(screen_y), 200, 100)
                self.text_input_widget.setStyleSheet(f"""
                QTextEdit {{
                    background-color: rgba(255, 255, 255, 200);
                    border: 1px solid {self.text_color.name()};
                    font-size: {self.font_size}px;
                    color: {self.text_color.name()};
                }}
                """)
                self.text_input_widget.show()
                self.text_input_widget.setFocus()
                # 保存起始位置
                self.text_edit_start_pos = QPointF(screen_x, screen_y)
                # 连接信号
                self.text_input_widget.textConfirmed.connect(self.finish_text_annotation)
                self.text_input_widget.editingCancelled.connect(self.cancel_text_annotation)
                # 创建临时批注
                self.temp_annotation = {
                    "type": "text",
                    "rect": [img_x, img_y, 200 / self.scale_factor, 100 / self.scale_factor],
                    "color": self.text_color.name(),
                    "text": "",
                    "font_size": self.font_size
                }
                # 设置正在编辑的批注
                self.editing_text_annotation = self.temp_annotation
                self.update()
        elif event.button() == Qt.LeftButton and not self.annotation_mode:
            # 正常的拖拽
            self.drag_start = event.pos()
            self.setCursor(Qt.ClosedHandCursor)
        else:
            super().mousePressEvent(event)
    def mouseMoveEvent(self, event):
        if self.text_selection_mode and self.is_selecting_text and self.selection_start is not None:
            # J模式下，拖动时更新选区
            self.selection_end = event.pos()
            self.update_selected_text()
            self.setCursor(Qt.IBeamCursor)
        elif self.annotation_mode and self.drawing:
            if self.annotation_mode == "rect" and self.temp_annotation:
                # 更新矩形大小
                current_pos = event.pos()
                start_x = self.annotation_start.x()
                start_y = self.annotation_start.y()
                rect_width = current_pos.x() - start_x
                rect_height = current_pos.y() - start_y
                img_x = (start_x - self.offset.x()) / self.scale_factor
                img_y = (start_y - self.offset.y()) / self.scale_factor
                img_width = rect_width / self.scale_factor
                img_height = rect_height / self.scale_factor
                # 确保宽度和高度为正
                if rect_width < 0:
                    img_x = img_x + img_width
                    img_width = -img_width
                if rect_height < 0:
                    img_y = img_y + img_height
                    img_height = -img_height
                self.temp_annotation["rect"] = [img_x, img_y, img_width, img_height]
                self.update()
            elif self.annotation_mode == "pen":
                # 添加画笔点
                img_x = (event.pos().x() - self.offset.x()) / self.scale_factor
                img_y = (event.pos().y() - self.offset.y()) / self.scale_factor
                self.pen_points.append((img_x, img_y)) # 修复：更新路径
                self.pen_path.lineTo(event.pos())
                self.update()
        elif self.drag_start:
            delta = event.pos() - self.drag_start
            self.offset += delta
            self.drag_start = event.pos()
            self.update()
        else:
            super().mouseMoveEvent(event)
    def mouseReleaseEvent(self, event):
        if self.text_selection_mode and self.is_selecting_text and event.button() == Qt.LeftButton:
            # J模式下，松开左键结束选取，保留高亮
            self.is_selecting_text = False
            self.update_selected_text()
            # 可在此处复制到剪贴板或弹出菜单
            if hasattr(self, 'selected_text') and self.selected_text:
                print(f"[DEBUG] Selected text: '{self.selected_text}'")
        elif self.annotation_mode and self.drawing and event.button() == Qt.LeftButton:
            self.drawing = False
            if self.annotation_mode == "rect" and self.temp_annotation:
                # 保存矩形批注
                final_rect = self.temp_annotation["rect"]
                if abs(final_rect[2]) > 5 and abs(final_rect[3]) > 5: # 最小尺寸检查
                    x, y, w, h = final_rect
                    # === 关键修复：转换为 0° PDF 坐标 ===
                    pdf_x, pdf_y, pdf_w, pdf_h = self._pixmap_rect_to_pdf_0deg_rect(x, y, w, h)
                    saved_annotation = {
                        "type": "rect",
                        "rect": [pdf_x, pdf_y, pdf_w, pdf_h],
                        "color": self.temp_annotation["color"],
                        "creation_rotation": 0 # 统一设为 0
                    }
                    self.annotations.append(saved_annotation)
                    if hasattr(self.window(), 'save_annotation'):
                        self.window().save_annotation(self.page_num, saved_annotation)
                self.temp_annotation = None
            elif self.annotation_mode == "pen" and len(self.pen_points) > 1:
                # 保存画笔批注
                # === 关键修复：将每个点转换为 0° PDF 坐标 ===
                converted_points = []
                for pt in self.pen_points:
                    if isinstance(pt, (list, tuple)) and len(pt) >= 2:
                        px, py = pt[0], pt[1]
                    else: # QPointF
                        px, py = pt.x(), pt.y()
                    pdf_x, pdf_y = self._pixmap_coord_to_pdf_0deg(px, py)
                    converted_points.append([pdf_x, pdf_y]) # 存为 list，兼容 JSON
                pen_annotation = {
                    "type": "pen",
                    "points": converted_points,
                    "color": self.pen_color.name(),
                    "width": self.pen_width,
                    "creation_rotation": 0 # 统一设为 0
                }
                self.annotations.append(pen_annotation)
                if hasattr(self.window(), 'save_annotation'):
                    self.window().save_annotation(self.page_num, pen_annotation)
                self.pen_points = []
                self.pen_path = None
            # 文本批注在文本编辑部件中处理
            self.update()
        elif event.button() == Qt.LeftButton and self.drag_start:
            self.drag_start = None
            self.setCursor(Qt.ArrowCursor)
        # === 新增：处理右键点击 ===
        elif event.button() == Qt.RightButton:
            self._handle_right_click(event)
        # =========================            
        else:
            super().mouseReleaseEvent(event)
    
    def _handle_right_click(self, event):
        """
        处理右键点击事件，显示复制菜单（如果有选中文本）。
        """
        # 检查是否有选中文本
        has_selection = hasattr(self, 'selected_text') and bool(self.selected_text.strip())
        
        if not has_selection:
            return # 如果没有选中，直接返回，不显示任何东西
            
        # 创建菜单
        from PyQt5.QtWidgets import QMenu, QAction
        menu = QMenu(self)
        
        # 使用主窗口的 tr 方法进行翻译
        main_window = self.window()
        copy_action = QAction(main_window.tr("Copy"), self)
        
        # === 核心：复用 Ctrl+C 的逻辑 ===
        def do_copy():
            clipboard = QApplication.clipboard()
            clipboard.setText(self.selected_text.strip())
            print(f"[INFO] Copied to clipboard : {self.selected_text.strip()}")
            # 显示状态栏提示

                
        copy_action.triggered.connect(do_copy)
        # ===============================
        
        menu.addAction(copy_action)
        menu.exec_(event.globalPos())

    def finish_text_annotation(self, text):
        if self.text_input_widget and self.temp_annotation:
            if text.strip():
                self.temp_annotation["text"] = text
                
                # === 关键修复：在 PDF 坐标系下计算文本尺寸 ===
                pdf_font_size = self.font_size  # 字体大小（pt），直接用于 PDF 坐标
                font = QFont("Arial", pdf_font_size)
                font_metrics = QFontMetrics(font)
                
                # 在 PDF 坐标系中，1pt = 1 单位，所以直接计算
                # 注意：这里不需要考虑 scale_factor！
                text_rect = font_metrics.boundingRect(
                    QRect(0, 0, 1000, 10000),  # 虚拟大矩形（PDF 坐标）
                    Qt.TextWordWrap,
                    text
                )
                pdf_text_width = text_rect.width()*1.1#计算宽度并留下余量
                pdf_text_height = text_rect.height()
                

                
                # 更新矩形尺寸（直接使用 PDF 坐标尺寸！）
                self.temp_annotation["rect"][2] = pdf_text_width
                self.temp_annotation["rect"][3] = pdf_text_height
                # ===========================================
                
                # 转换为 0° PDF 坐标（位置）
                x, y, w, h = self.temp_annotation["rect"]
                pdf_x, pdf_y, pdf_w, pdf_h = self._pixmap_rect_to_pdf_0deg_rect(x, y, w, h)
                saved_annotation = {
                    "type": "text",
                    "rect": [pdf_x, pdf_y, pdf_w, pdf_h],
                    "color": self.temp_annotation["color"],
                    "text": text,
                    "font_size": self.font_size,
                    "creation_rotation": 0
                }
                self.annotations.append(saved_annotation)
                if hasattr(self.window(), 'save_annotation'):
                    self.window().save_annotation(self.page_num, saved_annotation)
                self.text_input_widget.deleteLater()
                self.text_input_widget = None
                self.temp_annotation = None
                self.editing_text_annotation = None
                self.update()
    def cancel_text_annotation(self):
        """取消文本批注"""
        if self.text_input_widget:
            self.text_input_widget.deleteLater()
            self.text_input_widget = None
            self.temp_annotation = None
            self.editing_text_annotation = None
            self.update()

    def keyPressEvent(self, event):
        # === 新增：打印所有按键事件 ===
        print(f"[KEY DEBUG] Key: {event.key()}, Text: '{event.text()}', Modifiers: {event.modifiers()}, isAutoRepeat: {event.isAutoRepeat()}")
        # =============================

        if self.text_selection_mode and event.key() == Qt.Key_C and event.modifiers() == Qt.ControlModifier:
            # Ctrl+C: 复制选中文本
            if hasattr(self, 'selected_text') and self.selected_text.strip():
                clipboard = QApplication.clipboard()
                clipboard.setText(self.selected_text.strip())
                print(f"[INFO] Copied to clipboard: {self.selected_text.strip()}")

                # ===========================

                
        else:
            super().keyPressEvent(event)
    def cancel_annotation(self):
        """取消当前的批注绘制"""
        # 取消文本编辑
        if self.text_input_widget:
            self.cancel_text_annotation()
        
        self.annotation_mode = None
        self.drawing = False
        self.temp_annotation = None
        self.pen_points = []
        self.pen_path = None
        self.setCursor(Qt.ArrowCursor)
        self.update()
        
        if hasattr(self.window(), 'update_status'):
            self.window().update_status()
    
    def set_text_selection_mode(self, enabled: bool):
        """启用/禁用文字选取模式"""
        print(f"[DEBUG] Pane {self.page_num} set_text_selection_mode: {enabled}")
        self.text_selection_mode = enabled
        self.setCursor(Qt.IBeamCursor if enabled else Qt.ArrowCursor)
        # 清除旧选区
        self.selection_start = None
        self.selection_end = None
        self.text_selection_highlights = []
        self.update()

    def update_selected_text(self):
        if not self.doc_page or not self.page_text_dict:
            self.text_selection_highlights = []
            return
        if self.selection_start is None or self.selection_end is None:
            self.text_selection_highlights = []
            return

        # === 步骤1: 获取鼠标在当前 Widget 中的选区 (屏幕像素) ===
        sel_widget_x0 = min(self.selection_start.x(), self.selection_end.x())
        sel_widget_y0 = min(self.selection_start.y(), self.selection_end.y())
        sel_widget_x1 = max(self.selection_start.x(), self.selection_end.x())
        sel_widget_y1 = max(self.selection_start.y(), self.selection_end.y())

        selected_spans = []  # 存储 (y, x, text) 用于排序
        highlight_rects = []  # 存储 Pixmap 像素坐标，用于绘制
        
        # === 步骤2: 遍历所有文字块，将其 bbox 转换到当前屏幕坐标系 ===
        # 同时收集所有 span 的中心 Y 坐标，用于确定首尾行
        all_spans = []
        for block in self.page_text_dict.get("blocks", []):
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text = span["text"]
                    if not text.strip():
                        continue
                        
                    # span["bbox"] 是 0° PDF 坐标
                    pdf_x0, pdf_y0, pdf_x1, pdf_y1 = span["bbox"]
                    
                    # 1. 转为 Pixmap 像素坐标 (0°)
                    px0, py0 = pdf_x0 * RENDER_SCALE, pdf_y0 * RENDER_SCALE
                    px1, py1 = pdf_x1 * RENDER_SCALE, pdf_y1 * RENDER_SCALE
                    
                    # 2. 应用旋转，得到当前 Pixmap 坐标
                    corners_0deg_pixmap = [(px0, py0), (px1, py0), (px1, py1), (px0, py1)]
                    corners_current_pixmap = []
                    for (cx, cy) in corners_0deg_pixmap:
                        rot_x, rot_y = self._transform_point_for_rotation(
                            cx, cy, 0, self.rotation,
                            self.original_pixmap.width(), self.original_pixmap.height()
                        )
                        corners_current_pixmap.append((rot_x, rot_y))
                    
                    # 3. 将当前 Pixmap 坐标转为 Widget (屏幕) 坐标
                    screen_points = [
                        QPointF(cx * self.scale_factor + self.offset.x(),
                                cy * self.scale_factor + self.offset.y())
                        for (cx, cy) in corners_current_pixmap
                    ]
                    span_screen_x0 = min(p.x() for p in screen_points)
                    span_screen_y0 = min(p.y() for p in screen_points)
                    span_screen_x1 = max(p.x() for p in screen_points)
                    span_screen_y1 = max(p.y() for p in screen_points)
                    
                    center_x = (span_screen_x0 + span_screen_x1) / 2
                    center_y = (span_screen_y0 + span_screen_y1) / 2
                    
                    all_spans.append({
                        'span': span,
                        'text': text,
                        'screen_bbox': (span_screen_x0, span_screen_y0, span_screen_x1, span_screen_y1),
                        'center': (center_x, center_y),
                        'pdf_bbox': (pdf_x0, pdf_y0, pdf_x1, pdf_y1)
                    })

        if not all_spans:
            self.selected_text = ""
            self.text_selection_highlights = []
            self.update()
            return

        # === 步骤3: 找出被选中的 span 范围（按Y坐标）===
        # 找到Y坐标在选区内的所有span
        vertically_selected_spans = [
            s for s in all_spans 
            if sel_widget_y0 <= s['center'][1] <= sel_widget_y1
        ]
        
        if not vertically_selected_spans:
            self.selected_text = ""
            self.text_selection_highlights = []
            self.update()
            return

        # 按Y坐标排序，确定第一行和最后一行的Y范围
        vertically_selected_spans.sort(key=lambda s: s['center'][1])
        first_span_center_y = vertically_selected_spans[0]['center'][1]
        last_span_center_y = vertically_selected_spans[-1]['center'][1]

        # === 步骤4: 按阅读习惯处理每个 span ===
        for s in all_spans:
            span = s['span']
            text = s['text']
            screen_x0, screen_y0, screen_x1, screen_y1 = s['screen_bbox']
            pdf_x0, pdf_y0, pdf_x1, pdf_y1 = s['pdf_bbox']
            center_x, center_y = s['center']
            
            # 先判断垂直方向是否在选区内
            if not (sel_widget_y0 <= center_y <= sel_widget_y1):
                continue

            # --- 确定当前 span 属于哪一行 ---
            is_first_line = (abs(center_y - first_span_center_y) < 5) # 容忍微小差异
            is_last_line = (abs(center_y - last_span_center_y) < 5)

            # --- 智能插值逻辑 ---
            selected_text_part = ""
            highlight_pdf_x0, highlight_pdf_x1 = pdf_x0, pdf_x1

            if is_first_line and is_last_line:
                # 单行情况：精确裁剪
                clip_x0 = max(screen_x0, sel_widget_x0)
                clip_x1 = min(screen_x1, sel_widget_x1)
                if clip_x1 > clip_x0:
                    span_width = screen_x1 - screen_x0
                    if span_width > 0:
                        start_ratio = (clip_x0 - screen_x0) / span_width
                        end_ratio = (clip_x1 - screen_x0) / span_width
                        start_idx = int(len(text) * start_ratio)
                        end_idx = int(len(text) * end_ratio)
                        start_idx = max(0, min(start_idx, len(text)))
                        end_idx = max(0, min(end_idx, len(text)))
                        if start_idx < end_idx:
                            selected_text_part = text[start_idx:end_idx]
                            char_width = (pdf_x1 - pdf_x0) / len(text)
                            highlight_pdf_x0 = pdf_x0 + start_idx * char_width
                            highlight_pdf_x1 = pdf_x0 + end_idx * char_width
            elif is_first_line:
                # 第一行：从起点X到行尾
                if screen_x1 > sel_widget_x0: # 有交集
                    clip_x0 = max(screen_x0, sel_widget_x0)
                    span_width = screen_x1 - screen_x0
                    if span_width > 0:
                        start_ratio = (clip_x0 - screen_x0) / span_width
                        start_idx = int(len(text) * start_ratio)
                        start_idx = max(0, min(start_idx, len(text)))
                        selected_text_part = text[start_idx:]
                        char_width = (pdf_x1 - pdf_x0) / len(text)
                        highlight_pdf_x0 = pdf_x0 + start_idx * char_width
                        highlight_pdf_x1 = pdf_x1
            elif is_last_line:
                # 最后一行：从行首到终点X
                if screen_x0 < sel_widget_x1: # 有交集
                    clip_x1 = min(screen_x1, sel_widget_x1)
                    span_width = screen_x1 - screen_x0
                    if span_width > 0:
                        end_ratio = (clip_x1 - screen_x0) / span_width
                        end_idx = int(len(text) * end_ratio)
                        end_idx = max(0, min(end_idx, len(text)))
                        selected_text_part = text[:end_idx]
                        # === 修复：在这里重新计算 char_width ===
                        if len(text) > 0:
                            char_width = (pdf_x1 - pdf_x0) / len(text)
                            highlight_pdf_x0 = pdf_x0
                            highlight_pdf_x1 = pdf_x0 + end_idx * char_width
                        else:
                            highlight_pdf_x0, highlight_pdf_x1 = pdf_x0, pdf_x1
                        # =======================================
            else:
                # 中间完整行：全选
                selected_text_part = text
                highlight_pdf_x0, highlight_pdf_x1 = pdf_x0, pdf_x1

            if selected_text_part:
                selected_spans.append((center_y, center_x, selected_text_part))
                # 添加高亮矩形 (PDF 坐标 -> Pixmap 坐标)
                highlight_rects.append([
                    highlight_pdf_x0 * RENDER_SCALE,
                    pdf_y0 * RENDER_SCALE,
                    (highlight_pdf_x1 - highlight_pdf_x0) * RENDER_SCALE,
                    (pdf_y1 - pdf_y0) * RENDER_SCALE
                ])

        selected_spans.sort(key=lambda item: (item[0], item[1]))
        self.selected_text = "".join(text for _, _, text in selected_spans)
        self.text_selection_highlights = [
            {'rect': rect, 'color': QColor(0, 100, 255, 80)} 
            for rect in highlight_rects
        ]
        self.update()
    
    def set_annotation_mode(self, mode):
        """设置批注模式"""
        # 取消当前所有批注模式
        self.cancel_annotation()
        self.annotation_mode = mode
        if mode == "pen":
            self.setCursor(Qt.CrossCursor)
        elif mode == "rect":
            self.setCursor(Qt.CrossCursor)
        elif mode == "text":
            self.setCursor(Qt.IBeamCursor)
        else:
            self.setCursor(Qt.ArrowCursor)
    
    def set_pen_color(self, color):
        """设置画笔颜色"""
        self.pen_color = QColor(color)
    
    def set_rect_color(self, color):
        """设置矩形高亮颜色"""
        self.rect_color = QColor(color)
    
    def set_text_color(self, color):
        """设置文本颜色"""
        self.text_color = QColor(color)


class TactiReader(QMainWindow):
    def __init__(self, pdf_path=None):
        # 修复dpi导致吞字问题
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)        
        super().__init__()
        # 设置全局字体：中文用微软雅黑，英文用等宽粗体
        font = QFont()
        font.setFamily("Microsoft YaHei, Consolas, Courier New, monospace")
        font.setPointSize(9)
        self.setFont(font)
        # 主窗口背景设为浅灰
        self.setStyleSheet("QMainWindow { background-color: #f8f8f8; }")
        # === 国际化支持 ===
        # 1. 首先加载全局语言设置
        self.current_lang = "en"  # 默认语言
        self.translations = {
            "en": {},
            "zh": {
                # === 文件菜单 ===
                "File": "文件",
                "Open PDF...": "打开 PDF...",
                "Save As PDF...": "另存为 PDF...",
                "Save As PDF": "另存为 PDF",
                "PDF Files (*.pdf)": "PDF 文件 (*.pdf)",
                "Export Notebook...": "导出笔记...",
                "Open Notebook...": "打开笔记...",
                "Save Notebook": "保存笔记",
                "TactiReader Notebook (*.tactinote)": "TactiReader 笔记 (*.tactinote)",
                "Recent Files": "最近文件",
                "<No recent files>": "<无最近文件>",
                "Save Configuration (S)": "保存配置 (S)",

                # === 视图菜单 ===
                "View": "视图",
                "Toggle Single/Double Page Mode (Z)": "切换单/双页模式 (Z)",
                "Toggle Left Pane Lock/Follow (C)": "切换左窗格锁定/跟随 (C)",
                "Show/Hide Bookmarks & TOC Panel (N)": "显示/隐藏书签与目录面板 (N)",
                "Toggle Fullscreen (F11)": "全屏/退出全屏 (F11)",
                "Rotate Current Page Clockwise (~)": "顺时针旋转当前页 (~)",
                "Reset Current Page (X)": "重置当前页面 (X)",
                "Center Splitter and Reset (Ctrl+X)": "居中分隔条并重置 (Ctrl+X)",
                "Clear All Page Rotations (Ctrl+Shift+X)": "清除全文档旋转 (Ctrl+Shift+X)",
                "help.md": "help_zh.md",
                "about.md": "about_zh.md",
                # === 导航菜单 ===
                "Navigation": "导航",
                "Go to Page... (G)": "跳转到页码... (G)",
                "Go to Page": "跳转到页码",
                "Enter page number ({min}-{max}):": "输入页码 ({min}-{max})：",
                "Enter a number between {min} and {max}": "请输入 {min} 到 {max} 的页面",
                "Page number must be between 1 and {total_pages}": "页码必须在 1 到 {total_pages} 之间",
                "Please enter a valid number": "请输入有效数字",
                "Calibrate Physical Page Number... (Ctrl+G)": "标定物理页码... (Ctrl+G)",
                "Page Number Calibration": "页面标定",
                "Enter logical page number for physical page {physical}:": "输入物理第 {physical}页对应的逻辑页码:",
                "Clear Physical Page Offset (Ctrl+Shift+G)": "清除物理页码偏移 (Ctrl+Shift+G)",
                "Full-Text Search... (F)": "全文搜索... (F)",
                "Search in PDF": "在 PDF 中搜索",
                "Navigation Back (Ctrl+A)": "导航回退 (Ctrl+A)",
                "Set Flip Multiplier": "设置翻页倍数",
                "Flip by Multiplier": "按倍数翻页",
                "Next Pages (→)": "向前翻页 (→)",
                "Previous Pages (←)": "向后翻页 (←)",
                "Single Page Flip": "单页翻页",
                "Next Page (D)": "下一页 (D)",
                "Previous Page (A)": "上一页 (A)",
                "Jump to Home (Space)": "返回主页 (空格)",
                "Set Current Page as Home (Ctrl+Space)": "将当前页设为主页 (Ctrl+空格)",

                # === 瞬时书签 ===
                "Instant Bookmarks": "瞬时书签",
                "Jump To": "跳转",
                "Set": "设置",
                "Clear": "清除",
                "Jump to 'Q' (Q)": "跳转到 'Q' (Q)",
                "Jump to 'W' (W)": "跳转到 'W' (W)",
                "Jump to 'E' (E)": "跳转到 'E' (E)",
                "Jump to 'R' (R)": "跳转到 'R' (R)",
                "Jump to 'T' (T)": "跳转到 'T' (T)",
                "Jump to 'Y' (Y)": "跳转到 'Y' (Y)",
                "Jump to 'U' (U)": "跳转到 'U' (U)",
                "Jump to 'I' (I)": "跳转到 'I' (I)",
                "Jump to 'O' (O)": "跳转到 'O' (O)",
                "Jump to 'P' (P)": "跳转到 'P' (P)",
                "Set 'Q' Here (Ctrl+Q)": "在此处设置 'Q' (Ctrl+Q)",
                "Set 'W' Here (Ctrl+W)": "在此处设置 'W' (Ctrl+W)",
                "Set 'E' Here (Ctrl+E)": "在此处设置 'E' (Ctrl+E)",
                "Set 'R' Here (Ctrl+R)": "在此处设置 'R' (Ctrl+R)",
                "Set 'T' Here (Ctrl+T)": "在此处设置 'T' (Ctrl+T)",
                "Set 'Y' Here (Ctrl+Y)": "在此处设置 'Y' (Ctrl+Y)",
                "Set 'U' Here (Ctrl+U)": "在此处设置 'U' (Ctrl+U)",
                "Set 'I' Here (Ctrl+I)": "在此处设置 'I' (Ctrl+I)",
                "Set 'O' Here (Ctrl+O)": "在此处设置 'O' (Ctrl+O)",
                "Set 'P' Here (Ctrl+P)": "在此处设置 'P' (Ctrl+P)",
                "Clear 'Q' (Alt+Q)": "清除 'Q' (Alt+Q)",
                "Clear 'W' (Alt+W)": "清除 'W' (Alt+W)",
                "Clear 'E' (Alt+E)": "清除 'E' (Alt+E)",
                "Clear 'R' (Alt+R)": "清除 'R' (Alt+R)",
                "Clear 'T' (Alt+T)": "清除 'T' (Alt+T)",
                "Clear 'Y' (Alt+Y)": "清除 'Y' (Alt+Y)",
                "Clear 'U' (Alt+U)": "清除 'U' (Alt+U)",
                "Clear 'I' (Alt+I)": "清除 'I' (Alt+I)",
                "Clear 'O' (Alt+O)": "清除 'O' (Alt+O)",
                "Clear 'P' (Alt+P)": "清除 'P' (Alt+P)",
                "Set Bookmark": "设置书签",
                "Name for '{char}' (P.{page}):": "'{char}' 的名称（第 {page} 页）：",
                "🔖 '{char}' → {display_name}": "🔖 '{char}' → {display_name}",
                "⏩ '{char}': {display_name}": "⏩ '{char}'：{display_name}",
                "⚠️ '{char}' not set": "⚠️ '{char}' 未设置",

                # === 批注菜单 ===
                "Annotations": "批注",
                "Pen Mode (B)": "画笔模式 (B)",
                "Highlight Mode (H)": "高亮模式 (H)",
                "Text Mode (V)": "文本模式 (V)",
                "Finish or Exit Current Annotation (Esc)": "完成或退出当前批注 (Esc)",
                "Confirm Text Annotation (Ctrl+Enter)": "确认文字批注 (Ctrl+Enter)",
                "Pen Color": "画笔颜色",
                "Highlight Color": "高亮颜色",
                "Text Color": "文字颜色",
                "Pen Color 1": "画笔颜色 1",
                "Pen Color 2": "画笔颜色 2",
                "Pen Color 3": "画笔颜色 3",
                "Pen Color 4": "画笔颜色 4",
                "Pen Color 5": "画笔颜色 5",
                "Pen Color 6": "画笔颜色 6",
                "Pen Color 7": "画笔颜色 7",
                "Pen Color 8": "画笔颜色 8",
                "Pen Color 9": "画笔颜色 9",
                "Pen Color 10": "画笔颜色 10",
                "Highlight Color 1": "高亮颜色 1",
                "Highlight Color 2": "高亮颜色 2",
                "Highlight Color 3": "高亮颜色 3",
                "Highlight Color 4": "高亮颜色 4",
                "Highlight Color 5": "高亮颜色 5",
                "Highlight Color 6": "高亮颜色 6",
                "Highlight Color 7": "高亮颜色 7",
                "Highlight Color 8": "高亮颜色 8",
                "Text Color 1": "文字颜色 1",
                "Text Color 2": "文字颜色 2",
                "Text Color 3": "文字颜色 3",
                "Text Color 4": "文字颜色 4",
                "Text Color 5": "文字颜色 5",
                "Text Color 6": "文字颜色 6",
                "Text Color 7": "文字颜色 7",
                "Text Color 8": "文字颜色 8",
                "Undo Last Annotation (Ctrl+Z)": "撤销上一条批注 (Ctrl+Z)",
                "Clear Current Page Annotations (Ctrl+Shift+C)": "清除当前页所有批注 (Ctrl+Shift+C)",
                "Global Reset (Ctrl+Shift+R)": "全局重置 (Ctrl+Shift+R)",
                "✏️ Pen mode (press ESC to cancel)": "✏️ 画笔模式（按 ESC 取消）",
                "🔲 Highlight mode (press ESC to cancel)": "🔲 高亮模式（按 ESC 取消）",
                "📝 Text mode (press ESC to cancel)": "📝 文本模式（按 ESC 取消）",
                "🗑️ Cleared annotations on page {page}": "🗑️ 已清除第 {page} 页批注",
                "↩️ Undo last annotation on page {page}": "↩️ 已撤销第 {page} 页最后一条批注",
                "ℹ️ No annotations to undo on page {page}": "ℹ️ 第 {page} 页无可撤销批注",

                # === 工具菜单 ===
                "Tools": "工具",
                "Toggle Text Selection Mode (J)": "进入或退出文字选取模式 (J)",
                "Copy Selected Text (Ctrl+C)": "复制选中文本 (Ctrl+C)",
                "Copy": "复制",
                "Copied to clipboard": "已复制到剪贴板",

                # === 帮助菜单 ===
                "Help": "帮助",
                "TactiReader Help": "战术阅读器 帮助",
                "About TactiReader": "关于 战术阅读器",
                "About": "关于",
                "Language": "语言",
                "English": "English",
                "简体中文": "简体中文",
                "Language Changed": "语言已更改",
                "Please restart TactiReader to apply the new language.": "请重启 TactiReader 以应用新语言。",

                # === 通用 UI / 消息 ===
                "TactiReader": "战术阅读器",
                "Document Outline": "文档目录",
                "Search Highlight": "搜索高亮",
                "Focus: Left": "焦点：左窗格",
                "Focus: Right": "焦点：右窗格",
                "Focus: None": "焦点：无",
                "Single": "单页",
                "Double": "双页",
                "None": "无",
                "↔️ Mode: {mode}-page": "↔️ 模式：{mode}页",
                "⬅️ Left pane: Locked": "⬅️ 左面板：已锁定",
                "⬅️ Left pane: Following": "⬅️ 左面板：跟随",
                "🔁 Flip ×{x}": "🔁 翻页倍数 ×{x}",
                "🔄 Home reset to P.{page}": "🔄 主页重置为第 {page} 页",
                "🔄 Current pages reset (zoom+pan+rotation) & splitter centered": "🔄 当前页面重置（缩放+平移+旋转）且分隔条居中",
                "🔄 Left rotated to {angle}°": "🔄 左页旋转至 {angle}°",
                "🔄 Right rotated to {angle}°": "🔄 右页旋转至 {angle}°",
                "🗑️ All page rotations cleared for entire book!": "🗑️ 已清除整本书所有页面的旋转！",
                "💾 Configuration saved": "💾 配置已保存",
                "🗑️ All configuration cleared!": "🗑️ 所有配置已清除！",
                "<no bookmarks>": "<无书签>",

                # === 搜索对话框 ===
                "Search:": "搜索：",
                "Search": "搜索",
                "Enter search term...": "输入搜索内容...",
                "Found {count} result(s)": "找到 {count} 个结果",
                "No results": "无结果",
                "◀ Previous": "◀ 上一个",
                "Next ▶": "下一个 ▶",
                "Close": "关闭",
                "🔍 {context}": "🔍 {context}",

                # === 弹窗确认 ===
                "Clear All Config": "清除全部配置",
                "Are you sure you want to clear ALL settings (bookmarks, home, mode, etc.) for this PDF?": "确定要清除本 PDF 的所有设置（书签、主页、模式等）吗？",
                "Error": "错误",
                "OK": "确认",
                "Cancel": "取消",

                # === 笔记导入/导出消息 ===
                "No document is open.": "未打开任何文档。",
                "Failed to locate config file.": "无法定位配置文件。",
                "Notebook exported to: {}": "笔记已导出至：{}",
                "Failed to export notebook": "笔记导出失败",
                "Notebook imported from: {}": "笔记已从 {} 导入",
                "Failed to import notebook": "笔记导入失败",
                "Notebook saved.": "笔记已保存。",
                            # === 多文档功能 ===
                "Open in New Window": "在新窗口中打开",
            # =================
            }
        }
        
        # 尝试从全局配置文件加载语言
        if os.path.exists(GLOBAL_CONFIG_FILE):
            try:
                with open(GLOBAL_CONFIG_FILE, 'r') as f:
                    global_data = json.load(f)
                    global_config = global_data.get("global_config", {})
                    lang_from_global_config = global_config.get("language", "en")
                    if lang_from_global_config in self.translations:
                        self.current_lang = lang_from_global_config
            except Exception as e:
                print(f"Failed to load language from global config: {e}")
         
        # === NEW CODE START ===
        # 初始化最近文件列表
        self.recent_files = []
        if os.path.exists(GLOBAL_CONFIG_FILE):
            try:
                with open(GLOBAL_CONFIG_FILE, 'r') as f:
                    global_data = json.load(f)
                    global_config = global_data.get("global_config", {})
                    # 加载最近文件（过滤掉不存在的）
                    loaded_recent = global_config.get("recent_files", [])
                    self.recent_files = [f for f in loaded_recent if os.path.isfile(f)]
            except Exception as e:
                print(f"Failed to load recent files: {e}")
        # === 初始化全局打开文档列表 ===
        self.open_documents = []
        if os.path.exists(GLOBAL_CONFIG_FILE):
            try:
                with open(GLOBAL_CONFIG_FILE, 'r') as f:
                    global_data = json.load(f)
                    global_config = global_data.get("global_config", {})
                    # 加载已打开文档（过滤掉不存在的）
                    loaded_open_docs = global_config.get("open_documents", [])
                    self.open_documents = [f for f in loaded_open_docs if os.path.isfile(f) and (f.lower().endswith('.pdf') or f.lower().endswith('.tactinote'))]
            except Exception as e:
                print(f"Failed to load open documents: {e}")
        # ==============================                
        # === NEW CODE END ===

        # 2. 初始化核心变量
        self.pdf_path = None
        # === 新增：笔记本模式状态 ===
        self.notebook_source_path = None  # 记录源 .tactinote 文件路径
        # ==========================        
        self.doc = None
        self.total_pages = 0
        self.last_focused_pane = 'right'  # 可选值: 'left' 或 'right'
        # Auto-show help on first run (if no bookmarks/config exist)
        if not os.listdir(CONFIG_DIR) and not (pdf_path or self.recent_files):
            # 弹出独立的语言选择对话框
            lang_dlg = LanguageSelectDialog(self)
            lang_dlg.exec_()
            chosen_lang = lang_dlg.selected_lang

            # 立即设置并保存语言（不调用 set_language）
            self.current_lang = chosen_lang
            os.makedirs(os.path.dirname(GLOBAL_CONFIG_FILE), exist_ok=True)
            with open(GLOBAL_CONFIG_FILE, 'w') as f:
                json.dump({"global_config": {"language": chosen_lang}}, f, indent=2)

            # 再弹帮助
            QTimer.singleShot(300, self.show_help)
        # === NEW CODE END ===               
        # 3. 现在可以安全地创建UI元素，它们会使用正确的语言
        self.setWindowTitle(self.tr("TactiReader"))
        self.setWindowIcon(QIcon(resource_path("tactireader.png")))
        self.setGeometry(100, 100, 1200, 800)
        self.setFocusPolicy(Qt.StrongFocus)

        central = QWidget()
        self.setCentralWidget(central)

        # === 替换开始：使用 QSplitter 实现可拖动分隔 ===
        from PyQt5.QtWidgets import QSplitter

        # 创建主水平布局: [Bookmark Panel] | [Splitter(Left|Right)]
        main_layout = QHBoxLayout(central)
        main_layout.setSpacing(5)

        # Bookmark panel (保持不变)
        self.bookmark_panel = QWidget()
        self.bookmark_panel.setFixedWidth(180)
        
        self.bookmark_layout = QVBoxLayout(self.bookmark_panel)
        self.bookmark_layout.setAlignment(Qt.AlignTop)
        self.bookmark_layout.setSpacing(4)
        self.bookmark_layout.setContentsMargins(6, 6, 6, 6)
        main_layout.addWidget(self.bookmark_panel)
        self.bookmark_panel_visible = True
        # 创建左右窗格
        self.left_pane = TacticalPane(self)
        self.left_pane.is_left_pane = True  # ← 关键：标记为左窗格
        self.right_pane = TacticalPane(self)
        self.right_pane.is_left_pane = False  # ← 关键：标记为右窗格
        # === 新增：连接焦点信号 ===
        self.left_pane.focused.connect(self._on_reading_pane_focused)
        self.right_pane.focused.connect(self._on_reading_pane_focused)

        # 创建 splitter 并添加窗格
        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.addWidget(self.left_pane)
        self.splitter.addWidget(self.right_pane)
        self.splitter.setHandleWidth(6)  # 分隔条宽度
        self.splitter.setSizes([500, 500])

        # === 创建紧凑标签栏（默认隐藏）===
        self.doc_tab_bar = QTabBar()
        self.doc_tab_bar.setMovable(True)
        self.doc_tab_bar.setTabsClosable(True)
        self.doc_tab_bar.setFixedHeight(28)  # ← 关键：紧凑高度
        self.doc_tab_bar.tabCloseRequested.connect(self.close_document_tab)
        self.doc_tab_bar.currentChanged.connect(self.on_doc_tab_changed)
        self.doc_tab_bar.setContextMenuPolicy(Qt.CustomContextMenu)
        self.doc_tab_bar.customContextMenuRequested.connect(self.show_tab_context_menu)
        self.doc_tab_bar.hide()  # 默认隐藏
        # === UI 风格统一 ===
        # 字体：中文微软雅黑 + 英文等宽粗体
        tab_font = QFont()
        tab_font.setFamily("Microsoft YaHei, Consolas, Courier New, monospace")
        tab_font.setPointSize(9)
        tab_font.setBold(True)  # 粗体增强可读性
        self.doc_tab_bar.setFont(tab_font)
        
        # 样式表：匹配主窗口风格
        self.doc_tab_bar.setStyleSheet("""
            QTabBar {
                background-color: #f8f8f8;
                border-bottom: 1px solid #e0e0e0;
            }
            QTabBar::tab {
                background: #f8f8f8;
                color: #111111;
                padding: 4px 12px;
                margin: 0px;
                border: 1px solid #d0d0d0;
                border-bottom: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                min-width: 60px;
                height: 22px;
            }
            QTabBar::tab:selected {
                background: #e6f0ff;  /* VS Code 风格蓝色高亮 */
                color: #0066cc;
                font-weight: bold;
                border: 1px solid #a0c0ff;
                border-bottom: none;
            }
            QTabBar::tab:hover {
                background: #f0f8ff;
                color: #0066cc;
            }
            QTabBar::close-button {
                image: url(close.png);  /* 可选：自定义关闭图标 */
                subcontrol-position: right;
            }
            QTabBar::close-button:hover {
                background: #ffcccc;
                border-radius: 4px;
            }
        """)
        # ===================
        # 创建中央区域
        central_widget = QWidget()
        central_layout = QVBoxLayout(central_widget)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.addWidget(self.doc_tab_bar)
        central_layout.addWidget(self.splitter)
        main_layout.addWidget(central_widget)
        # ===========================
        # === 替换结束 ===
        # State
        self.single_page_mode = False
        self.right_page = 1
        self.home_page = 1
        self.annotation_mode = None        
        self.bookmarks = {}
        self.pdf_toc = []  # 存储 [(level, title, page), ...]
        self.toc_expanded = True  # 控制是否展开
        self.flip_multiplier = 1
        self.config_file = None
        self.left_locked = False
        self.locked_left_page = 1
        
        # 旋转状态
        self.page_rotations = {}  # 格式: {page_num: rotation_angle}
        self.page_number_offset = 0  # ← 新增：页码数字偏移（逻辑页 = 物理页 + offset）
        
        # 批注存储
        self.annotations = {}  # 格式: {page_num: [annotations]}
        
        # 搜索高亮相关
        self.search_highlights = {}  # {page_num: [{'rect': QRectF, 'color': QColor}, ...]}
        self.current_search_term = ""
        self.search_highlight_color = QColor(255, 255, 0, 60)  # 半透明黄色
        # === 历史栈：左右窗格独立，最多5步 ===
        # === 单步历史：左右窗格独立，仅保留最近一次跨页跳转前的位置 ===
        self.left_last_location = None   # (page_num, rotation, scale, offset) 或 None
        self.right_last_location = None  # 同上
        # ==================================================================
        # ===================================        
        # 颜色设置 - 每个功能独立
        self.pen_colors = [
            QColor(255, 0, 0),     # 红色
            QColor(0, 0, 255),     # 蓝色
            QColor(0, 255, 0),     # 绿色
            QColor(255, 255, 0),   # 黄色
            QColor(255, 0, 255),   # 紫色
            QColor(0, 255, 255),   # 青色
            QColor(255, 128, 0),   # 橙色
            QColor(128, 0, 255),   # 紫色
            QColor(255, 0, 128),   # 粉色
            QColor(0, 0, 0),       # 黑色
        ]
        
        self.rect_colors = [
            QColor(255, 255, 0, 128),  # 半透明黄色
            QColor(255, 200, 200, 128),  # 半透明浅红
            QColor(200, 255, 200, 128),  # 半透明浅绿
            QColor(200, 200, 255, 128),  # 半透明浅蓝
            QColor(255, 255, 200, 128),  # 半透明浅黄
            QColor(255, 200, 255, 128),  # 半透明浅紫
            QColor(200, 255, 255, 128),  # 半透明浅青
            QColor(255, 220, 180, 128),  # 半透明浅橙
        ]
        
        self.text_colors = [
            QColor(0, 0, 0),       # 黑色
            QColor(255, 0, 0),     # 红色
            QColor(0, 0, 255),     # 蓝色
            QColor(0, 100, 0),     # 深绿色
            QColor(128, 0, 128),   # 紫色
            QColor(139, 69, 19),   # 棕色
        ]
        
        # 当前颜色索引
        self.current_pen_color_index = 0
        self.current_rect_color_index = 0
        self.current_text_color_index = 0

        # === 全新菜单栏：TactiReader v2.0 防呆版 ===
        menubar = self.menuBar()
        # === 强制菜单栏为 VS Code 风格浅灰（不随系统变色）===
        menubar.setStyleSheet("""
            QMenuBar {
                background-color: #f8f8f8;
                color: #111111;
                border: none;
                padding: 2px;
                font-family: "Microsoft YaHei", "Consolas", sans-serif;
                font-size: 10pt;
                font-weight:450;
            }
            QMenuBar::item {
                background: transparent;
                padding: 4px 12px;
                border-radius: 4px;
            }
            QMenuBar::item:selected {
                background: rgba(0, 0, 0, 0.1);
            }
            QMenuBar::item:pressed {
                background: rgba(0, 0, 0, 0.2);
            }
            /* 子菜单样式 */
            QMenu {
                background-color: #fffffe;
                color: #111111;
                border: 1px solid #d0d0d0;
                font-weight:450;
            }
            QMenu::item {
                padding: 6px 24px;
            }
            QMenu::item:selected {
                background-color: #e6f0ff;
            }
        """)
        # ===================================================
        # --- 文件 (File) ---
        file_menu = menubar.addMenu(self.tr("File"))
        open_action = QAction(self.tr("Open PDF..."), self)
        open_action.triggered.connect(self.open_pdf_dialog)
        file_menu.addAction(open_action)
        
        save_as_pdf_action = QAction(self.tr("Save As PDF..."), self)
        save_as_pdf_action.triggered.connect(self.save_as_pdf)
        file_menu.addAction(save_as_pdf_action)
        
        file_menu.addSeparator()
        
        export_notebook_action = QAction(self.tr("Export Notebook..."), self)
        export_notebook_action.triggered.connect(self.export_notebook)
        file_menu.addAction(export_notebook_action)
        
        import_notebook_action = QAction(self.tr("Open Notebook..."), self)
        import_notebook_action.triggered.connect(self.import_notebook)
        file_menu.addAction(import_notebook_action)
        
        file_menu.addSeparator()
        
        # 最近文件子菜单 (复用已有逻辑)
        self.recent_menu = file_menu.addMenu(self.tr("Recent Files"))
        self.update_recent_files_menu()
        
        file_menu.addSeparator()
        
        # 保存配置 (S)
        save_config_action = QAction(self.tr("Save Configuration (S)"), self)
        save_config_action.triggered.connect(lambda: self._trigger_shortcut(Qt.Key_S))
        file_menu.addAction(save_config_action)
        
        # --- 视图 (View) ---
        view_menu = menubar.addMenu(self.tr("View"))
        # 切换单/双页模式 (Z)
        toggle_mode_action = QAction(self.tr("Toggle Single/Double Page Mode (Z)"), self)
        toggle_mode_action.triggered.connect(lambda: self._trigger_shortcut(Qt.Key_Z))
        view_menu.addAction(toggle_mode_action)
        
        # 切换左窗格锁定/跟随 (C)
        toggle_lock_action = QAction(self.tr("Toggle Left Pane Lock/Follow (C)"), self)
        toggle_lock_action.triggered.connect(lambda: self._trigger_shortcut(Qt.Key_C))
        view_menu.addAction(toggle_lock_action)
        
        view_menu.addSeparator()
        
        # 显示/隐藏书签与目录面板 (N)
        toggle_sidebar_action = QAction(self.tr("Show/Hide Bookmarks & TOC Panel (N)"), self)
        toggle_sidebar_action.triggered.connect(lambda: self._trigger_shortcut(Qt.Key_N))
        view_menu.addAction(toggle_sidebar_action)
        
        # 全屏/退出全屏 (F11)
        toggle_fullscreen_action = QAction(self.tr("Toggle Fullscreen (F11)"), self)
        toggle_fullscreen_action.triggered.connect(lambda: self._trigger_shortcut(Qt.Key_F11))
        view_menu.addAction(toggle_fullscreen_action)
        
        view_menu.addSeparator()
        
        # 顺时针旋转当前页 (`)
        rotate_clockwise_action = QAction(self.tr("Rotate Current Page Clockwise (~)"), self)
        rotate_clockwise_action.triggered.connect(lambda: self._trigger_shortcut(Qt.Key_QuoteLeft))
        view_menu.addAction(rotate_clockwise_action)
        
        # 重置当前页面 (X)
        reset_current_action = QAction(self.tr("Reset Current Page (X)"), self)
        reset_current_action.triggered.connect(lambda: self._trigger_shortcut(Qt.Key_X))
        view_menu.addAction(reset_current_action)
        
        # 居中分隔条并重置 (Ctrl+X)
        reset_both_action = QAction(self.tr("Center Splitter and Reset (Ctrl+X)"), self)
        reset_both_action.triggered.connect(lambda: self._trigger_shortcut(Qt.Key_X, Qt.ControlModifier))
        view_menu.addAction(reset_both_action)
        
        # 清除全文档旋转 (Ctrl+Shift+X)
        clear_all_rotations_action = QAction(self.tr("Clear All Page Rotations (Ctrl+Shift+X)"), self)
        clear_all_rotations_action.triggered.connect(lambda: self._trigger_shortcut(Qt.Key_X, Qt.ControlModifier | Qt.ShiftModifier))
        view_menu.addAction(clear_all_rotations_action)
        
        # --- 导航 (Navigation) ---
        nav_menu = menubar.addMenu(self.tr("Navigation"))
        # 跳转到页码... (G)
        goto_page_action = QAction(self.tr("Go to Page... (G)"), self)
        goto_page_action.triggered.connect(lambda: self._trigger_shortcut(Qt.Key_G))
        nav_menu.addAction(goto_page_action)
        
        # 标定物理页码... (Ctrl+G)
        calibrate_page_action = QAction(self.tr("Calibrate Physical Page Number... (Ctrl+G)"), self)
        calibrate_page_action.triggered.connect(lambda: self._trigger_shortcut(Qt.Key_G, Qt.ControlModifier))
        nav_menu.addAction(calibrate_page_action)
        
        # 清除物理页码偏移 (Ctrl+Shift+G)
        clear_page_offset_action = QAction(self.tr("Clear Physical Page Offset (Ctrl+Shift+G)"), self)
        clear_page_offset_action.triggered.connect(lambda: self._trigger_shortcut(Qt.Key_G, Qt.ControlModifier | Qt.ShiftModifier))
        nav_menu.addAction(clear_page_offset_action)
        
        # 全文搜索... (F)
        search_action = QAction(self.tr("Full-Text Search... (F)"), self)
        search_action.triggered.connect(lambda: self._trigger_shortcut(Qt.Key_F))
        nav_menu.addAction(search_action)
        
        # 导航回退 (Ctrl+A)
        navigate_back_action = QAction(self.tr("Navigation Back (Ctrl+A)"), self)
        navigate_back_action.triggered.connect(lambda: self._trigger_shortcut(Qt.Key_A, Qt.ControlModifier))
        nav_menu.addAction(navigate_back_action)
        
        nav_menu.addSeparator()
        
        # 设置翻页倍数
        multiplier_menu = nav_menu.addMenu(self.tr("Set Flip Multiplier"))
        for i in range(1, 10):
            action = QAction(self.tr(f"×{i} ({i})"), self)
            action.triggered.connect(lambda checked, num=i: self._trigger_shortcut(getattr(Qt, f'Key_{num}')))
            multiplier_menu.addAction(action)
        
        nav_menu.addSeparator()
        
        # 按倍数翻页
        flip_by_multiplier_menu = nav_menu.addMenu(self.tr("Flip by Multiplier"))
        next_by_mult_action = QAction(self.tr("Next Pages (→)"), self)
        next_by_mult_action.triggered.connect(lambda: self._trigger_shortcut(Qt.Key_Right))
        flip_by_multiplier_menu.addAction(next_by_mult_action)
        prev_by_mult_action = QAction(self.tr("Previous Pages (←)"), self)
        prev_by_mult_action.triggered.connect(lambda: self._trigger_shortcut(Qt.Key_Left))
        flip_by_multiplier_menu.addAction(prev_by_mult_action)
        
        # 单页翻页
        single_flip_menu = nav_menu.addMenu(self.tr("Single Page Flip"))
        next_page_action = QAction(self.tr("Next Page (D)"), self)
        next_page_action.triggered.connect(lambda: self._trigger_shortcut(Qt.Key_D))
        single_flip_menu.addAction(next_page_action)
        prev_page_action = QAction(self.tr("Previous Page (A)"), self)
        prev_page_action.triggered.connect(lambda: self._trigger_shortcut(Qt.Key_A))
        single_flip_menu.addAction(prev_page_action)
        
        nav_menu.addSeparator()
        
        # 返回主页 (空格)
        jump_to_home_action = QAction(self.tr("Jump to Home (Space)"), self)
        jump_to_home_action.triggered.connect(lambda: self._trigger_shortcut(Qt.Key_Space))
        nav_menu.addAction(jump_to_home_action)
        
        # 将当前页设为主页 (Ctrl+空格)
        set_home_action = QAction(self.tr("Set Current Page as Home (Ctrl+Space)"), self)
        set_home_action.triggered.connect(lambda: self._trigger_shortcut(Qt.Key_Space, Qt.ControlModifier))
        nav_menu.addAction(set_home_action)
        
        nav_menu.addSeparator()
        
        # 瞬时书签
        bookmark_menu = nav_menu.addMenu(self.tr("Instant Bookmarks"))
        # 跳转
        jump_sub_menu = bookmark_menu.addMenu(self.tr("Jump To"))
        for key_char in ['Q', 'W', 'E', 'R', 'T', 'Y', 'U', 'I', 'O', 'P']:
            qt_key = getattr(Qt, f'Key_{key_char}')
            action = QAction(self.tr(f"Jump to '{key_char}' ({key_char})"), self)
            action.triggered.connect(lambda checked, k=qt_key: self._trigger_shortcut(k))
            jump_sub_menu.addAction(action)
        # 设置
        set_sub_menu = bookmark_menu.addMenu(self.tr("Set"))
        for key_char in ['Q', 'W', 'E', 'R', 'T', 'Y', 'U', 'I', 'O', 'P']:
            qt_key = getattr(Qt, f'Key_{key_char}')
            action = QAction(self.tr(f"Set '{key_char}' Here (Ctrl+{key_char})"), self)
            action.triggered.connect(lambda checked, k=qt_key: self._trigger_shortcut(k, Qt.ControlModifier))
            set_sub_menu.addAction(action)
        # 清除
        clear_sub_menu = bookmark_menu.addMenu(self.tr("Clear"))
        for key_char in ['Q', 'W', 'E', 'R', 'T', 'Y', 'U', 'I', 'O', 'P']:
            qt_key = getattr(Qt, f'Key_{key_char}')
            action = QAction(self.tr(f"Clear '{key_char}' (Alt+{key_char})"), self)
            action.triggered.connect(lambda checked, k=qt_key: self._trigger_shortcut(k, Qt.AltModifier))
            clear_sub_menu.addAction(action)
        
        # --- 批注 (Annotation) ---
        annot_menu = menubar.addMenu(self.tr("Annotations"))
        # 画笔模式 (B)
        pen_action = QAction(self.tr("Pen Mode (B)"), self)
        pen_action.triggered.connect(lambda: self._trigger_shortcut(Qt.Key_B))
        annot_menu.addAction(pen_action)
        # 高亮模式 (H)
        highlight_action = QAction(self.tr("Highlight Mode (H)"), self)
        highlight_action.triggered.connect(lambda: self._trigger_shortcut(Qt.Key_H))
        annot_menu.addAction(highlight_action)
        # 文本模式 (V)
        text_action = QAction(self.tr("Text Mode (V)"), self)
        text_action.triggered.connect(lambda: self._trigger_shortcut(Qt.Key_V))
        annot_menu.addAction(text_action)
        # 完成或退出当前批注 (Esc)
        esc_action = QAction(self.tr("Finish or Exit Current Annotation (Esc)"), self)
        esc_action.triggered.connect(lambda: self._trigger_shortcut(Qt.Key_Escape))
        annot_menu.addAction(esc_action)
        # 确认文字批注 (Ctrl+Enter)
        confirm_text_action = QAction(self.tr("Confirm Text Annotation (Ctrl+Enter)"), self)
        confirm_text_action.triggered.connect(lambda: self._trigger_shortcut(Qt.Key_Return, Qt.ControlModifier))
        annot_menu.addAction(confirm_text_action)
        
        annot_menu.addSeparator()
        
        # 颜色选择 (复用你原有的逻辑)
        pen_color_menu = annot_menu.addMenu(self.tr("Pen Color"))
        for i, color in enumerate(self.pen_colors):
            color_action = QAction(self.tr(f"Pen Color {i+1}"), self)
            color_action.triggered.connect(lambda checked, idx=i: self.set_pen_color_index(idx))
            pixmap = QPixmap(16, 16)
            pixmap.fill(color)
            color_action.setIcon(QIcon(pixmap))
            pen_color_menu.addAction(color_action)
            
        rect_color_menu = annot_menu.addMenu(self.tr("Highlight Color"))
        for i, color in enumerate(self.rect_colors):
            color_action = QAction(self.tr(f"Highlight Color {i+1}"), self)
            color_action.triggered.connect(lambda checked, idx=i: self.set_rect_color_index(idx))
            pixmap = QPixmap(16, 16)
            pixmap.fill(color)
            color_action.setIcon(QIcon(pixmap))
            rect_color_menu.addAction(color_action)
            
        text_color_menu = annot_menu.addMenu(self.tr("Text Color"))
        for i, color in enumerate(self.text_colors):
            color_action = QAction(self.tr(f"Text Color {i+1}"), self)
            color_action.triggered.connect(lambda checked, idx=i: self.set_text_color_index(idx))
            pixmap = QPixmap(16, 16)
            pixmap.fill(color)
            color_action.setIcon(QIcon(pixmap))
            text_color_menu.addAction(color_action)
        
        annot_menu.addSeparator()
        
        # 撤销上一条批注 (Ctrl+Z)
        undo_action = QAction(self.tr("Undo Last Annotation (Ctrl+Z)"), self)
        undo_action.triggered.connect(lambda: self._trigger_shortcut(Qt.Key_Z, Qt.ControlModifier))
        annot_menu.addAction(undo_action)
        # 清除当前页所有批注 (Ctrl+Shift+C)
        clear_current_annot_action = QAction(self.tr("Clear Current Page Annotations (Ctrl+Shift+C)"), self)
        clear_current_annot_action.triggered.connect(lambda: self._trigger_shortcut(Qt.Key_C, Qt.ControlModifier | Qt.ShiftModifier))
        annot_menu.addAction(clear_current_annot_action)
        # 全局重置 (Ctrl+Shift+R)
        global_reset_action = QAction(self.tr("Global Reset (Ctrl+Shift+R)"), self)
        global_reset_action.triggered.connect(lambda: self._trigger_shortcut(Qt.Key_R, Qt.ControlModifier | Qt.ShiftModifier))
        annot_menu.addAction(global_reset_action)
        
        # --- 工具 (Tools) ---
        tools_menu = menubar.addMenu(self.tr("Tools"))
        # 进入或退出文字选取模式 (J)
        toggle_text_select_action = QAction(self.tr("Toggle Text Selection Mode (J)"), self)
        toggle_text_select_action.triggered.connect(self.toggle_text_selection_mode)
        tools_menu.addAction(toggle_text_select_action)

        
        # --- 帮助 (Help) ---
        help_menu = menubar.addMenu(self.tr("Help"))
        help_action = QAction(self.tr("TactiReader Help"), self)
        help_action.triggered.connect(self.show_help)
        help_menu.addAction(help_action)
        about_action = QAction(self.tr("About TactiReader"), self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
        
        help_menu.addSeparator()
        
        # --- 语言 (Language) - 独立顶级菜单 ---
        lang_menu = menubar.addMenu(self.tr("Language"))
        en_action = QAction(self.tr("English"), self)
        zh_action = QAction(self.tr("简体中文"), self)
        en_action.triggered.connect(lambda: self.set_language("en"))
        zh_action.triggered.connect(lambda: self.set_language("zh"))
        lang_menu.addAction(en_action)
        lang_menu.addAction(zh_action)
        
        # 状态栏颜色显示
        self.color_status_label = QLabel()
        # 设置状态栏字体
        status_font = QFont()
        status_font.setFamily("Microsoft YaHei, Consolas, Courier New, monospace")
        status_font.setPointSize(9)
        self.color_status_label.setFont(status_font)

        # ✅ 关键：单独设置 QSS 加粗（更可靠）
        self.color_status_label.setStyleSheet("font-weight: 500; color: #000000;")
        # 设置状态栏字体
        status_font = QFont()
        status_font.setFamily("Microsoft YaHei, Consolas, Courier New, monospace")
        status_font.setPointSize(9)
        self.color_status_label.setFont(status_font)
        self.statusBar().addPermanentWidget(self.color_status_label)
        self.statusBar().setStyleSheet("""
        QStatusBar {
            background-color: #f8f8f8;
            color: #111111;
            border-top: 1px solid #e0e0e0;
            font-weight:480;
        }
    """)
        self.update_color_display()
        
        
        # 搜索对话框
        self.search_dialog = None
        
        self.setAcceptDrops(True)
        self.addAction(QAction(self.tr("Search in PDF"), self, shortcut="F", triggered=self.search_text))
        # === 新增：全局 J 键 ===
        self.addAction(QAction(self.tr("Toggle Text Selection Mode"), self, shortcut="J", triggered=self.toggle_text_selection_mode))        
        # === F11 全屏支持 ===
        self.addAction(QAction(self.tr("Toggle Fullscreen"), self, shortcut="F11", triggered=self.toggle_fullscreen))
        # ===================        
        # === 新增：记录最后获得焦点的阅读窗格 ===
        self.last_focused_pane_is_left = False  # 默认右窗格
        # === NEW CODE START ===
        # === NEW CODE START ===
        # Auto-open: CLI path first, then all saved open documents
        if pdf_path and os.path.isfile(pdf_path):
            # 命令行参数优先
            if pdf_path.lower().endswith('.tactinote'):
                self.import_notebook_from_path(pdf_path)
                self.update_ui_text()  # ← 新增：更新标题
            elif pdf_path.lower().endswith('.pdf'):
                self.load_pdf(pdf_path)
                self.update_ui_text()  # ← 新增：更新标题
        elif self.open_documents:
            # 恢复所有已保存的文档标签
            for i, doc_path in enumerate(self.open_documents):
                if os.path.isfile(doc_path):
                    if i == 0:  # 加载第一个文档
                        if doc_path.lower().endswith('.tactinote'):
                            self.import_notebook_from_path(doc_path)
                            self.update_ui_text()  # ← 新增：更新标题
                        elif doc_path.lower().endswith('.pdf'):
                            self.load_pdf(doc_path)
                            self.update_ui_text()  # ← 新增：更新标题
                    # 其他文档已在 open_documents 中，无需额外处理
        # === NEW CODE END ===

    def import_notebook_from_path(self, notebook_path):
        """从给定路径导入笔记本，不弹出文件对话框"""
        if not os.path.isfile(notebook_path):
            return
        # === 关键：将 .tactinote 路径加入 open_documents ===
        abs_notebook_path = os.path.abspath(notebook_path)
        if abs_notebook_path not in self.open_documents:
            self.open_documents.append(abs_notebook_path)
            self.save_global_config()
        # =============================================
        try:

            
            # 1. 为这个 .tactinote 创建一个唯一的临时工作目录
            hash_id = hashlib.md5(notebook_path.encode('utf-8')).hexdigest()[:12]
            temp_base_dir = os.path.join(CONFIG_DIR, "..", "temp")
            os.makedirs(temp_base_dir, exist_ok=True)
            work_dir = os.path.join(temp_base_dir, f"nb_{hash_id}")
            os.makedirs(work_dir, exist_ok=True)
            
            pdf_path = os.path.join(work_dir, "document.pdf")
            session_json_path = os.path.join(work_dir, "session.json")
            
            # 2. 解压 .tactinote
            with zipfile.ZipFile(notebook_path, 'r') as zf:
                zf.extract("document.pdf", work_dir)
                zf.extract("session.json", work_dir)

            # 3. 正常加载 PDF
            if self.doc:
                self.doc.close()
            self.doc = fitz.open(pdf_path)
            self.pdf_path = notebook_path  # 保持原始 .tactinote 路径
            self.notebook_source_path = notebook_path  # 标记笔记本模式
            self.total_pages = len(self.doc)

            # 4. 进入笔记本模式
            self.config_file = session_json_path
            self.notebook_source_path = notebook_path

            # 5. 加载配置、TOC等
            self.load_config()
            self.load_pdf_toc()
            self.refresh_bookmark_panel()
            self.render_facing()
            self.right_pane.setFocus()
            self.update_status()
            self.update_ui_text()

            self.statusBar().showMessage(
                self.tr("Notebook imported from: {}").format(os.path.basename(notebook_path)), 3000
            )
            # === 新增：将 .tactinote 文件加入最近文件列表 ===
            self.add_to_recent_files(notebook_path)
            # ===========================================
        except Exception as e:
            QMessageBox.critical(self, self.tr("Error"), f"{self.tr('Failed to import notebook')}: {e}")
                # === 关键修复：刷新标签栏 ===
        self.update_document_tabs()
            # =========================
    def load_pdf_toc(self):
        """加载 PDF 内置书签（目录）并构建扁平列表"""
        if not self.doc:
            self.pdf_toc = []
            return
        try:
            raw_toc = self.doc.get_toc()
            # 过滤无效页码，保留 (level, title, page) 元组
            self.pdf_toc = [
                (lvl, title, max(1, min(int(page), self.total_pages)))
                for lvl, title, page in raw_toc
                if isinstance(page, (int, float)) and page > 0
            ]
        except Exception as e:
            print(f"Failed to load TOC: {e}")
            self.pdf_toc = []
    
    def create_toc_widget(self):
        """创建基于 QTreeWidget 的 TOC 面板（仅首次调用）"""
        if hasattr(self, '_toc_container'):
            return
        
        # 创建容器
        self._toc_container = QWidget()
        toc_layout = QVBoxLayout(self._toc_container)
        toc_layout.setContentsMargins(0, 0, 0, 0)
        toc_layout.setSpacing(2)
        # 标题按钮（可折叠整个TOC面板）
        toggle_btn = QPushButton("📄 " + self.tr("Document Outline"))
        # 设置字体：微软雅黑 + 等宽英文
        font = QFont()
        font.setFamily("Microsoft YaHei, Consolas, Courier New, monospace")
        font.setPointSize(9)
        toggle_btn.setFont(font)
        toggle_btn.setCheckable(True)
        toggle_btn.setChecked(self.toc_expanded)
        toggle_btn.setStyleSheet("""
            text-align: left;
            padding: 4px;
            font-weight: bold;
            border: none;
            background: transparent;
        """)
        toggle_btn.toggled.connect(self.toggle_toc)
        toc_layout.addWidget(toggle_btn)
        
        # === 核心：使用 QTreeWidget ===
        self._toc_tree = QTreeWidget()
        # === 防 DPI 变化导致的吞字 ===
        self._toc_tree.setStyleSheet("QTreeWidget::item { height: 24px; }")
        # ===========================
        # ===========================================
        self._toc_tree.setHeaderHidden(True)
        self._toc_tree.setIndentation(15)
        self._toc_tree.setItemsExpandable(True)
        self._toc_tree.setExpandsOnDoubleClick(True)        
        self._toc_tree.setStyleSheet("""
            QTreeWidget {
                font-family: "Microsoft YaHei", sans-serif;
                font-size: 9pt;
                background-color: #f8f8f8;
                border: 1px solid #ddd;
                outline: 0;
            }
            QTreeWidget::item {
                padding: 2px;
                border-bottom: 1px solid #eee;
                height: 24px; /* 初始高度，会被 setSizeHint 覆盖 */
            }
            QTreeWidget::item:hover {
                background-color: #e8e8e8;
            }
            QTreeWidget::item:selected {
                background-color: #d0e0ff;
                color: black;
            }
        """)
        
        # 连接点击事件
        self._toc_tree.itemClicked.connect(self._on_toc_item_clicked)
        self._toc_tree.setVisible(self.toc_expanded)
        toc_layout.addWidget(self._toc_tree)
        self.bookmark_layout.addWidget(self._toc_container)
    def _fill_toc_tree(self):
        """根据 self.pdf_toc 填充 QTreeWidget"""
        if not hasattr(self, '_toc_tree'):
            return
        self._toc_tree.clear()
        
        if not self.pdf_toc:
            return
        
        # === 关键修复：获取正确的可用宽度 ===
        # 使用书签面板的固定宽度减去必要的边距
        available_width = self.bookmark_panel.width() - 20  # 20px 边距（左右各10px）
        if available_width < 100:
            available_width = 160  # 最小宽度保证可读性
        # ===================================
        
        parent_stack = []
        for entry in self.pdf_toc:
            if len(entry) >= 3:
                level, title, page = entry[0], entry[1], entry[2]
            else:
                continue
                
            display_text = f"{title} (P.{page})"
            
            item = QTreeWidgetItem()
            
            # === 修复吞字：加大余量 + 动态高度 ===
            label = QLabel(display_text)
            toc_font = QFont()
            toc_font.setFamily("Microsoft YaHei, SimHei, Segoe UI, sans-serif")
            toc_font.setPointSize(9)
            label.setFont(toc_font)
            label.setWordWrap(True)
            label.setAlignment(Qt.AlignLeft | Qt.AlignTop)

            # 关键：加大内边距（上下各加 4px）
            label.setContentsMargins(4, 4, 4, 4)  # ← 比 setMargin 更精确

            # 设置宽度
            available_width = self.bookmark_panel.width() - 20
            if available_width < 100:
                available_width = 160
            label.setFixedWidth(available_width - 50)

            # 强制 layout 更新
            label.adjustSize()

            # 获取计算高度，并额外增加 6px 安全余量（防 DPI/字体渲染偏差）
            calculated_height = label.size().height()
            safe_height = calculated_height + 6  # ← 核心：加余量！

            # 设置最终尺寸
            item.setSizeHint(0, QSize(label.width(), safe_height))
            # ===================================
            item.setData(0, Qt.UserRole, page)
            
            # 处理层级关系
            if not parent_stack:
                self._toc_tree.addTopLevelItem(item)
                parent_stack.append((item, level))
            else:
                while parent_stack and parent_stack[-1][1] >= level:
                    parent_stack.pop()
                if parent_stack:
                    parent_stack[-1][0].addChild(item)
                else:
                    self._toc_tree.addTopLevelItem(item)
                parent_stack.append((item, level))
            
            self._toc_tree.setItemWidget(item, 0, label)
    def update_toc_content(self):
        """更新 TOC 树的内容"""
        self._fill_toc_tree()
    def _on_reading_pane_focused(self, is_left):
        """
        当左或右阅读窗格获得焦点时调用。
        :param is_left: True 表示左窗格获得焦点，False 表示右窗格。
        """
        self.last_focused_pane_is_left = is_left
    def _on_toc_item_clicked(self, item, column):
        """处理 TOC 树节点点击事件"""
        page_num = item.data(0, Qt.UserRole)
        if page_num is not None:
            self.jump_to_page(page_num)    
    def toggle_toc(self, checked):
        self.toc_expanded = checked
        if hasattr(self, '_toc_tree'):        # ✅ 安全检查
            self._toc_tree.setVisible(checked)  # ✅ 使用正确的变量名
        self.save_config()
    def search_text_with_highlight(self, search_term, case_sensitive=False):
        """执行搜索并高亮结果"""
        if not self.doc or not search_term:
            return []

        results = []
        self.search_highlights = {}  # 清空之前的高亮

        # 搜索所有页面
        for page_num in range(len(self.doc)):
            page = self.doc[page_num]
            try:
                # 获取页面文本
                text = page.get_text()
                search_text = search_term if case_sensitive else search_term.lower()
                page_text = text if case_sensitive else text.lower()

                # 查找所有匹配
                indices = []
                start = 0
                while True:
                    idx = page_text.find(search_text, start)
                    if idx == -1:
                        break
                    indices.append(idx)
                    start = idx + 1

                # 为每个匹配查找位置
                for idx in indices:
                    # 获取匹配文本的位置
                    match_text = text[idx:idx+len(search_term)]
                    # 使用 search_for 查找精确位置
                    match_rects = page.search_for(match_text)
                    for rect in match_rects:
                        # === 修复：将 PDF 坐标转换为 pixmap 坐标（因渲染时用了 Matrix(2.0, 2.0)）===
                        RENDER_SCALE = 2.0  # 必须与 render_page 中的 Matrix 缩放一致
                        highlight_rect = [
                            rect.x0 * RENDER_SCALE,
                            rect.y0 * RENDER_SCALE,
                            rect.width * RENDER_SCALE,
                            rect.height * RENDER_SCALE
                        ]
                        # ==================================================================

                        if page_num + 1 not in self.search_highlights:
                            self.search_highlights[page_num + 1] = []
                        self.search_highlights[page_num + 1].append({
                            'rect': highlight_rect,
                            'color': self.search_highlight_color
                        })
                        # ===========================================
                        # 添加到结果列表
                        context_start = max(0, idx - 40)
                        context_end = min(len(text), idx + len(search_term) + 40)
                        context = text[context_start:context_end]
                        results.append({
                            'page': page_num + 1,
                            'context': context.strip(),
                            'position': idx
                        })
            except Exception as e:
                print(f"Error searching page {page_num}: {e}")

        # 更新当前搜索词
        self.current_search_term = search_term
        # 应用高亮到当前显示的页面
        self.apply_search_highlights()
        return results
    def apply_search_highlights(self):
        """应用搜索高亮到当前页面"""
        # 更新左窗格高亮
        if self.left_pane.page_num in self.search_highlights:
            self.left_pane.set_search_highlights(self.search_highlights[self.left_pane.page_num], self.current_search_term)
        else:
            self.left_pane.set_search_highlights([])
            
        # 更新右窗格高亮
        if self.right_pane.page_num in self.search_highlights:
            self.right_pane.set_search_highlights(self.search_highlights[self.right_pane.page_num], self.current_search_term)
        else:
            self.right_pane.set_search_highlights([])

    def clear_search_highlights(self):
        """清除所有搜索高亮"""
        self.search_highlights = {}
        self.current_search_term = ""
        self.left_pane.set_search_highlights([])
        self.right_pane.set_search_highlights([])
        self.update_status()
    
    
    def tr(self, text, **kwargs):
        """翻译界面文本。text 是英文原文作为 key"""
        trans_dict = self.translations.get(self.current_lang, self.translations["en"])
        translated = trans_dict.get(text, text)
        if kwargs:
            translated = translated.format(**kwargs)
        return translated
        
    def set_language(self, lang):
        if lang in ("en", "zh"):
            self.current_lang = lang
            
            # === 修复：先加载现有全局配置，再更新语言 ===
            global_data = {}
            if os.path.exists(GLOBAL_CONFIG_FILE):
                try:
                    with open(GLOBAL_CONFIG_FILE, 'r') as f:
                        global_data = json.load(f)
                except Exception as e:
                    print(f"Failed to load global config: {e}")
            
            # 更新语言，保留其他字段（如 recent_files）
            global_config = global_data.get("global_config", {})
            global_config["language"] = self.current_lang
            global_data["global_config"] = global_config
            # ==========================================
            
            try:
                with open(GLOBAL_CONFIG_FILE, 'w') as f:
                    json.dump(global_data, f, indent=2)
            except Exception as e:
                print(f"Failed to save global config: {e}")
            
            self.save_config()
            self.update_ui_text()
            QMessageBox.information(
                self, self.tr("Language Changed"), self.tr("Please restart TactiReader to apply the new language.")
            )
    def update_ui_text(self):
        # 更新窗口标题
        if self.notebook_source_path:
            # 笔记本模式：显示 .tactinote 文件名
            self.setWindowTitle(f"{self.tr('TactiReader')} - {os.path.basename(self.notebook_source_path)}")
        elif hasattr(self, 'pdf_path') and self.pdf_path:
            # 普通PDF模式
            self.setWindowTitle(f"{self.tr('TactiReader')} - {os.path.basename(self.pdf_path)}")
        else:
            self.setWindowTitle(self.tr('TactiReader'))
        # 更新书签面板（会刷新 <no bookmarks>）
        self.refresh_bookmark_panel()
        # 更新菜单栏文本
        self.update_menu_texts()

    def update_menu_texts(self):
        """更新菜单栏文本以反映当前语言"""
        # 注意：PyQt 的菜单系统不直接暴露菜单项以便重置文本，
        # 所以理想情况下应在创建时动态翻译。
        # 这个方法是为了展示目的，实际应用中可能需要重建菜单。
        pass

    def open_pdf_dialog(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            self.tr("Open PDF or Notebook"),
            "",
            self.tr("PDF Files (*.pdf);;TactiReader Notebook (*.tactinote)")
        )
        if file_path:
            abs_file_path = os.path.abspath(file_path)
            
            # 如果已在打开列表中，切换到对应标签
            for i, path in enumerate(self.open_documents):
                if os.path.abspath(path) == abs_file_path:
                    self.doc_tab_bar.setCurrentIndex(i)
                    return
            
            # 添加到文档列表
            self.open_documents.append(abs_file_path)
            self.save_global_config()
            
            # 更新标签栏（会自动显示/隐藏）
            self.update_document_tabs()
            
            # 加载文档（必须在 update_document_tabs 之后，因为要设置 currentIndex）
            if file_path.lower().endswith('.tactinote'):
                self.import_notebook_from_path(file_path)
            else:
                self.load_pdf(file_path)
    # === NEW CODE START ===
    def add_to_recent_files(self, file_path):
        """将文件加入最近列表（去重+置顶），支持 .pdf 和 .tactinote"""
        if not os.path.isfile(file_path):
            return
        
        # === 移除扩展名检查，让 .tactinote 也能加入 ===
        # if not file_path.lower().endswith('.pdf'):
        #     return
        # =======================================
        
        if file_path in self.recent_files:
            self.recent_files.remove(file_path)
        self.recent_files.insert(0, file_path)
        self.recent_files = self.recent_files[:5]  # 只保留5个
        self.save_global_config()
        self.update_recent_files_menu()
    def update_recent_files_menu(self):
        """刷新“最近文件”子菜单"""
        self.recent_menu.clear()
        if self.recent_files:
            for fp in self.recent_files:
                action = QAction(os.path.basename(fp), self)
                action.setToolTip(fp)
                # === 修改：根据文件扩展名决定打开方式 ===
                if fp.lower().endswith('.tactinote'):
                    action.triggered.connect(lambda checked, path=fp: self.import_notebook_from_path(path))
                else:
                    action.triggered.connect(lambda checked, path=fp: self.load_pdf(path))
                # =======================================
                self.recent_menu.addAction(action)
        else:
            empty_action = QAction(self.tr("<No recent files>"), self)
            empty_action.setEnabled(False)
            self.recent_menu.addAction(empty_action)
    # === NEW CODE END ===

    def calibrate_page_number_offset(self):
        """Ctrl+G: 标定当前物理页对应的逻辑页码"""
        if not self.doc:
            return
        
        # 获取当前焦点窗格的物理页码
        if self.left_pane.hasFocus() and not self.single_page_mode:
            current_physical = self.left_pane.page_num
        else:
            current_physical = self.right_pane.page_num

        if current_physical < 1:
            return

        # 计算当前逻辑页（用于默认值）
        current_logical = current_physical + self.page_number_offset

        # 弹出对话框
        logical_page, ok = QInputDialog.getInt(
            self,
            self.tr("Page Number Calibration"),
            self.tr("Enter logical page number for physical page {physical}:").format(physical=current_physical),
            value=current_logical,
            min=1,
            max=99999
        )
        if ok:
            # 更新偏移量：logical = physical + offset → offset = logical - physical
            self.page_number_offset = logical_page - current_physical
            self.save_config()
            self.statusBar().showMessage(
                self.tr("🔢 Page calibration: logical = physical + {offset}").format(offset=self.page_number_offset),
                2000
            )

    def clear_page_number_offset(self):
        """Ctrl+Shift+G: 清除页码偏移"""
        self.page_number_offset = 0
        self.save_config()
        self.statusBar().showMessage(self.tr("🧹 Page number offset cleared"), 2000)
    
    # === 新增：辅助方法，用于菜单项触发快捷键 ===
    def _trigger_shortcut(self, key, modifiers=Qt.NoModifier):
        """
        模拟触发一个键盘快捷键事件。
        这样菜单项可以直接复用现有的 keyPressEvent 逻辑，无需重复代码。
        """
        event = QKeyEvent(QEvent.KeyPress, key, modifiers)
        self.keyPressEvent(event)
    # ===========================================    
    def load_pdf(self, pdf_path):
        """加载 PDF（增强版）"""
        abs_path = os.path.abspath(pdf_path)
        
        # 添加到文档列表（如果不存在）
        if abs_path not in self.open_documents:
            self.open_documents.append(abs_path)
            self.save_global_config()
        
        # 检查是否已经是当前文档
        current_abs = os.path.abspath(self.pdf_path) if self.pdf_path else None
        if current_abs == abs_path:
            # 已经是当前文档，只更新 UI
            self.update_document_tabs()
            return
        # === 仅添加这一行！复用你已有的逻辑 ===
        self.add_to_recent_files(pdf_path)
        # ===================================        
        # === 原有加载逻辑 ===
        if self.pdf_path:
            self.save_config()
        
        if self.doc:
            self.doc.close()
        
        try:
            self.doc = fitz.open(pdf_path)
            self.pdf_path = pdf_path
            self.total_pages = len(self.doc)
            
            self.config_file = get_config_path(pdf_path)
            self.load_config()
            
            self.load_pdf_toc()
            self.refresh_bookmark_panel()
            self.render_facing()
            self.right_pane.setFocus()
            self.update_status()
            
            # 更新标签栏（现在 self.pdf_path 已更新）
            self.update_document_tabs()
            
        except Exception as e:
            QMessageBox.critical(
                self, 
                self.tr("Error"), 
                self.tr("Failed to open PDF:\n{}").format(str(e))
            )
            if abs_path in self.open_documents:
                self.open_documents.remove(abs_path)
                self.save_global_config()
                self.update_document_tabs()
    def load_config(self):
        if not self.config_file or not os.path.exists(self.config_file):
            return
        try:
            with open(self.config_file, 'r') as f:
                data = json.load(f)
                config = data.get("config", {})
                self.flip_multiplier = config.get("multiplier", 1)
                self.home_page = max(1, min(config.get("home_page", 1), self.total_pages))
                self.right_page = max(1, min(config.get("last_page", 1), self.total_pages))
                self.single_page_mode = config.get("single_page_mode", False)

                self.left_locked = config.get("left_locked", False)
                self.locked_left_page = max(1, min(config.get("locked_left_page", 1), self.total_pages))
                                # 加载书签面板状态
                self.bookmark_panel_visible = config.get("bookmark_panel_visible", True)
                self.bookmark_panel.setVisible(self.bookmark_panel_visible)
                # 在 load_config 中，加载完 config 后：
                if "splitter_sizes" in config:
                    sizes = config["splitter_sizes"]
                    if len(sizes) == 2 and all(isinstance(x, int) and x >= 0 for x in sizes):
                        self.splitter.setSizes(sizes)
                
                # 加载颜色设置
                self.current_pen_color_index = config.get("pen_color_index", 0)
                self.current_rect_color_index = config.get("rect_color_index", 0)
                self.current_text_color_index = config.get("text_color_index", 0)
                # 注意：语言设置现在从全局配置加载，这里不再加载
                # self.current_lang = config.get("language", "en")
                
                # 更新面板颜色
                self.update_pane_colors()
                
                # 加载旋转状态
                if "page_rotations" in data:
                    self.page_rotations = data["page_rotations"]
                
                # 加载批注
                if "annotations" in data:
                    self.annotations = data["annotations"]
                self.page_number_offset = data.get("page_number_offset", 0)
                # === 加载全局视图状态（缩放/平移/旋转）===
                # 左窗格
                if "global_left_scale" in data:
                    self.left_pane.scale_factor = data["global_left_scale"]
                if "global_left_offset" in data:
                    offset = data["global_left_offset"]
                    self.left_pane.offset = QPointF(offset[0], offset[1])
                if "global_left_rotation" in data:
                    self.left_pane.rotation = data["global_left_rotation"]
                
                # 右窗格
                if "global_right_scale" in data:
                    self.right_pane.scale_factor = data["global_right_scale"]
                if "global_right_offset" in data:
                    offset = data["global_right_offset"]
                    self.right_pane.offset = QPointF(offset[0], offset[1])
                if "global_right_rotation" in data:
                    self.right_pane.rotation = data["global_right_rotation"]
                # =======================================
                bookmarks = {}
                for k, v in data.items():
                    if k != "config" and k != "annotations" and k != "page_rotations":
                        if isinstance(v, dict):
                            bookmarks[k] = v
                        else:
                            bookmarks[k] = {"page": v, "name": ""}
                self.bookmarks = bookmarks
        except Exception as e:
            print(f"Config load error: {e}")

    def save_config(self):
        if not self.config_file:
            return
        data = self.bookmarks.copy()
        data["config"] = {
            "multiplier": self.flip_multiplier,
            "home_page": self.home_page,
            "last_page": self.right_page,
            "single_page_mode": self.single_page_mode,
            "left_locked": self.left_locked,
            "locked_left_page": self.locked_left_page,
            "pen_color_index": self.current_pen_color_index,
            "rect_color_index": self.current_rect_color_index,
            "text_color_index": self.current_text_color_index,
            # === 新增：书签面板状态 ===
            "bookmark_panel_visible": self.bookmark_panel_visible,
            "splitter_sizes": self.splitter.sizes(),  # ← 新增这一行

        }
        data["page_rotations"] = self.page_rotations
        data["annotations"] = self.annotations
        data["page_number_offset"] = self.page_number_offset
        # === 保存全局视图状态（缩放/平移/旋转）===
        data["global_left_scale"] = self.left_pane.scale_factor
        data["global_left_offset"] = [self.left_pane.offset.x(), self.left_pane.offset.y()]
        data["global_left_rotation"] = self.left_pane.rotation
        
        data["global_right_scale"] = self.right_pane.scale_factor
        data["global_right_offset"] = [self.right_pane.offset.x(), self.right_pane.offset.y()]
        data["global_right_rotation"] = self.right_pane.rotation
        # =========================================
        try:
            with open(self.config_file, 'w') as f:
                json.dump(data, f, indent=2, default=self.serialize_annotations)
                
        except Exception as e:
            print(f"Save config failed: {e}")
    
    # === NEW CODE START ===
    def save_global_config(self):
        """保存全局配置（包括已打开文档）"""
        try:
            # 读取现有全局配置
            global_config = {}
            if os.path.exists(GLOBAL_CONFIG_FILE):
                with open(GLOBAL_CONFIG_FILE, 'r') as f:
                    data = json.load(f)
                    global_config = data.get("global_config", {})
            
            # 更新最近文件（保持原有逻辑）
            recent_files_clean = [f for f in self.recent_files if os.path.isfile(f)]
            global_config["recent_files"] = recent_files_clean[-10:]  # 保留最近10个
            
            # 新增：保存已打开文档
        # 保存已打开文档（支持 .pdf 和 .tactinote）
            open_docs_clean = [f for f in self.open_documents if os.path.isfile(f) and (f.lower().endswith('.pdf') or f.lower().endswith('.tactinote'))]
            global_config["open_documents"] = open_docs_clean[-10:]  # 保留最近10个
            
            # 保存语言设置
            global_config["language"] = self.current_lang
            
            # 写入文件
            os.makedirs(os.path.dirname(GLOBAL_CONFIG_FILE), exist_ok=True)
            with open(GLOBAL_CONFIG_FILE, 'w') as f:
                json.dump({"global_config": global_config}, f, indent=2)
                
        except Exception as e:
            print(f"Failed to save global config: {e}")

    def update_document_tabs(self):
        """更新标签栏显示（智能隐藏/显示）"""
        if not self.open_documents:
            self.doc_tab_bar.setVisible(False)
            return
        
        # 获取目标索引
        target_index = -1
        if self.pdf_path:
            current_abs = os.path.abspath(self.pdf_path)
            for i, path in enumerate(self.open_documents):
                if os.path.abspath(path) == current_abs:
                    target_index = i
                    break
        
        # 阻塞信号防止递归
        self.doc_tab_bar.blockSignals(True)
        
        # 清空并重建标签
        while self.doc_tab_bar.count() > 0:
            self.doc_tab_bar.removeTab(0)
        
        for path in self.open_documents:
            tab_text = os.path.basename(path)
            self.doc_tab_bar.addTab(tab_text)
        
        # 设置正确的当前索引
        if target_index >= 0 and target_index < len(self.open_documents):
            self.doc_tab_bar.setCurrentIndex(target_index)
        elif self.open_documents:
            self.doc_tab_bar.setCurrentIndex(0)
            self.pdf_path = self.open_documents[0]  # 同步路径
        
        # 恢复信号
        self.doc_tab_bar.blockSignals(False)
        
        # 控制显示/隐藏
        self.doc_tab_bar.setVisible(len(self.open_documents) > 1)
                # === 新增：更新窗口标题 ===
        self.update_ui_text()
        # ========================
    def on_doc_tab_changed(self, index):
        """标签切换时加载对应文档"""
        if 0 <= index < len(self.open_documents):
            # === 新增：切换前保存当前 .tactinote ===
            if getattr(self, 'notebook_source_path', None) is not None:
                self.save_config()
                self._flush_notebook_to_source()
            # ===================================
            
            file_path = self.open_documents[index]
            current_path = self.pdf_path or ""
            
            if os.path.abspath(file_path) != os.path.abspath(current_path):
                if file_path.lower().endswith('.tactinote'):
                    self.import_notebook_from_path(file_path)
                else:
                    self.load_pdf(file_path)

    def close_document_tab(self, index):
        if not self.open_documents or index >= len(self.open_documents):
            return
        
        closed_path = self.open_documents.pop(index)
        self.save_global_config()
        
        self.doc_tab_bar.blockSignals(True)
        self.doc_tab_bar.removeTab(index)
        self.doc_tab_bar.blockSignals(False)
        
        if self.open_documents:
            new_index = min(index, len(self.open_documents) - 1)
            new_path = self.open_documents[new_index]
            
            # === 关键：安全关闭并清空当前文档 ===
            if self.doc is not None:
                self.doc.close()
                self.doc = None  # ← 必须设为 None！
            self.pdf_path = None
            self.notebook_source_path = None
            self.config_file = None
            # =================================
            
            if new_path.lower().endswith('.tactinote'):
                self.import_notebook_from_path(new_path)
            else:
                self.load_pdf(new_path)
            
            self.doc_tab_bar.blockSignals(True)
            self.doc_tab_bar.setCurrentIndex(new_index)
            self.doc_tab_bar.blockSignals(False)
        else:
            if self.doc is not None:
                self.doc.close()
                self.doc = None
            self.pdf_path = None
            self.notebook_source_path = None
            self.config_file = None
            self.total_pages = 0
            
            self.left_pane.set_page(None, -1)
            self.right_pane.set_page(None, -1)
            self.refresh_bookmark_panel()
            self.update_status()
            self.update_ui_text()
            self.doc_tab_bar.clear()
        
        self.doc_tab_bar.setVisible(len(self.open_documents) > 1)
    def show_tab_context_menu(self, pos):
        """标签右键菜单"""
        index = self.doc_tab_bar.tabAt(pos)
        if index == -1:
            return
        
        menu = QMenu(self)
        open_in_new_window = menu.addAction(self.tr("Open in New Window"))
        action = menu.exec_(self.doc_tab_bar.mapToGlobal(pos))
        
        if action == open_in_new_window:
            pdf_path = self.open_documents[index]
            self.open_in_new_window(pdf_path)

    def open_in_new_window(self, pdf_path):
        """在新窗口中打开文档"""
        script_path = sys.argv[0]
        subprocess.Popen([sys.executable, script_path, pdf_path])

    def serialize_annotations(self, obj):
        """辅助函数用于序列化批注（处理QColor对象）"""
        if isinstance(obj, dict):
            return {k: self.serialize_annotations(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self.serialize_annotations(item) for item in obj]
        elif isinstance(obj, QColor):
            return obj.name()
        else:
            return obj

    def render_page(self, page_num):
        if page_num < 0 or page_num >= self.total_pages:
            return QPixmap()
        try:
            page = self.doc[page_num]
            mat = fitz.Matrix(2.0, 2.0)
            pix = page.get_pixmap(matrix=mat)
            stride = pix.stride if pix.stride is not None else pix.width * 3
            img_format = QImage.Format_RGBA8888 if pix.alpha else QImage.Format_RGB888
            qt_img = QImage(pix.samples, pix.width, pix.height, stride, img_format)
            return QPixmap.fromImage(qt_img)
        except Exception as e:
            print(f"Render error: {e}")
            return QPixmap()

    def render_facing(self):
        if not self.doc:
            return

        right_1idx = self.right_page
        self.left_pane.setVisible(not self.single_page_mode)

        # 渲染右页
        right_rotation = self.page_rotations.get(str(right_1idx), 0)
        self.right_pane.rotation = right_rotation
        right_pixmap = self.render_page(right_1idx - 1)
        right_annotations = self.get_annotations_for_page(right_1idx)
        # 应用搜索高亮
        if self.current_search_term and right_1idx in self.search_highlights:
            self.right_pane.set_search_highlights(self.search_highlights[right_1idx], self.current_search_term)
        else:
            self.right_pane.set_search_highlights([])
        self.right_pane.set_page(right_pixmap, right_1idx, is_left=False, 
                                reset_view=False, annotations=right_annotations)

        if not self.single_page_mode:
            # 计算左页码
            if self.left_locked and self.locked_left_page >= 1:
                left_page_num = self.locked_left_page
            else:
                left_page_num = max(1, right_1idx - 1)
            self.locked_left_page = left_page_num

            # 渲染左页
            left_rotation = self.page_rotations.get(str(left_page_num), 0)
            self.left_pane.rotation = left_rotation
            left_pixmap = self.render_page(left_page_num - 1)
            left_annotations = self.get_annotations_for_page(left_page_num)
            # 应用搜索高亮
            if self.current_search_term and left_page_num in self.search_highlights:
                self.left_pane.set_search_highlights(self.search_highlights[left_page_num], self.current_search_term)
            else:
                self.left_pane.set_search_highlights([])
            self.left_pane.set_page(left_pixmap, left_page_num, is_left=True, 
                                   reset_view=False, annotations=left_annotations)

        self.update_status()
    
    def get_annotations_for_page(self, page_num):
        """获取指定页面的批注"""
        page_key = str(page_num)
        if page_key in self.annotations:
            # 确保批注数据格式正确
            annotations = self.annotations[page_key]
            for annotation in annotations:
                # 修复：确保points是列表的列表
                if annotation.get("type") == "pen":
                    points = annotation.get("points", [])
                    if points and isinstance(points[0], dict):
                        # 转换字典格式的points为列表格式
                        annotation["points"] = [(p.get("x", 0), p.get("y", 0)) for p in points]
            return annotations
        return []
    
    def save_annotation(self, page_num, annotation):
        """保存批注"""
        page_key = str(page_num)
        if page_key not in self.annotations:
            self.annotations[page_key] = []
        self.annotations[page_key].append(annotation)
        self.save_config()
    
    def update_pane_colors(self):
        """更新面板颜色设置"""
        pen_color = self.pen_colors[self.current_pen_color_index]
        rect_color = self.rect_colors[self.current_rect_color_index]
        text_color = self.text_colors[self.current_text_color_index]
        
        self.left_pane.set_pen_color(pen_color)
        self.left_pane.set_rect_color(rect_color)
        self.left_pane.set_text_color(text_color)
        
        self.right_pane.set_pen_color(pen_color)
        self.right_pane.set_rect_color(rect_color)
        self.right_pane.set_text_color(text_color)

    def update_status(self):
        mode_str = self.tr("Single") if self.single_page_mode else self.tr("Double")
        lock_icon = "🔒" if self.left_locked else ""
        
        # 批注模式状态
        annotation_mode = self.tr("None")
        if self.left_pane.annotation_mode:
            annotation_mode = f"L:{self.left_pane.annotation_mode}"
        elif self.right_pane.annotation_mode:
            annotation_mode = f"R:{self.right_pane.annotation_mode}"
        
        # 搜索高亮状态
        search_status = f" 🔍{sum(len(h) for h in self.search_highlights.values())}" if self.search_highlights else ""

        # === 新增：计算左右窗格的逻辑页码 ===
        left_logical = self.left_pane.page_num + self.page_number_offset if self.left_pane.page_num > 0 else 0
        right_logical = self.right_pane.page_num + self.page_number_offset if self.right_pane.page_num > 0 else 0

        if self.single_page_mode:
            page_display = f"P.{right_logical}"
        else:
            page_display = f"L.{left_logical} R.{right_logical}"
        # ===================================

        msg = f"{mode_str} | {page_display} | Home: P.{self.home_page + self.page_number_offset} | ×{self.flip_multiplier} {lock_icon} | Annot: {annotation_mode}{search_status}"
        self.statusBar().showMessage(msg)
    def update_color_display(self):
        """更新状态栏颜色显示"""
        pen_color = self.pen_colors[self.current_pen_color_index]
        rect_color = self.rect_colors[self.current_rect_color_index]
        text_color = self.text_colors[self.current_text_color_index]
        
        # 创建颜色方块
        pen_html = f'<span style="color:{pen_color.name()}; background:white; padding:2px;">■</span>'
        rect_html = f'<span style="color:{rect_color.name()}; background:white; padding:2px;">■</span>'
        text_html = f'<span style="color:{text_color.name()}; background:white; padding:2px;">■</span>'
        
        self.color_status_label.setText(f" Pen:{pen_html}  Highlight:{rect_html}  Text:{text_html}")
    
    def set_pen_color_index(self, index):
        """设置画笔颜色索引"""
        self.current_pen_color_index = index
        pen_color = self.pen_colors[index]
        self.left_pane.set_pen_color(pen_color)
        self.right_pane.set_pen_color(pen_color)
        self.update_color_display()
        self.save_config()
    
    def set_rect_color_index(self, index):
        """设置矩形高亮颜色索引"""
        self.current_rect_color_index = index
        rect_color = self.rect_colors[index]
        self.left_pane.set_rect_color(rect_color)
        self.right_pane.set_rect_color(rect_color)
        self.update_color_display()
        self.save_config()
    
    def set_text_color_index(self, index):
        """设置文本颜色索引"""
        self.current_text_color_index = index
        text_color = self.text_colors[index]
        self.left_pane.set_text_color(text_color)
        self.right_pane.set_text_color(text_color)
        self.update_color_display()
        self.save_config()
    
    def set_annotation_mode(self, mode):
        """设置批注模式 (全局)"""
        self.annotation_mode = mode
        
        # === 关键：将模式同步到左右两个窗格 ===
        self.left_pane.set_annotation_mode(mode)
        self.right_pane.set_annotation_mode(mode)
        # ===================================
        
        # 更新状态栏
        if hasattr(self, 'update_status'):
            self.update_status()
    def clear_current_page_annotations(self):
        """清除当前焦点页面的批注"""
        if self.left_pane.hasFocus() and not self.single_page_mode:
            page_num = self.left_pane.page_num
            pane = self.left_pane
        else:
            page_num = self.right_pane.page_num
            pane = self.right_pane
        
        if str(page_num) in self.annotations:
            del self.annotations[str(page_num)]
            pane.annotations = []
            pane.update()
            self.save_config()
            self.statusBar().showMessage(self.tr("🗑️ Cleared annotations on page {page}").format(page=page_num), 2000)
    
    def undo_last_annotation(self):
        """撤销最后添加的批注"""
        if self.left_pane.hasFocus() and not self.single_page_mode:
            page_num = self.left_pane.page_num
            pane = self.left_pane
        else:
            page_num = self.right_pane.page_num
            pane = self.right_pane
        
        page_key = str(page_num)
        if page_key in self.annotations and self.annotations[page_key]:
            # 移除最后一个批注
            removed = self.annotations[page_key].pop()
            pane.annotations = self.annotations[page_key].copy()
            pane.update()
            self.save_config()
            self.statusBar().showMessage(self.tr("↩️ Undo last annotation on page {page}").format(page=page_num), 2000)
        else:
            self.statusBar().showMessage(self.tr("ℹ️ No annotations to undo on page {page}").format(page=page_num), 1000)

    def navigate_back(self):
        """Ctrl+A: 回退到上一个跨页位置（仅1步）"""
        is_left_focused = self.left_pane.hasFocus() and not self.single_page_mode
        last_location = self.left_last_location if is_left_focused else self.right_last_location
        pane = self.left_pane if is_left_focused else self.right_pane
        
        if last_location is None:
            self.statusBar().showMessage("⏪ No previous location to go back", 1000)
            return
        
        page_num, rotation, scale, offset = last_location
        
        # 跳转到历史页面
        self._jump_to_page_internal(page_num, is_left=is_left_focused)
        
        # 恢复视图状态
        pane.rotation = rotation
        pane.scale_factor = scale
        pane.offset = QPointF(offset[0], offset[1])
        pane.update()
        
        # 清空历史（避免重复回退）
        if is_left_focused:
            self.left_last_location = None
        else:
            self.right_last_location = None
        
        self.statusBar().showMessage(f"⏪ Back to P.{page_num}", 1000)
    def _jump_to_page_internal(self, page_1idx, is_left=False):
        if not self.doc:
            return
        if page_1idx < 1:
            page_1idx = 1
        if page_1idx > self.total_pages:
            page_1idx = self.total_pages
        # === 记录单步历史（仅当跳转超过1页时）===
        current_page = self.left_pane.page_num if is_left else self.right_pane.page_num
        target_page = page_1idx
        
        # 检查是否为“跨页跳转”（绝对值 > 1）且当前页有效
        if abs(target_page - current_page) > 1 and current_page >= 1:
            # 保存当前状态：(page, rotation, scale, offset)
            current_state = (
                current_page,
                self.left_pane.rotation if is_left else self.right_pane.rotation,
                self.left_pane.scale_factor if is_left else self.right_pane.scale_factor,
                (self.left_pane.offset.x(), self.left_pane.offset.y()) if is_left else (self.right_pane.offset.x(), self.right_pane.offset.y())
            )
            # 直接覆盖（只保留最新）
            if is_left:
                self.left_last_location = current_state
            else:
                self.right_last_location = current_state
        # ===================================
        # ===================================
        # 如果是操作左页（且非单页模式）
        if is_left and not self.single_page_mode:
            self.left_locked = True
            self.locked_left_page = page_1idx
            # 关键：通过 render_facing 统一处理渲染（包含旋转设置）
            self.render_facing()
            self.left_pane.setFocus()
            self.save_config()
           #return  # 避免执行后面的右页逻辑
        else:
            # 操作右页（或单页模式）
            if page_1idx > self.home_page:
                self.home_page = page_1idx
            self.right_page = page_1idx
            self.render_facing()
            self.right_pane.setFocus()
            self.update_status()
    def jump_to_page(self, page_1idx):
        """
        统一跳转入口。
        使用最后获得焦点的阅读窗格作为目标。
        """
        if not self.doc:
            return
        page_1idx = max(1, min(page_1idx, self.total_pages))

        # 判断目标窗格：使用最后记录的状态
        target_is_left = self.last_focused_pane_is_left and (not self.single_page_mode)

        # 调用内部实现
        self._jump_to_page_internal(page_1idx, is_left=target_is_left)
    def goto_page(self):
            if not self.doc:
                return
            
            # 创建自定义对话框以获得更好的控制
            dialog = QDialog(self)
            dialog.setWindowTitle(self.tr("Go to Page"))
            dialog.setMinimumWidth(350)  # 设置最小宽度
            
            layout = QVBoxLayout(dialog)
            
            # 添加标签
            min_logical = 1 + self.page_number_offset
            max_logical = self.total_pages + self.page_number_offset
            label = QLabel(self.tr("Enter page number ({min}-{max}):").format(min=min_logical, max=max_logical))
            
            
            layout.addWidget(label)
            
            # 添加输入框
            self.page_input = QLineEdit()
            self.page_input.setPlaceholderText(self.tr("Enter a number between {min} and {max}").format(min=min_logical, max=max_logical))            
            layout.addWidget(self.page_input)
            
            # 添加按钮
            button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
            button_box.accepted.connect(lambda: self.process_page_input(dialog))
            button_box.rejected.connect(dialog.reject)
            layout.addWidget(button_box)
            
            # 设置焦点到输入框
            self.page_input.setFocus()
            
            dialog.exec_()
        
    def process_page_input(self, dialog):
        page_str = self.page_input.text().strip()
        try:
            logical_page = int(page_str)
            # ⚠️ 保持原有转换逻辑不变！
            physical_page = logical_page - self.page_number_offset  # 注意是减号！
            
            if 1 <= physical_page <= self.total_pages:
                self.jump_to_page(physical_page)
                dialog.accept()
            else:
                QMessageBox.warning(
                    self, 
                    self.tr("Invalid Page"), 
                    self.tr("Physical page would be {physical}, which is out of range [1, {total_pages}].\n"
                        "Current offset: {offset}").format(
                        physical=physical_page,
                        total_pages=self.total_pages,
                        offset=self.page_number_offset
                    )
                )
        except ValueError:
            QMessageBox.warning(self, self.tr("Invalid Input"), self.tr("Please enter a valid number"))
    def search_text(self):
        """增强的搜索功能"""
        if not self.doc:
            return

        # 创建搜索对话框
        self.search_dialog = SearchDialog(self, self.doc)
        # === 重要：手动更新 SearchDialog 的 UI 文本 ===
        if self.search_dialog:
            dialog = self.search_dialog
            dialog.setWindowTitle(self.tr("Search in PDF"))
            dialog.search_button.setText(self.tr("Search"))
            dialog.prev_button.setText(self.tr("◀ Previous"))
            dialog.next_button.setText(self.tr("Next ▶"))
            dialog.close_button.setText(self.tr("Close"))
            dialog.result_count_label.setText(self.tr("No results"))
        # ===============================================

        self.search_dialog.searchResultSelected.connect(self.on_search_result_selected)
        # === 关键新增：连接对话框关闭信号，用于清除高亮 ===
        self.search_dialog.finished.connect(self.clear_search_highlights)
        # ===============================================
        self.search_dialog.show()
    def on_search_result_selected(self, page_num, context):
        """处理搜索结果选择"""
        self.jump_to_page(page_num)
        # 在状态栏显示上下文
        if len(context) > 50:
            context = context[:50] + "..."
        self.statusBar().showMessage(self.tr("🔍 {context}").format(context=context), 3000)
    def export_notebook(self):
        """导出笔记：将当前PDF和其配置打包为 .tactinote 文件"""
        if not self.pdf_path or not self.doc:
            QMessageBox.warning(self, self.tr("Save Notebook"), self.tr("No document is open.")) # <-- 这里改了
            return

        # 1. 确保最新状态已写入当前的配置文件
        self.save_config()

        # 2. 获取当前配置文件路径
        current_config_path = self.config_file
        if not current_config_path or not os.path.exists(current_config_path):
            QMessageBox.critical(self, self.tr("Error"), self.tr("Failed to locate config file."))
            return

        # 3. 弹出保存对话框
        # === 智能生成默认文件名 ===
        if self.notebook_source_path:
            # 如果当前是从一个 .tactinote 打开的，就用它的名字
            base_name = os.path.splitext(os.path.basename(self.notebook_source_path))[0]
        elif self.pdf_path:
            # 如果是普通PDF模式，就用PDF的名字
            base_name = os.path.splitext(os.path.basename(self.pdf_path))[0]
        else:
            base_name = "notebook"
        default_name = base_name + ".tactinote"
        # =========================
        save_path, _ = QFileDialog.getSaveFileName(
            self, self.tr("Export Notebook"), default_name,
            self.tr("TactiReader Notebook (*.tactinote)")
        )
        if not save_path:
            return
        if not save_path.endswith(".tactinote"):
            save_path += ".tactinote"

        try:
            import zipfile
            with zipfile.ZipFile(save_path, 'w', zipfile.ZIP_STORED) as zf:
                # 打包 PDF
                zf.write(self.pdf_path, "document.pdf")
                # 打包现有的 .json 配置文件，并重命名为 session.json
                zf.write(current_config_path, "session.json")
            
            self.statusBar().showMessage(
                self.tr("Notebook exported to: {}").format(os.path.basename(save_path)), 3000
            )
        except Exception as e:
            QMessageBox.critical(self, self.tr("Error"), f"{self.tr('Failed to export notebook')}: {e}")
    def save_as_pdf(self):
        """另存为PDF：复用现有逻辑，只做三件事"""
        if not self.doc or not self.pdf_path:
            return

        # === 智能生成默认文件名 ===
        if self.notebook_source_path:
            # 如果当前是从一个 .tactinote 打开的，就用它的名字（去掉 .tactinote 后缀）
            base_name = os.path.splitext(os.path.basename(self.notebook_source_path))[0]
        else:
            # 否则，用当前PDF的名字（去掉 .pdf 后缀）
            base_name = os.path.splitext(os.path.basename(self.pdf_path))[0]
        default_name = base_name + ".pdf"
        # =========================

        # 1. 弹出保存对话框
        new_pdf_path, _ = QFileDialog.getSaveFileName(
            self,
            self.tr("Save As PDF"),
            default_name,  # <-- 使用智能生成的默认名
            self.tr("PDF Files (*.pdf)")
        )
        if not new_pdf_path:
            return
        if not new_pdf_path.lower().endswith('.pdf'):
            new_pdf_path += '.pdf'

        try:
            import shutil
            # STEP 1: 确保当前状态已保存到磁盘 (save config)
            self.save_config()

            # STEP 2: 搬运PDF (pdf搬运)
            shutil.copy2(self.pdf_path, new_pdf_path)

            # STEP 3: 搬运JSON (json搬运)
            old_config_path = self.config_file
            new_config_path = get_config_path(new_pdf_path)
            if old_config_path and os.path.exists(old_config_path):
                shutil.copy2(old_config_path, new_config_path)

            # 完成
            print(f"[INFO] Save As successful: {new_pdf_path}")

        except Exception as e:
            print(f"[ERROR] Save As failed: {e}")
    def import_notebook(self):
        """导入笔记：从 .tactinote 文件加载，并进入笔记本模式"""
        notebook_path, _ = QFileDialog.getOpenFileName(
            self, self.tr("Import Notebook"), "",
            self.tr("TactiReader Notebook (*.tactinote)")
        )
        if not notebook_path:
            return

        # === 新增多标签支持：先注册到 open_documents ===
        abs_notebook_path = os.path.abspath(notebook_path)
        
        # 避免重复打开
        for i, path in enumerate(self.open_documents):
            if os.path.abspath(path) == abs_notebook_path:
                self.doc_tab_bar.setCurrentIndex(i)
                return
        
        # 添加到文档列表（关键！）
        self.open_documents.append(abs_notebook_path)
        self.save_global_config()
        # ===================================================

        try:
            import zipfile
            import shutil
            import hashlib
            
            # 1. 为这个 .tactinote 创建一个唯一的临时工作目录
            hash_id = hashlib.md5(notebook_path.encode('utf-8')).hexdigest()[:12]
            temp_base_dir = os.path.join(CONFIG_DIR, "..", "temp")
            os.makedirs(temp_base_dir, exist_ok=True)
            work_dir = os.path.join(temp_base_dir, f"nb_{hash_id}")
            os.makedirs(work_dir, exist_ok=True)
            
            pdf_path = os.path.join(work_dir, "document.pdf")
            session_json_path = os.path.join(work_dir, "session.json")
            
            # 2. 解压 .tactinote
            with zipfile.ZipFile(notebook_path, 'r') as zf:
                zf.extract("document.pdf", work_dir)
                zf.extract("session.json", work_dir)

            # 3. 正常加载 PDF
            if self.doc:
                self.doc.close()
            self.doc = fitz.open(pdf_path)
            self.pdf_path = pdf_path  # 注意：这里是临时 PDF 路径
            self.total_pages = len(self.doc)

            # 4. 进入笔记本模式
            self.config_file = session_json_path
            self.notebook_source_path = notebook_path  # ← 这是原始 .tactinote 路径

            # 5. 加载配置、TOC等
            self.load_config()
            self.load_pdf_toc()
            self.refresh_bookmark_panel()
            self.render_facing()
            self.right_pane.setFocus()
            self.update_status()
            self.update_ui_text()

            # === 更新标签栏（必须在设置完 notebook_source_path 后调用）===
            self.update_document_tabs()
            # ===========================================================

            self.statusBar().showMessage(
                self.tr("Notebook imported from: {}").format(os.path.basename(notebook_path)), 3000
            )
            self.add_to_recent_files(notebook_path)
            
        except Exception as e:
            QMessageBox.critical(self, self.tr("Error"), f"{self.tr('Failed to import notebook')}: {e}")
            # 如果失败，从 open_documents 中移除
            if abs_notebook_path in self.open_documents:
                self.open_documents.remove(abs_notebook_path)
                self.save_global_config()
                self.update_document_tabs()

    def _flush_notebook_to_source(self):
        """内部方法：将当前工作区的状态打包回源 .tactinote 文件"""
        if not self.notebook_source_path or not self.config_file:
            return

        try:
            import zipfile
            import tempfile
            import shutil

            work_dir = os.path.dirname(self.config_file)
            source_pdf = os.path.join(work_dir, "document.pdf")
            source_session = self.config_file

            # 创建一个临时的 .tactinote 文件
            temp_dir = tempfile.mkdtemp(prefix="tactireader_flush_")
            temp_notebook = os.path.join(temp_dir, "temp.tactinote")

            with zipfile.ZipFile(temp_notebook, 'w', zipfile.ZIP_STORED) as zf:
                zf.write(source_pdf, "document.pdf")
                zf.write(source_session, "session.json")

            # 原子性地替换源文件
            shutil.move(temp_notebook, self.notebook_source_path)
            # 清理工作目录
            shutil.rmtree(work_dir, ignore_errors=True)
            # 重置状态
            self.notebook_source_path = None

            self.statusBar().showMessage(self.tr("Notebook saved."), 2000)
        except Exception as e:
            print(f"Failed to flush notebook: {e}")
    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if len(urls) == 1 and urls[0].toLocalFile().lower().endswith('.pdf'):
                event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        url = event.mimeData().urls()[0]
        path = url.toLocalFile()
        if path.lower().endswith('.pdf'):
            self.load_pdf(path)

    def refresh_bookmark_panel(self):
        # === 第一步：清理旧的自定义书签和占位符 ===
        # 我们只删除 QLabel (占位符) 和 BookmarkButton，保留 TOC 容器
        for i in reversed(range(self.bookmark_layout.count())):
            widget = self.bookmark_layout.itemAt(i).widget()
            # 如果是 TOC 容器，跳过
            if widget is getattr(self, '_toc_container', None):
                continue
            # 否则，移除并销毁（这包括书签按钮和<no bookmarks>标签）
            self.bookmark_layout.removeWidget(widget)
            widget.deleteLater()
        
        # === 第二步：重新添加自定义书签（在顶部）===
        bookmark_widgets = []
        if not self.bookmarks:
            placeholder = QLabel(self.tr("<no bookmarks>"))
            placeholder.setAlignment(Qt.AlignCenter)
            placeholder.setWordWrap(True)  # ← 也支持换行
            placeholder.setStyleSheet("color: gray; font-style: italic;")
            bookmark_widgets.append(placeholder)
        else:
            keys_in_order = ['Q', 'W', 'E', 'R', 'T', 'Y', 'U', 'I', 'O', 'P']
            for key in keys_in_order:
                if key in self.bookmarks:
                    bm = self.bookmarks[key]
                    btn = BookmarkButton(key, bm['page'], bm.get('name', ''))
                    btn.bookmarkClicked.connect(self._on_bookmark_clicked)
                    bookmark_widgets.append(btn)
        
        # 将所有书签widget插入到布局的最前面（索引0开始）
        for i, widget in enumerate(bookmark_widgets):
            self.bookmark_layout.insertWidget(i, widget)
        
        # === 第三步：确保 TOC 面板存在并更新其内容 ===
        self.create_toc_widget()  # 首次创建
        self.update_toc_content()  # 更新内容（滚动位置保留）
    
    def toggle_bookmark_panel(self):
        """切换书签/目录面板的显示/隐藏状态"""
        self.bookmark_panel_visible = not self.bookmark_panel_visible
        self.bookmark_panel.setVisible(self.bookmark_panel_visible)
        
        # 更新 splitter 大小以适应变化
        if hasattr(self, 'splitter'):
            total_width = self.splitter.width()
            if self.bookmark_panel_visible:
                # 显示书签面板，阅读区域宽度减少
                reading_width = total_width
            else:
                # 隐藏书签面板，阅读区域占据更多空间
                reading_width = total_width + 180
            

        
        # 保存状态到配置
        self.save_config()
        
        # 状态栏提示
        status = "shown" if self.bookmark_panel_visible else "hidden"
        self.statusBar().showMessage(f"📂 Navigation panel {status}", 1000)    

    def _on_bookmark_clicked(self, key):
        if key in self.bookmarks:
            page = self.bookmarks[key]['page']
            self.jump_to_page(page)  

    def keyPressEvent(self, event):
        if not self.doc:
            return

        key = event.key()
        modifiers = event.modifiers()
        focused_on_left = self.left_pane.hasFocus() and not self.single_page_mode
        # Ctrl+X: Reset current two pages (zoom, pan, rotation) and center splitter
        # Ctrl+X: Reset current two pages (zoom, pan, rotation) and center splitter
        if key == Qt.Key_X and modifiers == Qt.ControlModifier:
            # === 先重置 splitter 尺寸 ===
            total_width = self.splitter.width()
            self.splitter.setSizes([total_width // 2, total_width // 2])
            # ===========================
            
            # Reset right pane
            self.right_pane.reset_view()
            self.page_rotations[self.right_pane.page_num] = 0
            
            # Reset left pane if in double page mode
            if not self.single_page_mode:
                self.left_pane.reset_view()
                self.page_rotations[self.left_pane.page_num] = 0
            
            self.save_config()
            self.statusBar().showMessage(self.tr("🔄 Current pages reset (zoom+pan+rotation) & splitter centered"), 1500)
            return

        # Ctrl+Shift+X: Clear all rotations for the entire book
        if key == Qt.Key_X and modifiers == (Qt.ControlModifier | Qt.ShiftModifier):
            # Clear all page rotations
            self.page_rotations.clear()
            
            # Reset both panes' view states
            self.left_pane.reset_view()
            self.right_pane.reset_view()
            
            # Also clear any stored annotations view states if needed (though annotations don't store view)
            self.save_config()
            self.render_facing()  # Re-render to apply rotation=0 to all pages
            self.statusBar().showMessage(self.tr("🗑️ All page rotations cleared for entire book!"), 2000)
            return
        # X: Reset zoom AND rotation on focused pane
        if key == Qt.Key_X and modifiers == Qt.NoModifier:
            if focused_on_left:
                self.left_pane.reset_view()
                self.page_rotations[self.left_pane.page_num] = 0
                self.save_config()
                self.statusBar().showMessage(self.tr("⬅️ Left reset (zoom+rotation)"), 1000)
            else:
                self.right_pane.reset_view()
                self.page_rotations[self.right_pane.page_num] = 0
                self.save_config()
                self.statusBar().showMessage(self.tr("➡️ Right reset (zoom+rotation)"), 1000)
            return

        # ~: Rotate clockwise on focused pane
        if key == Qt.Key_QuoteLeft and modifiers == Qt.NoModifier:
            if focused_on_left:
                self.left_pane.rotate_clockwise()
                self.page_rotations[str(self.left_pane.page_num)] = self.left_pane.rotation
                self.save_config()
                self.statusBar().showMessage(self.tr("🔄 Left rotated to {angle}°").format(angle=self.left_pane.rotation), 1000)
            else:
                self.right_pane.rotate_clockwise()
                self.page_rotations[str(self.right_pane.page_num)] = self.right_pane.rotation
                self.save_config()
                self.statusBar().showMessage(self.tr("🔄 Right rotated to {angle}°").format(angle=self.right_pane.rotation), 1000)
            return

        # B: 自由画笔
        if key == Qt.Key_B and modifiers == Qt.NoModifier:
            self.set_annotation_mode("pen")
            self.statusBar().showMessage(self.tr("✏️ Pen mode (press ESC to cancel)"), 2000)
            return
            
        # H: 矩形高亮
        if key == Qt.Key_H and modifiers == Qt.NoModifier:
            self.set_annotation_mode("rect")
            self.statusBar().showMessage(self.tr("🔲 Highlight mode (press ESC to cancel)"), 2000)
            return
            
        # V: 文本框
        if key == Qt.Key_V and modifiers == Qt.NoModifier:
            self.set_annotation_mode("text")
            self.statusBar().showMessage(self.tr("📝 Text mode (press ESC to cancel)"), 2000)
            return

        # Z: Toggle single/double page mode
        if key == Qt.Key_Z and modifiers == Qt.NoModifier:
            self.single_page_mode = not self.single_page_mode
            if self.single_page_mode:
                self.left_locked = False
            self.save_config()
            self.render_facing()
            mode_name = self.tr("Single") if self.single_page_mode else self.tr("Double")
            self.statusBar().showMessage(self.tr("↔️ Mode: {mode}-page").format(mode=mode_name), 1500)
            return

        # C: Toggle left pane lock/follow (only in double mode)
        if key == Qt.Key_C and modifiers == Qt.NoModifier and not self.single_page_mode:
            self.left_locked = not self.left_locked
            if not self.left_locked:
                self.locked_left_page = max(1, self.right_page - 1)
            self.render_facing()
            status = self.tr("Locked") if self.left_locked else self.tr("Following")
            self.statusBar().showMessage(f"⬅️ Left pane: {status}", 1500)
            self.save_config()
            return

        # S: Save config manually (or flush notebook)
        if key == Qt.Key_S and modifiers == Qt.NoModifier:
            if self.notebook_source_path is not None:
                # 笔记本模式：立即打包回源 .tactinote 文件
                self.save_config()
                self._flush_notebook_to_source()
            else:
                # 普通PDF模式：保存到 AppData
                self.save_config()
                self.statusBar().showMessage(self.tr("💾 Configuration saved"), 1500)
            return

        # SPACE: Jump to Home
        if key == Qt.Key_Space and modifiers == Qt.NoModifier:
            target = self.home_page
            self.jump_to_page(target)

        # Ctrl+Space: Reset Home to current page
        if key == Qt.Key_Space and modifiers == Qt.ControlModifier:
            self.home_page = self.right_page
            self.save_config()
            self.statusBar().showMessage(self.tr("🔄 Home reset to P.{page}").format(page=self.home_page), 2000)
            return
        # Ctrl+A: Navigate back in history
        if key == Qt.Key_A and modifiers == Qt.ControlModifier:
            self.navigate_back()
            return
        # A/D: Single step
        if key == Qt.Key_A and modifiers == Qt.NoModifier:
            focused_on_left = self.left_pane.hasFocus() and not self.single_page_mode
            current_page = self.left_pane.page_num if focused_on_left else self.right_page
            self.jump_to_page(current_page - 1)
            return
        if key == Qt.Key_D and modifiers == Qt.NoModifier:
            focused_on_left = self.left_pane.hasFocus() and not self.single_page_mode
            current_page = self.left_pane.page_num if focused_on_left else self.right_page
            self.jump_to_page(current_page + 1)
            return

        # Digit keys for multiplier
        digit_map = {getattr(Qt, f'Key_{i}'): i for i in range(1, 10)}
        if key in digit_map and modifiers == Qt.NoModifier:
            self.flip_multiplier = digit_map[key]
            self.save_config()
            self.statusBar().showMessage(self.tr("🔁 Flip ×{x}").format(x=self.flip_multiplier), 1500)
            return

        # Arrow keys
        if key == Qt.Key_Left and modifiers == Qt.NoModifier:
            focused_on_left = self.left_pane.hasFocus() and not self.single_page_mode
            current_page = self.left_pane.page_num if focused_on_left else self.right_page
            self.jump_to_page(current_page - self.flip_multiplier)
            return
        if key == Qt.Key_Right and modifiers == Qt.NoModifier:
            focused_on_left = self.left_pane.hasFocus() and not self.single_page_mode
            current_page = self.left_pane.page_num if focused_on_left else self.right_page
            self.jump_to_page(current_page + self.flip_multiplier)
            return

        # F/G
        if key == Qt.Key_F and modifiers == Qt.NoModifier:
            self.search_text()
            return
        if key == Qt.Key_G and modifiers == Qt.NoModifier:
            self.goto_page()
            return
        # Ctrl+G: Calibrate page number offset
        if key == Qt.Key_G and modifiers == Qt.ControlModifier:
            self.calibrate_page_number_offset()
            return
        # Ctrl+Shift+G: Clear page number offset
        if key == Qt.Key_G and modifiers == (Qt.ControlModifier | Qt.ShiftModifier):
            self.clear_page_number_offset()
            return
        # Clear all config: Ctrl+Shift+R
        if key == Qt.Key_R and modifiers == (Qt.ControlModifier | Qt.ShiftModifier):
            reply = QMessageBox.question(
                self, self.tr("Clear All Config"),
                self.tr("Are you sure you want to clear ALL settings (bookmarks, home, mode, etc.) for this PDF?"),
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self.home_page = 1
                self.bookmarks = {}
                self.flip_multiplier = 1
                self.single_page_mode = False
                self.left_locked = False
                self.locked_left_page = 1
                self.annotations = {}
                self.page_rotations = {}
                self.search_highlights = {}  # 清空搜索高亮
                self.current_search_term = ""
                self.current_pen_color_index = 0
                self.current_rect_color_index = 0
                self.current_text_color_index = 0
                self.update_pane_colors()
                self.save_config()
                self.render_facing()
                self.refresh_bookmark_panel()
                self.statusBar().showMessage(self.tr("🗑️ All configuration cleared!"), 2000)
            return

        # 清除当前页面批注: Ctrl+Shift+C
        if key == Qt.Key_C and modifiers == (Qt.ControlModifier | Qt.ShiftModifier):
            self.clear_current_page_annotations()
            return
            
        # 撤销批注: Ctrl+Z
        if key == Qt.Key_Z and modifiers == Qt.ControlModifier:
            self.undo_last_annotation()
            return
        # N: Toggle bookmark/TOC panel visibility
        if key == Qt.Key_N and modifiers == Qt.NoModifier:
            self.toggle_bookmark_panel()
            return
        # Bookmarks: Q to P
        bookmark_key_map = {
            Qt.Key_Q: 'Q', Qt.Key_W: 'W', Qt.Key_E: 'E', Qt.Key_R: 'R',
            Qt.Key_T: 'T', Qt.Key_Y: 'Y', Qt.Key_U: 'U', Qt.Key_I: 'I',
            Qt.Key_O: 'O', Qt.Key_P: 'P'
        }

        if key in bookmark_key_map:
            char = bookmark_key_map[key]

            if modifiers == Qt.AltModifier:
                if char in self.bookmarks:
                    name = self.bookmarks[char].get("name", "") or f"P.{self.bookmarks[char]['page']}"
                    del self.bookmarks[char]
                    self.save_config()
                    self.refresh_bookmark_panel()
                    self.statusBar().showMessage(self.tr("🗑️ Cleared '{char}': {name}").format(char=char, name=name), 2000)
                else:
                    self.statusBar().showMessage(self.tr("ℹ️ '{char}' was empty").format(char=char), 1000)
                return

            elif modifiers == Qt.ControlModifier:
                current_page = self.right_page if not focused_on_left else self.left_pane.page_num
                name, ok = QInputDialog.getText(
                    self,
                    self.tr("Set Bookmark") + f" {char}",
                    self.tr("Name for '{char}' (P.{page}):").format(char=char, page=current_page),
                    text=self.bookmarks.get(char, {}).get("name", "")
                )
                if ok:
                    self.bookmarks[char] = {"page": current_page, "name": name.strip()}
                    self.save_config()
                    self.refresh_bookmark_panel()
                    display_name = name.strip() or f"P.{current_page}"
                    self.statusBar().showMessage(self.tr("🔖 '{char}' → {display_name}").format(char=char, display_name=display_name), 2000)
                return

            elif modifiers == Qt.NoModifier:
                if char in self.bookmarks:
                    bm = self.bookmarks[char]
                    self.jump_to_page(bm["page"])
                    display_name = bm.get("name", "").strip() or f"P.{bm['page']}"
                    self.statusBar().showMessage(self.tr("⏩ '{char}': {display_name}").format(char=char, display_name=display_name), 1500)
                else:
                    self.statusBar().showMessage(self.tr("⚠️ '{char}' not set").format(char=char), 1500)
                return

        # ESC: 取消批注模式
        if key == Qt.Key_Escape and modifiers == Qt.NoModifier:
            self.left_pane.cancel_annotation()
            self.right_pane.cancel_annotation()
                        # 2. 退出文字选取模式 (通知两个窗格)
            self.left_pane.set_text_selection_mode(False)
            self.right_pane.set_text_selection_mode(False)
            return

        super().keyPressEvent(event)

    def toggle_fullscreen(self):
        """切换全屏模式"""
        if self.isFullScreen():
            self.showNormal()
            # 退出全屏时显示菜单栏和状态栏
            self.menuBar().setVisible(True)
            self.statusBar().setVisible(True)
        else:
            self.showFullScreen()
            # 进入全屏时隐藏菜单栏和状态栏
            self.menuBar().setVisible(False)
            self.statusBar().setVisible(False)
    
    def toggle_text_selection_mode(self):
        """全局切换文字选取模式（同步左右窗格）"""
        new_state = not self.right_pane.text_selection_mode
        self.left_pane.set_text_selection_mode(new_state)
        self.right_pane.set_text_selection_mode(new_state)
        status = "ON" if new_state else "OFF"
        self.statusBar().showMessage(f"🔤 Text Selection Mode: {status}", 2000)    
    def show_help(self):
        viewer = MarkdownViewer(self.tr("Help"), self.tr("help.md"), self)
        viewer.exec_()

    def show_about(self):
        viewer = MarkdownViewer(self.tr("About"), self.tr("about.md"), self)
        viewer.exec_()
    
    def closeEvent(self, event):
        if self.doc:
            self.save_config()
            # === 新增：如果是笔记本模式，退出时打包回源文件 ===
            if self.notebook_source_path is not None:
                self._flush_notebook_to_source()
            # =============================================
            self.doc.close()
        event.accept()

class MarkdownViewer(QDialog):
    def __init__(self, title, md_file, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(800, 600)
        
        # 使用 QTextEdit（只读、纯文本/markdown 渲染）
        self.text_edit = QTextBrowser()
        self.text_edit.setReadOnly(True)
        # === 新增：设置更大的默认字体 ===
        font = self.text_edit.font()
        font.setPointSize(13)  # 默认通常是 9-10，12 更清晰
        self.text_edit.setFont(font)
        # 构建文件路径
        if getattr(sys, 'frozen', False):
            base_path = sys._MEIPASS
        else:
            base_path = os.path.dirname(os.path.abspath(__file__))
        full_path = os.path.join(base_path, md_file)
        
        # 读取并渲染 Markdown
        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                md_content = f.read()
            html = markdown.markdown(md_content, extensions=['fenced_code'])
            self.text_edit.setHtml(html)
        except Exception as e:
            self.text_edit.setPlainText(f"无法加载帮助文件: {md_file}\n错误: {str(e)}")
        
        layout = QVBoxLayout()
        layout.addWidget(self.text_edit)
        self.setLayout(layout)
if __name__ == "__main__":
    # === 修复：DPI 设置必须在 QApplication 之前 ===
    #QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    #QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)
    # ===========================================
    
    app = QApplication(sys.argv)
    initial_pdf = sys.argv[1] if len(sys.argv) > 1 else None
    window = TactiReader(initial_pdf)
    window.show()
    sys.exit(app.exec_())