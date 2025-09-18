import sys
import os
import csv
import time
from threading import Lock

import serial
import serial.tools.list_ports

from PyQt5 import QtCore, QtWidgets, QtGui
import openpyxl


class SerialReaderThread(QtCore.QThread):
    line_received = QtCore.pyqtSignal(str)
    error_occurred = QtCore.pyqtSignal(str)

    def __init__(self, port: str, baudrate: int, parent=None):
        super().__init__(parent)
        self.port = port
        self.baudrate = baudrate
        self._running = False
        self._serial = None

    def run(self):
        try:
            self._serial = serial.Serial(self.port, self.baudrate, timeout=1)
        except Exception as e:
            self.error_occurred.emit(f"Cannot open serial port {self.port}: {e}")
            return

        self._running = True
        while self._running:
            try:
                if self._serial.in_waiting:
                    line = self._serial.readline().decode(errors='ignore').strip()
                    if line:
                        timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
                        self.line_received.emit(f"{timestamp} - {line}")
                else:
                    self.msleep(100)
            except Exception as e:
                self.error_occurred.emit(f"Read error: {e}")
                break

        if self._serial and self._serial.is_open:
            try:
                self._serial.close()
            except:
                pass

    def stop(self):
        self._running = False
        self.wait()


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Serial Port Logger")
        self.resize(800, 600)

        self.csv_file_path = "serial_log.csv"
        self.csv_lock = Lock()
        self.is_dark = False

        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        layout = QtWidgets.QVBoxLayout(central)

        # Top controls
        top_layout = QtWidgets.QHBoxLayout()
        self.port_combo = QtWidgets.QComboBox()
        self.refresh_btn = QtWidgets.QPushButton("Refresh")
        self.baud_combo = QtWidgets.QComboBox()
        self.start_btn = QtWidgets.QPushButton("Start")
        self.start_btn.setObjectName("start_btn")
        self.stop_btn = QtWidgets.QPushButton("Stop")
        self.stop_btn.setObjectName("stop_btn")
        self.mode_toggle_btn = QtWidgets.QPushButton("Dark Mode")

        top_layout.addWidget(QtWidgets.QLabel("COM Port:"))
        top_layout.addWidget(self.port_combo)
        top_layout.addWidget(self.refresh_btn)
        top_layout.addWidget(QtWidgets.QLabel("Baud:"))
        top_layout.addWidget(self.baud_combo)
        top_layout.addWidget(self.start_btn)
        top_layout.addWidget(self.stop_btn)
        top_layout.addWidget(self.mode_toggle_btn)
        layout.addLayout(top_layout)

        # Filter
        filter_layout = QtWidgets.QHBoxLayout()
        self.filter_edit = QtWidgets.QLineEdit()
        filter_layout.addWidget(QtWidgets.QLabel("Filter:"))
        filter_layout.addWidget(self.filter_edit)
        layout.addLayout(filter_layout)

        # Log view
        self.log_text = QtWidgets.QPlainTextEdit()
        self.log_text.setReadOnly(True)
        layout.addWidget(self.log_text)

        # Command input
        command_layout = QtWidgets.QHBoxLayout()
        self.command_input = QtWidgets.QLineEdit()
        self.command_input.setPlaceholderText("Type command to send...")
        self.send_button = QtWidgets.QPushButton("Send")
        command_layout.addWidget(self.command_input)
        command_layout.addWidget(self.send_button)
        layout.addLayout(command_layout)

        # Save/export/clear
        button_layout = QtWidgets.QHBoxLayout()
        self.save_btn = QtWidgets.QPushButton("Save Log As...")
        self.export_excel_btn = QtWidgets.QPushButton("Export to Excel (.xlsx)")
        self.clear_btn = QtWidgets.QPushButton("Clear Console")
        button_layout.addWidget(self.save_btn)
        button_layout.addWidget(self.export_excel_btn)
        button_layout.addWidget(self.clear_btn)
        layout.addLayout(button_layout)

        # Status bar
        self.status = self.statusBar()

        # Defaults
        self.baud_combo.addItems(["9600", "19200", "38400", "57600", "115200"])
        self.baud_combo.setCurrentText("9600")
        self.stop_btn.setEnabled(False)

        # Serial thread
        self.serial_thread = None

        # Connections
        self.refresh_btn.clicked.connect(self.refresh_ports)
        self.start_btn.clicked.connect(self.start_logging)
        self.stop_btn.clicked.connect(self.stop_logging)
        self.save_btn.clicked.connect(self.save_log)
        self.export_excel_btn.clicked.connect(self.export_to_excel)
        self.clear_btn.clicked.connect(self.clear_console)
        self.send_button.clicked.connect(self.send_command)
        self.filter_edit.textChanged.connect(self.apply_filter)
        self.mode_toggle_btn.clicked.connect(self.toggle_mode)

        self.refresh_ports()

    def refresh_ports(self):
        self.port_combo.clear()
        ports = [p.device for p in serial.tools.list_ports.comports()]
        self.port_combo.addItems(ports)
        self.status.showMessage("Ports refreshed.")

    def start_logging(self):
        port = self.port_combo.currentText()
        try:
            baud = int(self.baud_combo.currentText())
        except:
            self.status.showMessage("Invalid baud rate.")
            return

        if not port:
            self.status.showMessage("No COM port selected.")
            return

        self.serial_thread = SerialReaderThread(port, baud)
        self.serial_thread.line_received.connect(self.on_line_received)
        self.serial_thread.error_occurred.connect(self.on_error)
        self.serial_thread.start()

        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.status.showMessage(f"Logging started on {port} at {baud} baud.")

    def stop_logging(self):
        if self.serial_thread:
            self.serial_thread.stop()
            self.serial_thread = None
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.status.showMessage("Logging stopped.")

    def on_line_received(self, line: str):
        self.log_text.appendPlainText(line)
        with self.csv_lock:
            new_file = not os.path.isfile(self.csv_file_path)
            with open(self.csv_file_path, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                if new_file:
                    writer.writerow(['Timestamp', 'Data'])
                if " - " in line:
                    ts, data = line.split(" - ", 1)
                else:
                    ts, data = "", line
                writer.writerow([ts, data])
        self.apply_filter()

    def on_error(self, msg: str):
        QtWidgets.QMessageBox.critical(self, "Serial Error", msg)
        self.stop_logging()

    def apply_filter(self):
        text = self.filter_edit.text().lower()
        lines = self.log_text.toPlainText().splitlines()
        self.log_text.clear()
        for line in lines:
            if text in line.lower():
                self.log_text.appendPlainText(line)

    def save_log(self):
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save Log", "", "Text Files (*.txt);;All Files (*)")
        if path:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(self.log_text.toPlainText())
            self.status.showMessage(f"Log saved to {path}")

    def export_to_excel(self):
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Export to Excel", "serial_log.xlsx", "Excel Files (*.xlsx);;All Files (*)"
        )
        if not path:
            return

        try:
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Log"
            ws.append(["Timestamp", "Message"])

            for line in self.log_text.toPlainText().splitlines():
                if " - " in line:
                    ts, msg = line.split(" - ", 1)
                else:
                    ts, msg = "", line
                ws.append([ts, msg])

            wb.save(path)
            self.status.showMessage(f"Exported to Excel: {path}", 5000)
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Export Error", str(e))

    def clear_console(self):
        self.log_text.clear()
        self.status.showMessage("Console cleared.", 3000)

    def send_command(self):
        command = self.command_input.text().strip()
        if command and self.serial_thread and self.serial_thread._serial and self.serial_thread._serial.is_open:
            try:
                self.serial_thread._serial.write((command + '\n').encode())
                self.command_input.clear()
                timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
                log_entry = f"{timestamp} - → {command}"
                self.log_text.appendPlainText(log_entry)
                with self.csv_lock:
                    with open(self.csv_file_path, 'a', newline='', encoding='utf-8') as f:
                        writer = csv.writer(f)
                        writer.writerow([timestamp, f"→ {command}"])
            except Exception as e:
                QtWidgets.QMessageBox.warning(self, "Send Error", str(e))
        else:
            QtWidgets.QMessageBox.warning(self, "Not Connected", "No serial connection available.")

    def toggle_mode(self):
        if self.is_dark:
            self.setStyleSheet("")
            self.mode_toggle_btn.setText("Dark Mode")
        else:
            self.setStyleSheet(self.dark_stylesheet())
            self.mode_toggle_btn.setText("Light Mode")
        self.is_dark = not self.is_dark

    def dark_stylesheet(self):
        return """
        QWidget {
            background-color: #121212;
            color: #eeeeee;
        }
        QPushButton {
            background-color: #2c2c2c;
            color: white;
            border: 1px solid #444;
            padding: 5px;
        }
        QPushButton:hover {
            background-color: #3a3a3a;
        }
        QPushButton:pressed {
            background-color: #555;
        }
        QPushButton:disabled {
            background-color: #1e1e1e;
            color: #666;
        }
        QPushButton#start_btn {
            background-color: #145214;
        }
        QPushButton#stop_btn {
            background-color: #801515;
        }
        QLineEdit, QComboBox, QPlainTextEdit {
            background-color: #1e1e1e;
            color: #eeeeee;
            border: 1px solid #444;
        }
        """

    def closeEvent(self, event):
        if self.serial_thread:
            self.serial_thread.stop()
        event.accept()


def main():
    app = QtWidgets.QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
