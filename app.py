import streamlit as st
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from email.mime.text import MIMEText
import pandas as pd
import smtplib
from pathlib import Path
import time
import datetime
import random
import tarfile
import numpy as np


class Dataset:
    """
    Handles loading and accessing data from a single H5 dataset.
    """

    def __init__(self, path):
        self.data = pd.read_hdf(path)
        self.n_images = len(self.data["images"].iloc[0])

    def get_nb_images(self):
        """Returns the number of images per question in this dataset."""
        return self.n_images

    def get_data(self, idx):
        """
        Retrieves image references (e.g., filenames) and prompt for a given question ID.
        Returns the raw image references (e.g., dictionary of {hash: filename}) and the prompt string.
        """
        return self.data[self.data["id_question"] == idx][["images", "prompt"]].values[
            0
        ]

    def get_ids_question(self):
        """Returns a list of all unique question IDs in this dataset."""
        return self.data["id_question"].tolist()


class DataSession:
    """
    Manages the overall survey data, including multiple stages and image extraction from a tar file.
    """

    def __init__(
        self,
        first_stage: Path,
        second_stage: Path,
        path_img: str,
        n_questions: int = -1,
    ):
        self.n_questions_per_stage = n_questions
        self.dataset = {
            0: Dataset(first_stage),
            1: Dataset(second_stage),
        }
        self.question_order = {
            0: np.random.permutation(self.dataset[0].get_ids_question())[
                : self.n_questions_per_stage
            ],
            1: np.random.permutation(self.dataset[1].get_ids_question())[
                : self.n_questions_per_stage
            ],
        }
        self.total_nquestions = len(self.question_order[0]) + len(
            self.question_order[1]
        )
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
        try:
            self.tar = tarfile.open("data/img.tar", "r:")
        except tarfile.ReadError as e:
            st.error(
                f"Error opening tar file 'data/img.tar': {e}. Please ensure it exists and is not corrupted."
            )
            self.tar = None

    def extract_image(self, image_name: str) -> bytes:
        if self.tar is None:
            raise ValueError("Tar file not loaded. Cannot extract image.")
        name_in_tar = "img/" + image_name
        if name_in_tar not in self.tar.getnames():
            raise ValueError(f"'{name_in_tar}' not found in tar file.")
        f = self.tar.extractfile(name_in_tar)
        if f is None:
            raise ValueError(f"Could not extract '{name_in_tar}' from tar file.")
        return f.read()

    def get_stop(self, current_question_idx: int) -> bool:
        return current_question_idx >= self.total_nquestions

    def get_nb_images(self, current_question_idx: int) -> int:
        stage, _ = self.question_number2stageandindex[current_question_idx]
        return self.dataset[stage].get_nb_images()

    def get_data_question(
        self, current_question_idx: int
    ) -> tuple[dict[str, bytes], str]:
        stage, dataset_idx = self.question_number2stageandindex[current_question_idx]
        image_references, prompt = self.dataset[stage].get_data(dataset_idx)
        images_data = {k: self.extract_image(v) for k, v in image_references.items()}
        return images_data, prompt

    def get_stage_idquestion(self, current_question_idx: int) -> tuple[int, int]:
        return self.question_number2stageandindex[current_question_idx]

    def get_nquestions(self) -> int:
        return self.total_nquestions


# --- UI Constants ---
TITLE_TEXT = "### Text-Image Evaluation"
TEXT_QUESTION = (
    "Which image(s) best match(es) the description? Select all that apply or none."
)
PREFERENCE_QUESTION = "Which image do you prefer?"
HOMEPAGE_INDICATION = """
# Welcome to the Text-Image Evaluation! 🚀

You will see a description and multiple images.

Your task:
1. Select all images that match the description. Choose none if no image matches.
2. Pick your favorite image or none if you have no preference.

**Tips:**
- Zoom your browser for better visibility.
- Click the square in the top-right corner of an image to enlarge it.

The evaluation has two stages:
1. Stage 1: 3 images per description.
2. Stage 2: 2 images per description.

You cannot revisit previous questions. A progress bar will track your progress.

Thank you for participating! 😊
"""
FINISH_INDICATION = "### Survey Complete! 🎉"
ACKNOWLEDGMENT = """
Thank you for your participation! 😊
Your responses have been recorded. Click the button below to start a new session
if you'd like to annotate more images.

**Please close this tab when you see the success message.**
"""
LOGIN_INDICATION = "### 🔒 Login to Access the App"
SUBMIT_BUTTON_TEXT = "Continue"
QUESTION_AGE = "What is your age range?"
QUESTION_EXPERT = "Are you an expert in computer vision?"
NQUESTIONS_PER_STAGE = 6


# --- Email Sending Function ---
def send_email(subject, body, json_attachment, age, expert):
    try:
        email_from = st.secrets.email_credentials.email_from
        password = st.secrets.email_credentials.password
        smtp_server = st.secrets.email_credentials.smtp_server
        smtp_port = st.secrets.email_credentials.smtp_port
        email_to = st.secrets.email_credentials.email_to

        msg = MIMEMultipart()
        msg["From"] = email_from
        msg["To"] = email_to
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        part = MIMEBase("application", "octet-stream")
        part.set_payload(json_attachment.encode("utf-8"))
        encoders.encode_base64(part)
        filename = (
            datetime.datetime.now().strftime("%Y_%m_%d_%H_%M_%S") + f"_{age}_{expert}"
        )
        part.add_header("Content-Disposition", f"attachment; filename={filename}.json")
        msg.attach(part)

        with smtplib.SMTP_SSL(smtp_server, smtp_port) as server:
            server.login(email_from, password)
            server.sendmail(email_from, email_to, msg.as_string())
        st.success("Data saved successfully! Thank you for your participation.")
        st.balloons()
        return True
    except Exception as e:
        st.error(f"Error during saving: {e}")
        return False


# --- Session State Management ---
def initialize_session_state():
    defaults = {
        "authenticated": False,
        "start": False,
        "end": False,
        "age": None,
        "expert": None,
        "user_responses": pd.DataFrame(
            columns=["stage", "id_question", "choice", "preference"]
        ),
        "dataset": None,
        "current_question": 0,
        "shuffle": None,
        "choice_semantic_pills": [],
        "radio_pref_choice": "None",
        "id_to_hash_map": {},
        "email_sent_flag": False,
        "login_message_placeholder": None,  # Added for dynamic messages on login page
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def start_survey():
    if (
        st.session_state.get("age_radio") is None
        or st.session_state.get("expert_radio") is None
    ):
        st.error("Please answer all questions before starting the survey.")
        return

    st.session_state.start = True
    st.session_state.age = st.session_state.age_radio
    st.session_state.expert = st.session_state.expert_radio
    st.session_state.dataset = DataSession(
        first_stage=Path("data/gsn_eval.h5"),
        second_stage=Path("data/sd3_eval.h5"),
        path_img="img",
        n_questions=NQUESTIONS_PER_STAGE,
    )
    # Rerun to transition to the survey page
    st.rerun()


def restart_survey():
    st.session_state.user_responses = pd.DataFrame(
        columns=["stage", "id_question", "choice", "preference"]
    )
    st.session_state.dataset = DataSession(
        first_stage=Path("data/gsn_eval.h5"),
        second_stage=Path("data/sd3_eval.h5"),
        path_img="img",
        n_questions=NQUESTIONS_PER_STAGE,
    )
    st.session_state.current_question = 0
    st.session_state.end = False
    st.session_state.shuffle = None
    st.session_state.choice_semantic_pills = []
    st.session_state.radio_pref_choice = "None"
    st.session_state.id_to_hash_map = {}
    st.session_state.email_sent_flag = False


def handle_login_submission():
    """
    Handles authentication and manages the UI feedback for correct/incorrect password.
    This function will be called directly in the form's submission block.
    """
    password_input = st.session_state.password_input_field

    if password_input == st.secrets.access_credentials.password:
        # Correct password: Set authenticated and force rerun
        st.session_state.authenticated = True
        st.success("You have successfully logged in!")
        st.rerun()  # Force an immediate rerun to switch to the homepage
    else:
        # Incorrect password: Show spinner, then error message
        # Use the placeholder created in create_login_page
        if st.session_state.login_message_placeholder:
            with st.session_state.login_message_placeholder:
                with st.spinner("Authenticating..."):
                    time.sleep(2)  # Simulate work/delay for wrong password
                st.error("Incorrect password. Please try again.")


def submit_question_response():
    selected_semantic_indices = st.session_state.choice_semantic_pills
    selected_preference_value = st.session_state.radio_pref_choice

    stage, id_question = st.session_state.dataset.get_stage_idquestion(
        st.session_state.current_question
    )

    if not selected_semantic_indices:
        final_choices = [None]
    else:
        final_choices = [
            st.session_state.id_to_hash_map[idx] for idx in selected_semantic_indices
        ]

    if selected_preference_value == "None":
        final_preference = None
    else:
        pref_index = int(selected_preference_value)
        final_preference = st.session_state.id_to_hash_map.get(pref_index)

    new_entry = pd.DataFrame(
        {
            "stage": [stage],
            "id_question": [id_question],
            "choice": [final_choices],
            "preference": [final_preference],
        }
    )
    st.session_state.user_responses = pd.concat(
        [st.session_state.user_responses, new_entry], ignore_index=True
    )

    st.session_state.current_question += 1
    st.session_state.shuffle = None
    st.session_state.choice_semantic_pills = []
    st.session_state.radio_pref_choice = "None"
    st.session_state.id_to_hash_map = {}

    if st.session_state.dataset.get_stop(st.session_state.current_question):
        st.session_state.end = True

    # st.rerun()  # Rerun to update the page after submission


# --- UI Page Functions ---
def create_login_page():
    st.markdown(LOGIN_INDICATION)
    with st.form("login_form"):
        password = st.text_input(
            "Enter the password", type="password", key="password_input_field"
        )
        submitted = st.form_submit_button("Login")

        # Create a placeholder at the top level of the login page function
        if (
            "login_message_placeholder" not in st.session_state
            or st.session_state.login_message_placeholder is None
        ):
            st.session_state.login_message_placeholder = st.empty()

        if submitted:
            handle_login_submission()  # Call the function that handles login and rerun


def create_homepage():
    st.markdown(HOMEPAGE_INDICATION)
    with st.form("user_info_form"):
        st.radio(
            QUESTION_AGE,
            ["-18", "18-25", "26-35", "36-45", "46-55", "+55"],
            index=None,
            key="age_radio",
            horizontal=True,
        )
        st.radio(
            QUESTION_EXPERT,
            ["Yes", "No"],
            key="expert_radio",
            index=None,
            horizontal=True,
        )
        submitted = st.form_submit_button(SUBMIT_BUTTON_TEXT)
        if submitted:
            start_survey()


def create_survey_page():
    st.markdown(TITLE_TEXT)
    progress_value = (
        st.session_state.current_question / st.session_state.dataset.get_nquestions()
    )
    st.progress(
        progress_value,
        text=f"Progress: {st.session_state.current_question}/{st.session_state.dataset.get_nquestions()}",
    )

    n_images = st.session_state.dataset.get_nb_images(st.session_state.current_question)
    images_raw, prompt = st.session_state.dataset.get_data_question(
        st.session_state.current_question
    )
    images_list = list(images_raw.items())

    if st.session_state.shuffle is None:
        st.session_state.shuffle = random.sample(range(n_images), n_images)

    shuffled_images = [images_list[i] for i in st.session_state.shuffle]
    st.session_state.id_to_hash_map = {
        i: shuffled_images[i][0] for i in range(n_images)
    }

    st.markdown(f"**Caption:** {prompt}")

    cols = st.columns(n_images)
    for i, col in enumerate(cols):
        with col:
            st.markdown(
                f"<div style='text-align: center; font-size: 20px; font-weight: bold;'>{i}</div>",
                unsafe_allow_html=True,
            )
            st.image(shuffled_images[i][1], use_container_width=True)

    st.pills(
        label=TEXT_QUESTION,
        options=[i for i in range(n_images)],
        key="choice_semantic_pills",
        selection_mode="multi",
    )

    radio_options = ["None"] + [str(i) for i in range(n_images)]
    st.radio(
        label=PREFERENCE_QUESTION,
        options=radio_options,
        index=0,
        key="radio_pref_choice",
        horizontal=True,
    )

    st.button(
        label=SUBMIT_BUTTON_TEXT, on_click=submit_question_response, type="primary"
    )


def create_finish_page():
    st.markdown(FINISH_INDICATION)
    st.progress(1.0, text="Survey Complete!")
    st.markdown(ACKNOWLEDGMENT)

    if st.session_state.get("email_sent_flag", False) is False:
        if send_email(
            subject="[User Evaluation Results]",
            body=f"Evaluation completed.\nAge: {st.session_state.age}\nExpert: {st.session_state.expert}",
            json_attachment=st.session_state.user_responses.to_json(orient="records"),
            age=st.session_state.age,
            expert=st.session_state.expert,
        ):
            st.session_state.email_sent_flag = True

    st.button(label="Start New Session", on_click=restart_survey, type="secondary")
    # print dataframe
    print(st.session_state.user_responses)


# --- Main Application Flow ---
def main():
    initialize_session_state()

    if not st.session_state.authenticated:
        create_login_page()
    elif not st.session_state.start:
        create_homepage()
    elif st.session_state.end:
        create_finish_page()
    else:
        create_survey_page()


if __name__ == "__main__":
    main()
