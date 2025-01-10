# main.py
import sys
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget
from PyQt5.QtCore import QThread, pyqtSignal, Qt
from PyQt5.QtGui import QPixmap, QImage, QStandardItem, QStandardItemModel
from main_ui import Ui_MainWindow
from detector import Detector
from control_servo import ControlServo
import cv2
import numpy as np
import pandas as pd
import os
import time
import recognizer
from resigter_user import Ui_RegisterWindow

recognizer = recognizer.Recognizer()

class MainWindow(QMainWindow):
    def __init__(self):
        super(MainWindow, self).__init__()
        self.centralWidget = QWidget()
        self.setCentralWidget(self.centralWidget)

        self.uic = Ui_MainWindow()
        self.uic.setupUi(self)

        # Connect UI buttons to functions
        self.uic.startBtn.clicked.connect(self.start_camera)
        self.uic.stopBtn.clicked.connect(self.stop_camera)
        self.uic.deleteBtn.clicked.connect(self.user_to_enemy)

        # Instantiate ControlServo with optional port
        self.control_servo = ControlServo(port='COM4')
        self.control_servo.connection_status_signal.connect(self.handle_servo_connection_status)
        self.control_servo.start()

        # Instantiate Detector with ControlServo
        self.detector = Detector(self.control_servo)

        # Pass the detector to CaptureVideo
        self.camera_thread = CaptureVideo(self, self.detector)
        self.camera_thread.signal.connect(self.show_webcam)

        # Initialize a flag to indicate servo availability
        self.servo_available = self.control_servo.active

    def handle_servo_connection_status(self, success, message):
        if success:
            self.uic.logBox.append(f"Servo Control: {message}")
            self.servo_available = True
        else:
            self.uic.logBox.append(f"Servo Control: {message}")
            self.servo_available = False

    def start_camera(self):
        self.uic.logBox.append('Start camera')
        # Start camera 
        if not self.camera_thread.isRunning():
            self.camera_thread.start()
        self.loadUsersToTable()  # Example call to display the table

    def show_webcam(self, cv_img):
        qt_img = self.convert_cv_qt(cv_img)
        self.uic.videoCamera.setPixmap(qt_img)

    def convert_cv_qt(self, cv_img):
        rgb_image = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_image.shape
        bytes_per_line = ch * w
        convert_to_Qt_format = QImage(rgb_image.data,
                                      w,
                                      h,
                                      bytes_per_line,
                                      QImage.Format.Format_RGB888)  # Updated format
        p = convert_to_Qt_format.scaled(800, 600, Qt.AspectRatioMode.KeepAspectRatio)
        return QPixmap.fromImage(p)

    def stop_camera(self):
        os.execl(sys.executable, sys.executable, *sys.argv)

    def user_to_enemy(self):
        # Define file paths
        users_file = "users.xlsx"

        # Ensure users.xlsx exists; if not, create it with appropriate headers
        if not os.path.exists(users_file):
            df_users = pd.DataFrame(columns=["Name", "Sex", "RegisterTime", "Type"])
            df_users.to_excel(users_file, index=False)
            self.uic.logBox.append("Created users.xlsx as it did not exist.")
        else:
            df_users = pd.read_excel(users_file)
            # Ensure 'Type' column exists
            if 'Type' not in df_users.columns:
                df_users['Type'] = 'User'
                df_users.to_excel(users_file, index=False)
                self.uic.logBox.append("Added 'Type' column to users.xlsx.")

        df_users = pd.read_excel(users_file)

        if df_users.empty:
            self.uic.logBox.append("No users available to move to the enemy list.")
            return

        selected_rows = self.uic.infoTable.selectionModel().selectedRows()
        row_indexes = [idx.row() for idx in selected_rows]

        if not row_indexes:
            user_to_move = df_users.iloc[-1]
            user_to_move['Type'] = 'Enemy'
            self.uic.logBox.append(f"Moved last user to enemy list: {user_to_move['Name']}")
            df_users.iloc[-1] = user_to_move
        else:
            users_moved = df_users.loc[row_indexes, 'Name'].tolist()
            df_users.loc[row_indexes, 'Type'] = 'Enemy'
            self.uic.logBox.append(f"Moved selected users to enemy: {', '.join(users_moved)}")

        # Save the updated DataFrames back to Excel
        df_users.to_excel(users_file, index=False)

        # Update the label map to include the new enemies
        self.recognizer.save_label_map()
        self.uic.logBox.append("Updated label with new enemy entries.")

        # Reload the user table in the UI
        self.loadUsersToTable()


    def keyPressEvent(self, event):
        if event.text() == 'a':
            self.register_win = QtWidgets.QMainWindow()
            self.register_ui = Ui_RegisterWindow()
            self.register_ui.setupUi(self.register_win, callback=self.startRegister)
            self.register_win.show()

    def startRegister(self, user_id):
        folder_name = f"user_{user_id}"
        self.uic.logBox.append(f"Registering new user: {folder_name}")
        self.user_to_register = folder_name
        self.register_mode = True

    def loadUsersToTable(self):
        users_file = "users.xlsx"
        enemies_file = "enemies.xlsx"
        
        # Load users and enemies
        df_users = pd.read_excel(users_file) if os.path.exists(users_file) else pd.DataFrame()
        df_enemies = pd.read_excel(enemies_file) if os.path.exists(enemies_file) else pd.DataFrame()
        
        # Add Type column
        if not df_users.empty:
            df_users['Type'] = 'User'
        if not df_enemies.empty:
            df_enemies['Type'] = 'Enemy'
        
        # Combine data
        df_combined = pd.concat([df_users, df_enemies], ignore_index=True)
        
        # Create model
        model = QStandardItemModel()
        if not df_combined.empty:
            model.setHorizontalHeaderLabels(df_combined.columns.tolist())
            for row in range(df_combined.shape[0]):
                for col in range(df_combined.shape[1]):
                    item = QStandardItem(str(df_combined.iat[row, col]))
                    model.setItem(row, col, item)
        
        self.uic.infoTable.setModel(model)


    def closeEvent(self, event):
        # Ensure threads are properly closed when the application exits
        self.control_servo.stop()
        if self.camera_thread.isRunning():
            self.camera_thread.stop()
            self.camera_thread.wait()
        event.accept()




class CaptureVideo(QThread):
    signal = pyqtSignal(np.ndarray)

    def __init__(self, parent, detector):
        super(CaptureVideo, self).__init__(parent)
        self.parent = parent
        self.detector = detector
        self.camera = cv2.VideoCapture(0)
        self.running = True

    def run(self):
        while self.running:
            ret, frame = self.camera.read()
            if ret:
                copy_frame = frame.copy()
                register_mode = getattr(self.parent, "register_mode", False)
                user_name = getattr(self.parent, "user_to_register", None)
                processed_frame, bboxs = self.detector.detect_faces(copy_frame, register_mode, user_name)
                self.signal.emit(processed_frame)
            # Optional: Add a small sleep to reduce CPU usage
            time.sleep(0.02)

    def stop(self):
        self.running = False
        self.wait()
        self.camera.release()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    main_win = MainWindow()
    main_win.show()
    sys.exit(app.exec())
