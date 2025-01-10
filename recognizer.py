import os
import cv2
import numpy as np
import json  # Import json for serialization

# recognizer.py

class Recognizer:
    def __init__(self):
        self.recognizer = cv2.face.LBPHFaceRecognizer_create()
        self.label_map = {}  # Maps label (int) to {'name': str, 'type': str}
        self.model_loaded = False
        self.model_path = "face_model.yml"
        self.label_map_path = "label_map.json"  # Path to save label_map

    def train_model(self, dataset_path="dataset"):
        faces = []
        labels = []
        label_counter = 0

        # Build a label map and training data
        for folder_name in os.listdir(dataset_path):
            user_folder = os.path.join(dataset_path, folder_name)
            if os.path.isdir(user_folder):
                self.label_map[label_counter] = {"name": folder_name, "type": "User"}
                for img_file in os.listdir(user_folder):
                    if img_file.lower().endswith(".jpg"):
                        img_path = os.path.join(user_folder, img_file)
                        gray = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
                        if gray is not None:
                            faces.append(gray)
                            labels.append(label_counter)
                label_counter += 1

        # Include enemies in the label map
        enemies_file = "enemies.xlsx"
        if os.path.exists(enemies_file):
            df_enemies = pd.read_excel(enemies_file)
            for idx, row in df_enemies.iterrows():
                self.label_map[label_counter] = {"name": row["Name"], "type": "Enemy"}
                # Assuming enemy images are stored similarly
                enemy_folder = os.path.join(dataset_path, row["Name"])
                for img_file in os.listdir(enemy_folder):
                    if img_file.lower().endswith(".jpg"):
                        img_path = os.path.join(enemy_folder, img_file)
                        gray = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
                        if gray is not None:
                            faces.append(gray)
                            labels.append(label_counter)
                label_counter += 1

        if len(faces) > 0:
            self.recognizer.train(faces, np.array(labels))
            self.recognizer.save(self.model_path)
            self.model_loaded = True
            self.save_label_map()  # Save label_map after training
            self.load_model() 

    def save_label_map(self):
        import pandas as pd
        label_map_data = {}
        
        # Load users
        users_file = "users.xlsx"
        if os.path.exists(users_file):
            df_users = pd.read_excel(users_file)
            for idx, row in df_users.iterrows():
                label_map_data[str(idx)] = {"name": row["Name"], "type": "User"}
        
        # Load enemies
        enemies_file = "enemies.xlsx"
        if os.path.exists(enemies_file):
            df_enemies = pd.read_excel(enemies_file)
            for idx, row in df_enemies.iterrows():
                label_map_data[str(len(label_map_data))] = {"name": row["Name"], "type": "Enemy"}
        
        self.label_map = label_map_data
        
        with open(self.label_map_path, "w") as f:
            json.dump(self.label_map, f, indent=4)
        print(f"Label map saved to {self.label_map_path}")
        
    def load_model(self):
        if os.path.exists(self.model_path):
            self.recognizer.read(self.model_path)
            self.model_loaded = True
            self.load_label_map()  # Load label_map when loading the model
            print(f"Model loaded from {self.model_path}")
        else:
            print(f"Model file {self.model_path} not found.")

    def load_label_map(self):
        if os.path.exists(self.label_map_path):
            with open(self.label_map_path, "r") as f:
                self.label_map = json.load(f)
            print(f"Label map loaded from {self.label_map_path}")
        else:
            print(f"Label map file {self.label_map_path} not found.")

    def recognize_face(self, face_region):
        # Convert to grayscale for LBPH
        gray_face = cv2.cvtColor(face_region, cv2.COLOR_BGR2GRAY)
        if not self.model_loaded:
            return False, None, None

        label, confidence = self.recognizer.predict(gray_face)
        # Lower confidence => better match
        if confidence < 100:
            label_str = str(label)
            user_info = self.label_map.get(label_str, None)
            if user_info:
                return True, user_info['name'], user_info['type']
        return False, None, None
