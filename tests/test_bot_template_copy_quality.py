import ast
from pathlib import Path

from backend.apps.bot.defaults import DEFAULT_TEMPLATES
from backend.domain.template_stages import STAGE_DEFAULTS


def test_candidate_templates_have_full_text_copy() -> None:
    keys = (
        "interview_confirmed_candidate",
        "confirm_2h",
        "reminder_10m",
        "att_confirmed_link",
        "att_declined_reason_prompt",
        "intro_day_invitation",
        "intro_day_reminder",
        "t1_done",
        "t2_intro",
        "slot_proposal_candidate",
        "candidate_reschedule_prompt",
        "result_fail",
    )
    for key in keys:
        text = DEFAULT_TEMPLATES.get(key, "").strip()
        assert text, f"Template '{key}' must not be empty"
        assert len(" ".join(text.split())) >= 60, f"Template '{key}' looks too short"


def test_interview_confirmed_candidate_template_has_updated_meeting_copy() -> None:
    text = DEFAULT_TEMPLATES["interview_confirmed_candidate"]
    assert "Поздравляем — вы на шаг ближе" in text
    assert "💬 <b>Формат:</b> видеочат | 15–20 мин" in text
    assert "• тихое место для созвона" in text
    assert "используйте кнопки ниже, чтобы перенести или отменить встречу" in text


def test_stage_templates_have_no_placeholder_stubs() -> None:
    stage3 = STAGE_DEFAULTS["stage3_intro_invite"]
    assert "{intro_address}" in stage3
    assert "{intro_contact}" in stage3
    assert "[Согласованный адрес" not in stage3
    assert "[Имя, телефон" not in stage3


def test_bot_runtime_template_keys_have_default_texts() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    known_keys = set(DEFAULT_TEMPLATES) | set(STAGE_DEFAULTS)
    runtime_keys: set[str] = set()

    for path in (repo_root / "backend/apps/bot").rglob("*.py"):
        if path.name in {"defaults.py", "jinja_renderer.py", "template_provider.py"}:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if isinstance(node.func, ast.Name) and node.func.id == "_render_tpl" and len(node.args) >= 2:
                candidate = node.args[1]
            elif isinstance(node.func, ast.Attribute) and node.func.attr == "render" and len(node.args) >= 1:
                candidate = node.args[0]
            else:
                continue
            if isinstance(candidate, ast.Constant) and isinstance(candidate.value, str):
                runtime_keys.add(candidate.value)

    missing = runtime_keys - known_keys
    assert missing == set()
