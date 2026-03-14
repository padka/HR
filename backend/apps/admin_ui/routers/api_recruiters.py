from fastapi import APIRouter

from . import api_misc

router = APIRouter(prefix="/api", tags=["api"])

router.add_api_route('/recruiter-plan', api_misc.api_recruiter_plan, methods=['GET'])
router.add_api_route('/recruiter-plan/{city_id}/entries', api_misc.api_recruiter_plan_add, methods=['POST'])
router.add_api_route('/recruiter-plan/entries/{entry_id}', api_misc.api_recruiter_plan_delete, methods=['DELETE'])
