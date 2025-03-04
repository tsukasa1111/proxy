import sys
import os
import tempfile
import urllib.request
import urllib.parse
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFileDialog, QMessageBox,
    QTableWidget, QTableWidgetItem, QSpinBox, QHeaderView,
    QDialog, QScrollArea, QComboBox
)
from PyQt5.QtCore import QUrl, Qt, QSize
from PyQt5.QtGui import QDesktopServices, QPixmap, QIcon

from reportlab.lib.pagesizes import A4, A3, portrait, landscape
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

# 左上を原点として画像を描画
def draw_image(pc: canvas.Canvas, page_size, image, x, y, w, h):
    pc.drawImage(image, x, page_size[1] - y - h, w, h)

# 左上を原点として矩形を描画（ガイドライン用）
def fill_rect(pc: canvas.Canvas, page_size, x, y, w, h, color=(1, 1, 1)):
    pc.setStrokeColorRGB(*color)
    pc.rect(x, page_size[1] - y - h, w, h, stroke=False, fill=True)

# 各画像とその印刷枚数のリストをもとにPDFを生成
def create_pdf(image_quantity_list, output_file, page_option):
    if page_option == "A3":
        ps = landscape(A3)
        grid_x = 6    # 横6枚
        grid_y = 3    # 縦3枚 (計18枚／ページ)
        begin = (22 * mm, 17 * mm)
    else:  # "A4"
        ps = portrait(A4)
        grid_x = 3    # 横3枚
        grid_y = 3    # 縦3枚 (計9枚／ページ)
        begin = (11 * mm, 17 * mm)

    card_size = (63 * mm, 88 * mm)
    margin = (1 * mm, 1 * mm)
    total_per_page = grid_x * grid_y

    pc = canvas.Canvas(output_file, pagesize=ps)

    images = []
    for image, qty in image_quantity_list:
        images.extend([image] * qty)

    for i, image in enumerate(images):
        x_pos = i % grid_x
        y_pos = (i % total_per_page) // grid_x
        x = begin[0] + x_pos * (card_size[0] + margin[0])
        y = begin[1] + y_pos * (card_size[1] + margin[1])
        draw_image(pc, ps, image, x, y, *card_size)

        if (x_pos, y_pos) == (grid_x - 1, grid_y - 1) or i == len(images) - 1:
            for col in range(grid_x + 1):
                if col == 0:
                    x_line = begin[0] - margin[0]
                else:
                    x_line = begin[0] + col * card_size[0] + (col - 1) * margin[0]
                fill_rect(pc, ps, x_line, 0, margin[0], ps[1])
            for row in range(grid_y + 1):
                if row == 0:
                    y_line = begin[1] - margin[1]
                else:
                    y_line = begin[1] + row * card_size[1] + (row - 1) * margin[1]
                fill_rect(pc, ps, 0, y_line, ps[0], margin[1])
            pc.showPage()

    pc.save()

# GUIアプリケーション本体
class CardProxyApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("プロキシ生成ツール")
        self.setAcceptDrops(True)
        # 一時ファイルのパスを保存するリスト
        self.temp_files = []
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout()

        size_layout = QHBoxLayout()
        size_label = QLabel("ページサイズ:")
        self.page_combo = QComboBox()
        self.page_combo.addItems(["A4", "A3"])
        size_layout.addWidget(size_label)
        size_layout.addWidget(self.page_combo)
        size_layout.addStretch()
        layout.addLayout(size_layout)
        
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["画像ファイル", "印刷枚数"])
        self.table.setIconSize(QSize(96, 96))
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        layout.addWidget(self.table)
        
        btn_layout = QHBoxLayout()
        self.add_button = QPushButton("画像追加")
        self.add_button.clicked.connect(self.add_images)
        btn_layout.addWidget(self.add_button)
        
        self.remove_button = QPushButton("選択削除")
        self.remove_button.clicked.connect(self.remove_selected)
        btn_layout.addWidget(self.remove_button)
        layout.addLayout(btn_layout)
        
        btn_layout2 = QHBoxLayout()
        self.preview_button = QPushButton("プレビュー")
        self.preview_button.clicked.connect(self.preview_pdf)
        btn_layout2.addWidget(self.preview_button)
        
        self.generate_button = QPushButton("生成")
        self.generate_button.clicked.connect(self.generate_pdf)
        btn_layout2.addWidget(self.generate_button)
        layout.addLayout(btn_layout2)
        
        self.setLayout(layout)
        self.table.cellDoubleClicked.connect(self.on_cell_double_clicked)
    
    def add_images(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "画像ファイルを選択", "", "Image Files (*.jpg *.png)"
        )
        if files:
            for file in files:
                self.add_image_to_table(file)
    
    def add_image_to_table(self, file):
        row = self.table.rowCount()
        self.table.insertRow(row)
        base_name = os.path.basename(file)
        item = QTableWidgetItem(base_name)
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        item.setData(Qt.UserRole, file)
        pixmap = QPixmap(file)
        if not pixmap.isNull():
            thumb = pixmap.scaled(96, 96, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            item.setIcon(QIcon(thumb))
        self.table.setItem(row, 0, item)
        spin = QSpinBox()
        spin.setMinimum(1)
        spin.setValue(1)
        self.table.setCellWidget(row, 1, spin)
        self.table.setRowHeight(row, 110)
    
    def remove_selected(self):
        selected = self.table.selectedItems()
        rows = set()
        for item in selected:
            rows.add(item.row())
        for row in sorted(rows, reverse=True):
            self.table.removeRow(row)
    
    def get_image_quantity_list(self):
        image_list = []
        for row in range(self.table.rowCount()):
            file_item = self.table.item(row, 0)
            if file_item:
                file_path = file_item.data(Qt.UserRole)
                spin = self.table.cellWidget(row, 1)
                if spin:
                    qty = spin.value()
                    image_list.append((file_path, qty))
        return image_list
    
    def on_cell_double_clicked(self, row, column):
        if column == 0:
            item = self.table.item(row, column)
            file_path = item.data(Qt.UserRole)
            if file_path and os.path.exists(file_path):
                self.show_image_dialog(file_path)
            else:
                QMessageBox.warning(self, "エラー", "画像ファイルが見つかりません")
    
    def show_image_dialog(self, file_path):
        dialog = QDialog(self)
        dialog.setWindowTitle(os.path.basename(file_path))
        scroll = QScrollArea(dialog)
        label = QLabel()
        pixmap = QPixmap(file_path)
        label.setPixmap(pixmap)
        label.setScaledContents(True)
        scroll.setWidget(label)
        layout = QVBoxLayout(dialog)
        layout.addWidget(scroll)
        dialog.resize(800, 600)
        dialog.exec_()
    
    def preview_pdf(self):
        image_quantity_list = self.get_image_quantity_list()
        if not image_quantity_list:
            QMessageBox.critical(self, "エラー", "画像が選択されていません")
            return
        page_option = self.page_combo.currentText()
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        temp_file.close()
        create_pdf(image_quantity_list, temp_file.name, page_option)
        QDesktopServices.openUrl(QUrl.fromLocalFile(temp_file.name))
        # プレビュー用PDFも一時ファイルリストに追加
        self.temp_files.append(temp_file.name)
    
    def generate_pdf(self):
        image_quantity_list = self.get_image_quantity_list()
        if not image_quantity_list:
            QMessageBox.critical(self, "エラー", "画像が選択されていません")
            return
        page_option = self.page_combo.currentText()
        file_path, _ = QFileDialog.getSaveFileName(
            self, "保存先を選択", "output.pdf", "PDF Files (*.pdf)"
        )
        if file_path:
            create_pdf(image_quantity_list, file_path, page_option)
            QMessageBox.information(self, "完了", f"PDFが生成されました:\n{file_path}")

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()
    
    def dropEvent(self, event):
        for url in event.mimeData().urls():
            print("Dropped URL:", url.toString())
            local_file = url.toLocalFile()
            if local_file and os.path.exists(local_file):
                file_path = local_file
            else:
                remote_url = url.toString()
                print("Remote URL:", remote_url)
                if remote_url.startswith("/"):
                    remote_url = "https://dm.takaratomy.co.jp" + remote_url
                    print("Converted to absolute URL:", remote_url)
                if "card/detail/" in remote_url:
                    parsed = urllib.parse.urlparse(remote_url)
                    qs = urllib.parse.parse_qs(parsed.query)
                    if "id" in qs:
                        card_id = qs["id"][0]
                        remote_url = "https://dm.takaratomy.co.jp/wp-content/card/cardthumb/" + card_id + ".jpg"
                        print("Converted detail URL to image URL:", remote_url)
                ext = os.path.splitext(remote_url)[1]
                if not ext:
                    ext = ".jpg"
                temp_fd, temp_path = tempfile.mkstemp(suffix=ext)
                os.close(temp_fd)
                try:
                    req = urllib.request.Request(remote_url, headers={'User-Agent': 'Mozilla/5.0'})
                    with urllib.request.urlopen(req) as response, open(temp_path, 'wb') as out_file:
                        out_file.write(response.read())
                    file_path = temp_path
                    # ダウンロードした一時ファイルをリストに追加
                    self.temp_files.append(file_path)
                except Exception as e:
                    QMessageBox.warning(self, "エラー", f"画像のダウンロードに失敗しました:\n{e}")
                    continue
            print("File path:", file_path)
            pixmap = QPixmap(file_path)
            if pixmap.isNull():
                QMessageBox.warning(self, "エラー", "ダウンロードしたファイルが画像として読み込めませんでした。")
                continue
            self.add_image_to_table(file_path)
        event.acceptProposedAction()
    
    def closeEvent(self, event):
        # プログラム終了時に、一時ファイルを削除
        for file in self.temp_files:
            if os.path.exists(file):
                try:
                    os.remove(file)
                except Exception as e:
                    print(f"Failed to remove temporary file {file}: {e}")
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = CardProxyApp()
    window.resize(800, 600)
    window.show()
    sys.exit(app.exec_())
