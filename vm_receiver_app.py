import keyboard
import pyperclip
import time
import os
import sys
import winreg
import threading
import string
import string

# 配置常量
START_SEQ = "]]u[["  # 起始特征码
END_SEQ = "[[u]]"    # 结束特征码

class ProMaxReceiver:
    def __init__(self):
        self.buffer = ""
        self.is_capturing = False
        self.magic_start = list(START_SEQ)
        self.magic_end = list(END_SEQ)
        self.input_history = []

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

        # 记录最近输入的字符
        char = e.name
        if len(char) == 1:
            self.input_history.append(char)
            if len(self.input_history) > 20:
                self.input_history.pop(0)

        # 检测起始特征码
        if not self.is_capturing:
            if "".join(self.input_history).endswith(START_SEQ):
                print(f"[{time.strftime('%H:%M:%S')}] 检测到起始特征码 {START_SEQ}，进入捕获模式...")
                self.is_capturing = True
                self.buffer = ""
                # 删除刚刚打出来的特征码 (退格)
                for _ in range(len(START_SEQ)):
                    keyboard.send('backspace')
                return

        # 检测结束特征码
        else:
            # 记录 hex 字符
            # 提前过滤掉非 hex 字符，防止特征码的前缀 (如 [[u) 混入 buffer
            if len(char) == 1 and char in string.hexdigits:
                self.buffer += char

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
                
                self.buffer = ""
                self.input_history = [] # 清空历史，准备下一次
                return

    def run(self):
        # 隐藏控制台窗口（如果在 Windows 上运行且没有使用 pythonw）
        # 实际使用时建议用户运行 pythonw vm_receiver_app.py
        
        print("无敌粘贴大法ProMax - 虚拟机接收端(模拟输入法模式)")
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
