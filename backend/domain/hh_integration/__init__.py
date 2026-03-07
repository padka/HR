"""Direct HeadHunter integration domain."""

from .client import HHApiClient, HHApiError, HHOAuthTokens
from .importer import (
    import_hh_negotiations,
    import_hh_vacancies,
    serialize_import_result,
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
    "HHOAuthTokens",
    "import_hh_vacancies",
    "import_hh_negotiations",
    "serialize_import_result",
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
