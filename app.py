import streamlit as st
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from email.mime.text import MIMEText
import pandas as pd
import smtplib
from pathlib import Path
from utils import DataSession
import time
import datetime

title_text = "### Text-Image Evaluation"
chosen_one_label = "🔻"
text_question = (
    "Which image(s) best matche(s) the description? Select all that apply or none."
)
size_icon = "big"
stage = ["wo_guidance", "w_guidance"]

homepage_indication = """
# Welcome to the evaluation of the text-image generation evaluation! 🚀

You will be presented with a description and multiples images. Your task is to select the images that best matches the description.

- You can select multiple images if you think they match the description equally well.
- You can also not select any image if you think none of them match the description.

You can zoom in the images by clicking on the arrows in the top right corner of the image.

You will have two stages to complete.
- First one where you will be presented only two images
- A second one where you will be presented three images. 

During the completion of the evaluation, you will not be able to go back to previous questions.
A progress bar will indicate your progress.

Thank you for your participation! 😊
"""

finish_indication = """ ### The End"""
acknowledgment = "Thank you for your participation! 😊"
warning = "**Please quit when the success message appears.**"
login_indication = """### 🔒 Login to Access the App"""
text_submit = "Continue"
question_age = "What is yor age range?"
question_expert = "Are you an expert in computer vision?"

TITLE = st.empty()
PROGRESSBAR = st.empty()
DESCRIPITON = st.empty()
CAPTION = st.empty()
COLS = st.empty()
CHECKBOX = {}
SUBMIT = st.empty()
CAPTIONS = {}
IMAGES = {}
ID2HASH = {}


def send_email(
    subject,
    body,
    json_attachment,
):

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
    timestamp = datetime.datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
    part.add_header("Content-Disposition", f"attachment; filename={timestamp}.json")
    msg.attach(part)

    try:
        with smtplib.SMTP_SSL(smtp_server, smtp_port) as server:
            server.login(email_from, password)
            server.sendmail(email_from, email_to, msg.as_string())
        st.success(f"Data saved, thanks")
        st.balloons()
    except Exception as e:
        st.error(f"Error during saving: {e}")


def start_survey():
    if st.session_state.age_radio is None or st.session_state.expert_radio is None:
        st.toast("Please answer all questions before starting the survey")
    else:
        st.session_state.start = True
        st.session_state.age = st.session_state.age_radio
        st.session_state.expert = st.session_state.expert_radio


def create_finish_page():
    TITLE.markdown(finish_indication, unsafe_allow_html=False)
    PROGRESSBAR.progress(
        st.session_state.current_question / st.session_state.dataset.get_nquestions()
    )
    DESCRIPITON.markdown(acknowledgment)
    CAPTION.markdown(warning)
    send_email(
        subject="User Evaluation",
        body=f"""Attached is the JSON file with the evaluation.\nAge: {st.session_state.age}, Expert: {st.session_state.expert}
        """,
        json_attachment=st.session_state.user_responses.to_json(orient="records"),
    )


def authenticate(password):
    if password == st.secrets.access_credentials.password:
        st.session_state.authenticated = True
        st.toast("You have successfully logged in!")
    else:
        with st.spinner("Authenticating..."):
            time.sleep(5)
        st.error("Incorrect password. Please try again.")


def update_choice_val():
    choices = []
    for i in range(
        st.session_state.dataset.get_nb_images(st.session_state.current_question)
    ):
        if st.session_state[f"checkbox_{i}"]:
            choices.append(i)
    if len(choices) == 0:
        choices.append(None)
    st.session_state.choice_val = choices


def change_caption():
    update_choice_val()
    n_images = st.session_state.dataset.get_nb_images(st.session_state.current_question)
    for i in range(n_images):
        if i is not None and i in st.session_state.choice_val:
            CAPTIONS[i].markdown(
                f"<div style='text-align: center'><{size_icon}>{chosen_one_label}</{size_icon}> </div>",
                unsafe_allow_html=True,
            )
        else:
            CAPTIONS[i].markdown(f"", unsafe_allow_html=True)


def create_survey_page():
    TITLE.markdown(title_text, unsafe_allow_html=False)
    PROGRESSBAR.progress(
        st.session_state.current_question / st.session_state.dataset.get_nquestions()
    )
    n_images = st.session_state.dataset.get_nb_images(st.session_state.current_question)
    cols = COLS.columns(n_images)
    images, prompt = st.session_state.dataset.get_data_question(
        st.session_state.current_question
    )
    DESCRIPITON.markdown(f"{text_question}")
    CAPTION.markdown(f"CAPTION : **{prompt}**")
    for (i, col), (hash, image) in zip(enumerate(cols), images.items()):
        with col:
            CAPTIONS[i] = st.markdown(f"", unsafe_allow_html=True)
            IMAGES[i] = st.image(image)
            ID2HASH[i] = hash
            _, subcol2 = st.columns(2)
            with subcol2:
                CHECKBOX[i] = st.container()
                with CHECKBOX[i]:
                    st.checkbox(
                        label=f"{i}",
                        value=False,
                        key=f"checkbox_{i}",
                        on_change=change_caption,
                        label_visibility="collapsed",
                    )
    change_caption()
    SUBMIT.button(label=text_submit, on_click=submit_clicked)


def create_homepage():
    TITLE.markdown(homepage_indication, unsafe_allow_html=False)
    DESCRIPITON.radio(
        question_age,
        ["< 18", "18-25", "26-35", "36-45", "46-55", "> 55"],
        index=None,
        key="age_radio",
        horizontal=True,
    )
    CAPTION.radio(
        question_expert, ["Yes", "No"], key="expert_radio", index=None, horizontal=True
    )
    SUBMIT.button(label=text_submit, on_click=start_survey)


def submit_clicked():
    if st.session_state.choice_val is None:
        st.error("Please answer the question before submitting")
    else:
        stage, id_question = st.session_state.dataset.get_stage_idquestion(
            st.session_state.current_question
        )
        final_choices = []
        for i in st.session_state.choice_val:
            if i is not None:
                final_choices.append(ID2HASH[i])
            else:
                final_choices.append(None)
        new_entry = pd.DataFrame(
            {
                "stage": [stage],
                "id_question": [id_question],
                "choice": [final_choices],
            }
        )
        st.session_state.user_responses = pd.concat(
            [st.session_state.user_responses, new_entry], ignore_index=True
        )

        for i in range(
            st.session_state.dataset.get_nb_images(st.session_state.current_question)
        ):
            CAPTIONS[i].empty()
            IMAGES[i].empty()
            CHECKBOX[i].empty()
            st.session_state[f"checkbox_{i}"] = False
        st.session_state.current_question += 1
        st.session_state.choice_val = None
        if st.session_state.dataset.get_stop(st.session_state.current_question):
            st.session_state.end = True


if "authenticated" not in st.session_state or not st.session_state.authenticated:
    st.session_state.authenticated = False
    TITLE.markdown(login_indication, unsafe_allow_html=False)
    password = DESCRIPITON.text_input("Enter the password", type="password")
    SUBMIT.button(label="Submit", on_click=authenticate, args=(password,))

else:
    if "start" not in st.session_state:
        st.session_state.start = False
        st.session_state.end = False
    if "age" not in st.session_state:
        st.session_state.age = None
    if "expert" not in st.session_state:
        st.session_state.expert = None
    if "choice_val" not in st.session_state:
        st.session_state.choice_val = None  # To store selected image index
    if "user_responses" not in st.session_state:
        st.session_state.user_responses = pd.DataFrame(
            columns=["stage", "id_question", "choice"]
        )
    if "dataset" not in st.session_state:
        st.session_state.dataset = DataSession(
            path_guidance=Path("data/w_guidance_eval.pkl"),
            path_wo_guidance=Path("data/wo_guidance_eval.pkl"),
        )
        st.session_state.current_question = 0

    if st.session_state.start and not st.session_state.end:
        create_survey_page()  # If the survey has started, show the survey page
    elif st.session_state.end:
        create_finish_page()
    else:
        create_homepage()  # Otherwise, show the homepage
