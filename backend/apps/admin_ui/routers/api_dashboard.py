from fastapi import APIRouter

from . import api_misc

router = APIRouter(prefix="/api", tags=["api"])

router.add_api_route('/csrf', api_misc.api_csrf, methods=['GET'])
router.add_api_route('/health', api_misc.api_health, methods=['GET'])
router.add_api_route('/dashboard/summary', api_misc.api_dashboard_summary, methods=['GET'])
router.add_api_route('/dashboard/incoming', api_misc.api_dashboard_incoming, methods=['GET'])
router.add_api_route('/dashboard/recruiter-performance', api_misc.api_dashboard_recruiter_performance, methods=['GET'])
router.add_api_route('/dashboard/calendar', api_misc.api_dashboard_calendar, methods=['GET'])
router.add_api_route('/calendar/events', api_misc.api_calendar_events, methods=['GET'])
router.add_api_route('/calendar/tasks', api_misc.api_calendar_task_create, methods=['POST'])
router.add_api_route('/calendar/tasks/{task_id}', api_misc.api_calendar_task_update, methods=['PATCH'])
router.add_api_route('/calendar/tasks/{task_id}', api_misc.api_calendar_task_delete, methods=['DELETE'])
router.add_api_route('/dashboard/funnel', api_misc.api_dashboard_funnel, methods=['GET'])
router.add_api_route('/kpis/current', api_misc.api_weekly_kpis, methods=['GET'])
router.add_api_route('/kpis/history', api_misc.api_weekly_history, methods=['GET'])
