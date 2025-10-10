from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import BareFilesPathWrapper

__all__ = ["create_api_session"]


@dataclass
class _ConfiguredTelegramAPIServer:
    base: str
    file: str
    is_local: bool = False
    wrap_local_file: BareFilesPathWrapper = BareFilesPathWrapper()

    def __post_init__(self) -> None:
        configured = self.base.strip()
        normalized = configured.rstrip("/") or configured
        object.__setattr__(self, "_api_template", f"{normalized}/bot{{token}}/{{method}}")
        object.__setattr__(self, "_file_template", f"{normalized}/file/bot{{token}}/{{path}}")
        object.__setattr__(self, "base", configured)
        object.__setattr__(self, "file", f"{normalized}/file/bot{{token}}/{{path}}")

    def api_url(self, token: str, method: str) -> str:
        return self._api_template.format(token=token, method=method)

    def file_url(self, token: str, path: str) -> str:
        return self._file_template.format(token=token, path=path)


def create_api_session(base_url: Optional[str]) -> Optional[AiohttpSession]:
    clean = (base_url or "").strip()
    if not clean:
        return None
    server = _ConfiguredTelegramAPIServer(base=clean, file=clean)
    return AiohttpSession(api=server)
