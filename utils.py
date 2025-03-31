import pandas as pd
import numpy as np
from cryptography.fernet import Fernet
import streamlit as st
from PIL import Image
from pathlib import Path
import tarfile


def decrypted(path):
    with open(path, "rb") as file:
        encrypted_data = file.read()

    cipher_suite = Fernet(st.secrets.access_credentials.filepwd.encode())
    decrypted_data = cipher_suite.decrypt(encrypted_data)
    with open("temp_data.h5", "wb") as file:
        file.write(decrypted_data)
    df = pd.read_hdf("temp_data.h5")
    return df


class Dataset:
    def __init__(self, path):
        # self.data = decrypted(path)
        self.data = pd.read_hdf(path)
        self.n_images = len(self.data["images"].iloc[0])

    def get_nb_images(self):
        return self.n_images

    def get_data(self, idx):
        return self.data[self.data["id_question"] == idx][["images", "prompt"]].values[
            0
        ]

    def get_ids_question(self):
        return self.data["id_question"].tolist()


class DataSession:

    def __init__(self, first_stage, second_stage, path_img, n_questions=-1):
        self.n_questions = n_questions
        self.dataset = {
            0: Dataset(first_stage),
            1: Dataset(second_stage),
        }
        self.stage = 0
        self.current_question = 0
        self.question_order = {
            0: np.random.permutation(self.dataset[0].get_ids_question())[:n_questions],
            1: np.random.permutation(self.dataset[1].get_ids_question())[:n_questions],
        }
        self.nquestions = len(self.question_order[0]) + len(self.question_order[1])
        self.question_number2stageandindex = {
            i: (0, j) for i, j in enumerate(self.question_order[0])
        }
        self.question_number2stageandindex.update(
            {
                i + len(self.question_order[0]): (1, j)
                for i, j in enumerate(self.question_order[1])
            }
        )
        self.path_img = Path(path_img)
        # self.tar = tarfile.open("img.tar.gz", "r:gz")
        self.tar = tarfile.open("data/img.tar", "r:")

    def extract_image(self, image_name):
        # extract image from tar file
        name_in_tar = "img/" + image_name
        if name_in_tar not in self.tar.getnames():
            raise ValueError(f"{name_in_tar} not in tar file")
        self.tar.extract(name_in_tar, "img")
        return Image.open("img/" + image_name)

    def get_stop(self, idx):
        return idx >= self.nquestions

    def get_nb_images(self, question_id):
        stage, _ = self.question_number2stageandindex[question_id]
        return self.dataset[stage].get_nb_images()

    def get_data_question(self, idx):
        stage, idx = self.question_number2stageandindex[idx]
        images, prompt = self.dataset[stage].get_data(idx)
        images = {k: self.extract_image(v) for k, v in images.items()}
        # images = {k: Image.open(self.path_img / v) for k, v in images.items()}
        return images, prompt

    def get_stage_idquestion(self, idx):
        return self.question_number2stageandindex[idx]

    def get_nquestions(self):
        return self.nquestions
