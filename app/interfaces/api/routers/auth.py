"""Identity and profile endpoints for the local application."""

from fastapi import APIRouter, Depends, HTTPException

from app.domain.models.user_profile import UserProfile
from app.interfaces.api import main as api


router = APIRouter(tags=["authentication"])


@router.post("/auth/register")
def register(credentials: api.RegistrationRequest) -> dict[str, object]:
    try:
        profile = UserProfile(
            professional_role=credentials.professional_role,
            preferred_language=credentials.preferred_language,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Invalid professional profile or language.") from exc
    try:
        api.get_repository().register_user(credentials.user_id, credentials.password, profile)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    token = api.get_repository().create_auth_token(credentials.user_id)
    return {"user_id": credentials.user_id, "token": token, "profile": profile.model_dump()}


@router.post("/auth/login")
def login(credentials: api.CredentialsRequest) -> dict[str, object]:
    if not api.get_repository().authenticate_user(credentials.user_id, credentials.password):
        raise HTTPException(status_code=401, detail="Invalid user ID or password.")
    token = api.get_repository().create_auth_token(credentials.user_id)
    return {
        "user_id": credentials.user_id,
        "token": token,
        "profile": api.get_repository().get_user_profile(credentials.user_id).model_dump(),
    }


@router.post("/auth/reset-password")
def reset_password(credentials: api.CredentialsRequest) -> dict[str, object]:
    """Local-only recovery flow; public deployments must replace it."""
    try:
        api.get_repository().reset_password_without_verification(credentials.user_id, credentials.password)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "user_id": credentials.user_id,
        "token": api.get_repository().create_auth_token(credentials.user_id),
        "profile": api.get_repository().get_user_profile(credentials.user_id).model_dump(),
    }


@router.get("/users/{user_id}/profile")
def get_user_profile(
    user_id: str, authenticated_user: str = Depends(api._authenticated_user)
) -> dict[str, object]:
    api._assert_owner(user_id, authenticated_user)
    return {"profile": api.get_repository().get_user_profile(user_id).model_dump()}


@router.put("/users/{user_id}/profile")
def update_user_profile(
    user_id: str,
    request: api.UserProfileRequest,
    authenticated_user: str = Depends(api._authenticated_user),
) -> dict[str, object]:
    api._assert_owner(user_id, authenticated_user)
    try:
        profile = UserProfile(
            professional_role=request.professional_role,
            preferred_language=request.preferred_language,
        )
        api.get_repository().update_user_profile(user_id, profile)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Invalid professional profile or language.") from exc
    return {"profile": profile.model_dump()}
