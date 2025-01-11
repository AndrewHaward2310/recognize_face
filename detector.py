# detector.py
import os
import cv2
import time
import numpy as np
import pandas as pd
from recognizer import Recognizer
from cvzone.FaceDetectionModule import FaceDetector

class Detector:
    def __init__(self, control_servo):
        self.detector = FaceDetector()
        self.recognizer = Recognizer()
        self.recognizer.load_model()
        self.user_name = None
        self.register_mode = False
        self.model_has_been_trained = False

        self.known_faces = {}
        self.next_face_id = 0
        self.trackers = {}
        self.bounding_boxes = {}
        self.unrecognized_start = {}
        self.capture_in_progress = {}
        self.capture_count = {}
        self.current_user = {}

        self.control_servo = control_servo

    def train_model(self):
        self.recognizer.train_model()
        self.model_has_been_trained = True

    def draw_bounding_box(self, img, fx, fy, fw, fh, color, label, countdown=False, face_id=None):
        cv2.rectangle(img, (fx, fy), (fx + fw, fy + fh), color, 2)
        cv2.putText(img, label, (fx, fy - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.9, color, 2)
        
        if countdown:
            if face_id is not None and face_id in self.unrecognized_start:
                remaining_time = 30 - int(time.time() - self.unrecognized_start[face_id])
                remaining_time = max(0, remaining_time)  # Prevent negative time
                cv2.putText(img, f"Time to lock: {remaining_time}s",
                            (fx, fy + fh + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.9, color, 2)
            else:
                cv2.putText(img, "Time to lock: N/A",
                            (fx, fy + fh + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.9, color, 2)

    def detect_faces(self, img, register_mode=False, user_name=None):
        self.register_mode = register_mode
        self.user_name = user_name

        img, bboxs = self.detector.findFaces(img, draw=False)
        if img is None:
            return img, bboxs

        ws, hs, _ = img.shape
        current_time = time.time()

        if bboxs:
            for bbox in bboxs:
                x, y, w, h = bbox["bbox"]
                fx, fy, fw, fh = x, y, w, h
                face_id = self.get_face_id(bbox)

                if face_id not in self.trackers:
                    tracker = cv2.TrackerKCF_create()
                    tracker.init(img, (fx, fy, fw, fh))
                    self.trackers[face_id] = tracker
                    self.bounding_boxes[face_id] = (fx, fy, fw, fh)
                    self.unrecognized_start[face_id] = current_time
                    self.capture_in_progress[face_id] = False
                    self.capture_count[face_id] = 0
                    self.current_user[face_id] = None

                success, updated_bbox = self.trackers[face_id].update(img)
                if success:
                    fx, fy, fw, fh = [int(v) for v in updated_bbox]
                    self.bounding_boxes[face_id] = (fx, fy, fw, fh)

                    face_img = img[fy:fy+fh, fx:fx+fw]
                    recognized, user_label, user_type = self.recognizer.recognize_face(face_img)
                    
                    if recognized:
                        if user_type == "Enemy":
                            self.lock_target(img, fx, fy, ws, hs, face_id, "ENEMY")
                        else:
                            # Draw green box for users
                            color = (0, 255, 0)  # Green
                            self.draw_bounding_box(img, fx, fy, fw, fh, color, str(user_label))
                        
                        self.current_user[face_id] = user_label
                        self.unrecognized_start[face_id] = current_time
                    else:
                        elapsed = current_time - self.unrecognized_start[face_id]
                        if not self.register_mode:
                            if elapsed > 30:
                                self.lock_target(img, fx, fy, ws, hs, face_id, "ENEMY")
                            else:
                                self.draw_bounding_box(img, fx, fy, fw, fh, (0, 255, 255), "UNKNOWN", countdown=True, face_id=face_id)
                    
                    if self.register_mode and self.user_name:
                        self.capture_face(img, face_id, face_img, fx, fy, fw, fh)
                else:
                    continue

        return img, bboxs

    def get_face_id(self, bbox):
        x, y, w, h = bbox["bbox"]
        center = (x + w // 2, y + h // 2)
        for face_id, (fx, fy, fw, fh) in self.bounding_boxes.items():
            existing_center = (fx + fw // 2, fy + fh // 2)
            distance = np.linalg.norm(np.array(center) - np.array(existing_center))
            if distance < 50:
                return face_id
        face_id = self.next_face_id
        self.next_face_id += 1
        return face_id

    def lock_target(self, img, fx, fy, ws, hs, face_id, label):
        cv2.circle(img, (fx + self.bounding_boxes[face_id][2] // 2,
                        fy + self.bounding_boxes[face_id][3] // 2), 50, (0, 0, 255), 2)
        cv2.putText(img, label, (fx + 15, fy - 15),
                    cv2.FONT_HERSHEY_PLAIN, 2, (0, 0, 255), 2)
        cv2.line(img, (0, fy + self.bounding_boxes[face_id][3] // 2),
                 (hs, fy + self.bounding_boxes[face_id][3] // 2), (0, 0, 0), 2)
        cv2.line(img, (fx + self.bounding_boxes[face_id][2] // 2, 0),
                 (fx + self.bounding_boxes[face_id][2] // 2, ws), (0, 0, 0), 2)
        cv2.circle(img, (fx + self.bounding_boxes[face_id][2] // 2,
                        fy + self.bounding_boxes[face_id][3] // 2), 15, (0, 0, 255), cv2.FILLED)
        cv2.putText(img, "TARGET LOCKED", (850, 50),
                    cv2.FONT_HERSHEY_PLAIN, 3, (255, 0, 255), 3)

        # Emit the target coordinates to ControlServo if active
        if self.control_servo and self.control_servo.active:
            target_x = fx + self.bounding_boxes[face_id][2] // 2
            target_y = fy + self.bounding_boxes[face_id][3] // 2
            self.control_servo.set_target_signal.emit(target_x, target_y, ws, hs)

    def capture_face(self, img, face_id, face_img, fx, fy, fw, fh):
        import sys, os
        if not self.capture_in_progress[face_id]:
            self.capture_in_progress[face_id] = True
            self.capture_count[face_id] = 0

        if self.capture_count[face_id] < 100:
            folder_name = f"dataset/{self.user_name}"
            if not os.path.exists(folder_name):
                os.makedirs(folder_name)
            img_path = os.path.join(folder_name, f"{self.capture_count[face_id]}.jpg")
            cv2.imwrite(img_path, face_img)
            self.capture_count[face_id] += 1
            # Update the bounding box with capture count
            self.draw_bounding_box(img, fx, fy, fw, fh, (0, 0, 255), str(self.capture_count[face_id]))
        else:
            self.capture_in_progress[face_id] = False
            self.capture_count[face_id] = 0
            self.register_mode = False
            self.recognizer.train_model()
            print(f"Finished capturing for user: {self.user_name}")
    
            os.execl(sys.executable, sys.executable, *sys.argv)
