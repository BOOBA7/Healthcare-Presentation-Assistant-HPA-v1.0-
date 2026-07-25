"""Streamlit user interface for the Healthcare Presentation Assistant."""
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

import streamlit as st
from langchain_core.messages import HumanMessage

from app.ai.agents.healthcare_presentation_agent import HealthcarePresentationAgent
from app.ai.workflows.graph_state import GraphState
from app.application.use_cases.export_powerpoint import ExportPowerPointUseCase
from app.application.use_cases.extract_pdf_resource import ExtractPdfResourceUseCase


st.set_page_config(page_title="Healthcare Presentation Assistant", page_icon="🩺", layout="wide")


@st.cache_resource
def get_agent() -> HealthcarePresentationAgent:
    return HealthcarePresentationAgent()


def get_state() -> GraphState:
    if "state" not in st.session_state:
        st.session_state.state = GraphState()
        st.session_state.thread_id = str(uuid4())
    return st.session_state.state


def message_text(message) -> str:
    content = getattr(message, "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            block.get("text", "")
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        ).strip()
    return str(content)


st.title("🩺 Healthcare Presentation Assistant")
st.caption("Créez une présentation scientifique à partir de ressources PDF validées.")

state = get_state()

with st.sidebar:
    st.header("Ressource scientifique")
    uploaded_pdf = st.file_uploader("Déposez un PDF", type=["pdf"])
    if st.button("Ajouter le PDF", disabled=uploaded_pdf is None):
        if state.presentation is None:
            st.warning("Créez d’abord la présentation dans la conversation.")
        else:
            try:
                resource = ExtractPdfResourceUseCase().execute(uploaded_pdf.name, uploaded_pdf.getvalue())
                state.presentation.resources.append(resource)
                st.success(f"{resource.filename} ajouté ({len(resource.extracted_text or '')} caractères extraits).")
            except ValueError as exc:
                st.error(str(exc))

    st.divider()
    if state.presentation:
        st.write(f"**Présentation :** {state.presentation.title}")
        st.write(f"**Ressources :** {len(state.presentation.resources)}")
        st.write(f"**Slides :** {len(state.presentation.slides)}")
        if st.button("Préparer le PowerPoint", disabled=not state.presentation.state.presentation_validated):
            try:
                with TemporaryDirectory() as directory:
                    path = ExportPowerPointUseCase().execute(state.presentation, Path(directory))
                    st.session_state.pptx_data = path.read_bytes()
                    st.session_state.pptx_name = f"{state.presentation.title}.pptx"
            except ValueError as exc:
                st.error(str(exc))
    if "pptx_data" in st.session_state:
        st.download_button("Télécharger le PowerPoint", st.session_state.pptx_data, st.session_state.pptx_name, "application/vnd.openxmlformats-officedocument.presentationml.presentation")

for message in state.messages:
    role = "user" if isinstance(message, HumanMessage) else "assistant"
    with st.chat_message(role):
        st.write(message_text(message))

if prompt := st.chat_input("Décrivez votre présentation ou répondez à la question..."):
    with st.chat_message("user"):
        st.write(prompt)
    state.messages.append(HumanMessage(content=prompt))
    with st.chat_message("assistant"):
        with st.spinner("Analyse en cours..."):
            try:
                result = get_agent().invoke(state, st.session_state.thread_id)
                st.session_state.state = GraphState(**result)
                messages = result.get("messages", [])
                st.write(message_text(messages[-1]) if messages else "Aucune réponse reçue.")
            except Exception as exc:
                text = str(exc)
                if "RESOURCE_EXHAUSTED" in text or "429" in text:
                    st.error("Le quota Gemini est atteint. Réessayez plus tard ou utilisez un projet API avec du quota.")
                else:
                    st.error("Le modèle n’a pas pu traiter cette demande.")
