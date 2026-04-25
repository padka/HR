"""OAuth helpers for HH employer integration."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlencode

from backend.apps.admin_ui.security import Principal
from backend.core.settings import get_settings
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

_STATE_SALT = "hh-oauth-state"
_CANDIDATE_STATE_SALT = "hh-candidate-oauth-state"
_PUBLIC_CANDIDATE_STATE_SALT = "hh-public-candidate-oauth-state"


@dataclass(frozen=True)
class HHOAuthState:
    principal_type: str
    principal_id: int
    return_to: str | None = None


@dataclass(frozen=True)
class HHCandidateOAuthState:
    candidate_id: int
    access_session_id: int
    journey_session_id: int
    return_to: str | None = None


@dataclass(frozen=True)
class HHPublicCandidateOAuthState:
    intake_id: int
    return_to: str | None = None


def _serializer() -> URLSafeTimedSerializer:
    settings = get_settings()
    return URLSafeTimedSerializer(settings.session_secret, salt=_STATE_SALT)


def _candidate_serializer() -> URLSafeTimedSerializer:
    settings = get_settings()
    return URLSafeTimedSerializer(settings.session_secret, salt=_CANDIDATE_STATE_SALT)


def _public_candidate_serializer() -> URLSafeTimedSerializer:
    settings = get_settings()
    return URLSafeTimedSerializer(settings.session_secret, salt=_PUBLIC_CANDIDATE_STATE_SALT)


def sign_hh_oauth_state(principal: Principal, *, return_to: str | None = None) -> str:
    return _serializer().dumps(
        {
            "principal_type": principal.type,
            "principal_id": principal.id,
            "return_to": return_to,
        }
    )


def sign_hh_candidate_oauth_state(
    *,
    candidate_id: int,
    access_session_id: int,
    journey_session_id: int,
    return_to: str | None = None,
) -> str:
    return _candidate_serializer().dumps(
        {
            "candidate_id": int(candidate_id),
            "access_session_id": int(access_session_id),
            "journey_session_id": int(journey_session_id),
            "return_to": return_to,
        }
    )


def sign_hh_public_candidate_oauth_state(
    *,
    intake_id: int,
    return_to: str | None = None,
) -> str:
    return _public_candidate_serializer().dumps(
        {
            "state_type": "public_candidate",
            "intake_id": int(intake_id),
            "return_to": return_to,
        }
    )


def parse_hh_oauth_state(value: str) -> HHOAuthState:
    settings = get_settings()
    try:
        payload = _serializer().loads(value, max_age=settings.hh_oauth_state_ttl_seconds)
    except SignatureExpired as exc:
        raise ValueError("HH OAuth state expired") from exc
    except BadSignature as exc:
        raise ValueError("HH OAuth state is invalid") from exc
    return HHOAuthState(
        principal_type=str(payload.get("principal_type") or ""),
        principal_id=int(payload.get("principal_id") or 0),
        return_to=(str(payload.get("return_to") or "") or None),
    )


def parse_hh_candidate_oauth_state(value: str) -> HHCandidateOAuthState:
    settings = get_settings()
    try:
        payload = _candidate_serializer().loads(
            value,
            max_age=settings.hh_oauth_state_ttl_seconds,
        )
    except SignatureExpired as exc:
        raise ValueError("HH candidate OAuth state expired") from exc
    except BadSignature as exc:
        raise ValueError("HH candidate OAuth state is invalid") from exc
    return HHCandidateOAuthState(
        candidate_id=int(payload.get("candidate_id") or 0),
        access_session_id=int(payload.get("access_session_id") or 0),
        journey_session_id=int(payload.get("journey_session_id") or 0),
        return_to=(str(payload.get("return_to") or "") or None),
    )


def parse_hh_public_candidate_oauth_state(value: str) -> HHPublicCandidateOAuthState:
    settings = get_settings()
    try:
        payload = _public_candidate_serializer().loads(
            value,
            max_age=settings.hh_oauth_state_ttl_seconds,
        )
    except SignatureExpired as exc:
        raise ValueError("HH public candidate OAuth state expired") from exc
    except BadSignature as exc:
        raise ValueError("HH public candidate OAuth state is invalid") from exc
    return HHPublicCandidateOAuthState(
        intake_id=int(payload.get("intake_id") or 0),
        return_to=(str(payload.get("return_to") or "") or None),
    )


def build_hh_authorize_url(principal: Principal, *, return_to: str | None = None) -> tuple[str, str]:
    settings = get_settings()
    if not settings.hh_integration_enabled:
        raise ValueError("HH integration is disabled")
    if not settings.hh_client_id:
        raise ValueError("HH_CLIENT_ID is not configured")
    if not settings.hh_redirect_uri:
        raise ValueError("HH_REDIRECT_URI is not configured")

    state = sign_hh_oauth_state(principal, return_to=return_to)
    params = {
        "response_type": "code",
        "client_id": settings.hh_client_id,
        "redirect_uri": settings.hh_redirect_uri,
        "state": state,
        "role": "employer",
        "force_role": "true",
        "skip_choose_account": "true",
    }
    return f"{settings.hh_oauth_authorize_url}?{urlencode(params)}", state


def build_hh_candidate_authorize_url(
    *,
    candidate_id: int,
    access_session_id: int,
    journey_session_id: int,
    return_to: str | None = None,
) -> tuple[str, str]:
    settings = get_settings()
    if not settings.hh_candidate_oauth_enabled:
        raise ValueError("HH candidate OAuth is disabled")
    if not settings.hh_candidate_client_id:
        raise ValueError("HH_CANDIDATE_CLIENT_ID is not configured")
    if not settings.hh_candidate_redirect_uri:
        raise ValueError("HH_CANDIDATE_REDIRECT_URI is not configured")

    state = sign_hh_candidate_oauth_state(
        candidate_id=candidate_id,
        access_session_id=access_session_id,
        journey_session_id=journey_session_id,
        return_to=return_to,
    )
    params = {
        "response_type": "code",
        "client_id": settings.hh_candidate_client_id,
        "redirect_uri": settings.hh_candidate_redirect_uri,
        "state": state,
        "role": "applicant",
        "force_role": "true",
    }
    return f"{settings.hh_oauth_authorize_url}?{urlencode(params)}", state


def build_hh_public_candidate_authorize_url(
    *,
    intake_id: int,
    return_to: str | None = None,
) -> tuple[str, str]:
    settings = get_settings()
    if not settings.hh_candidate_oauth_enabled:
        raise ValueError("HH candidate OAuth is disabled")
    if not settings.hh_candidate_client_id:
        raise ValueError("HH_CANDIDATE_CLIENT_ID is not configured")
    if not settings.hh_candidate_redirect_uri:
        raise ValueError("HH_CANDIDATE_REDIRECT_URI is not configured")

    state = sign_hh_public_candidate_oauth_state(
        intake_id=int(intake_id),
        return_to=return_to,
    )
    params = {
        "response_type": "code",
        "client_id": settings.hh_candidate_client_id,
        "redirect_uri": settings.hh_candidate_redirect_uri,
        "state": state,
        "role": "applicant",
        "force_role": "true",
    }
    return f"{settings.hh_oauth_authorize_url}?{urlencode(params)}", state
