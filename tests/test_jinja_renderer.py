"""Tests for Jinja2-based message template renderer."""

from __future__ import annotations

import pytest
from datetime import datetime, timezone

from backend.apps.bot.jinja_renderer import (
    JinjaRenderer,
    filter_format_datetime,
    filter_format_date,
    filter_format_time,
    filter_format_short,
    get_renderer,
    reset_renderer,
)


class TestDatetimeFilters:
    """Test custom Jinja2 filters for datetime formatting."""

    def test_format_datetime_msk(self):
        """Test full datetime format with Moscow timezone."""
        dt = datetime(2024, 12, 12, 12, 30, 0, tzinfo=timezone.utc)
        result = filter_format_datetime(dt, "Europe/Moscow")
        assert result == "Чт, 12 дек • 15:30 (МСК)"

    def test_format_datetime_nsk(self):
        """Test full datetime format with Novosibirsk timezone."""
        dt = datetime(2024, 12, 12, 12, 30, 0, tzinfo=timezone.utc)
        result = filter_format_datetime(dt, "Asia/Novosibirsk")
        assert result == "Чт, 12 дек • 19:30 (НСК)"

    def test_format_datetime_utc_fallback(self):
        """Test fallback to UTC for unknown timezone."""
        dt = datetime(2024, 12, 12, 12, 30, 0, tzinfo=timezone.utc)
        result = filter_format_datetime(dt, "Invalid/Timezone")
        assert result == "Чт, 12 дек • 12:30 (UTC)"

    def test_format_date(self):
        """Test date-only format."""
        dt = datetime(2024, 12, 12, 12, 30, 0, tzinfo=timezone.utc)
        result = filter_format_date(dt, "Europe/Moscow")
        assert result == "Чт, 12 дек"

    def test_format_time(self):
        """Test time-only format."""
        dt = datetime(2024, 12, 12, 12, 30, 0, tzinfo=timezone.utc)
        result = filter_format_time(dt, "Europe/Moscow")
        assert result == "15:30 (МСК)"

    def test_format_short(self):
        """Test short format without day name."""
        dt = datetime(2024, 12, 12, 12, 30, 0, tzinfo=timezone.utc)
        result = filter_format_short(dt, "Europe/Moscow")
        assert result == "12.12 • 15:30"

    def test_format_with_none_timezone(self):
        """Test formatting with None timezone (should use UTC)."""
        dt = datetime(2024, 12, 12, 12, 30, 0, tzinfo=timezone.utc)
        result = filter_format_datetime(dt, None)
        assert result == "Чт, 12 дек • 12:30 (UTC)"


class TestJinjaRenderer:
    """Test JinjaRenderer class."""

    @pytest.fixture(autouse=True)
    def _reset_renderer(self):
        """Reset global renderer before each test."""
        reset_renderer()
        yield
        reset_renderer()

    def test_get_renderer_singleton(self):
        """Test that get_renderer returns same instance."""
        renderer1 = get_renderer()
        renderer2 = get_renderer()
        assert renderer1 is renderer2

    def test_render_simple_template(self):
        """Test rendering a simple template."""
        renderer = JinjaRenderer()
        # Create a simple test template
        context = {"name": "Alice", "value": 42}
        # We'll use one of the existing templates for this test

    def test_render_interview_confirmed(self):
        """Test rendering interview_confirmed template."""
        renderer = get_renderer()
        dt = datetime(2024, 12, 12, 12, 30, 0, tzinfo=timezone.utc)

        context = {
            "candidate_name": "Анна Иванова",
            "start_utc": dt,
            "tz_name": "Europe/Moscow",
            "format_text": "Видеозвонок • 15-20 мин",
        }

        result = renderer.render("messages/interview_confirmed", context)

        assert "<b>✅ Встреча подтверждена</b>" in result
        assert "Анна Иванова" in result
        assert "Чт, 12 дек • 15:30 (МСК)" in result
        assert "Видеозвонок • 15-20 мин" in result
        assert "Стабильный интернет" in result

    def test_render_reminder_6h(self):
        """Test rendering reminder_6h template."""
        renderer = get_renderer()
        dt = datetime(2024, 12, 12, 12, 30, 0, tzinfo=timezone.utc)

        context = {
            "start_utc": dt,
            "tz_name": "Europe/Moscow",
        }

        result = renderer.render("messages/reminder_6h", context)

        assert "<b>⏰ Встреча сегодня</b>" in result
        assert "Чт, 12 дек • 15:30 (МСК)" in result
        assert "Подтвердите участие" in result

    def test_render_reminder_2h_with_link(self):
        """Test rendering reminder_2h template with meeting link."""
        renderer = get_renderer()
        dt = datetime(2024, 12, 12, 12, 30, 0, tzinfo=timezone.utc)

        context = {
            "start_utc": dt,
            "tz_name": "Europe/Moscow",
            "meet_link": "https://telemost.yandex.ru/example",
        }

        result = renderer.render("messages/reminder_2h", context)

        assert "<b>⏰ Встреча через 2 часа</b>" in result
        assert "https://telemost.yandex.ru/example" in result
        assert "Если планы изменились" in result

    def test_render_intro_day_invitation(self):
        """Test rendering intro_day_invitation template."""
        renderer = get_renderer()
        dt = datetime(2024, 12, 12, 12, 30, 0, tzinfo=timezone.utc)

        context = {
            "start_utc": dt,
            "tz_name": "Europe/Moscow",
            "address": "ул. Ленина, 10, офис 5",
            "contact_name": "Иванов Иван Иванович",
            "contact_phone": "+7 900 123-45-67",
        }

        result = renderer.render("messages/intro_day_invitation", context)

        assert "<b>🎉 Ознакомительный день</b>" in result
        assert "SMART" in result
        assert "ул. Ленина, 10, офис 5" in result
        assert "Иванов Иван Иванович" in result
        assert "+7 900 123-45-67" in result
        assert "Паспорт" in result

    def test_render_reschedule_prompt(self):
        """Test rendering reschedule_prompt template."""
        renderer = get_renderer()

        context = {
            "old_datetime": "Чт, 12 дек • 15:30 (МСК)",
        }

        result = renderer.render("messages/reschedule_prompt", context)

        assert "<b>🔁 Изменение встречи</b>" in result
        assert "Чт, 12 дек • 15:30 (МСК)" in result
        assert "Давайте подберём другое время" in result

    def test_render_no_show_gentle(self):
        """Test rendering no_show_gentle template."""
        renderer = get_renderer()
        dt = datetime(2024, 12, 12, 12, 30, 0, tzinfo=timezone.utc)

        context = {
            "start_utc": dt,
            "tz_name": "Europe/Moscow",
        }

        result = renderer.render("messages/no_show_gentle", context)

        assert "<b>📞 Не удалось связаться</b>" in result
        assert "Чт, 12 дек • 15:30 (МСК)" in result
        assert "Если у вас всё ещё есть интерес" in result

    def test_render_template_not_found(self):
        """Test that TemplateNotFound is raised for missing template."""
        renderer = get_renderer()

        with pytest.raises(Exception):  # Jinja2 TemplateNotFound
            renderer.render("messages/nonexistent_template", {})

    def test_render_safe_with_fallback(self):
        """Test render_safe returns fallback on error."""
        renderer = get_renderer()

        result = renderer.render_safe(
            "messages/nonexistent_template",
            {},
            fallback="Fallback message",
        )

        assert result == "Fallback message"

    def test_render_with_missing_variables(self):
        """Test rendering with missing context variables (should not crash)."""
        renderer = get_renderer()
        dt = datetime(2024, 12, 12, 12, 30, 0, tzinfo=timezone.utc)

        # Missing candidate_name, but should still render
        context = {
            "start_utc": dt,
            "tz_name": "Europe/Moscow",
        }

        result = renderer.render("messages/interview_confirmed", context)

        # Should render without crashing, even if variable is missing
        assert "<b>✅ Встреча подтверждена</b>" in result


class TestTemplateBlocks:
    """Test individual template blocks."""

    @pytest.fixture(autouse=True)
    def _reset_renderer(self):
        """Reset global renderer before each test."""
        reset_renderer()
        yield
        reset_renderer()

    def test_header_block(self):
        """Test header.j2 block macro."""
        renderer = get_renderer()

        # Create minimal template to test header import
        result = renderer.render(
            "messages/reminder_6h",
            {
                "start_utc": datetime(2024, 12, 12, 12, 30, 0, tzinfo=timezone.utc),
                "tz_name": "UTC",
            },
        )

        # Header should produce bold text with emoji
        assert "<b>⏰ Встреча сегодня</b>" in result

    def test_info_row_date(self):
        """Test info_row.j2 date macro."""
        renderer = get_renderer()
        dt = datetime(2024, 12, 12, 12, 30, 0, tzinfo=timezone.utc)

        result = renderer.render(
            "messages/reminder_6h",
            {
                "start_utc": dt,
                "tz_name": "Europe/Moscow",
            },
        )

        # Should contain date with emoji
        assert "📅 Чт, 12 дек • 15:30 (МСК)" in result

    def test_checklist_block(self):
        """Test checklist.j2 block macro."""
        renderer = get_renderer()
        dt = datetime(2024, 12, 12, 12, 30, 0, tzinfo=timezone.utc)

        result = renderer.render(
            "messages/interview_confirmed",
            {
                "candidate_name": "Test",
                "start_utc": dt,
                "tz_name": "UTC",
            },
        )

        # Should contain checklist items with checkmarks
        assert "⚡ <b>Подготовьтесь заранее:</b>" in result
        assert "✓ Стабильный интернет" in result


class TestHTMLEscaping:
    """Test HTML escaping security for user input."""

    def test_candidate_name_html_injection(self):
        """Test that candidate name with HTML is escaped."""
        renderer = get_renderer()
        dt = datetime(2024, 12, 12, 12, 30, 0, tzinfo=timezone.utc)

        # Malicious candidate name with HTML tags
        result = renderer.render(
            "messages/interview_confirmed",
            {
                "candidate_name": "<b>Evil</b> & <script>alert('xss')</script>",
                "start_utc": dt,
                "tz_name": "UTC",
            },
        )

        # HTML should be escaped
        assert "&lt;b&gt;Evil&lt;/b&gt;" in result
        assert "&lt;script&gt;" in result
        assert "<script>" not in result  # Should NOT contain unescaped script tag

    def test_address_html_injection(self):
        """Test that address with HTML is escaped."""
        renderer = get_renderer()
        dt = datetime(2024, 12, 12, 12, 30, 0, tzinfo=timezone.utc)

        # Malicious address with HTML tags
        result = renderer.render(
            "messages/intro_day_invitation",
            {
                "start_utc": dt,
                "tz_name": "UTC",
                "address": "<a href='evil.com'>Click me</a> & <img src=x onerror=alert(1)>",
                "contact_name": "Test",
                "contact_phone": "+7 900 123-45-67",
            },
        )

        # HTML should be escaped
        assert "&lt;a href=" in result
        assert "&lt;img " in result
        assert "<img src=x" not in result  # Should NOT contain unescaped img tag

    def test_intentional_html_preserved(self):
        """Test that intentional HTML in templates is preserved."""
        renderer = get_renderer()
        dt = datetime(2024, 12, 12, 12, 30, 0, tzinfo=timezone.utc)

        result = renderer.render(
            "messages/interview_confirmed",
            {
                "candidate_name": "Test User",
                "start_utc": dt,
                "tz_name": "UTC",
            },
        )

        # Intentional HTML from template should be preserved
        assert "<b>✅ Встреча подтверждена</b>" in result
        assert "⚡ <b>Подготовьтесь заранее:</b>" in result
