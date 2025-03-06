import sys
import os
import tempfile
import urllib.request
import urllib.parse
import re
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QPushButton, QLabel, QFileDialog, QMessageBox,
    QTableWidget, QTableWidgetItem, QSpinBox, QDoubleSpinBox, QHeaderView,
    QDialog, QScrollArea, QComboBox, QCheckBox, QMenu
)
from PyQt5.QtCore import QUrl, Qt, QSize, QPoint
from PyQt5.QtGui import QDesktopServices, QPixmap, QIcon

from reportlab.lib.pagesizes import A4, A3, portrait, landscape
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

# 左上を原点として画像を描画
def draw_image(pc: canvas.Canvas, page_size, image, x, y, w, h):
    pc.drawImage(image, x, page_size[1] - y - h, w, h)

# 左上を原点として矩形（ガイドライン）を描画
def fill_rect(pc: canvas.Canvas, page_size, x, y, w, h, color=(1, 1, 1)):
    pc.setStrokeColorRGB(*color)
    pc.rect(x, page_size[1] - y - h, w, h, stroke=False, fill=True)

# 画像と枚数リストからPDFを生成
def create_pdf(image_quantity_list, output_file, page_option, draw_guidelines=True, remove_margin=False, card_size_mode="標準サイズ", custom_card_size=None):
    # ページサイズの設定（A3 は横置き、A4 は縦置き）
    if page_option == "A3":
        ps = landscape(A3)
    else:
        ps = portrait(A4)
    
    # カードサイズの決定
    if card_size_mode == "標準サイズ":
        card_width, card_height = 63.5 * mm, 88.9 * mm
    elif card_size_mode == "任意のサイズ":
        if custom_card_size is not None:
            card_width, card_height = custom_card_size[0] * mm, custom_card_size[1] * mm
        else:
            card_width, card_height = 63.5 * mm, 88.9 * mm
    else:
        card_width, card_height = 63.5 * mm, 88.9 * mm

    # カード間の隙間（余白）
    h_gap = 0 * mm if remove_margin else 1 * mm
    v_gap = 0 * mm if remove_margin else 1 * mm

    # ページ全体の幅・高さを使ってグリッド数を計算
    grid_x = int((ps[0] + h_gap) // (card_width + h_gap))
    grid_y = int((ps[1] + v_gap) // (card_height + v_gap))
    if grid_x < 1: grid_x = 1
    if grid_y < 1: grid_y = 1
    total_per_page = grid_x * grid_y

    # 配置開始位置（左上端 = (0,0)）
    x_start = 0
    y_start = 0

    pc = canvas.Canvas(output_file, pagesize=ps)
    images = []
    for image, qty in image_quantity_list:
        images.extend([image] * qty)

    for i, image in enumerate(images):
        page_index = i % total_per_page
        col = page_index % grid_x
        row = page_index // grid_x
        x = x_start + col * (card_width + h_gap)
        y = y_start + row * (card_height + v_gap)
        draw_image(pc, ps, image, x, y, card_width, card_height)

        # ページの最後または最終画像でページを確定
        if (page_index == total_per_page - 1) or (i == len(images) - 1):
            if draw_guidelines:
                # 縦方向ガイドライン：ページ全体の高さまで
                for col in range(grid_x + 1):
                    if col == 0:
                        x_line = x_start
                    else:
                        x_line = x_start + col * (card_width + h_gap) - h_gap
                    fill_rect(pc, ps, x_line, 0, h_gap, ps[1])
                # 横方向ガイドライン：ページ全体の幅まで
                for row in range(grid_y + 1):
                    if row == 0:
                        y_line = y_start
                    else:
                        y_line = y_start + row * (card_height + v_gap) - v_gap
                    fill_rect(pc, ps, 0, y_line, ps[0], v_gap)
            pc.showPage()
    pc.save()

# GUIアプリケーション本体
class CardProxyApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("プロキシ生成ツール")
        self.setAcceptDrops(True)
        self.temp_files = []  # 一時ファイルパス保持用
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        
        # オプションエリア（グループボックス）のレイアウト内に「i」ボタンを右端に配置
        options_group = QGroupBox("オプション")
        options_layout = QHBoxLayout()
        
        # ページサイズ選択
        page_label = QLabel("ページサイズ:")
        self.page_combo = QComboBox()
        self.page_combo.addItems(["A4", "A3"])
        options_layout.addWidget(page_label)
        options_layout.addWidget(self.page_combo)
        
        # カードサイズ選択（「標準サイズ」と「任意のサイズ」）
        size_label = QLabel("カードサイズ:")
        self.size_combo = QComboBox()
        self.size_combo.addItems(["標準サイズ", "任意のサイズ"])
        options_layout.addWidget(size_label)
        options_layout.addWidget(self.size_combo)
        self.size_combo.currentTextChanged.connect(self.on_size_combo_changed)
        
        # 任意のサイズ入力領域（初期は非表示）
        self.custom_size_widget = QWidget()
        custom_layout = QHBoxLayout()
        custom_layout.setContentsMargins(0, 0, 0, 0)
        custom_layout.addWidget(QLabel("幅(mm):"))
        self.custom_width_spin = QDoubleSpinBox()
        self.custom_width_spin.setRange(1, 500)
        self.custom_width_spin.setDecimals(1)
        self.custom_width_spin.setValue(63)
        custom_layout.addWidget(self.custom_width_spin)
        custom_layout.addWidget(QLabel("高さ(mm):"))
        self.custom_height_spin = QDoubleSpinBox()
        self.custom_height_spin.setRange(1, 500)
        self.custom_height_spin.setDecimals(1)
        self.custom_height_spin.setValue(88)
        custom_layout.addWidget(self.custom_height_spin)
        self.custom_size_widget.setLayout(custom_layout)
        self.custom_size_widget.setVisible(False)
        options_layout.addWidget(self.custom_size_widget)
        
        # ガイドライン・余白オプション
        self.guidelines_checkbox = QCheckBox("ガイドラインを描画")
        self.guidelines_checkbox.setChecked(True)
        options_layout.addWidget(self.guidelines_checkbox)
        self.margin_checkbox = QCheckBox("余白を削除")
        self.margin_checkbox.setChecked(False)
        options_layout.addWidget(self.margin_checkbox)
        
        # 右端に余白を入れて「i」ボタンを配置
        options_layout.addStretch()
        info_button = QPushButton("i")
        info_button.setMaximumSize(30, 30)
        info_button.clicked.connect(self.show_help)
        options_layout.addWidget(info_button)
        
        options_group.setLayout(options_layout)
        layout.addWidget(options_group)
        self.margin_checkbox.stateChanged.connect(self.update_options)

        # 画像と枚数のテーブル
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["画像ファイル", "印刷枚数"])
        self.table.setIconSize(QSize(96, 96))
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        layout.addWidget(self.table)

        # 画像追加・削除ボタンエリア
        btn_layout = QHBoxLayout()
        self.add_button = QPushButton("画像追加")
        self.add_button.clicked.connect(self.add_images)
        btn_layout.addWidget(self.add_button)
        self.delete_button = QPushButton("削除")
        self.delete_button.setEnabled(False)
        self.delete_button.clicked.connect(self.remove_selected)
        btn_layout.addWidget(self.delete_button)
        layout.addLayout(btn_layout)

        # プレビュー／生成ボタンエリア
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
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)
        self.table.itemSelectionChanged.connect(self.update_delete_button)
    
    def show_help(self):
        help_text = (
            "【使い方】\n\n"
            "1. 画像追加ボタンまたはドラッグ＆ドロップでカード画像を追加します。\n"
            "2. 各画像に対して印刷枚数を設定してください。\n"
            "3. オプションでページサイズ（A4 または A3）とカードサイズを設定できます。\n"
            "   カードサイズの選択肢は「標準サイズ」と「任意のサイズ」です。\n"
            "   標準サイズは 63.5mm × 88.9mm となっています。\n"
            "   任意のサイズを選択した場合は、右側の入力欄に幅と高さ（単位: mm）を入力してください。\n"
            "4. ガイドラインや余白の表示・削除も設定可能です。\n"
            "5. プレビューでPDFの配置を確認し、生成ボタンでPDFファイルとして保存します。\n"
            "※ ドラッグ＆ドロップにも対応しています。"
        )
        QMessageBox.information(self, "使い方", help_text)
    
    def on_size_combo_changed(self, text):
        self.custom_size_widget.setVisible(text == "任意のサイズ")
    
    def update_options(self):
        if self.margin_checkbox.isChecked():
            self.guidelines_checkbox.setChecked(False)
            self.guidelines_checkbox.setEnabled(False)
        else:
            self.guidelines_checkbox.setEnabled(True)
    
    def update_delete_button(self):
        self.delete_button.setEnabled(bool(self.table.selectedItems()))
    
    def show_context_menu(self, pos):
        index = self.table.indexAt(pos)
        if index.isValid():
            menu = QMenu(self)
            delete_action = menu.addAction("削除")
            action = menu.exec_(self.table.viewport().mapToGlobal(pos))
            if action == delete_action:
                self.table.removeRow(index.row())
    
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
        spin.setMinimumHeight(40)
        spin.setStyleSheet("""
            QSpinBox { font-size: 16pt; padding: 5px; min-width: 80px; }
            QSpinBox::up-button, QSpinBox::down-button { width: 30px; height: 30px; }
        """)
        self.table.setCellWidget(row, 1, spin)
        self.table.setRowHeight(row, 110)
    
    def remove_selected(self):
        selected = self.table.selectedItems()
        rows = set(item.row() for item in selected)
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
        card_size_mode = self.size_combo.currentText()
        custom_size = (self.custom_width_spin.value(), self.custom_height_spin.value()) if card_size_mode == "任意のサイズ" else None
        draw_guidelines = self.guidelines_checkbox.isChecked()
        remove_margin = self.margin_checkbox.isChecked()
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        temp_file.close()
        create_pdf(image_quantity_list, temp_file.name, page_option, draw_guidelines, remove_margin, card_size_mode, custom_size)
        QDesktopServices.openUrl(QUrl.fromLocalFile(temp_file.name))
        self.temp_files.append(temp_file.name)
    
    def generate_pdf(self):
        image_quantity_list = self.get_image_quantity_list()
        if not image_quantity_list:
            QMessageBox.critical(self, "エラー", "画像が選択されていません")
            return
        page_option = self.page_combo.currentText()
        card_size_mode = self.size_combo.currentText()
        custom_size = (self.custom_width_spin.value(), self.custom_height_spin.value()) if card_size_mode == "任意のサイズ" else None
        draw_guidelines = self.guidelines_checkbox.isChecked()
        remove_margin = self.margin_checkbox.isChecked()
        file_path, _ = QFileDialog.getSaveFileName(
            self, "保存先を選択", "output.pdf", "PDF Files (*.pdf)"
        )
        if file_path:
            create_pdf(image_quantity_list, file_path, page_option, draw_guidelines, remove_margin, card_size_mode, custom_size)
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
                        candidate1 = "https://dm.takaratomy.co.jp/wp-content/card/cardthumb/" + card_id + ".jpg"
                        candidate2 = "https://dm.takaratomy.co.jp/wp-content/card/cardthumb/" + card_id + "a.jpg"
                        print("Converted detail URL to image URL candidates:", candidate1, candidate2)
                        success = False
                        file_path = None
                        for candidate in [candidate1, candidate2]:
                            try:
                                temp_fd, temp_path = tempfile.mkstemp(suffix=".jpg")
                                os.close(temp_fd)
                                req = urllib.request.Request(candidate, headers={'User-Agent': 'Mozilla/5.0'})
                                with urllib.request.urlopen(req) as response, open(temp_path, 'wb') as out_file:
                                    out_file.write(response.read())
                                pixmap = QPixmap(temp_path)
                                if not pixmap.isNull():
                                    file_path = temp_path
                                    success = True
                                    break
                                else:
                                    os.remove(temp_path)
                                    print("Candidate failed (invalid image):", candidate)
                            except Exception as e:
                                print("Failed candidate:", candidate, "Error:", e)
                        if not success:
                            QMessageBox.warning(self, "エラー", f"画像のダウンロードに失敗しました:\n{remote_url}")
                            continue
                        self.temp_files.append(file_path)
                    else:
                        continue
                else:
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
