from backend.apps.bot.defaults import DEFAULT_TEMPLATES
from backend.domain.template_stages import STAGE_DEFAULTS


def test_candidate_templates_have_full_text_copy() -> None:
    keys = (
        "interview_confirmed_candidate",
        "confirm_2h",
        "att_confirmed_link",
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


def test_stage_templates_have_no_placeholder_stubs() -> None:
    stage3 = STAGE_DEFAULTS["stage3_intro_invite"]
    assert "{intro_address}" in stage3
    assert "{intro_contact}" in stage3
    assert "[Согласованный адрес" not in stage3
    assert "[Имя, телефон" not in stage3
