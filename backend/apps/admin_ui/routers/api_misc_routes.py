from fastapi import APIRouter

from . import api_misc

router = APIRouter(prefix="/api", tags=["api"])

router.add_api_route('/notifications/feed', api_misc.api_notifications_feed, methods=['GET'])
router.add_api_route('/notifications/logs', api_misc.api_notifications_logs, methods=['GET'])
router.add_api_route('/system/messenger-health', api_misc.api_system_messenger_health, methods=['GET'])
router.add_api_route('/system/messenger-health/{channel}/recover', api_misc.api_recover_messenger_channel, methods=['POST'])
router.add_api_route('/candidates/{candidate_id}/channel-health', api_misc.api_candidate_channel_health, methods=['GET'])
router.add_api_route('/notifications/{notification_id}/retry', api_misc.api_notifications_retry, methods=['POST'])
router.add_api_route('/notifications/{notification_id}/cancel', api_misc.api_notifications_cancel, methods=['POST'])
router.add_api_route('/bot/integration', api_misc.api_bot_integration_status, methods=['GET'])
router.add_api_route('/bot/integration', api_misc.api_bot_integration_update, methods=['POST'])
router.add_api_route('/bot/cities/refresh', api_misc.api_bot_cities_refresh, methods=['POST'])
router.add_api_route('/bot/reminder-policy', api_misc.api_bot_reminder_policy, methods=['GET'])
router.add_api_route('/bot/reminder-policy', api_misc.api_bot_reminder_policy_update, methods=['PUT'])
router.add_api_route('/bot/reminders/jobs', api_misc.api_bot_reminder_jobs, methods=['GET'])
router.add_api_route('/bot/reminders/resync', api_misc.api_bot_reminder_resync, methods=['POST'])
router.add_api_route('/bot/reminder-jobs/{job_id:path}', api_misc.api_cancel_reminder_job, methods=['DELETE'])
router.add_api_route('/vacancies', api_misc.api_list_vacancies, methods=['GET'])
router.add_api_route('/vacancies', api_misc.api_create_vacancy, methods=['POST'])
router.add_api_route('/vacancies/{vacancy_id}', api_misc.api_update_vacancy, methods=['PUT'])
router.add_api_route('/vacancies/{vacancy_id}', api_misc.api_delete_vacancy, methods=['DELETE'])
router.add_api_route('/vacancies/{vacancy_id}/questions/{test_id}', api_misc.api_get_vacancy_questions, methods=['GET'])
