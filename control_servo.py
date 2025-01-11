# control_servo.py
import pyfirmata 
from PyQt5.QtCore import QThread, pyqtSignal, pyqtSlot
import numpy as np
import time
import threading
import serial  # Ensure this is imported to handle SerialException

class ControlServo(QThread):
    set_target_signal = pyqtSignal(int, int, int, int)    
    connection_status_signal = pyqtSignal(bool, str)

    def __init__(self, parent=None, port='COM4', baudrate=57600):
        super(ControlServo, self).__init__(parent)
        self.port = port
        self.baudrate = baudrate
        self.servo_pinX = None
        self.servo_pinY = None
        self.board = None
        self.target_queue = []
        self.lock = threading.Lock()
        self.running = True
        self.active = False  

        try:
            self.board = pyfirmata.Arduino(self.port, baudrate=self.baudrate)

            self.iterator = pyfirmata.util.Iterator(self.board)
            self.iterator.start()
            time.sleep(1)

            self.board.servo_config(9, min_pulse=544, max_pulse=2400)   # Configure servo pin 9
            self.board.servo_config(10, min_pulse=544, max_pulse=2400)  # Configure servo pin 10
            self.servo_pinX = self.board.get_pin('d:9:s')
            self.servo_pinY = self.board.get_pin('d:10:s')
            print("Servo pin X:", self.servo_pinX)
            print("Servo pin Y:", self.servo_pinY)
            if not self.servo_pinX or not self.servo_pinY:
                raise ValueError("Servo pins not initialized.")
            self.servo_pinX.write(90)  
            self.servo_pinY.write(90) 
            time.sleep(1)
            self.active = True
            # Test servo movement
            print(f"Connected to Arduino on {self.port}")
            self.connection_status_signal.emit(True, f"Connected to {self.port}")
        except serial.SerialException as e:
            self.active = False
            print(f"Failed to connect to Arduino on {self.port}: {e}")
            self.connection_status_signal.emit(False, f"Failed to connect to {self.port}: {e}")

        self.set_target_signal.connect(self.set_target)

    def run(self):
        while self.running:
            if self.active:
                with self.lock:
                    if self.target_queue:
                        fx, fy, ws, hs = self.target_queue.pop(0)
                        servoX = np.interp(fx, [0, ws], [0, 180])
                        servoY = np.interp(fy, [0, hs], [0, 180])
                        servoX = max(0, min(180, servoX))
                        servoY = max(0, min(180, servoY))
                        self.servo_pinX.write(servoX)
                        self.servo_pinY.write(servoY)
                        print(f"Servo X set to: {servoX}, Servo Y set to: {servoY}")
            time.sleep(0.1)
    
    def stop(self):
        self.running = False
        self.wait()
        if self.board:
            self.board.exit()

    @pyqtSlot(int, int, int, int)
    def set_target(self, fx, fy, ws, hs):
        if self.active:
            with self.lock:
                self.target_queue.append((fx, fy, ws, hs))
        else:
            print("Servo control is inactive. Target not set.")


