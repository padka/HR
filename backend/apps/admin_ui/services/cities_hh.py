from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import and_, select

from backend.apps.admin_ui.security import Principal
from backend.core.db import async_session
from backend.domain.hh_integration import (
    HHApiClient,
    HHApiError,
    apply_refreshed_tokens,
    decrypt_access_token,
    decrypt_refresh_token,
    get_connection_for_principal,
)
from backend.domain.hh_integration.models import ExternalVacancyBinding
from backend.domain.models import City, Vacancy


def _string(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _normalized_city_names(city: City) -> set[str]:
    names = {
        _string(getattr(city, "name", None)),
        _string(getattr(city, "name_plain", None)),
    }
    return {name.casefold() for name in names if name}


def _binding_area_name(binding: ExternalVacancyBinding | None) -> str | None:
    if binding is None or not isinstance(binding.payload_snapshot, dict):
        return None
    area = binding.payload_snapshot.get("area")
    if isinstance(area, dict):
        return _string(area.get("name"))
    return None


def _binding_title(binding: ExternalVacancyBinding | None, live_payload: dict[str, Any] | None) -> str:
    if live_payload is not None:
        live_name = _string(live_payload.get("name"))
        if live_name:
            return live_name
    if binding and binding.title_snapshot:
        return binding.title_snapshot
    return "HH вакансия"


def _live_vacancy_area_names(payload: dict[str, Any] | None) -> set[str]:
    if not isinstance(payload, dict):
        return set()
    names = {
        _string((payload.get("area") or {}).get("name")) if isinstance(payload.get("area"), dict) else None,
        _string((payload.get("address") or {}).get("city")) if isinstance(payload.get("address"), dict) else None,
    }
    return {name.casefold() for name in names if name}


def _vacancy_publication_status(
    *,
    vacancy: Vacancy | None,
    binding: ExternalVacancyBinding | None,
    live_payload: dict[str, Any] | None,
) -> tuple[str, str]:
    if binding is None:
        return ("not_linked", "Не привязана к HH")
    if live_payload is not None:
        if vacancy is None:
            return ("published", "Опубликована на HH (без привязки к CRM)")
        return ("published", "Опубликована на HH")
    snapshot = binding.payload_snapshot if isinstance(binding.payload_snapshot, dict) else {}
    if snapshot.get("archived") is True:
        return ("archived", "Архивирована на HH")
    if snapshot.get("published") is False:
        return ("unpublished", "Снята с публикации")
    if vacancy is not None and vacancy.is_active is False:
        return ("inactive_local", "Локальная вакансия неактивна")
    if vacancy is None:
        return ("unbound_hh", "Найдена в HH, но не привязана к вакансии CRM")
    return ("not_found_in_active_feed", "Не найдена среди активных вакансий HH")


async def _load_active_hh_vacancies(
    session,
    *,
    principal: Principal,
    wanted_ids: set[str],
) -> tuple[dict[str, dict[str, Any]], str | None]:
    if not wanted_ids:
        return {}, None

    connection = await get_connection_for_principal(session, principal)
    if connection is None or not connection.employer_id:
        return {}, None

    client = HHApiClient()

    async def _fetch(access_token: str) -> dict[str, dict[str, Any]]:
        page = 0
        found: dict[str, dict[str, Any]] = {}
        while True:
            payload = await client.list_vacancies(
                access_token,
                employer_id=connection.employer_id,
                manager_account_id=connection.manager_account_id,
                page=page,
                per_page=50,
            )
            items = payload.get("items")
            if not isinstance(items, list) or not items:
                break
            for item in items:
                if not isinstance(item, dict):
                    continue
                item_id = _string(item.get("id"))
                if item_id and item_id in wanted_ids:
                    found[item_id] = item
            pages = int(payload.get("pages") or 0)
            page += 1
            if wanted_ids.issubset(found.keys()):
                break
            if pages and page >= pages:
                break
        return found

    try:
        return await _fetch(decrypt_access_token(connection)), None
    except HHApiError as exc:
        if exc.status_code != 401:
            return {}, str(exc)
        try:
            tokens = await client.refresh_access_token(decrypt_refresh_token(connection))
            apply_refreshed_tokens(connection, tokens)
            await session.commit()
            return await _fetch(tokens.access_token), None
        except HHApiError as refresh_exc:
            connection.last_error = str(refresh_exc)
            await session.commit()
            return {}, str(refresh_exc)


async def _load_active_hh_vacancies_for_city(
    session,
    *,
    principal: Principal,
    city_names: set[str],
) -> tuple[dict[str, dict[str, Any]], str | None]:
    if not city_names:
        return {}, None

    connection = await get_connection_for_principal(session, principal)
    if connection is None or not connection.employer_id:
        return {}, None

    client = HHApiClient()

    async def _fetch(access_token: str) -> dict[str, dict[str, Any]]:
        page = 0
        found: dict[str, dict[str, Any]] = {}
        while True:
            payload = await client.list_vacancies(
                access_token,
                employer_id=connection.employer_id,
                manager_account_id=connection.manager_account_id,
                page=page,
                per_page=50,
            )
            items = payload.get("items")
            if not isinstance(items, list) or not items:
                break
            for item in items:
                if not isinstance(item, dict):
                    continue
                item_id = _string(item.get("id"))
                if not item_id:
                    continue
                if _live_vacancy_area_names(item) & city_names:
                    found[item_id] = item
            pages = int(payload.get("pages") or 0)
            page += 1
            if pages and page >= pages:
                break
        return found

    try:
        return await _fetch(decrypt_access_token(connection)), None
    except HHApiError as exc:
        if exc.status_code != 401:
            return {}, str(exc)
        try:
            tokens = await client.refresh_access_token(decrypt_refresh_token(connection))
            apply_refreshed_tokens(connection, tokens)
            await session.commit()
            return await _fetch(tokens.access_token), None
        except HHApiError as refresh_exc:
            connection.last_error = str(refresh_exc)
            await session.commit()
            return {}, str(refresh_exc)


async def get_city_hh_vacancy_statuses(
    city_id: int,
    *,
    principal: Principal,
) -> dict[str, Any] | None:
    async with async_session() as session:
        city = await session.get(City, city_id)
        if city is None:
            return None

        rows = (
            await session.execute(
                select(Vacancy, ExternalVacancyBinding)
                .outerjoin(
                    ExternalVacancyBinding,
                    and_(
                        ExternalVacancyBinding.vacancy_id == Vacancy.id,
                        ExternalVacancyBinding.source == "hh",
                    ),
                )
                .where(Vacancy.city_id == city_id)
                .order_by(Vacancy.is_active.desc(), Vacancy.updated_at.desc(), Vacancy.id.desc())
            )
        ).all()

        unbound_bindings = (
            await session.execute(
                select(ExternalVacancyBinding)
                .where(
                    ExternalVacancyBinding.source == "hh",
                    ExternalVacancyBinding.vacancy_id.is_(None),
                )
                .order_by(ExternalVacancyBinding.id.desc())
            )
        ).scalars().all()
        city_names = _normalized_city_names(city)
        matched_unbound_bindings = [
            binding
            for binding in unbound_bindings
            if (_binding_area_name(binding) or "").casefold() in city_names
        ]

        wanted_ids = {
            _string(binding.external_vacancy_id)
            for vacancy, binding in rows
            if binding is not None and _string(binding.external_vacancy_id)
        }
        wanted_ids.update(
            _string(binding.external_vacancy_id)
            for binding in matched_unbound_bindings
            if _string(binding.external_vacancy_id)
        )
        wanted_ids = {item for item in wanted_ids if item}
        active_vacancies_map, api_error = await _load_active_hh_vacancies(
            session,
            principal=principal,
            wanted_ids=wanted_ids,
        )
        if not active_vacancies_map:
            city_active_vacancies_map, city_api_error = await _load_active_hh_vacancies_for_city(
                session,
                principal=principal,
                city_names=city_names,
            )
            if city_active_vacancies_map:
                active_vacancies_map = city_active_vacancies_map
            if api_error is None:
                api_error = city_api_error

        items: list[dict[str, Any]] = []
        now_iso = datetime.now(UTC).isoformat()
        seen_external_ids: set[str] = set()
        for vacancy, binding in rows:
            external_vacancy_id = _string(binding.external_vacancy_id) if binding is not None else None
            live_payload = active_vacancies_map.get(external_vacancy_id or "")
            snapshot = binding.payload_snapshot if binding and isinstance(binding.payload_snapshot, dict) else {}
            status, status_label = _vacancy_publication_status(
                vacancy=vacancy,
                binding=binding,
                live_payload=live_payload,
            )
            source_payload = live_payload or snapshot
            hh_title = _binding_title(binding, live_payload)
            if external_vacancy_id:
                seen_external_ids.add(external_vacancy_id)

            items.append(
                {
                    "vacancy_id": vacancy.id,
                    "vacancy_title": vacancy.title,
                    "vacancy_slug": vacancy.slug,
                    "vacancy_is_active": vacancy.is_active,
                    "hh_linked": binding is not None,
                    "local_vacancy_linked": True,
                    "external_vacancy_id": external_vacancy_id,
                    "hh_title": hh_title,
                    "hh_url": _string(source_payload.get("url"))
                    or _string(source_payload.get("alternate_url"))
                    or (binding.external_url if binding else None),
                    "status": status,
                    "status_label": status_label,
                    "status_source": "live_api" if live_payload is not None else ("snapshot" if binding is not None else "local"),
                    "published": bool(live_payload is not None) if binding is not None else False,
                    "last_checked_at": now_iso if binding is not None else None,
                    "last_hh_sync_at": binding.last_hh_sync_at.isoformat() if binding and binding.last_hh_sync_at else None,
                }
            )

        for binding in matched_unbound_bindings:
            external_vacancy_id = _string(binding.external_vacancy_id)
            if external_vacancy_id and external_vacancy_id in seen_external_ids:
                continue
            live_payload = active_vacancies_map.get(external_vacancy_id or "")
            snapshot = binding.payload_snapshot if isinstance(binding.payload_snapshot, dict) else {}
            status, status_label = _vacancy_publication_status(
                vacancy=None,
                binding=binding,
                live_payload=live_payload,
            )
            source_payload = live_payload or snapshot
            hh_title = _binding_title(binding, live_payload)
            if external_vacancy_id:
                seen_external_ids.add(external_vacancy_id)

            items.append(
                {
                    "vacancy_id": -binding.id,
                    "vacancy_title": hh_title,
                    "vacancy_slug": f"hh-unbound-{binding.id}",
                    "vacancy_is_active": True,
                    "hh_linked": True,
                    "local_vacancy_linked": False,
                    "external_vacancy_id": external_vacancy_id,
                    "hh_title": hh_title,
                    "hh_url": _string(source_payload.get("url"))
                    or _string(source_payload.get("alternate_url"))
                    or binding.external_url,
                    "status": status,
                    "status_label": status_label,
                    "status_source": "live_api" if live_payload is not None else "snapshot",
                    "published": bool(live_payload is not None),
                    "last_checked_at": now_iso,
                    "last_hh_sync_at": binding.last_hh_sync_at.isoformat() if binding.last_hh_sync_at else None,
                }
            )

        for external_vacancy_id, live_payload in active_vacancies_map.items():
            if external_vacancy_id in seen_external_ids:
                continue
            hh_title = _binding_title(None, live_payload)
            seen_external_ids.add(external_vacancy_id)
            items.append(
                {
                    "vacancy_id": -(len(items) + 1),
                    "vacancy_title": hh_title,
                    "vacancy_slug": f"hh-live-{external_vacancy_id}",
                    "vacancy_is_active": True,
                    "hh_linked": True,
                    "local_vacancy_linked": False,
                    "external_vacancy_id": external_vacancy_id,
                    "hh_title": hh_title,
                    "hh_url": _string(live_payload.get("url")) or _string(live_payload.get("alternate_url")),
                    "status": "published",
                    "status_label": "Опубликована на HH (без привязки к CRM)",
                    "status_source": "live_api",
                    "published": True,
                    "last_checked_at": now_iso,
                    "last_hh_sync_at": None,
                }
            )

        return {
            "ok": True,
            "city_id": city.id,
            "city_name": getattr(city, "name_plain", city.name),
            "api_error": api_error,
            "items": items,
        }
