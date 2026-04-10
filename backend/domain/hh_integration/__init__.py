"""Direct HeadHunter integration domain."""

from .client import HHApiClient, HHApiError, HHNormalizedError, HHOAuthTokens, normalize_hh_api_error
from .importer import (
    import_hh_negotiations,
    import_hh_vacancies,
    serialize_import_result,
)
from .outbound import (
    HHSyncIntent,
    enqueue_candidate_status_sync,
    load_candidate_hh_link_context,
    resolve_hh_sync_intent,
    should_sync_candidate_status,
)
from .oauth import build_hh_authorize_url, parse_hh_oauth_state, sign_hh_oauth_state
from .service import (
    apply_refreshed_tokens,
    build_connection_summary,
    build_webhook_target_url,
    decrypt_access_token,
    decrypt_refresh_token,
    get_connection_for_principal,
    get_connection_for_webhook_key,
    upsert_hh_connection,
)

__all__ = [
    "HHApiClient",
    "HHApiError",
    "HHNormalizedError",
    "HHOAuthTokens",
    "normalize_hh_api_error",
    "import_hh_vacancies",
    "import_hh_negotiations",
    "serialize_import_result",
    "HHSyncIntent",
    "enqueue_candidate_status_sync",
    "load_candidate_hh_link_context",
    "resolve_hh_sync_intent",
    "should_sync_candidate_status",
    "build_hh_authorize_url",
    "sign_hh_oauth_state",
    "parse_hh_oauth_state",
    "decrypt_access_token",
    "decrypt_refresh_token",
    "apply_refreshed_tokens",
    "build_webhook_target_url",
    "build_connection_summary",
    "get_connection_for_principal",
    "get_connection_for_webhook_key",
    "upsert_hh_connection",
]
