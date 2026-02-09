import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timezone
from backend.apps.admin_ui.services.message_templates import create_message_template
from backend.apps.bot.services import NotificationService, configure_notification_service, configure
from backend.apps.bot.template_provider import TemplateProvider

@pytest.mark.asyncio
async def test_e2e_notification_refactor():
    # 1. Create Template in DB
    key = "interview_confirmed_candidate"
    body = "Hello {{ candidate_name }}, confirmed!"
    
    ok, errors, tmpl = await create_message_template(
        key=key, locale="ru", channel="tg", body=body, is_active=True
    )
    assert ok, f"Failed to create template: {errors}"

    # 2. Setup Service
    provider = TemplateProvider()
    
    service = NotificationService(
        scheduler=MagicMock(), 
        template_provider=provider,
        batch_size=10, 
        poll_interval=1.0
    )
    configure_notification_service(service)
    
    mock_bot_instance = AsyncMock()
    configure(bot=mock_bot_instance, state_manager=MagicMock())

    # 3. Mock dependencies
    with patch("backend.apps.bot.services.get_slot", new_callable=AsyncMock) as mock_get_slot, \
         patch("backend.apps.bot.services.get_recruiter", new_callable=AsyncMock) as mock_get_recruiter, \
         patch("backend.apps.bot.services.update_outbox_entry", new_callable=AsyncMock), \
         patch("backend.apps.bot.services.add_notification_log", new_callable=AsyncMock), \
         patch("backend.apps.bot.services.notification_log_exists", new_callable=AsyncMock) as mock_log_exists, \
         patch("backend.apps.bot.services.get_notification_log", new_callable=AsyncMock) as mock_get_log, \
         patch("backend.apps.bot.services._send_with_retry", new_callable=AsyncMock) as mock_send:
        
        mock_slot = MagicMock()
        mock_slot.id = 123
        mock_slot.candidate_tg_id = 999
        mock_slot.candidate_fio = "John Doe"
        mock_slot.start_utc = datetime.now(timezone.utc)
        mock_slot.candidate_tz = "UTC"
        mock_slot.candidate_city_id = None
        mock_slot.recruiter_id = 1
        mock_get_slot.return_value = mock_slot
        
        mock_log_exists.return_value = False
        mock_get_log.return_value = None 

        # 4. Simulate Worker Processing
        item = MagicMock()
        item.id = 55
        item.booking_id = 123
        item.candidate_tg_id = 999
        item.attempts = 0
        item.payload = {}
        
        await service._process_candidate_confirmation(item)
        
        # 5. Verify
        # _send_with_retry is mocked, so we check it
        mock_send.assert_called_once()
        call_args = mock_send.call_args
        # Args: (bot, method, correlation_id)
        # method is SendMessage object
        method_arg = call_args[0][1]
        assert method_arg.chat_id == 999
        assert method_arg.text == "Hello John Doe, confirmed!"