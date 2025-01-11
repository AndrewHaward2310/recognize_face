# control_servo.py
import pyfirmata
from pyfirmata import util
from PyQt5.QtCore import QThread, pyqtSignal, pyqtSlot
import numpy as np
import time
import threading
import serial

class ControlServo(QThread):
    # Tín hiệu để nhận tọa độ mục tiêu
    set_target_signal = pyqtSignal(int, int, int, int)    
    # Tín hiệu để thông báo trạng thái kết nối
    connection_status_signal = pyqtSignal(bool, str)

    def __init__(self, parent=None, port='COM4', baudrate=57600):
        super(ControlServo, self).__init__(parent)
        self.port = port
        self.baudrate = baudrate
        self.servo_pinX = None
        self.servo_pinY = None
        self.board = None
        self.lock = threading.Lock()
        self.running = True
        self.active = False  
        self.target_x = 90  # Vị trí mục tiêu ban đầu cho servo X
        self.target_y = 90  # Vị trí mục tiêu ban đầu cho servo Y
        self.current_x = 90  # Vị trí hiện tại của servo X
        self.current_y = 90  # Vị trí hiện tại của servo Y

        try:
            # Kết nối tới Arduino
            self.board = pyfirmata.Arduino(self.port, baudrate=self.baudrate)

            # Khởi tạo Iterator để liên tục giao tiếp với Arduino
            self.iterator = util.Iterator(self.board)
            self.iterator.start()
            time.sleep(1)  # Chờ một chút để Iterator khởi động

            # Cấu hình các chân servo
            self.board.servo_config(9, min_pulse=544, max_pulse=2400)   # Chân servo X
            self.board.servo_config(10, min_pulse=544, max_pulse=2400)  # Chân servo Y
            self.servo_pinX = self.board.get_pin('d:9:s')
            self.servo_pinY = self.board.get_pin('d:10:s')
            print("Servo pin X:", self.servo_pinX)
            print("Servo pin Y:", self.servo_pinY)
            if not self.servo_pinX or not self.servo_pinY:
                raise ValueError("Servo pins not initialized.")

            # Đặt servo về vị trí trung tâm ban đầu
            self.servo_pinX.write(self.current_x)  
            self.servo_pinY.write(self.current_y) 
            time.sleep(1)
            self.active = True
            # Thông báo kết nối thành công
            print(f"Connected to Arduino on {self.port}")
            self.connection_status_signal.emit(True, f"Connected to {self.port}")
        except serial.SerialException as e:
            self.active = False
            print(f"Failed to connect to Arduino on {self.port}: {e}")
            self.connection_status_signal.emit(False, f"Failed to connect to {self.port}: {e}")
        except Exception as e:
            self.active = False
            print(f"Error initializing ControlServo: {e}")
            self.connection_status_signal.emit(False, f"Error initializing ControlServo: {e}")

        # Kết nối tín hiệu để nhận mục tiêu
        self.set_target_signal.connect(self.set_target)

    def run(self):
        while self.running:
            if self.active:
                with self.lock:
                    target_x = self.target_x
                    target_y = self.target_y
                    current_x = self.current_x
                    current_y = self.current_y

                # Kích thước bước di chuyển (độ) - điều chỉnh theo nhu cầu
                step_size = 2  

                # Cập nhật vị trí hiện tại của servo X tiến gần tới mục tiêu
                if current_x < target_x:
                    current_x = min(current_x + step_size, target_x)
                elif current_x > target_x:
                    current_x = max(current_x - step_size, target_x)

                # Cập nhật vị trí hiện tại của servo Y tiến gần tới mục tiêu
                if current_y < target_y:
                    current_y = min(current_y + step_size, target_y)
                elif current_y > target_y:
                    current_y = max(current_y - step_size, target_y)

                # Ghi vị trí mới vào servo
                self.servo_pinX.write(current_x)
                self.servo_pinY.write(current_y)

                # Cập nhật lại vị trí hiện tại
                with self.lock:
                    self.current_x = current_x
                    self.current_y = current_y

                # In ra vị trí hiện tại của servo để theo dõi
                print(f"Servo X: {self.current_x}°, Servo Y: {self.current_y}°")
            # Thời gian chờ ngắn để điều chỉnh tốc độ cập nhật
            time.sleep(0.02)  # 50Hz

    def stop(self):
        self.running = False
        self.wait()
        if self.board:
            self.board.exit()

    @pyqtSlot(int, int, int, int)
    def set_target(self, fx, fy, ws, hs):
        if self.active:
            with self.lock:
                # Cập nhật vị trí mục tiêu dựa trên tọa độ nhận được
                self.target_x = np.interp(fx, [0, ws], [0, 180])
                self.target_y = np.interp(fy, [0, hs], [0, 180])
                self.target_x = max(0, min(180, self.target_x))
                self.target_y = max(0, min(180, self.target_y))
                print(f"Updated target -> X: {self.target_x}, Y: {self.target_y}")
        else:
            print("Servo control is inactive. Target not set.")
