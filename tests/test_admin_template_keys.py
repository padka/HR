import asyncio
import json
import sys
import types

def _stub_migrations_package() -> None:
    if "backend.migrations" in sys.modules:
        return

    fake_module = types.ModuleType("backend.migrations")

    def _noop_upgrade_to_head(*_args, **_kwargs) -> None:
        return None

    fake_module.upgrade_to_head = _noop_upgrade_to_head  # type: ignore[attr-defined]
    fake_module.__all__ = ["upgrade_to_head"]  # type: ignore[attr-defined]
    fake_module.__path__ = []  # type: ignore[attr-defined]
    sys.modules["backend.migrations"] = fake_module
    sys.modules.setdefault("backend.migrations.runner", fake_module)


_stub_migrations_package()


def _ensure_slots_stub() -> None:
    if "backend.apps.admin_ui.services.slots.core" in sys.modules:
        return

    fake_core = types.ModuleType("backend.apps.admin_ui.services.slots.core")

    async def _fake_api_slots_payload(*_args, **_kwargs):
        return {}

    async def _fake_async(*_args, **_kwargs):
        return None

    fake_core.api_slots_payload = _fake_api_slots_payload  # type: ignore[attr-defined]

    fake_package = types.ModuleType("backend.apps.admin_ui.services.slots")
    fake_package.core = fake_core  # type: ignore[attr-defined]
    fake_package.api_slots_payload = _fake_api_slots_payload  # type: ignore[attr-defined]
    fake_package.create_slot = _fake_async  # type: ignore[attr-defined]
    fake_package.list_slots = _fake_async  # type: ignore[attr-defined]
    fake_package.recruiters_for_slot_form = _fake_async  # type: ignore[attr-defined]
    fake_package.set_slot_outcome = _fake_async  # type: ignore[attr-defined]

    sys.modules["backend.apps.admin_ui.services.slots"] = fake_package
    sys.modules["backend.apps.admin_ui.services.slots.core"] = fake_core


_ensure_slots_stub()


def _ensure_router_stubs() -> None:
    stubbed = [
        "backend.apps.admin_ui.routers.candidates",
        "backend.apps.admin_ui.routers.cities",
        "backend.apps.admin_ui.routers.dashboard",
        "backend.apps.admin_ui.routers.recruiters",
        "backend.apps.admin_ui.routers.regions",
        "backend.apps.admin_ui.routers.slots",
        "backend.apps.admin_ui.routers.system",
        "backend.apps.admin_ui.routers.templates",
        "backend.apps.admin_ui.routers.questions",
    ]
    for name in stubbed:
        if name not in sys.modules:
            sys.modules[name] = types.ModuleType(name)


_ensure_router_stubs()



from backend.apps.admin_ui.routers.api import api_template_keys
from backend.apps.admin_ui.services.templates import list_known_template_keys


def test_template_keys_endpoint_matches_runtime() -> None:
    response = asyncio.run(api_template_keys())

    assert response.status_code == 200
    payload = json.loads(response.body.decode("utf-8"))
    assert payload == list_known_template_keys()
