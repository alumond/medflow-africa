"""Optional Streamlit host for the custom five-page interface; run API first."""

import os

import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(
    page_title="MedFlow Africa", page_icon="◧", layout="wide", initial_sidebar_state="collapsed"
)
st.markdown(
    "<style>.block-container{padding:0!important;max-width:none!important}header[data-testid=stHeader]{display:none}iframe{border:0!important}</style>",
    unsafe_allow_html=True,
)
api_url = os.environ.get("MEDFLOW_API_URL", "http://127.0.0.1:8000")
components.iframe(api_url, height=1800, scrolling=True)
