import sys
import os
import json
import time
import random
import threading
import urllib.request
import zipfile
import ctypes
import shutil

from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QRadioButton, QPlainTextEdit, QDoubleSpinBox, 
                             QCheckBox, QPushButton, QLineEdit, QGroupBox, QMessageBox,
                             QButtonGroup)
from PyQt5.QtCore import Qt, pyqtSignal, QObject
from PyQt5.QtGui import QFont

import keyboard
import pyperclip
from pynput.keyboard import Controller
import win32gui
import win32process

try:
    import interception
except Exception as e:
    interception = None
    interception_err = str(e)
else:
    interception_err = None

CONFIG_FILE = "config.json"

DEFAULT_CONFIG = {
    "mode": "clipboard",
    "input_text": "",
    "interval": 0.0,
    "random_interval": False,
    "delay": 0.0,
    "trigger_hotkey": "F8",
    "stop_hotkey": "F9",
    "advanced_mode": False
}

class WorkerSignals(QObject):
    finished = pyqtSignal()
    error = pyqtSignal(str)
    log = pyqtSignal(str)

class TypingWorker(threading.Thread):
    def __init__(self, config, my_pid):
        super().__init__()
        self.config = config
        self.my_pid = my_pid
        self.signals = WorkerSignals()
        self.stop_requested = False
        self.controller = Controller()

    def run(self):
        try:
            self.signals.log.emit("开始任务...")
            delay = self.config.get("delay", 0.0)
            if delay > 0:
                self.signals.log.emit(f"延时 {delay} 秒...")
                start_time = time.time()
                while time.time() - start_time < delay:
                    if self.stop_requested:
                        self.signals.log.emit("已停止。")
                        return
                    time.sleep(0.1)

            # 目标窗口检测
            hwnd = win32gui.GetForegroundWindow()
            _, active_pid = win32process.GetWindowThreadProcessId(hwnd)
            if active_pid == self.my_pid:
                self.signals.log.emit("目标窗口为本程序自身，已自动停止。")
                self.signals.finished.emit()
                return

            text_to_type = ""
            if self.config.get("mode") == "clipboard":
                text_to_type = pyperclip.paste()
                if not text_to_type:
                    self.signals.log.emit("剪贴板为空！")
                    self.signals.finished.emit()
                    return
            else:
                text_to_type = self.config.get("input_text", "")
                if not text_to_type:
                    self.signals.log.emit("输入内容为空！")
                    self.signals.finished.emit()
                    return

            is_advanced = self.config.get("advanced_mode", False)
            if is_advanced:
                self.type_advanced(text_to_type)
            else:
                self.type_normal(text_to_type)

        except Exception as e:
            self.signals.error.emit(str(e))
        finally:
            self.signals.finished.emit()

    def type_normal(self, text):
        interval = self.config.get("interval", 0.0)
        random_interval = self.config.get("random_interval", False)
        for char in text:
            if self.stop_requested:
                self.signals.log.emit("已停止。")
                break
            
            # 正常打字
            self.controller.type(char)
            
            if interval > 0:
                sleep_time = interval
                if random_interval:
                    sleep_time = interval * random.uniform(0.5, 1.5)
                time.sleep(sleep_time)
        self.signals.log.emit("输入完成！")

    def type_advanced(self, text):
        if interception is None:
            self.signals.error.emit(f"未安装 interception-python 库！({interception_err})")
            return
            
        try:
            # 高级模式下拦截并发送按键
            interception.auto_capture_devices(keyboard=True, mouse=False)
        except Exception as e:
            self.signals.error.emit(f"Interception 驱动异常: {e}")
            return

        interval = self.config.get("interval", 0.0)
        random_interval = self.config.get("random_interval", False)
        
        hex_text = text.encode('utf-8').hex()
        
        # 使用新型特征码协议替代 F12
        START_SEQ = "]]u[["
        END_SEQ = "[[u]]"
        
        self.signals.log.emit(f"发送高级模式特征码 {START_SEQ}...")
        interception.write(START_SEQ)
        time.sleep(0.1)
        
        self.signals.log.emit(f"发送编码数据 ({len(hex_text)} 个字符)...")
        # 为保证接收准确，在大流量数据时稍微给点间隙
        for char in hex_text:
            if self.stop_requested:
                self.signals.log.emit("已停止。")
                break
            interception.press(char)
            
            if interval > 0:
                sleep_time = interval
                if random_interval:
                    sleep_time = interval * random.uniform(0.5, 1.5)
                time.sleep(sleep_time)
            else:
                time.sleep(0.005)

        if not self.stop_requested:
            self.signals.log.emit(f"发送特征码结束符 {END_SEQ}...")
            interception.write(END_SEQ)
            self.signals.log.emit("高级模式输入完成！")


class MainWindow(QWidget):
    log_signal = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.config = DEFAULT_CONFIG.copy()
        self.worker = None
        self.my_pid = os.getpid()
        self.log_signal.connect(self.append_log)
        self.load_config()
        self.init_ui()
        self.connect_signals()
        self.register_hotkeys()

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.config.update(data)
            except Exception as e:
                print(f"Failed to load config: {e}")

    def save_config(self, *args):
        self.config["mode"] = "clipboard" if self.radio_clip.isChecked() else "input"
        self.config["input_text"] = self.text_input.toPlainText()
        self.config["interval"] = self.spin_interval.value()
        self.config["random_interval"] = self.chk_random.isChecked()
        self.config["delay"] = self.spin_delay.value()
        self.config["trigger_hotkey"] = self.edit_trigger.text()
        self.config["stop_hotkey"] = self.edit_stop.text()
        self.config["advanced_mode"] = self.chk_adv.isChecked()
        
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"Failed to save config: {e}")

    def init_ui(self):
        self.setWindowTitle("无敌粘贴大法promax")
        self.resize(550, 650)
        
        main_layout = QVBoxLayout()
        
        # 1. 模式选择和输入区
        gb_mode = QGroupBox("输入来源")
        vbox_mode = QVBoxLayout()
        
        self.radio_clip = QRadioButton("剪贴板模式 (自动从剪贴板获取内容)")
        self.radio_input = QRadioButton("输入模式 (手动输入或粘贴到下方文本框)")
        self.mode_group = QButtonGroup()
        self.mode_group.addButton(self.radio_clip)
        self.mode_group.addButton(self.radio_input)
        
        if self.config["mode"] == "clipboard":
            self.radio_clip.setChecked(True)
        else:
            self.radio_input.setChecked(True)
            
        self.text_input = QPlainTextEdit()
        self.text_input.setPlaceholderText("在此处输入要模拟打字的内容...")
        self.text_input.setPlainText(self.config["input_text"])
        self.text_input.setEnabled(self.radio_input.isChecked())
        
        vbox_mode.addWidget(self.radio_clip)
        vbox_mode.addWidget(self.radio_input)
        vbox_mode.addWidget(self.text_input)
        gb_mode.setLayout(vbox_mode)
        
        self.radio_clip.toggled.connect(lambda: self.text_input.setEnabled(self.radio_input.isChecked()))
        
        # 2. 模拟打字设置区
        gb_settings = QGroupBox("打字参数设置")
        hbox_settings = QHBoxLayout()
        
        hbox_settings.addWidget(QLabel("打字间隔 (秒):"))
        self.spin_interval = QDoubleSpinBox()
        self.spin_interval.setRange(0.0, 1.0)
        self.spin_interval.setSingleStep(0.01)
        self.spin_interval.setValue(self.config["interval"])
        hbox_settings.addWidget(self.spin_interval)
        
        self.chk_random = QCheckBox("随机间隔 (±50%)")
        self.chk_random.setChecked(self.config["random_interval"])
        hbox_settings.addWidget(self.chk_random)
        
        hbox_settings.addWidget(QLabel("触发延时 (秒):"))
        self.spin_delay = QDoubleSpinBox()
        self.spin_delay.setRange(0.0, 60.0)
        self.spin_delay.setValue(self.config["delay"])
        hbox_settings.addWidget(self.spin_delay)
        
        gb_settings.setLayout(hbox_settings)
        
        # 3. 热键设置区
        gb_hotkeys = QGroupBox("控制与快捷键")
        vbox_hotkeys = QVBoxLayout()
        
        hbox_keys = QHBoxLayout()
        hbox_keys.addWidget(QLabel("触发键:"))
        self.edit_trigger = QLineEdit(self.config["trigger_hotkey"])
        hbox_keys.addWidget(self.edit_trigger)
        
        hbox_keys.addWidget(QLabel("停止键:"))
        self.edit_stop = QLineEdit(self.config["stop_hotkey"])
        hbox_keys.addWidget(self.edit_stop)
        
        self.btn_apply_hotkeys = QPushButton("应用热键")
        hbox_keys.addWidget(self.btn_apply_hotkeys)
        vbox_hotkeys.addLayout(hbox_keys)

        hbox_manual = QHBoxLayout()
        self.btn_start = QPushButton("▶ 手动开始 (F8)")
        self.btn_start.setStyleSheet("background-color: #e1f5fe; height: 35px; font-weight: bold;")
        self.btn_start.clicked.connect(self.on_trigger)
        
        self.btn_stop_manual = QPushButton("■ 手动停止 (F9)")
        self.btn_stop_manual.setStyleSheet("background-color: #ffebee; height: 35px; font-weight: bold;")
        self.btn_stop_manual.clicked.connect(self.on_stop)
        
        hbox_manual.addWidget(self.btn_start)
        hbox_manual.addWidget(self.btn_stop_manual)
        vbox_hotkeys.addLayout(hbox_manual)
        
        gb_hotkeys.setLayout(vbox_hotkeys)
        
        # 4. 高级模式 (虚拟机穿透)
        gb_adv = QGroupBox("高级输入模式 (VM穿透无vmtools限制)")
        vbox_adv = QVBoxLayout()
        
        self.chk_adv = QCheckBox("启用高级输入模式 (配合虚拟机内的接收端使用)")
        self.chk_adv.setChecked(self.config["advanced_mode"])
        vbox_adv.addWidget(self.chk_adv)
        
        hbox_driver = QHBoxLayout()
        if interception:
            status_text = "Interception 库已安装"
        else:
            status_text = f"缺少 Interception 库 ({interception_err})"
            
        self.lbl_driver = QLabel(f"驱动状态: {status_text}")
        hbox_driver.addWidget(self.lbl_driver)
        
        self.btn_install_driver = QPushButton("下载并安装驱动")
        self.btn_install_driver.clicked.connect(self.on_install_driver)
        hbox_driver.addWidget(self.btn_install_driver)
        
        vbox_adv.addLayout(hbox_driver)
        gb_adv.setLayout(vbox_adv)
        
        # 5. 日志与状态
        self.log_output = QPlainTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setPlaceholderText("运行日志...")
        
        main_layout.addWidget(gb_mode)
        main_layout.addWidget(gb_settings)
        main_layout.addWidget(gb_hotkeys)
        main_layout.addWidget(gb_adv)
        main_layout.addWidget(self.log_output)
        
        self.setLayout(main_layout)

    def connect_signals(self):
        self.radio_clip.toggled.connect(self.save_config)
        self.radio_input.toggled.connect(self.save_config)
        self.text_input.textChanged.connect(self.save_config)
        self.spin_interval.valueChanged.connect(self.save_config)
        self.chk_random.stateChanged.connect(self.save_config)
        self.spin_delay.valueChanged.connect(self.save_config)
        self.chk_adv.stateChanged.connect(self.save_config)
        self.btn_apply_hotkeys.clicked.connect(self.apply_hotkeys)

    def apply_hotkeys(self):
        self.save_config()
        self.register_hotkeys()

    def register_hotkeys(self):
        # 移除之前可能存在的所有热键，防止重复注册
        try:
            keyboard.unhook_all()
        except:
            pass
            
        trigger_key = self.config.get("trigger_hotkey", "F8")
        stop_key = self.config.get("stop_hotkey", "F9")
        
        # 更新按钮显示
        if hasattr(self, 'btn_start'):
            self.btn_start.setText(f"▶ 手动开始 ({trigger_key})")
        if hasattr(self, 'btn_stop_manual'):
            self.btn_stop_manual.setText(f"■ 手动停止 ({stop_key})")

        if not trigger_key or not stop_key:
            self.append_log("警告: 热键配置不能为空")
            return

        try:
            keyboard.add_hotkey(trigger_key, self.on_trigger, suppress=True)
            self.append_log(f"已注册触发热键: {trigger_key}")
        except Exception as e:
            self.append_log(f"注册触发热键失败 ({trigger_key}): {e}")
            
        try:
            keyboard.add_hotkey(stop_key, self.on_stop, suppress=True)
            self.append_log(f"已注册停止热键: {stop_key}")
        except Exception as e:
            self.append_log(f"注册停止热键失败 ({stop_key}): {e}")

    def on_trigger(self):
        if self.worker is not None and self.worker.is_alive():
            self.log_signal.emit("当前已有任务正在运行中...")
            return
            
        # Refresh config in memory from JSON or UI (since UI saves on change)
        self.worker = TypingWorker(self.config, self.my_pid)
        self.worker.signals.log.connect(self.append_log)
        self.worker.signals.error.connect(lambda e: self.append_log(f"错误: {e}"))
        self.worker.start()

    def on_stop(self):
        if self.worker is not None and self.worker.is_alive():
            self.worker.stop_requested = True
            self.log_signal.emit("收到停止指令...")

    def append_log(self, text):
        t = time.strftime("%H:%M:%S")
        self.log_output.appendPlainText(f"[{t}] {text}")
        
    def on_install_driver(self):
        msg = ("即将为您自动下载并安装 Interception 驱动（需要管理员权限）。\n"
               "安装过程可能会弹出命令行黑窗口，安装完成后必须重启计算机才能生效。\n\n是否继续？")
        reply = QMessageBox.question(self, "安装驱动", msg, QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            threading.Thread(target=self.run_driver_installer).start()

    def run_driver_installer(self):
        # 处理 PyInstaller 打包后的路径
        if getattr(sys, 'frozen', False):
            base_path = sys._MEIPASS
        else:
            base_path = os.getcwd()

        # 优先使用本地已存在的 Interception_Installer 文件夹
        local_dir = os.path.join(base_path, "Interception_Installer")
        zip_path = os.path.join(base_path, "Interception.zip")
        extract_dir = os.path.join(os.getcwd(), "Interception_Driver")
        
        try:
            if os.path.exists(local_dir):
                self.log_signal.emit(f"检测到本地存在 {local_dir} 文件夹，直接使用该文件夹进行安装...")
                target_dir = local_dir
            else:
                if os.path.exists(zip_path):
                    self.log_signal.emit(f"检测到本地存在 {zip_path}，正在直接使用本地压缩文件...")
                    source_zip = zip_path
                else:
                    self.log_signal.emit("正在从网络下载 Interception 驱动...")
                    url = "https://github.com/oblitum/Interception/releases/download/v1.0.1/Interception.zip"
                    source_zip = os.path.join(os.getcwd(), "Interception.zip")
                    urllib.request.urlretrieve(url, source_zip)
                    self.log_signal.emit("下载完成，正在解压...")
                
                with zipfile.ZipFile(source_zip, 'r') as zip_ref:
                    zip_ref.extractall(extract_dir)
                target_dir = extract_dir
            
            # 关键步骤：复制对应的 DLL 到当前目录，否则库无法加载
            dll_src = os.path.join(target_dir, "library", "x64", "interception.dll")
            if not os.path.exists(dll_src):
                 dll_src = os.path.join(target_dir, "library", "x86", "interception.dll")
            
            if os.path.exists(dll_src):
                shutil.copy(dll_src, os.getcwd())
                self.log_signal.emit("已将 interception.dll 复制到程序目录。")
            
            installer_path = os.path.join(target_dir, "command line installer", "install-interception.exe")
            if os.path.exists(installer_path):
                self.log_signal.emit("正在启动安装程序，请在UAC弹窗中点击“是”...")
                # 使用 cmd /k 保持窗口开启，让用户看到安装结果
                cmd_command = f'"{installer_path}" /install'
                ctypes.windll.shell32.ShellExecuteW(None, "runas", "cmd.exe", f"/k {cmd_command}", None, 1)
                self.log_signal.emit("安装窗口已弹出，请在黑窗口中确认出现 'Successfully installed' 字样后重启电脑。")
            else:
                self.log_signal.emit(f"错误: 未能在 {target_dir} 中找到 install-interception.exe。")
        except Exception as e:
            self.log_signal.emit(f"驱动安装失败: {e}")
            self.log_signal.emit("建议手动运行 'Interception_Installer\\command line installer\\install-interception.exe /install'。")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
