from fastapi import APIRouter

from . import api_misc

router = APIRouter(prefix="/api", tags=["api"])

router.add_api_route('/candidates/{candidate_id}', api_misc.api_candidate, methods=['GET'])
router.add_api_route('/candidates/{candidate_id}/hh', api_misc.api_candidate_hh_summary, methods=['GET'])
router.add_api_route('/candidates/{candidate_id}/cohort-comparison', api_misc.api_candidate_cohort_comparison, methods=['GET'])
router.add_api_route('/candidates/{candidate_id}', api_misc.api_candidate_delete, methods=['DELETE'])
router.add_api_route('/candidates', api_misc.api_candidates_list, methods=['GET'])
router.add_api_route('/candidates/{candidate_id}/actions/{action_key}', api_misc.api_candidate_action, methods=['POST'])
router.add_api_route('/candidates/{candidate_id}/kanban-status', api_misc.api_candidate_kanban_status, methods=['POST'])
router.add_api_route('/candidates/{candidate_id}/assign-recruiter', api_misc.api_assign_candidate_recruiter, methods=['POST'])
router.add_api_route('/candidates', api_misc.api_create_candidate, methods=['POST'], status_code=201)
router.add_api_route('/candidates/{candidate_id}/available-slots', api_misc.api_candidate_available_slots, methods=['GET'])
router.add_api_route('/candidates/{candidate_id}/schedule-slot', api_misc.api_schedule_slot, methods=['POST'])
router.add_api_route('/candidates/{candidate_id}/schedule-intro-day', api_misc.api_schedule_intro_day, methods=['POST'])
router.add_api_route('/candidates/{candidate_id}/channels/max-link', api_misc.api_candidate_max_link, methods=['POST'])
