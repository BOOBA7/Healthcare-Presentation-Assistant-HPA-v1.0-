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
from app.application.use_cases.summarize_resources import SummarizeResourcesUseCase
from app.application.use_cases.discuss_resources import DiscussResourcesUseCase
from app.application.use_cases.manage_project_resources import (
    AddProjectResourceUseCase,
    AttachResourceToPresentationUseCase,
    DetachResourceFromPresentationUseCase,
    RemoveProjectResourceUseCase,
)
from app.application.use_cases.workflow_steps import (
    RejectBlueprintItemUseCase,
    RejectSlideUseCase,
    EditBlueprintItemUseCase,
    EditSlideUseCase,
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
from app.domain.models.execution_context import ExecutionContext
from app.application.services.conversation_history import add_turn, ensure_history, message_text as transcript_message_text
from app.application.services.resource_library import ensure_resource_library


st.set_page_config(page_title="Healthcare Presentation Assistant", page_icon="🩺", layout="wide")


ROLE_OPTIONS = [
    "professor_medicine",
    "assistant_professor",
    "veterinarian",
    "biologist",
    "pharmacist",
    "specialist_physician",
    "resident_physician",
]


def role_label(role: str) -> str:
    return {
        "professor_medicine": "Professor of Medicine",
        "assistant_professor": "Assistant Professor",
        "veterinarian": "Veterinarian",
        "biologist": "Biologist",
        "pharmacist": "Pharmacist",
        "specialist_physician": "Specialist Physician",
        "resident_physician": "Resident Physician",
    }.get(role, role.replace("_", " ").title())


def role_emblem(role: str) -> str:
    """Return the same clear professional emblems used by the web application."""
    asclepius = """<svg viewBox="0 0 32 32" aria-hidden="true"><path d="M16 3v26M12 6c-5 1-5 7-1 8 6 1 6-6 1-4-4 2-1 8 4 8 5 0 7-6 3-10-2-2-5-2-7-1"/><path d="M12 3h8"/></svg>"""
    emblems = {
        "professor_medicine": asclepius,
        "assistant_professor": asclepius,
        "specialist_physician": asclepius,
        "resident_physician": asclepius,
        # Veterinary medicine: a recognisable V combined with the Rod of Asclepius.
        "veterinarian": """<svg viewBox="0 0 40 32" aria-hidden="true"><path d="M3 4 12 28 21 4"/><path d="M28 3v26M25 7c-4 1-4 6-1 7 5 1 5-5 1-4-3 1-1 6 3 6 4 0 6-5 3-8-2-2-5-2-6-1"/><path d="M24 3h8"/></svg>""",
        "biologist": """<svg viewBox="0 0 32 32" aria-hidden="true"><path d="M8 4c12 7 4 17 16 24M24 4C12 11 20 21 8 28M10 8h12M8 16h16M10 24h12"/></svg>""",
        "pharmacist": """<svg viewBox="0 0 32 32" aria-hidden="true"><path d="M6 20h20M9 20c1 6 13 6 14 0M12 25h8M17 5c7-2 9 6 4 8-5 2-7-4-3-6 3-2 6 3 2 6-3 3-8 0-8-4"/><path d="M13 14h8l-2 6h-4z"/></svg>""",
    }
    return emblems.get(role, asclepius)


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
            st.button("Sign in with Google", on_click=st.login)
            st.stop()
        return str(st.user.get("sub") or st.user.get("email"))

    if local_user_id := st.session_state.get("local_authenticated_user_id"):
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
        if ensure_resource_library(state):
            get_repository().save(user_id, project_id, thread_id, state)
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
    """Create a human-named Project with an internal, stable identifier."""
    project_name = str(st.session_state.get("new_project_name_input", "")).strip()
    if not project_name:
        st.session_state.project_error = "Enter a Project name."
        return
    project_id = f"project-{uuid4()}"
    get_repository().create_empty(user_id, project_id, project_name)
    st.session_state.project_selector = project_id
    st.session_state.active_project_id = None
    st.session_state.new_project_name_input = ""
    st.session_state.pop("project_error", None)


def sign_out() -> None:
    if bool(st.secrets.get("AUTH_REQUIRED", False)):
        st.logout()
        return
    st.session_state.pop("local_authenticated_user_id", None)


def delete_active_project(user_id: str, project_id: str) -> None:
    get_repository().delete_project(user_id, project_id)
    remaining_projects = get_repository().list_projects(user_id)
    if remaining_projects:
        st.session_state.project_selector = remaining_projects[0]["id"]
    else:
        st.session_state.pop("project_selector", None)
    st.session_state.active_project_id = None
    st.session_state.pop("confirm_project_delete", None)


def delete_account(user_id: str) -> None:
    """Delete local data only after the user confirms in the sidebar."""
    get_repository().delete_user(user_id)
    sign_out()


def remove_resource(resource_id: str) -> None:
    state = st.session_state.get("state")
    if state is None:
        return
    try:
        RemoveProjectResourceUseCase().execute(state, resource_id)
        save_state()
        st.session_state.pop("pending_resource_delete", None)
        st.session_state.resource_deleted = True
    except ValueError as exc:
        st.session_state.resource_error = str(exc)


def run_validation(tool, **arguments: object) -> None:
    try:
        st.session_state.state = tool.func(st.session_state.state, **arguments)
        st.session_state.state.execution = ExecutionContext()
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


def save_blueprint_edit(index: int, title: str, objective: str, key_message: str, origin: str) -> None:
    try:
        st.session_state.state = EditBlueprintItemUseCase().execute(
            st.session_state.state,
            index,
            title=title,
            objective=objective,
            key_message=key_message,
            content_origin=origin,
        )
        save_state()
        st.success("Blueprint item saved as user content. Re-approve the agenda and blueprint before generating slides.")
    except ValueError as exc:
        st.error(str(exc))


def save_slide_edit(
    index: int,
    title: str,
    objective: str,
    key_messages: str,
    content: str,
    speaker_notes: str,
    origin: str,
) -> None:
    try:
        st.session_state.state = EditSlideUseCase().execute(
            st.session_state.state,
            index,
            title=title,
            objective=objective,
            key_messages=key_messages.splitlines(),
            content=content,
            speaker_notes=speaker_notes,
            content_origin=origin,
        )
        save_state()
        st.success("Slide saved as user content. It must be approved again before final export.")
    except ValueError as exc:
        st.error(str(exc))


def analyze_uploaded_resources() -> None:
    state = st.session_state.state
    try:
        analysis = SummarizeResourcesUseCase().execute(
            state.resource_library, language=state.user_profile.preferred_language
        )
        state.resource_analysis = analysis
        ensure_history(state)
        add_turn(state, "assistant", f"Resource overview:\n{analysis.summary}")
        save_state()
        st.success("Resource overview generated. You can now discuss it in the chat before creating slides.")
    except ValueError as exc:
        st.error(str(exc))
    except Exception:
        st.error("The model could not analyze the uploaded resources. Please retry.")


def discuss_uploaded_resources(question: str) -> None:
    state = st.session_state.state
    try:
        answer = DiscussResourcesUseCase().execute(
            state.resource_library, question, language=state.user_profile.preferred_language
        )
        add_turn(state, "user", question)
        add_turn(state, "assistant", answer)
        save_state()
        st.session_state.resource_discussion_answer = answer
    except ValueError as exc:
        st.session_state.resource_error = str(exc)
    except Exception:
        st.session_state.resource_error = "The model could not discuss the uploaded resources. Please retry."


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
    user_id = authenticated_user_id()
    if st.session_state.get("active_user_id") != user_id:
        st.session_state.pop("project_selector", None)

    profile = get_repository().get_user_profile(user_id)
    st.markdown(
        """<style>
        .profile-summary {display:flex; align-items:center; gap:.55rem; margin:.2rem 0 .45rem;}
        .profile-emblem {width:2.35rem;height:2.35rem;display:grid;place-items:center;border-radius:.7rem;background:#e7f4f1;color:#087f73;}
        .profile-emblem svg {width:1.65rem;height:1.65rem;fill:none;stroke:currentColor;stroke-width:2.15;stroke-linecap:round;stroke-linejoin:round;}
        .profile-summary strong {font-size:.96rem;}
        .resource-row {display:flex;align-items:center;justify-content:space-between;gap:.45rem;padding:.35rem 0;border-bottom:1px solid #edf0f2;}
        .resource-row small {display:block;color:#64748b;overflow-wrap:anywhere;}
        </style>""",
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div class="profile-summary"><span class="profile-emblem">{role_emblem(profile.professional_role)}</span><strong>{role_label(profile.professional_role)}</strong></div>',
        unsafe_allow_html=True,
    )
    with st.expander(f"User · {user_id}", expanded=False):
        role = st.selectbox(
            "Professional profile",
            options=ROLE_OPTIONS,
            index=ROLE_OPTIONS.index(profile.professional_role),
            format_func=role_label,
        )
        language = st.selectbox(
            "Language",
            options=["en", "fr", "ar"],
            index=["en", "fr", "ar"].index(profile.preferred_language),
        )
        selected_profile = UserProfile(professional_role=role, preferred_language=language)
        if selected_profile != profile:
            get_repository().update_user_profile(user_id, selected_profile)
            profile = selected_profile
            st.rerun()
        if st.button("Sign out", use_container_width=True):
            sign_out()
            st.rerun()
        if not bool(st.secrets.get("AUTH_REQUIRED", False)):
            if st.button("Delete my account", type="secondary", use_container_width=True):
                st.session_state.confirm_account_delete = True
            if st.session_state.get("confirm_account_delete"):
                st.warning("This permanently deletes your account, Projects and conversation history.")
                confirm, cancel = st.columns(2)
                if confirm.button("Delete permanently", type="primary", use_container_width=True):
                    delete_account(user_id)
                    st.rerun()
                if cancel.button("Cancel", use_container_width=True):
                    st.session_state.pop("confirm_account_delete", None)
                    st.rerun()

    projects = get_repository().list_projects(user_id)
    if not projects:
        first_project_id = f"project-{uuid4()}"
        get_repository().create_empty(user_id, first_project_id, "My first Project")
        projects = get_repository().list_projects(user_id)
    project_ids = [project["id"] for project in projects]
    project_names = {project["id"]: project["name"] for project in projects}
    default_project = st.session_state.get("project_selector", project_ids[0])
    if default_project not in project_names:
        default_project = project_ids[0]
    with st.expander(f"Project · {project_names[default_project]}", expanded=True):
        project_id = st.selectbox(
            "Project",
            options=project_ids,
            index=project_ids.index(default_project),
            key="project_selector",
            format_func=lambda item: project_names[item],
            help="Each Project retains its own conversation, resources and presentation.",
        )
        st.text_input(
            "Name of the new Project",
            placeholder="e.g. Depression for general practice",
            max_chars=128,
            key="new_project_name_input",
        )
        st.button("Create Project", on_click=open_or_create_project, args=(user_id,), use_container_width=True)
        if project_error := st.session_state.pop("project_error", None):
            st.error(project_error)
        if st.button("Delete this Project", type="secondary", use_container_width=True):
            st.session_state.confirm_project_delete = project_id
        if st.session_state.get("confirm_project_delete") == project_id:
            st.warning("This permanently deletes this Project and its conversation history.")
            confirm, cancel = st.columns(2)
            confirm.button(
                "Delete Project",
                type="primary",
                use_container_width=True,
                on_click=delete_active_project,
                args=(user_id, project_id),
            )
            if cancel.button("Cancel", use_container_width=True):
                st.session_state.pop("confirm_project_delete", None)
                st.rerun()

    state = load_project_state(user_id, project_id)
    if ensure_history(state):
        save_state()
    state.user_profile = profile
    save_state()
    st.caption(f"Project · Session {st.session_state.thread_id[:8]}")
    st.divider()
    st.header("Scientific sources")
    uploaded_pdf = st.file_uploader("Upload a PDF", type=["pdf"])
    if st.button("Add resource", disabled=uploaded_pdf is None, use_container_width=True):
        if uploaded_pdf.size > 20 * 1024 * 1024:
            st.error("PDF files are limited to 20 MB.")
        else:
            try:
                resource = ExtractPdfResourceUseCase().execute(uploaded_pdf.name, uploaded_pdf.getvalue())
                AddProjectResourceUseCase().execute(state, resource)
                save_state()
                st.success(
                    f"{resource.filename} added to the Project library "
                    f"({len(resource.extracted_text or '')} extracted characters)."
                )
            except ValueError as exc:
                st.error(str(exc))

    if state.resource_library:
        st.caption("Project resource library")
        attached_ids = {resource.id for resource in state.presentation.resources} if state.presentation else set()
        for resource in state.resource_library:
            label, action, remove = st.columns([5, 2, 1])
            label.markdown(
                f"<div class=\"resource-row\"><div><strong>{resource.filename}</strong>"
                f"<small>{'Selected for production' if resource.id in attached_ids else 'Library only'}</small></div></div>",
                unsafe_allow_html=True,
            )
            if state.presentation:
                if resource.id in attached_ids:
                    if action.button("Detach", key=f"detach_resource_{resource.id}", use_container_width=True):
                        try:
                            DetachResourceFromPresentationUseCase().execute(state, resource.id)
                            save_state()
                            st.rerun()
                        except ValueError as exc:
                            st.error(str(exc))
                elif action.button("Use in presentation", key=f"attach_resource_{resource.id}", use_container_width=True):
                    try:
                        AttachResourceToPresentationUseCase().execute(state, resource.id)
                        save_state()
                        st.success("Resource selected. Validate selected resources when you request a blueprint.")
                        st.rerun()
                    except ValueError as exc:
                        st.error(str(exc))
            if remove.button("×", key=f"remove_resource_{resource.id}", help="Remove resource"):
                st.session_state.pending_resource_delete = resource.id
        pending_resource = st.session_state.get("pending_resource_delete")
        if pending_resource:
            st.warning("Removing a resource resets generated content and approvals based on the resources.")
            confirm, cancel = st.columns(2)
            if confirm.button("Remove resource", type="primary", use_container_width=True):
                remove_resource(pending_resource)
                st.rerun()
            if cancel.button("Cancel", use_container_width=True):
                st.session_state.pop("pending_resource_delete", None)
                st.rerun()
    if st.session_state.pop("resource_deleted", False):
        st.success("Resource removed. Dependent generated content and approvals were reset.")
    if resource_error := st.session_state.pop("resource_error", None):
        st.error(resource_error)

    if state.resource_library:
        st.button("Analyze uploaded resources", on_click=analyze_uploaded_resources, use_container_width=True)

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

if state.resource_analysis:
    st.divider()
    st.subheader("Resource overview")
    st.caption("AI-generated discussion starter based only on the uploaded PDF resources.")
    st.write(state.resource_analysis.summary)

if state.resource_library:
    st.subheader("Discuss the PDF library")
    resource_question = st.text_area(
        "Ask a question answered only from the uploaded PDFs",
        key="resource_discussion_question",
        placeholder="What is the central idea of these resources?",
    )
    if st.button("Ask about resources", disabled=not resource_question.strip(), use_container_width=True):
        discuss_uploaded_resources(resource_question)
        st.rerun()

if (
    state.presentation
    and state.execution.tool_output.get("error_code") == "RESOURCES_VALIDATION_REQUIRED"
):
    st.divider()
    st.subheader("Human validation required")
    st.info("The assistant needs your validation before it can generate the blueprint.")
    st.button(
        "Validate resources and continue",
        type="primary",
        on_click=run_validation,
        args=(validate_resources,),
        key="contextual_validate_resources",
    )

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
        st.caption(
            {
                "ai_generated": "AI-generated content",
                "user_edited": "User-edited content",
                "user_authored": "User-authored content",
            }[outline.content_origin]
        )
        with st.expander("Edit this blueprint item", expanded=False):
            edited_title = st.text_input("Title", value=outline.title, key=f"blueprint_edit_title_{index}_{outline.content_origin}")
            edited_objective = st.text_area("Objective", value=outline.objective, key=f"blueprint_edit_objective_{index}_{outline.content_origin}")
            edited_key_message = st.text_area("Key message", value=outline.key_message, key=f"blueprint_edit_message_{index}_{outline.content_origin}")
            origin = st.radio(
                "Content origin",
                options=["user_edited", "user_authored"],
                index=0 if outline.content_origin != "user_authored" else 1,
                format_func=lambda value: "Edited from AI content" if value == "user_edited" else "Written by user",
                key=f"blueprint_edit_origin_{index}_{outline.content_origin}",
            )
            if st.button("Save user edit", key=f"blueprint_edit_save_{index}"):
                save_blueprint_edit(index, edited_title, edited_objective, edited_key_message, origin)
                st.rerun()
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
        st.caption(
            {
                "ai_generated": "AI-generated content",
                "user_edited": "User-edited content",
                "user_authored": "User-authored content",
            }[slide.content_origin]
        )
        with st.expander("Edit this slide", expanded=False):
            edited_title = st.text_input("Title", value=slide.title, key=f"slide_edit_title_{index}_{slide.content_origin}")
            edited_objective = st.text_area("Objective", value=slide.objective or "", key=f"slide_edit_objective_{index}_{slide.content_origin}")
            edited_messages = st.text_area(
                "Key messages (one per line)",
                value="\n".join(slide.key_messages),
                key=f"slide_edit_messages_{index}_{slide.content_origin}",
            )
            edited_content = st.text_area("Slide content", value=slide.content, key=f"slide_edit_content_{index}_{slide.content_origin}")
            edited_notes = st.text_area("Speaker notes", value=slide.speaker_notes or "", key=f"slide_edit_notes_{index}_{slide.content_origin}")
            origin = st.radio(
                "Content origin",
                options=["user_edited", "user_authored"],
                index=0 if slide.content_origin != "user_authored" else 1,
                format_func=lambda value: "Edited from AI content" if value == "user_edited" else "Written by user",
                key=f"slide_edit_origin_{index}_{slide.content_origin}",
            )
            if st.button("Save user edit", key=f"slide_edit_save_{index}"):
                save_slide_edit(index, edited_title, edited_objective, edited_messages, edited_content, edited_notes, origin)
                st.rerun()
        if slide.reference_details and slide.content_origin == "ai_generated":
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

for turn in state.conversation_history:
    with st.chat_message(turn.role):
        st.write(turn.text)

if prompt := st.chat_input("Discutez d’une idée ou demandez explicitement de créer/générer votre présentation..."):
    with st.chat_message("user"):
        st.write(prompt)
    state.messages.append(HumanMessage(content=prompt))
    add_turn(state, "user", prompt)
    state.user_profile = get_repository().get_user_profile(user_id)
    if state.presentation is not None:
        state.presentation.owner_profile = state.user_profile
    with st.chat_message("assistant"):
        with st.spinner("Analyse en cours..."):
            try:
                result = get_agent().invoke(state, st.session_state.thread_id)
                st.session_state.state = GraphState(**result)
                state = st.session_state.state
                ensure_history(state)
                assistant_text = next(
                    (
                        transcript_message_text(message)
                        for message in reversed(state.messages)
                        if getattr(message, "type", "") == "ai" and transcript_message_text(message)
                    ),
                    "",
                )
                if assistant_text and (
                    not state.conversation_history
                    or state.conversation_history[-1].role != "assistant"
                    or state.conversation_history[-1].text != assistant_text
                ):
                    add_turn(state, "assistant", assistant_text)
                save_state()
                st.write(assistant_text or "Aucune réponse reçue.")
            except Exception as exc:
                text = str(exc)
                if "RESOURCE_EXHAUSTED" in text or "429" in text:
                    st.error("Le quota Gemini est atteint. Réessayez plus tard ou utilisez un projet API avec du quota.")
                else:
                    st.error("Le modèle n’a pas pu traiter cette demande.")
