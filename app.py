import streamlit as st
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from email.mime.text import MIMEText
import pandas as pd
import smtplib
import numpy as np
from pathlib import Path
from utils import DataSession

# import streamlit_authenticator as stauth

label_bad = "bad"
label_good = "good"
title_text = "### Text-Image Evaluation"
chosen_one_label = "🔻"
text_question = "Which image best matches the description?"
size_icon = "big"
stage = ["wo_guidance", "w_guidance"]

homepage_indication = """
# Welcome to the evaluation of the text-image generation evaluation! 🚀

You will be presented with a description and multiples images. Your task is to select the image that best matches the description. You can also select "equally bad" or "equally good" if you think that none of the images are better than the others. 

You can zoom in the images by clicking on the arrows in the top right corner of the image.

You will have two stages to complete. 
- First one where you will be presented only two images
- A second one where you will be presented three images. 



Thank you for your participation! 😊
"""

finish_indication = """
## The End

Please quit when the success message appears. 

Thank you for your participation! 😊

"""
login_indication = """### 🔒 Login to Access the App"""

text_submit = "Continue"

TITLE = st.empty()
DESCRIPITON = st.empty()
COLS = st.empty()
RADIO = st.empty()
STARTINFO = st.empty()
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
    part.add_header("Content-Disposition", f"attachment; filename=responses.json")
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
    st.session_state.start = True


def create_finish_page():
    TITLE.markdown(finish_indication, unsafe_allow_html=False)
    send_email(
        subject="User Evaluation",
        body="Attached is the JSON file with the evaluation",
        json_attachment=st.session_state.user_responses.to_json(orient="records"),
    )

    st.write(st.session_state.user_responses)


def authenticate(password):
    if password == st.secrets.access_credentials.password:
        st.session_state.authenticated = True
        st.success("You have successfully logged in!")
    else:
        st.error("Incorrect password. Please try again.")


def change_caption():
    idx = st.session_state.choice_val
    n_images = st.session_state.dataset.get_nb_images(st.session_state.current_question)
    if isinstance(idx, int):
        for i in range(n_images):
            if i == idx:
                CAPTIONS[i].markdown(
                    f"<div style='text-align: center'> {i}<{size_icon}>{chosen_one_label}</{size_icon}> </div>",
                    unsafe_allow_html=True,
                )
            else:
                CAPTIONS[i].markdown(
                    f"<div style='text-align: center'> {i} </div>",
                    unsafe_allow_html=True,
                )
    else:
        for i in range(n_images):
            CAPTIONS[i].markdown(
                f"<div style='text-align: center'> {i} </div>", unsafe_allow_html=True
            )


def create_survey_page():
    TITLE.markdown(title_text, unsafe_allow_html=False)
    n_images = st.session_state.dataset.get_nb_images(st.session_state.current_question)
    cols = COLS.columns(n_images)
    images, prompt = st.session_state.dataset.get_data_question(
        st.session_state.current_question
    )
    DESCRIPITON.markdown(f"##### CAPTION : {prompt}")

    for (i, col), (hash, image) in zip(enumerate(cols), images.items()):
        with col:
            CAPTIONS[i] = st.markdown(
                f"<div style='text-align: center'> {i} </div>", unsafe_allow_html=True
            )
            IMAGES[i] = st.image(image)
            ID2HASH[i] = hash
    RADIO.radio(
        label=text_question,
        options=[
            _
            for _ in range(
                st.session_state.dataset.get_nb_images(
                    st.session_state.current_question
                )
            )
        ]
        + ["equally bad", "equally good"],
        horizontal=True,
        index=None,
        key="choice_val",
        on_change=change_caption,
        args=(),
    )
    change_caption()
    SUBMIT.button(label=text_submit, on_click=submit_clicked)


def create_homepage():
    TITLE.markdown(homepage_indication, unsafe_allow_html=False)
    SUBMIT.button(label=text_submit, on_click=start_survey)


def submit_clicked():
    if st.session_state.choice_val is None:
        st.error("Please answer the question before submitting")
    else:
        stage, id_question = st.session_state.dataset.get_stage_idquestion(
            st.session_state.current_question
        )
        if st.session_state.choice_val == "equally bad":
            choice = label_bad
        elif st.session_state.choice_val == "equally good":
            choice = label_good
        else:
            choice = ID2HASH[st.session_state.choice_val]
        new_entry = pd.DataFrame(
            {
                "stage": [stage],
                "id_question": [id_question],
                "choice": [choice],
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
