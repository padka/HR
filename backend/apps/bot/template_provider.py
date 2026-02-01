"""Database-backed message template provider with caching and metrics."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Optional, Tuple

from jinja2 import Environment, FileSystemLoader, select_autoescape

from backend.domain.repositories import get_message_template
from backend.utils.jinja_renderer import render_template
from backend.apps.bot.metrics import record_template_fallback

logger = logging.getLogger(__name__)


@dataclass
class TemplateRecord:
    """Message template record from database."""
    key: str
    locale: str
    channel: str
    version: int
    city_id: Optional[int]
    body: str


@dataclass
class RenderedTemplate:
    key: str
    version: int
    city_id: Optional[int]
    text: str


class TemplateResolutionError(RuntimeError):
    """Raised when a template cannot be resolved."""

    def __init__(self, key: str, *, locale: str, channel: str, city_id: Optional[int]) -> None:
        self.key = key
        self.locale = locale
        self.channel = channel
        self.city_id = city_id
        city_part = f" для города #{city_id}" if city_id is not None else ""
        message = (
            f"Активный шаблон '{key}'{city_part} не найден для канала '{channel}' (locale={locale}). "
            "Добавьте городской или общий шаблон в разделе «Шаблоны сообщений»."
        )
        super().__init__(message)


class TemplateProvider:
    """Resolve messaging templates from the database with short-term caching."""

    def __init__(self, *, cache_ttl: int = 60) -> None:
        self._cache_ttl = timedelta(seconds=max(1, cache_ttl))
        self._cache: Dict[
            Tuple[str, str, str, Optional[int]], Tuple[Optional[TemplateRecord], datetime]
        ] = {}
        self._lock = asyncio.Lock()

    async def get(
        self,
        key: str,
        *,
        locale: str = "ru",
        channel: str = "tg",
        city_id: Optional[int] = None,
        strict: bool = False,
    ) -> TemplateRecord:
        cache_key = (key, locale, channel, city_id)
        now = datetime.now(timezone.utc)
        async with self._lock:
            cached = self._cache.get(cache_key)
            if cached and cached[1] > now:
                record = cached[0]
                if record is None:
                    raise TemplateResolutionError(key, locale=locale, channel=channel, city_id=city_id)
                return record

        template = await get_message_template(key, locale=locale, channel=channel, city_id=city_id)
        if template is None:
            await record_template_fallback(key)
            raise TemplateResolutionError(key, locale=locale, channel=channel, city_id=city_id)

        record = TemplateRecord(
            key=template.key,
            locale=template.locale,
            channel=template.channel,
            version=template.version,
            city_id=getattr(template, "city_id", None),
            body=template.body_md,
        )
        async with self._lock:
            self._cache[cache_key] = (record, now + self._cache_ttl)
        return record

    async def render(
        self,
        key: str,
        context: Dict[str, object],
        *,
        locale: str = "ru",
        channel: str = "tg",
        city_id: Optional[int] = None,
        strict: bool = False,
    ) -> Optional[RenderedTemplate]:
        try:
            template = await self.get(key, locale=locale, channel=channel, city_id=city_id, strict=strict)
        except TemplateResolutionError:
             logger.warning(f"Template not found: {key} (city={city_id})")
             return None

        try:
            text = render_template(template.body, context)
        except Exception:
            logger.exception("Failed to render template %s", key)
            text = template.body

        return RenderedTemplate(
            key=template.key,
            version=template.version,
            city_id=template.city_id,
            text=text,
        )

    async def invalidate(
        self,
        *,
        key: Optional[str] = None,
        locale: str = "ru",
        channel: str = "tg",
        city_id: Optional[int] = None,
    ) -> None:
        async with self._lock:
            if key is None:
                self._cache.clear()
                return
            targets = []
            for cache_key in list(self._cache.keys()):
                same_key = cache_key[0] == key and cache_key[1] == locale and cache_key[2] == channel
                if not same_key:
                    continue
                if city_id is None or cache_key[3] == city_id:
                    targets.append(cache_key)
            for cache_key in targets:
                self._cache.pop(cache_key, None)


class Jinja2TemplateProvider:
    """
    Template provider that renders templates from the filesystem using Jinja2.
    """
    def __init__(self, template_dir: Optional[Path] = None) -> None:
        if template_dir is None:
            template_dir = Path(__file__).parent / "templates"
        
        self._env = Environment(
            loader=FileSystemLoader(template_dir),
            autoescape=select_autoescape(['html', 'xml']),
            enable_async=True
        )

    async def render(
        self,
        key: str,
        context: Dict[str, object],
        *,
        locale: str = "ru",
        channel: str = "tg",
        city_id: Optional[int] = None,
        strict: bool = False,
    ) -> Optional[RenderedTemplate]:
        # Strategy:
        # 1. {key}_{city_id}.html (if city_id)
        # 2. {key}.html
        
        template_names = []
        if city_id is not None:
            template_names.append(f"{key}_{city_id}.html")
        template_names.append(f"{key}.html")
        
        template = None
        for name in template_names:
            try:
                template = self._env.get_template(name)
                break
            except Exception:
                continue
        
        if template is None:
            logger.warning(f"Template not found: {key} (city={city_id})")
            return None

        try:
            text = await template.render_async(context)
            return RenderedTemplate(
                key=key,
                version=1,
                city_id=city_id,
                text=text,
            )
        except Exception:
            logger.exception("Failed to render template %s", key)
            return None


__all__ = [
    "TemplateProvider",
    "Jinja2TemplateProvider",
    "TemplateRecord",
    "RenderedTemplate",
    "TemplateResolutionError",
]
