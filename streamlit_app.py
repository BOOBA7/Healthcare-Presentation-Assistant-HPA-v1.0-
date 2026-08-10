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
from app.application.use_cases.update_presentation_details import UpdatePresentationDetailsUseCase
from app.application.use_cases.update_project_evidence_settings import UpdateProjectEvidenceSettingsUseCase
from app.application.use_cases.manage_project_resources import (
    AddProjectResourceUseCase,
    AttachResourceToPresentationUseCase,
    DetachResourceFromPresentationUseCase,
    RemoveProjectResourceUseCase,
)
from app.application.use_cases.workflow_steps import (
    BuildBlueprintWorkflowUseCase,
    CollectPresentationContextUseCase,
    CreatePresentationWorkflowUseCase,
    RejectBlueprintItemUseCase,
    RejectSlideUseCase,
    EditBlueprintItemUseCase,
    EditSlideUseCase,
    RegenerateBlueprintUseCase,
    RegenerateSlideUseCase,
    ReviewBlueprintItemUseCase,
    ReviewSlideUseCase,
    GenerateSlidesWorkflowUseCase,
    ValidatePresentationContextUseCase,
)
from app.ai.workflows.tools import (
    validate_final_presentation,
    validate_resources,
)
from app.interfaces.storage.user_session_repository import UserSessionRepository
from app.domain.models.user_profile import UserProfile
from app.domain.enums.presentation_theme import PresentationTheme
from app.domain.enums.workflow_status import WorkflowStatus
from app.domain.enums.evidence_context_mode import EvidenceContextMode
from app.domain.enums.audience_type import AudienceType
from app.domain.enums.language import Language
from app.domain.enums.presentation_type import PresentationType
from app.domain.models.execution_context import ExecutionContext
from app.application.services.conversation_history import (
    add_resource_turn,
    add_turn,
    ensure_history,
    message_text as transcript_message_text,
)
from app.application.services.resource_library import ensure_resource_library, resolve_presentation_resources
from app.application.services.workflow_policy import WorkflowPolicy
from app.application.services.citation_presentation import (
    citation_display_details,
    format_citations_for_display,
)


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
            get_repository().save_with_event(
                user_id, project_id, thread_id, state,
                "PROJECT_STATE_MIGRATED", "system", {"reason": "resource_library_normalization"},
            )
        st.session_state.pop("pptx_data", None)
        st.session_state.pop("pptx_name", None)
    st.session_state.state.resource_chunks = get_repository().load_resource_chunks(user_id, project_id)
    return st.session_state.state


def save_state() -> None:
    get_repository().save_with_event(
        st.session_state.active_user_id,
        st.session_state.active_project_id,
        st.session_state.thread_id,
        st.session_state.state,
        "PROJECT_STATE_SAVED",
        "user",
        {},
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


def create_presentation_from_setup(
    topic: str,
    audience: AudienceType,
    presentation_type: PresentationType,
    language: Language,
    duration_minutes: int,
    objective: str,
) -> None:
    """Create a draft through explicit human input, never through chat intent."""
    try:
        state = st.session_state.state
        state = CollectPresentationContextUseCase().execute(
            state,
            topic=topic,
            audience=audience,
            presentation_type=presentation_type,
            language=language,
            duration_minutes=duration_minutes,
            objective=objective,
        )
        state = ValidatePresentationContextUseCase().execute(state)
        st.session_state.state = CreatePresentationWorkflowUseCase().execute(state)
        save_state()
        st.success("Presentation created. Select and validate its PDF evidence in Resources.")
    except ValueError as exc:
        st.error(str(exc))


def run_explicit_generation(action: str) -> None:
    """Run a human-clicked generation command; chat never advances this state."""
    try:
        with st.spinner(f"Generating {action} from validated resources..."):
            if action == "blueprint":
                st.session_state.state = BuildBlueprintWorkflowUseCase().execute(st.session_state.state)
            else:
                st.session_state.state = GenerateSlidesWorkflowUseCase().execute(st.session_state.state)
        st.session_state.state.execution = ExecutionContext(last_tool=f"generate_{action}")
        save_state()
        st.success(f"{action.title()} generation completed.")
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
            state.resource_library,
            language=state.user_profile.preferred_language,
            chunks=state.resource_chunks,
            evidence_context_mode=state.evidence_context_mode,
            patient_case_mode=state.patient_case_mode,
        )
        state.resource_analysis = analysis
        save_state()
        st.success("Resource overview generated in the Resources workspace.")
    except ValueError as exc:
        st.error(str(exc))
    except Exception:
        st.error("The model could not analyze the uploaded resources. Please retry.")


def discuss_uploaded_resources(question: str) -> None:
    state = st.session_state.state
    try:
        answer = DiscussResourcesUseCase().execute(
            state.resource_library,
            question,
            language=state.user_profile.preferred_language,
            chunks=state.resource_chunks,
            evidence_context_mode=state.evidence_context_mode,
            patient_case_mode=state.patient_case_mode,
        )
        add_resource_turn(state, "user", question)
        add_resource_turn(state, "assistant", answer)
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


def render_model_message(text: str, resources) -> None:
    """Render readable source titles while retaining technical IDs on demand."""
    st.markdown(format_citations_for_display(text, resources))
    details = citation_display_details(text, resources)
    if details:
        with st.expander("Technical citation details", expanded=False):
            for detail in details:
                location = f" · p. {detail.pages}" if detail.pages else ""
                st.caption(f"{detail.title}{location}")
                st.code(f"resource_id: {detail.resource_id}", language=None)


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

workspace_key = f"active_workspace_{user_id}_{project_id}"
workspace = st.segmented_control(
    "Workspace",
    options=("Presentation Studio", "Resources", "Resource Analysis"),
    default="Presentation Studio",
    key=workspace_key,
)
resource_validation_required = WorkflowPolicy.requires_resource_validation(state.presentation)

if workspace == "Resources":
    st.header("Resources")
    st.caption("Upload, select and validate the PDF evidence used for presentation production.")
    with st.expander("Evidence and Patient Case Mode", expanded=False):
        st.caption(
            "Evidence mode changes passage selection only. Validation, provenance and human approval remain required."
        )
        selected_evidence_mode = st.selectbox(
            "Evidence context mode",
            options=list(EvidenceContextMode),
            index=list(EvidenceContextMode).index(state.evidence_context_mode),
            format_func=lambda mode: {
                EvidenceContextMode.BM25: "BM25 retrieval — default",
                EvidenceContextMode.DIRECT_BOUNDED: "Direct bounded PDF context — experimental",
            }[mode],
        )
        patient_case_mode = st.checkbox(
            "Enable Patient Case Mode (de-identified information only)",
            value=state.patient_case_mode,
        )
        patient_case_acknowledged = st.checkbox(
            "I confirm that no patient-identifying information will be entered or uploaded.",
            value=state.patient_case_acknowledged,
            disabled=not patient_case_mode,
        )
        if patient_case_mode:
            st.warning(
                "HPA detects obvious identifiers before LLM use, but cannot guarantee de-identification. "
                "Remove patient names, full dates, identifiers, contact details and addresses."
            )
        if st.button("Save evidence settings", use_container_width=True):
            try:
                UpdateProjectEvidenceSettingsUseCase().execute(
                    state,
                    evidence_context_mode=selected_evidence_mode,
                    patient_case_mode=patient_case_mode,
                    patient_case_acknowledged=patient_case_acknowledged,
                )
                save_state()
                st.success("Evidence settings saved.")
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))

    uploaded_pdf = st.file_uploader("Upload a PDF", type=["pdf"])
    if st.button("Add resource", disabled=uploaded_pdf is None, use_container_width=True):
        if uploaded_pdf.size > 20 * 1024 * 1024:
            st.error("PDF files are limited to 20 MB.")
        else:
            try:
                resource = ExtractPdfResourceUseCase().execute(
                    uploaded_pdf.name,
                    uploaded_pdf.getvalue(),
                    patient_case_mode=state.patient_case_mode,
                )
                AddProjectResourceUseCase().execute(state, resource)
                save_state()
                st.success(f"{resource.filename} was added to this Project library.")
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))

    if not state.resource_library:
        st.info("Upload a PDF to build this Project's source library.")
    else:
        st.subheader("Project resource library")
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
                        st.success("Resource selected for production evidence.")
                        st.rerun()
                    except ValueError as exc:
                        st.error(str(exc))
            if remove.button("×", key=f"remove_resource_{resource.id}", help="Remove resource"):
                st.session_state.pending_resource_delete = resource.id
        pending_resource = st.session_state.get("pending_resource_delete")
        if pending_resource:
            st.warning("Removing a resource resets generated content and approvals based on that evidence.")
            confirm, cancel = st.columns(2)
            if confirm.button("Remove resource", type="primary", use_container_width=True):
                remove_resource(pending_resource)
                st.rerun()
            if cancel.button("Cancel", use_container_width=True):
                st.session_state.pop("pending_resource_delete", None)
                st.rerun()
    if resource_validation_required:
        st.info("The selected resources need your approval before the blueprint can be generated.")
        st.button(
            "Validate resources and continue",
            type="primary",
            on_click=run_validation,
            args=(validate_resources,),
            key="resource_workspace_validate_resources",
        )
    if st.session_state.pop("resource_deleted", False):
        st.success("Resource removed. Dependent generated content and approvals were reset.")
    if resource_error := st.session_state.pop("resource_error", None):
        st.error(resource_error)
    st.stop()

if workspace == "Resource Analysis":
    st.header("Resource Analysis")
    st.caption("Explore uploaded PDFs without selecting, validating or generating presentation content.")
    if not state.resource_library:
        st.info("Upload a PDF first in Resources.")
        st.stop()

    analyze_column, status_column = st.columns([1, 2])
    analyze_column.button(
        "Analyze uploaded resources",
        on_click=analyze_uploaded_resources,
        use_container_width=True,
    )
    status_column.caption(f"{len(state.resource_library)} PDF resource(s) in this Project library")
    st.divider()

    st.subheader("Resource overview")
    st.caption("AI-generated discussion starter based only on the uploaded PDF resources.")
    if state.resource_analysis:
        render_model_message(state.resource_analysis.summary, state.resource_library)
    else:
        st.info("Select Analyze uploaded resources to generate a source-only overview.")

    st.divider()
    st.subheader("Resource chat")
    st.caption("This discussion is separate from the Presentation assistant chat.")
    for turn in state.resource_conversation_history:
        with st.chat_message(turn.role):
            if turn.role == "assistant":
                render_model_message(turn.text, state.resource_library)
            else:
                st.write(turn.text)
    resource_question = st.chat_input(
        "Ask a question answered only from the uploaded PDFs",
        key=f"resource_discussion_question_{project_id}",
    )
    if resource_question:
        with st.chat_message("user"):
            st.write(resource_question)
        with st.chat_message("assistant"):
            with st.spinner("Searching uploaded PDFs..."):
                discuss_uploaded_resources(resource_question)
                error = st.session_state.pop("resource_error", None)
                if error:
                    st.error(error)
                else:
                    render_model_message(
                        st.session_state.get("resource_discussion_answer", ""), state.resource_library
                    )
        st.rerun()
    st.stop()

st.header("Presentation Studio")
st.caption("Human-controlled workflow. Chat can assist with discussion, but it cannot create or generate presentation content.")

if state.presentation:
    with st.expander("Title-slide details", expanded=False):
        st.caption("Optional human-supplied details. Empty fields are not shown on the PowerPoint title slide.")
        context = state.presentation.context
        presenter_name = st.text_input("Presenter name", value=context.presenter_name or "")
        presenter_title = st.text_input("Professional title", value=context.presenter_title or "")
        organization = st.text_input("Organization", value=context.organization or "")
        event_name = st.text_input("Event name", value=context.event_name or "")
        venue = st.text_input("Venue", value=context.venue or "")
        presentation_date = st.text_input("Presentation date", value=context.presentation_date or "")
        if st.button("Save title-slide details", use_container_width=True):
            try:
                UpdatePresentationDetailsUseCase().execute(
                    state,
                    presenter_name=presenter_name,
                    presenter_title=presenter_title,
                    organization=organization,
                    event_name=event_name,
                    venue=venue,
                    presentation_date=presentation_date,
                )
                save_state()
                st.success("Title-slide details saved.")
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))
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
    if state.presentation.state.slides_validated and not state.presentation.state.presentation_validated:
        st.button(
            "Approve final presentation",
            on_click=run_validation,
            args=(validate_final_presentation,),
            kwargs={"approved": True},
            use_container_width=True,
        )
    if st.button("Prepare PowerPoint", disabled=not state.presentation.state.presentation_validated):
        try:
            with TemporaryDirectory() as directory:
                path = ExportPowerPointUseCase().execute(
                    state.presentation,
                    Path(directory),
                    resources=resolve_presentation_resources(state),
                )
                st.session_state.pptx_data = path.read_bytes()
                st.session_state.pptx_name = f"{state.presentation.title}.pptx"
        except ValueError as exc:
            st.error(str(exc))
    if "pptx_data" in st.session_state:
        st.download_button(
            "Download PowerPoint",
            st.session_state.pptx_data,
            st.session_state.pptx_name,
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        )

if state.presentation is None:
    st.caption("Create the presentation through explicit human-controlled fields.")
    collected_context = state.conversation_context
    default_audience = (
        collected_context.audience
        if isinstance(collected_context.audience, AudienceType)
        else AudienceType.GENERAL_PRACTITIONER
    )
    default_type = (
        collected_context.presentation_type
        if isinstance(collected_context.presentation_type, PresentationType)
        else PresentationType.LECTURE
    )
    default_language = (
        collected_context.language
        if isinstance(collected_context.language, Language)
        else Language.ENGLISH
    )
    with st.form("presentation_setup_form"):
        setup_topic = st.text_input("Presentation topic", value=collected_context.topic or "", max_chars=500)
        first, second, third = st.columns(3)
        setup_audience = first.selectbox(
            "Target audience",
            options=list(AudienceType),
            index=list(AudienceType).index(default_audience),
        )
        setup_type = second.selectbox(
            "Presentation type",
            options=list(PresentationType),
            index=list(PresentationType).index(default_type),
        )
        setup_language = third.selectbox(
            "Presentation language",
            options=list(Language),
            index=list(Language).index(default_language),
        )
        setup_duration = st.number_input(
            "Duration (minutes)",
            min_value=1,
            max_value=480,
            value=collected_context.duration_minutes or 10,
        )
        setup_objective = st.text_area(
            "Presentation objective",
            value=collected_context.objective or "",
            max_chars=4000,
        )
        setup_submit = st.form_submit_button("Create presentation", type="primary")
    if setup_submit:
        if not setup_topic.strip() or not setup_objective.strip():
            st.error("Presentation topic and objective are required.")
        else:
            create_presentation_from_setup(
                setup_topic.strip(),
                setup_audience,
                setup_type,
                setup_language,
                int(setup_duration),
                setup_objective.strip(),
            )
            st.rerun()
    st.info("After creation, select PDFs in Resources and validate them before blueprint generation.")

if resource_validation_required:
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

if (
    state.presentation
    and state.presentation.state.workflow_status == WorkflowStatus.AWAITING_SLIDE_RESOLUTION
):
    blocked_slide = state.presentation.state.blocked_slide_number or "?"
    st.warning(
        f"Slide {blocked_slide} cannot be generated by AI from the validated PDFs. "
        "Edit its blueprint item, add a relevant PDF, or select ‘Written by user’."
    )

if state.presentation and state.presentation.state.workflow_status == WorkflowStatus.BLUEPRINT_GENERATION:
    st.subheader("Blueprint generation")
    st.caption("This action is controlled by the workflow and uses only selected, human-validated PDFs.")
    st.button(
        "Generate blueprint",
        type="primary",
        on_click=run_explicit_generation,
        args=("blueprint",),
        key="generate_blueprint_command",
    )

if state.presentation and state.presentation.state.workflow_status == WorkflowStatus.SLIDE_GENERATION:
    st.subheader("Slide generation")
    st.caption("This action is controlled by the workflow and validates available evidence before model generation.")
    st.button(
        "Generate slides",
        type="primary",
        on_click=run_explicit_generation,
        args=("slides",),
        key="generate_slides_command",
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
        if turn.role == "assistant":
            render_model_message(turn.text, state.resource_library)
        else:
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
                if assistant_text:
                    render_model_message(assistant_text, state.resource_library)
                else:
                    st.write("Aucune réponse reçue.")
            except ValueError as exc:
                st.error(str(exc))
            except Exception as exc:
                text = str(exc)
                if "RESOURCE_EXHAUSTED" in text or "429" in text:
                    st.error("Le quota Gemini est atteint. Réessayez plus tard ou utilisez un projet API avec du quota.")
                else:
                    st.error("Le modèle n’a pas pu traiter cette demande.")
