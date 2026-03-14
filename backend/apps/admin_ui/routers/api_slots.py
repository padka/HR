from fastapi import APIRouter

from . import api_misc

router = APIRouter(prefix="/api", tags=["api"])

router.add_api_route('/slots', api_misc.api_slots, methods=['GET'])
router.add_api_route('/slots/bulk_create', api_misc.api_slots_bulk_create, methods=['POST'])
router.add_api_route('/slots/{slot_id}/approve_booking', api_misc.api_slot_approve, methods=['POST'])
router.add_api_route('/slots/{slot_id}/reject_booking', api_misc.api_slot_reject, methods=['POST'])
router.add_api_route('/slots/{slot_id}/reschedule', api_misc.api_slot_reschedule, methods=['POST'])
router.add_api_route('/slots/{slot_id}/propose', api_misc.api_slot_propose, methods=['POST'])
router.add_api_route('/slots/{slot_id}/outcome', api_misc.api_slot_outcome, methods=['POST'])
router.add_api_route('/slots/{slot_id}/book', api_misc.api_slot_book, methods=['POST'])
router.add_api_route('/slots/manual-bookings', api_misc.api_slots_manual_booking, methods=['POST'])
router.add_api_route('/slots/{slot_id}', api_misc.api_slot_delete, methods=['DELETE'])
router.add_api_route('/slots/bulk', api_misc.api_slots_bulk, methods=['POST'])
