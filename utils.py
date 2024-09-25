import pandas as pd
import numpy as np
from cryptography.fernet import Fernet
import streamlit as st


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
        self.data = decrypted(path)
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

    def __init__(self, path_guidance, path_wo_guidance):
        self.dataset = {
            0: Dataset(path_wo_guidance),
            1: Dataset(path_guidance),
        }
        self.stage = 0
        self.current_question = 0
        self.question_order = {
            0: np.random.permutation(self.dataset[0].get_ids_question()),
            1: np.random.permutation(
                self.dataset[1].get_ids_question(),
            ),
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

    def get_stop(self, idx):
        return idx >= self.nquestions

    def get_nb_images(self, question_id):
        stage, _ = self.question_number2stageandindex[question_id]
        return self.dataset[stage].get_nb_images()

    def get_data_question(self, idx):
        stage, idx = self.question_number2stageandindex[idx]
        return self.dataset[stage].get_data(idx)

    def get_stage_idquestion(self, idx):
        return self.question_number2stageandindex[idx]

    def get_nquestions(self):
        return self.nquestions
