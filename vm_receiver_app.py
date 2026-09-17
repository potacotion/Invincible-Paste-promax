import keyboard
import pyperclip
import time
import os
import sys
import winreg
import threading
import string

# 配置常量
APP_VERSION = "1.0.0"
START_SEQ = "]]u[["  # 起始特征码
END_SEQ = "[[u]]"    # 结束特征码
CAPTURE_TIMEOUT = 5.0  # 捕获模式空闲超时（秒），防止发送端中断后永久卡在捕获态

class ProMaxReceiver:
    def __init__(self):
        self.buffer = ""
        self.is_capturing = False
        self.magic_start = list(START_SEQ)
        self.magic_end = list(END_SEQ)
        self.input_history = []
        self.last_event_time = 0.0

    def reset_capture(self):
        """退出捕获模式并清空状态。"""
        self.buffer = ""
        self.is_capturing = False
        self.input_history = []
        self.last_event_time = 0.0

    def install_autostart(self):
        """将程序添加到 Windows 启动项注册表"""
        try:
            # 获取当前脚本/可执行文件路径
            if getattr(sys, 'frozen', False):
                path = sys.executable
            else:
                path = os.path.abspath(__file__)
                # 如果是 python 脚本，需要使用 pythonw.exe 来静默运行
                pythonw_path = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
                path = f'"{pythonw_path}" "{path}"'

            key = winreg.HKEY_CURRENT_USER
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
            with winreg.OpenKey(key, key_path, 0, winreg.KEY_SET_VALUE) as reg_key:
                winreg.SetValueEx(reg_key, "ProMaxPasteReceiver", 0, winreg.REG_SZ, path)
            return True
        except Exception as e:
            print(f"安装自启动失败: {e}")
            return False

    def on_key_event(self, e):
        if e.event_type != 'down':
            return

        now = time.time()

        # 捕获模式下长时间没有新按键 => 发送端中断，自动退出，避免污染下一次传输
        if self.is_capturing and now - self.last_event_time > CAPTURE_TIMEOUT:
            print(f"[{time.strftime('%H:%M:%S')}] 捕获超时 ({CAPTURE_TIMEOUT:.0f}s)，自动退出捕获模式（目标窗口可能残留部分 hex 字符）。")
            self.reset_capture()
        self.last_event_time = now

        # 记录最近输入的字符
        char = e.name
        if len(char) == 1:
            self.input_history.append(char)
            if len(self.input_history) > 20:
                self.input_history.pop(0)

        if not self.is_capturing:
            # 检测起始特征码
            if "".join(self.input_history).endswith(START_SEQ):
                print(f"[{time.strftime('%H:%M:%S')}] 检测到起始特征码 {START_SEQ}，进入捕获模式...")
                self.is_capturing = True
                self.buffer = ""
                # 删除刚刚打出来的特征码 (退格)
                for _ in range(len(START_SEQ)):
                    keyboard.send('backspace')
                return
        else:
            # 捕获中又出现起始特征码 => 上一次传输中断后重传，重新开始本次捕获
            if "".join(self.input_history).endswith(START_SEQ):
                print(f"[{time.strftime('%H:%M:%S')}] 捕获中出现新的起始特征码，重置本次捕获...")
                # 删除上一次残留的部分 hex 以及本次打出的特征码 (退格)
                for _ in range(len(self.buffer) + len(START_SEQ)):
                    keyboard.send('backspace')
                self.buffer = ""
                self.input_history = []
                return

            # 记录 hex 字符
            # 提前过滤掉非 hex 字符，防止特征码的前缀 (如 [[u) 混入 buffer
            if len(char) == 1 and char in string.hexdigits:
                self.buffer += char

            # 检测结束特征码
            if "".join(self.input_history).endswith(END_SEQ):
                print(f"[{time.strftime('%H:%M:%S')}] 检测到结束特征码 {END_SEQ}，准备解码内容...")
                self.is_capturing = False

                # 删除特征码 (回退其长度)
                # 等待一小会儿确保输入事件已送达应用
                time.sleep(0.05)
                for _ in range(len(END_SEQ)):
                    keyboard.send('backspace')

                # 处理缓冲区中的十六进制
                try:
                    # 缓冲区已经预过滤过了，这里直接使用
                    real_hex = self.buffer.strip()

                    print(f"[{time.strftime('%H:%M:%S')}] 捕获 HEX 数据: {real_hex}")

                    # 此时屏幕上应该只有 hex 字符，删掉它们
                    for _ in range(len(real_hex)):
                        keyboard.send('backspace')

                    # 解码并粘贴
                    if not real_hex:
                        raise ValueError("HEX 缓冲区为空")

                    text = bytes.fromhex(real_hex).decode('utf-8')
                    if text:
                        print(f"[{time.strftime('%H:%M:%S')}] 成功解码内容: {text[:50]}...")
                        # 逐字模拟打字输入，避开禁止粘贴限制
                        keyboard.write(text, delay=0.01)
                except Exception as ex:
                    print(f"[{time.strftime('%H:%M:%S')}] 解码失败: {ex}")

                self.reset_capture()
                return

    def run(self):
        # 隐藏控制台窗口（如果在 Windows 上运行且没有使用 pythonw）
        # 实际使用时建议用户运行 pythonw vm_receiver_app.py
        
        print(f"无敌粘贴大法ProMax - 虚拟机接收端 v{APP_VERSION} (模拟输入法模式)")
        print(f"监听序列: {START_SEQ} + HEX + {END_SEQ}")
        
        # 注册自启动
        if self.install_autostart():
            print("已自动注册为系统自启动项。")
        
        keyboard.hook(self.on_key_event)
        keyboard.wait()

if __name__ == "__main__":
    # 如果有参数 --install，仅执行安装逻辑
    receiver = ProMaxReceiver()
    if "--install" in sys.argv:
        if receiver.install_autostart():
            print("安装成功！下次开机将自动在后台运行。")
        sys.exit(0)
    
    receiver.run()
