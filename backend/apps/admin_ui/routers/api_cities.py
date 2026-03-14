from fastapi import APIRouter

from . import api_misc

router = APIRouter(prefix="/api", tags=["api"])

router.add_api_route('/timezones', api_misc.api_timezones, methods=['GET'])
router.add_api_route('/city_owners', api_misc.api_city_owners, methods=['GET'])
