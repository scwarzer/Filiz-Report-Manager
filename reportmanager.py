import os
import sys
import base64
import hashlib
import configparser

import pandas as pd
from cryptography.fernet import Fernet

from PyQt5.QtCore import Qt, QDateTime, QThread, pyqtSignal
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLineEdit, QPushButton,
    QVBoxLayout, QHBoxLayout, QTextEdit, QPlainTextEdit, QFileDialog,
    QMessageBox, QCheckBox, QGridLayout, QListWidget, QGroupBox,
    QDateTimeEdit, QDialogButtonBox, QDialog, QLabel, QSizePolicy
)

from defaultTests import DataTests, DefaultTests
from gpsCellular import gpsCellularAnalyzer
from dataFetch import FetchWorker


class MainApp(QMainWindow):
    def __init__(self):
        super().__init__()

        # === Konsolu İnşa Et ===
        self.init_console()

        # === Uygulama Bilgisi ===
        self.version = "1.0.0"
        self.setWindowTitle(f"Filiz Report Manager {self.version}")

        self.setFixedSize(450,500)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)  # Yatay sabit, dikey esnek

        # === Ana Merkez Widget ve Layout ===
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)

        # === Test Yardımcısı Sınıf ===
        self.tester = DataTests()

        # === Arayüzü İnşa Et ===
        self.build_main_ui()
        self.load_portal_key_from_config()

    def build_main_ui(self):

        # === MENU BAR ===
        menu_bar = self.menuBar()

        # === FILE MENU ===

        file_menu = menu_bar.addMenu("File")
        open_drep_action = file_menu.addAction("Open .drep File")
        open_drep_action.triggered.connect(self.open_drep_file)

        create_drep_action = file_menu.addAction("Create .drep File")
        create_drep_action.triggered.connect(self.create_drep_file)

        # === HELP MENU ===

        help_menu = menu_bar.addMenu("Help")
        open_console_action = help_menu.addAction("Open Console")
        open_console_action.triggered.connect(lambda: self.console_window.show())

        credentials_action = help_menu.addAction("Set Credentials")
        credentials_action.triggered.connect(self.open_credentials_dialog)

        # === ANA LAYOUT ===
        device_layout = QVBoxLayout()

        # === DEVICE INFO GROUP ===
        device_group = QGroupBox("Device Configuration")
        device_group_layout = QVBoxLayout()

        # === 1. SATIR: DEVICE ID LAYOUT (IN GRID) ===
        row1 = QGridLayout()

        self.device_label = QLabel("Device ID:")
        self.device_display = QLabel("N/A")
        self.device_display.setFrameStyle(QLabel.Panel | QLabel.Sunken)
        self.device_display.setMinimumWidth(200)
        self.device_display.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.device_display.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)


        row1.addWidget(self.device_label, 0, 0)
        row1.addWidget(self.device_display, 0, 1)

        row1.setColumnStretch(0, 1)
        row1.setColumnStretch(1, 4)

        device_group_layout.addLayout(row1)

        # === 2. SATIR: START/END DATE LAYOUT (IN GRID) ===
        row2 = QGridLayout()

        self.start_date_label = QLabel("Start Date:")
        self.start_date_picker = QDateTimeEdit()
        self.start_date_picker.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        self.start_date_picker.setCalendarPopup(True)

        update_range_btn = QPushButton("Update Date Range")
        update_range_btn.clicked.connect(self.update_date_range)

        self.end_date_label = QLabel("End Date:")
        self.end_date_picker = QDateTimeEdit()
        self.end_date_picker.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        self.end_date_picker.setCalendarPopup(True)
        self.end_date_picker.setEnabled(False)

        self.end_date_checkbox = QCheckBox("Enable End Date")
        self.end_date_checkbox.stateChanged.connect(lambda state: self.end_date_picker.setEnabled(state == Qt.Checked))

        row2.addWidget(self.start_date_label, 0, 0)
        row2.addWidget(self.start_date_picker, 0, 1)
        row2.addWidget(update_range_btn, 0, 2)

        row2.addWidget(self.end_date_label, 1, 0)
        row2.addWidget(self.end_date_picker, 1, 1)
        row2.addWidget(self.end_date_checkbox, 1, 2)

        row2.setColumnStretch(0, 1)
        row2.setColumnStretch(1, 2)
        row2.setColumnStretch(2, 2)

        device_group_layout.addLayout(row2)

        device_group.setLayout(device_group_layout)
        device_layout.addWidget(device_group)

        # === FETCH GROUP ===
        fetch_group = QGroupBox("Fetch Data")
        fetch_group_layout = QHBoxLayout()

        self.fetch_status_label = QLabel("Ready.")
        self.fetch_status_label.setStyleSheet("color: gray; font-weight: bold;")

        self.update_btn = QPushButton("   Fetch Data   ")
        self.update_btn.clicked.connect(self.fetch_data)

        fetch_group_layout.addWidget(self.fetch_status_label)
        fetch_group_layout.addStretch()
        fetch_group_layout.addWidget(self.update_btn)

        fetch_group.setLayout(fetch_group_layout)
        device_layout.addWidget(fetch_group)

        # === RUN TEST GROUP ===
        test_group = QGroupBox("Run Test")
        test_group_layout = QVBoxLayout()

        # Test List
        self.test_list = QListWidget()
        self.test_list.addItem("1. Default Tests")
        self.test_list.addItem("2. GPS-Cellular Analyze")
        self.test_list.setSelectionMode(QListWidget.SingleSelection)
        self.test_list.setMinimumHeight(200)
        test_group_layout.addWidget(self.test_list)

        # Run Button (aligned right)
        run_btn_layout = QHBoxLayout()
        run_btn_layout.addStretch()
        self.run_test_btn = QPushButton("   Run Selected Test    ")
        self.run_test_btn.clicked.connect(self.run_selected_test)
        run_btn_layout.addWidget(self.run_test_btn)
        test_group_layout.addLayout(run_btn_layout)

        # Group finalize
        test_group.setLayout(test_group_layout)
        device_layout.addWidget(test_group)

        # Main layout finalize
        self.main_layout.addLayout(device_layout)
        self.device_display.setFocus()

        print(f"Status: App builded. Version: {self.version}")

    def init_console(self):
        self.console_window = QWidget()
        self.console_window.setWindowTitle("Console")
        self.console_window.setFixedSize(600, 400)

        layout = QVBoxLayout()
        self.console_widget = ConsoleWidget()
        layout.addWidget(self.console_widget)
        self.console_window.setLayout(layout)

        # Standart çıktıyı yönlendir
        sys.stdout = self.console_widget
        sys.stderr = self.console_widget


    def update_date_range(self):
        try:
            start_str = self.start_date_picker.dateTime().toString("yyyy-MM-dd HH:mm:ss")
            self.start_date = pd.to_datetime(start_str)

            end_str = None
            if self.end_date_checkbox.isChecked():
                end_str = self.end_date_picker.dateTime().toString("yyyy-MM-dd HH:mm:ss")
                self.end_date = pd.to_datetime(end_str)
            else:
                self.end_date = None

            device_id = self.device_display.text().strip()
            if not device_id:
                QMessageBox.warning(self, "Warning", "Device ID is empty.")
                print("Status: update_date_range aborted - device ID is empty.")
                return

            drep_path = os.path.join(os.getcwd(), "Device Reports", f"{device_id}.drep")
            if not os.path.exists(drep_path):
                QMessageBox.warning(self, "Warning",
                                    f"No .drep file found for device ID {device_id}. Please create one first.")
                print(f"Status: update_date_range aborted - .drep file not found for ID {device_id}.")
                return

            config = configparser.ConfigParser()
            config.read(drep_path)

            if "INFO" not in config:
                config["INFO"] = {}

            config["INFO"]["startDate"] = start_str
            print(f"Status: Start date saved as {start_str}")

            if end_str:
                config["INFO"]["endDate"] = end_str
                print(f"Status: End date saved as {end_str}")
            elif "endDate" in config["INFO"]:
                del config["INFO"]["endDate"]
                print("Status: End date removed from config.")

            with open(drep_path, "w") as file:
                config.write(file)

            print("Status: Date range updated in .drep file.")

            # TEKRAR OKUMA YAP
            self.load_drep_file(drep_path)


            msg = f"Start Date: {start_str}"
            msg += f"\nEnd Date: {end_str}" if end_str else "\nEnd Date: Disabled"
            QMessageBox.information(self, "Updated", msg)

        except Exception as e:
            print(f"Status: Failed to update date range. Error: {e}")
            QMessageBox.critical(self, "Error", f"Failed to update date range:\n{e}")

    def fetch_data(self):
        if hasattr(self, "device_id") and str(self.device_id).isdigit():
            device_id = int(self.device_id)

        if device_id is None:
            QMessageBox.warning(self, "Warning", "Please enter a valid ID.")
            return

        try:
            config = configparser.ConfigParser()
            if not os.path.exists("config.ini"):
                raise FileNotFoundError("config.ini not found.")
            config.read("config.ini")
            if "PORTAL" not in config or "Key" not in config["PORTAL"]:
                raise ValueError("Key not found in config.ini")

            portal_key = config["PORTAL"]["Key"]

            manager = CredentialManager()
            email, password = manager.decrypt(portal_key)

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load credentials:\n{e}")
            return

        # Fetch başlarken:
        self.fetch_status_label.setText("Fetching...")
        self.fetch_status_label.setStyleSheet("color: gray; font-weight: bold;")

        self.set_loading(True)

        def on_finished(df):
            self.set_loading(False)
            if df is not None and not df.empty:
                df["LogDate"] = pd.to_datetime(df["LogDate"], errors="coerce")

                # Start Date filtresi
                if hasattr(self, "start_date") and self.start_date:
                    df = df[df["LogDate"] >= self.start_date]

                # End Date filtresi
                if hasattr(self, "end_date") and self.end_date:
                    if str(self.end_date) != "2000-01-01 00:00:00":
                        df = df[df["LogDate"] <= self.end_date]

                self.df_all = df
                print(f"Status: {len(df)} records after filtering by LogDate range.")

                # Başarıyla tamamlanırsa:
                self.fetch_status_label.setText("Fetch Successful.")
                self.fetch_status_label.setStyleSheet("color: green; font-weight: bold;")


            else:
                print("Warning: Dataframe is empty.")
                self.fetch_status_label.setText("Fetch Failed.")
                self.fetch_status_label.setStyleSheet("color: red; font-weight: bold;")

        def on_error(message):
            self.set_loading(False)
            print(f"Error: Error during fetch: {message}")

            # Hata durumunda:
            self.fetch_status_label.setText("Fetch Failed.")
            self.fetch_status_label.setStyleSheet("color: red; font-weight: bold;")

        self.thread = QThread()
        self.worker = FetchWorker(device_id, email, password)
        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(on_finished)
        self.worker.error.connect(on_error)

        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)

        self.thread.start()

    def run_selected_test(self):
        selected_item = self.test_list.currentItem()
        if not selected_item:
            QMessageBox.warning(self, "Warning", "Please select a test.")
            return

        text = selected_item.text()

        if text == "1. Default Tests":
            self.run_default_tests()

        elif text == "2. GPS-Cellular Analyze":
            self.run_gpscellular_Analyze()

        else:
            QMessageBox.warning(self, "Warning", "Unknown test selected.")

    def run_default_tests(self):
        if not hasattr(self, 'df_all') or self.df_all is None:
            QMessageBox.warning(self, "Warning", "Please fetch data first.")
            return

        try:
            dialog = DefaultTests(
                tester=self.tester,
                df_all=self.df_all,
                device_id_input=self.device_display,
                selected_tests=None
            )
            dialog.exec_()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"An unexpected error occurred:\n{str(e)}")

    def run_gpscellular_Analyze(self):
        if not hasattr(self, 'df_all') or self.df_all is None:
            QMessageBox.warning(self, "Warning", "Please fetch data first.")
            return

        try:
            dialog = gpsCellularAnalyzer(df=self.df_all, parent=self)

            if not dialog.success:
                QMessageBox.warning(self, "Warning", "Could not generate map. Missing or invalid coordinates.")
                return

            dialog.exec_()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to open map viewer:\n{e}")

    def load_drep_file(self, file_path: str):
        try:
            config = configparser.ConfigParser()
            config.read(file_path)

            if "INFO" not in config:
                raise ValueError("Missing [INFO] section in .drep file")

            # === Device ID
            if "deviceId" in config["INFO"]:
                self.device_id = config["INFO"]["deviceId"]
                self.device_display.setText(self.device_id)

                # Fetch durumunu sıfırla
                self.fetch_status_label.setText("Ready.")
                self.fetch_status_label.setStyleSheet("color: gray; font-weight: bold;")

                # === Start Date
                start_str = config["INFO"].get("startDate", "2000-01-01 00:00:00")
                self.start_date = pd.to_datetime(start_str)
                dt_start = QDateTime.fromString(start_str, "yyyy-MM-dd HH:mm:ss")
                self.start_date_picker.setDateTime(
                    dt_start if dt_start.isValid()
                    else QDateTime.fromString("2000-01-01 00:00:00", "yyyy-MM-dd HH:mm:ss")
                )

                # === End Date
                end_str = config["INFO"].get("endDate", "2000-01-01 00:00:00")
                self.end_date = pd.to_datetime(end_str)
                dt_end = QDateTime.fromString(end_str, "yyyy-MM-dd HH:mm:ss")

                if "endDate" in config["INFO"] and dt_end.isValid():
                    self.end_date_picker.setDateTime(dt_end)
                    self.end_date_checkbox.setChecked(True)
                    self.end_date_picker.setEnabled(True)
                else:
                    self.end_date_picker.setDateTime(
                        QDateTime.fromString("2000-01-01 00:00:00", "yyyy-MM-dd HH:mm:ss")
                    )
                    self.end_date_checkbox.setChecked(False)
                    self.end_date_picker.setEnabled(False)
            else:
                raise ValueError("deviceId not found in .drep file")

            print("Status: .drep file loaded successfully.")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load .drep file:\n{e}")

    def set_loading(self, active=True):
        if active:
            self.central_widget.setEnabled(False)
            QApplication.processEvents()
        else:
            self.central_widget.setEnabled(True)
            QApplication.processEvents()

    def open_drep_file(self):
        reports_dir = os.path.join(os.getcwd(), "Device Reports")
        os.makedirs(reports_dir, exist_ok=True)

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open .drep File",
            reports_dir,
            "Device Report (*.drep)"
        )
        if not file_path:
            return

        self.load_drep_file(file_path)
        self.device_display.setFocus()

    def create_drep_file(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Create .drep File")

        layout = QVBoxLayout()

        # Device ID input
        id_input = QLineEdit()
        id_input.setPlaceholderText("Enter Device ID")
        layout.addWidget(QLabel("Device ID:"))
        layout.addWidget(id_input)

        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        layout.addWidget(buttons)

        dialog.setLayout(layout)

        def handle_save():
            device_id = id_input.text().strip()
            if not device_id:
                QMessageBox.warning(dialog, "Warning", "Device ID is required.")
                return

            # ⏰ Otomatik tarih
            default_dt = "2000-01-01 00:00:00"
            config = configparser.ConfigParser()
            config["INFO"] = {
                "deviceId": device_id,
                "startDate": default_dt,
            }

            try:
                save_dir = os.path.join(os.getcwd(), "Device Reports")
                os.makedirs(save_dir, exist_ok=True)
                default_path = os.path.join(save_dir, f"{device_id}.drep")

                file_path, _ = QFileDialog.getSaveFileName(
                    self,
                    "Save .drep File",
                    default_path,
                    "Device Report (*.drep)"
                )
                if not file_path:
                    return

                with open(file_path, 'w') as file:
                    config.write(file)

                QMessageBox.information(self, "Success", f".drep file saved.\n{file_path}")
                self.load_drep_file(file_path)  # doğrudan aç
                dialog.accept()

            except Exception as e:
                QMessageBox.critical(dialog, "Error", f"Failed to create .drep file:\n{str(e)}")

        buttons.accepted.connect(handle_save)
        buttons.rejected.connect(dialog.reject)

        dialog.exec_()

    def open_credentials_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Set Credentials")
        dialog.setFixedSize(250, 400)  # ✅ Sabit boyut

        layout = QVBoxLayout()

        email_input = QLineEdit()
        email_input.setPlaceholderText("Enter portal e-mail")

        pass_input = QLineEdit()
        pass_input.setPlaceholderText("Enter password")
        pass_input.setEchoMode(QLineEdit.Password)

        create_btn = QPushButton("Create Key")
        save_btn = QPushButton("Save Key")

        result_box = QTextEdit()
        result_box.setReadOnly(True)

        def create_key():
            try:
                email = email_input.text().strip()
                password = pass_input.text().strip()

                if not email or not password:
                    QMessageBox.warning(dialog, "Warning", "Email and password cannot be empty.")
                    print("Status: Empty credentials entered.")
                    return
                manager = CredentialManager()
                encrypted = manager.encrypt(email, password)
                result_box.setText(encrypted)
                self.portal_key = encrypted
                print("Status: Key created successfully.")

            except Exception as e:
                QMessageBox.critical(dialog, "Error", f"Failed to create key:\n{e}")
                print(f"Status: Key creation failed. Error: {e}")

        def save_to_config():
            key = result_box.toPlainText().strip()
            if not key:
                QMessageBox.warning(dialog, "Warning", "There is no key to save.")
                print("Status: No key found in result box to save.")
                return

            try:
                config = configparser.ConfigParser()

                if os.path.exists("config.ini"):
                    config.read("config.ini")
                    print("Status: config.ini loaded for writing.")
                else:
                    print("Status: config.ini will be created.")

                if "PORTAL" not in config:
                    config["PORTAL"] = {}

                config["PORTAL"]["Key"] = key

                with open("config.ini", "w") as configfile:
                    config.write(configfile)

                QMessageBox.information(dialog, "Success", "Key saved to config file.")
                print("Status: Key saved to config.ini successfully.")

            except Exception as e:
                QMessageBox.critical(dialog, "Error", f"Failed to save key:\n{e}")
                print(f"Status: Failed to save key to config.ini. Error: {e}")

        # === DIALOG AÇILIR AÇILMAZ: Mevcut key varsa yükle ===
        try:
            config = configparser.ConfigParser()
            if os.path.exists("config.ini"):
                config.read("config.ini")
                print("Status: config.ini loaded on dialog init.")
                if "PORTAL" in config and "Key" in config["PORTAL"]:
                    result_box.setText(config["PORTAL"]["Key"])
                    print("Status: Existing key loaded into result box.")
                else:
                    print("Status: No key found in config.ini.")
            else:
                print("Status: config.ini does not exist.")

        except Exception as e:
            print(f"Status: Could not load existing key. Error: {e}")

        # === Bağlantılar ve Layout ===
        create_btn.clicked.connect(create_key)
        save_btn.clicked.connect(save_to_config)

        layout.addWidget(QLabel("E-mail:"))
        layout.addWidget(email_input)
        layout.addWidget(QLabel("Password:"))
        layout.addWidget(pass_input)
        layout.addWidget(create_btn)
        layout.addWidget(QLabel("Key:"))
        layout.addWidget(result_box)
        layout.addWidget(save_btn)

        dialog.setLayout(layout)
        dialog.exec_()

    def load_portal_key_from_config(self):
        config = configparser.ConfigParser()

        if not os.path.exists("config.ini"):
            print("Status: config.ini not found.")
            return

        config.read("config.ini")


        if "PORTAL" not in config or "Key" not in config["PORTAL"]:
            print("Status: Key not found in config file.")
            return

        self.portal_key = config["PORTAL"]["Key"]
        print("Status: Key loaded from config.ini.")

        try:
            manager = CredentialManager()
            email, password = manager.decrypt(self.portal_key)
            self.portal_email = email
            self.portal_password = password
            print("Status: Key decrypted successfully.")
        except Exception as e:
            print("Status: Failed to decrypt key.")
            self.portal_email = None
            self.portal_password = None

class ConsoleWidget(QPlainTextEdit):
    print_signal = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.print_signal.connect(self._append_safe)

    def write(self, message):
        self.print_signal.emit(message)

    def _append_safe(self, message):
        for line in message.rstrip().splitlines():
            self.appendPlainText(line)
        self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())

    def flush(self):
        pass

class CredentialManager:
    def __init__(self, passphrase: str = "deutschlandüberallen"):
        key = hashlib.sha256(passphrase.encode()).digest()
        self.fernet = Fernet(base64.urlsafe_b64encode(key))

    def encrypt(self, email: str, password: str) -> str:
        data = f"{email}||{password}".encode()
        return self.fernet.encrypt(data).decode()

    def decrypt(self, token: str) -> list:
        decrypted = self.fernet.decrypt(token.encode()).decode()
        return decrypted.split("||")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainApp()
    window.show()
    sys.exit(app.exec_())