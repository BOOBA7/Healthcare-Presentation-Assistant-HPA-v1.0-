"""Streamlit user interface for the Healthcare Presentation Assistant."""
from pathlib import Path
from tempfile import TemporaryDirectory

import streamlit as st
from langchain_core.messages import HumanMessage

from app.ai.agents.healthcare_presentation_agent import HealthcarePresentationAgent
from app.ai.workflows.graph_state import GraphState
from app.application.use_cases.export_powerpoint import ExportPowerPointUseCase
from app.application.use_cases.extract_pdf_resource import ExtractPdfResourceUseCase
from app.application.use_cases.workflow_steps import (
    RejectBlueprintItemUseCase,
    RejectSlideUseCase,
    RegenerateBlueprintUseCase,
    RegenerateSlideUseCase,
    ReviewBlueprintItemUseCase,
    ReviewSlideUseCase,
)
from app.ai.workflows.tools import (
    validate_blueprint,
    validate_final_presentation,
    validate_resources,
    validate_slides,
)
from app.interfaces.storage.user_session_repository import UserSessionRepository
from app.domain.models.user_profile import UserProfile
from app.domain.enums.presentation_theme import PresentationTheme


st.set_page_config(page_title="Healthcare Presentation Assistant", page_icon="🩺", layout="wide")


@st.cache_resource
def get_agent() -> HealthcarePresentationAgent:
    return HealthcarePresentationAgent()


@st.cache_resource
def get_repository() -> UserSessionRepository:
    return UserSessionRepository()


def authenticated_user_id() -> str:
    """Use OIDC identity when configured, otherwise require a local password."""
    auth_required = bool(st.secrets.get("AUTH_REQUIRED", False))
    if auth_required:
        if not st.user.is_logged_in:
            st.title("Healthcare Presentation Assistant")
            st.button("Se connecter avec Google", on_click=st.login)
            st.stop()
        st.sidebar.button("Se déconnecter", on_click=st.logout)
        return str(st.user.get("sub") or st.user.get("email"))

    if local_user_id := st.session_state.get("local_authenticated_user_id"):
        st.caption(f"Connecté : {local_user_id}")
        if st.button("Se déconnecter"):
            st.session_state.pop("local_authenticated_user_id", None)
            st.rerun()
        return str(local_user_id)

    st.caption("Local sign in")
    with st.form("local_login"):
        user_id = st.text_input("User ID", max_chars=128).strip()
        password = st.text_input("Password", type="password", max_chars=256)
        login, register = st.columns(2)
        login_clicked = login.form_submit_button("Sign in")
        register_clicked = register.form_submit_button("Create account")
    if login_clicked:
        if get_repository().authenticate_user(user_id, password):
            st.session_state.local_authenticated_user_id = user_id
            st.rerun()
        st.error("Invalid user ID or password.")
    if register_clicked:
        try:
            if len(password) < 8:
                raise ValueError("Password must contain at least 8 characters.")
            get_repository().register_user(user_id, password)
            st.session_state.local_authenticated_user_id = user_id
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))
    st.stop()


def load_project_state(user_id: str, project_id: str) -> GraphState:
    """Load an isolated workflow state for one user project."""
    if (
        st.session_state.get("active_user_id") != user_id
        or st.session_state.get("active_project_id") != project_id
    ):
        stored = get_repository().load(user_id, project_id)
        thread_id, state = stored if stored else get_repository().create_empty(user_id, project_id)
        st.session_state.active_user_id = user_id
        st.session_state.active_project_id = project_id
        st.session_state.thread_id = thread_id
        st.session_state.state = state
        st.session_state.pop("pptx_data", None)
        st.session_state.pop("pptx_name", None)
    return st.session_state.state


def save_state() -> None:
    get_repository().save(
        st.session_state.active_user_id,
        st.session_state.active_project_id,
        st.session_state.thread_id,
        st.session_state.state,
    )


def open_or_create_project(user_id: str) -> None:
    """Callback used before widgets render, so changing the selected project is safe."""
    project_id = str(st.session_state.get("new_project_id_input", "")).strip()
    if not project_id:
        st.session_state.project_error = "Enter a Project ID."
        return
    if get_repository().load(user_id, project_id) is None:
        get_repository().create_empty(user_id, project_id)
    st.session_state.project_selector = project_id
    st.session_state.active_project_id = None
    st.session_state.pop("project_error", None)


def run_validation(tool, **arguments: object) -> None:
    try:
        st.session_state.state = tool.func(st.session_state.state, **arguments)
        save_state()
        st.success("Validation enregistrée.")
    except ValueError as exc:
        st.error(str(exc))


def review_item(use_case, index: int, comments: str) -> None:
    try:
        st.session_state.state = use_case.execute(st.session_state.state, index, comments)
        save_state()
        st.success("Élément validé et commentaire enregistré.")
    except ValueError as exc:
        st.error(str(exc))


def run_action(use_case, *arguments: object) -> None:
    try:
        st.session_state.state = use_case.execute(st.session_state.state, *arguments)
        save_state()
        st.success("Demande exécutée.")
    except ValueError as exc:
        st.error(str(exc))


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
st.caption("Discuss ideas, then create a scientific presentation from validated PDF resources.")

with st.sidebar:
    st.header("User")
    user_id = authenticated_user_id()
    if st.session_state.get("active_user_id") != user_id:
        st.session_state.pop("project_selector", None)

    project_ids = get_repository().list_project_ids(user_id)
    if not project_ids:
        project_ids = ["project-1"]
    default_project = st.session_state.get("project_selector", project_ids[0])
    if default_project not in project_ids:
        default_project = project_ids[0]
    project_id = st.selectbox(
        "Project",
        options=project_ids,
        index=project_ids.index(default_project),
        key="project_selector",
        help="Each Project retains its own conversation, resources and presentation.",
    )
    st.text_input(
        "New Project ID",
        placeholder="ex. depression-medecine-generale",
        max_chars=128,
        key="new_project_id_input",
    )
    st.button("Create / open Project", on_click=open_or_create_project, args=(user_id,))
    if project_error := st.session_state.pop("project_error", None):
        st.error(project_error)

    profile = get_repository().get_user_profile(user_id)
    role = st.selectbox(
        "Professional profile",
        options=["professor_medicine", "assistant_professor", "veterinarian", "biologist", "specialist_physician", "resident_physician"],
        index=["professor_medicine", "assistant_professor", "veterinarian", "biologist", "specialist_physician", "resident_physician"].index(profile.professional_role),
        format_func=lambda value: value.replace("_", " ").title(),
    )
    language = st.selectbox("Language", options=["en", "fr", "ar"], index=["en", "fr", "ar"].index(profile.preferred_language))
    selected_profile = UserProfile(professional_role=role, preferred_language=language)
    if selected_profile != profile:
        get_repository().update_user_profile(user_id, selected_profile)
        profile = selected_profile
    state = load_project_state(user_id, project_id)
    state.user_profile = profile
    save_state()
    st.caption(f"Project : {project_id} · Session : {st.session_state.thread_id[:8]}")
    st.divider()
    st.header("Ressource scientifique")
    uploaded_pdf = st.file_uploader("Déposez un PDF", type=["pdf"])
    if st.button("Ajouter le PDF", disabled=uploaded_pdf is None):
        if state.presentation is None:
            st.warning("Créez d’abord la présentation dans la conversation.")
        elif uploaded_pdf.size > 20 * 1024 * 1024:
            st.error("Les PDF sont limités à 20 Mo.")
        else:
            try:
                resource = ExtractPdfResourceUseCase().execute(uploaded_pdf.name, uploaded_pdf.getvalue())
                state.presentation.resources.append(resource)
                save_state()
                st.success(f"{resource.filename} ajouté ({len(resource.extracted_text or '')} caractères extraits).")
            except ValueError as exc:
                st.error(str(exc))

    st.divider()
    if state.presentation:
        selected_theme = st.selectbox(
            "PowerPoint template",
            options=list(PresentationTheme),
            index=list(PresentationTheme).index(state.presentation.theme),
            format_func=lambda theme: {
                PresentationTheme.CLINICAL: "Clinical clarity",
                PresentationTheme.ACADEMIC: "Academic prestige",
                PresentationTheme.EXECUTIVE: "Executive impact",
                PresentationTheme.MIDNIGHT: "Midnight focus",
            }[theme],
        )
        if selected_theme != state.presentation.theme:
            state.presentation.theme = selected_theme
            save_state()
        st.write(f"**Présentation :** {state.presentation.title}")
        st.write(f"**Ressources :** {len(state.presentation.resources)}")
        st.write(f"**Slides :** {len(state.presentation.slides)}")
        if state.presentation.resources and not state.presentation.state.resources_validated:
            st.button("Valider les ressources", on_click=run_validation, args=(validate_resources,))
        if state.presentation.blueprint and not state.presentation.state.blueprint_validated:
            all_blueprint_items_validated = all(item.is_validated for item in state.presentation.blueprint.slides)
            st.button("Approuver le blueprint complet", disabled=not all_blueprint_items_validated, on_click=run_validation, args=(validate_blueprint,), kwargs={"approved": True})
        if state.presentation.slides and not state.presentation.state.slides_validated:
            all_slides_validated = all(slide.is_validated for slide in state.presentation.slides)
            st.button("Approuver toutes les slides", disabled=not all_slides_validated, on_click=run_validation, args=(validate_slides,), kwargs={"approved": True})
        if state.presentation.state.slides_validated and not state.presentation.state.presentation_validated:
            st.button("Approuver la présentation finale", on_click=run_validation, args=(validate_final_presentation,), kwargs={"approved": True})
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

if state.presentation and state.presentation.blueprint:
    st.divider()
    if state.presentation.agenda:
        st.subheader("Agenda — slide 2")
        st.caption("Proposed from the AI blueprint. Save your changes, then approve the agenda before approving the blueprint.")
        agenda_items = st.text_area(
            "Agenda items (one per line)",
            value="\n".join(state.presentation.agenda.items),
            key="agenda_items",
        )
        agenda_comments = st.text_area(
            "Agenda review comment",
            value=state.presentation.agenda.reviewer_comments or "",
            key="agenda_comments",
        )
        save_agenda, approve_agenda = st.columns(2)
        if save_agenda.button("Save agenda"):
            items = [item.strip() for item in agenda_items.splitlines() if item.strip()]
            if not items:
                st.error("Agenda must contain at least one item.")
            else:
                state.presentation.agenda.items = items
                state.presentation.agenda.reviewer_comments = agenda_comments.strip() or None
                state.presentation.agenda.is_validated = False
                state.presentation.blueprint.is_validated = False
                state.presentation.state.blueprint_validated = False
                state.presentation.state.slides_validated = False
                state.presentation.state.presentation_validated = False
                save_state()
                st.success("Agenda saved. Approve it when ready.")
        if approve_agenda.button("Approve agenda", disabled=state.presentation.agenda.is_validated):
            state.presentation.agenda.is_validated = True
            save_state()
            st.success("Agenda approved.")
    if st.toggle("Afficher et réviser le blueprint", key="show_blueprint"):
        outlines = state.presentation.blueprint.slides
        index = min(st.session_state.get("blueprint_index", 0), len(outlines) - 1)
        st.session_state.blueprint_index = index
        outline = outlines[index]
        previous, counter, next_item = st.columns([1, 2, 1])
        if previous.button("← Précédent", disabled=index == 0, key="blueprint_previous"):
            st.session_state.blueprint_index = index - 1
            st.rerun()
        counter.markdown(f"**Élément {index + 1} / {len(outlines)}**")
        if next_item.button("Suivant →", disabled=index == len(outlines) - 1, key="blueprint_next"):
            st.session_state.blueprint_index = index + 1
            st.rerun()
        st.subheader(outline.title)
        st.write(f"**Objectif :** {outline.objective}")
        st.write(f"**Message clé :** {outline.key_message}")
        comments = st.text_area("Commentaire du relecteur", value=outline.reviewer_comments or "", key=f"blueprint_comment_{index}")
        approve, reject = st.columns(2)
        approve.button("Valider cet élément", disabled=outline.is_validated, on_click=review_item, args=(ReviewBlueprintItemUseCase(), index, comments), key=f"blueprint_validate_{index}")
        reject.button("Refuser / demander correction", on_click=review_item, args=(RejectBlueprintItemUseCase(), index, comments), key=f"blueprint_reject_{index}")
        st.button("Régénérer le blueprint avec les commentaires", on_click=run_action, args=(RegenerateBlueprintUseCase(),), key="blueprint_regenerate")
        if outline.is_validated:
            st.success("Élément validé.")

if state.presentation and state.presentation.slides:
    st.divider()
    if st.toggle("Afficher et réviser les slides", key="show_slides"):
        slides = state.presentation.slides
        index = min(st.session_state.get("slide_index", 0), len(slides) - 1)
        st.session_state.slide_index = index
        slide = slides[index]
        previous, counter, next_item = st.columns([1, 2, 1])
        if previous.button("← Précédente", disabled=index == 0, key="slide_previous"):
            st.session_state.slide_index = index - 1
            st.rerun()
        counter.markdown(f"**Slide {index + 1} / {len(slides)}**")
        if next_item.button("Suivante →", disabled=index == len(slides) - 1, key="slide_next"):
            st.session_state.slide_index = index + 1
            st.rerun()
        st.subheader(slide.title)
        st.write(slide.content)
        st.markdown("**Messages clés**")
        st.write(slide.key_messages)
        if slide.reference_details:
            st.markdown("**Preuves vérifiées**")
            for reference in slide.reference_details:
                st.caption(
                    f"{reference.get('title', 'Source')} · ID {reference.get('resource_id')} "
                    f"· page {reference.get('page')}"
                )
                st.info(f"« {reference.get('evidence_excerpt')} »")
        comments = st.text_area("Commentaire du relecteur", value=slide.reviewer_comments or "", key=f"slide_comment_{index}")
        approve, reject = st.columns(2)
        approve.button("Valider cette slide", disabled=slide.is_validated, on_click=review_item, args=(ReviewSlideUseCase(), index, comments), key=f"slide_validate_{index}")
        reject.button("Refuser / demander correction", on_click=review_item, args=(RejectSlideUseCase(), index, comments), key=f"slide_reject_{index}")
        st.button("Régénérer cette slide", on_click=run_action, args=(RegenerateSlideUseCase(), index), key=f"slide_regenerate_{index}")
        if slide.is_validated:
            st.success("Slide validée.")

for message in state.messages:
    role = "user" if isinstance(message, HumanMessage) else "assistant"
    with st.chat_message(role):
        st.write(message_text(message))

if prompt := st.chat_input("Discutez d’une idée ou demandez explicitement de créer/générer votre présentation..."):
    with st.chat_message("user"):
        st.write(prompt)
    state.messages.append(HumanMessage(content=prompt))
    state.user_profile = get_repository().get_user_profile(user_id)
    if state.presentation is not None:
        state.presentation.owner_profile = state.user_profile
    with st.chat_message("assistant"):
        with st.spinner("Analyse en cours..."):
            try:
                result = get_agent().invoke(state, st.session_state.thread_id)
                st.session_state.state = GraphState(**result)
                save_state()
                messages = result.get("messages", [])
                st.write(message_text(messages[-1]) if messages else "Aucune réponse reçue.")
            except Exception as exc:
                text = str(exc)
                if "RESOURCE_EXHAUSTED" in text or "429" in text:
                    st.error("Le quota Gemini est atteint. Réessayez plus tard ou utilisez un projet API avec du quota.")
                else:
                    st.error("Le modèle n’a pas pu traiter cette demande.")
