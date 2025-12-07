from __future__ import annotations

from backend.apps.bot import config

def test_refresh_questions_bank_updates_globals(monkeypatch):
    sample = {"test1": [{"id": "q1"}], "test2": [{"id": "q2"}]}

    def fake_loader(*, include_inactive: bool = False):
        return sample

    monkeypatch.setattr(config, "load_all_test_questions", fake_loader)

    config.refresh_questions_bank()

    assert config.TEST1_QUESTIONS == [{"id": "q1"}]
    assert config.TEST2_QUESTIONS == [{"id": "q2"}]
    assert config._QUESTIONS_BANK == sample


def test_refresh_questions_bank_fallbacks(monkeypatch):
    # Force loader to raise and ensure defaults are used without crashing.
    def failing_loader(*, include_inactive: bool = False):
        raise RuntimeError("db down")

    monkeypatch.setattr(config, "load_all_test_questions", failing_loader)

    config.refresh_questions_bank()

    assert config.TEST1_QUESTIONS  # default questions present
    assert config.TEST2_QUESTIONS
