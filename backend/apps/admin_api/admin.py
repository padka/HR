from sqladmin import Admin, ModelView
from sqlalchemy.ext.asyncio import AsyncEngine

from backend.domain.models import Recruiter, City, Template, Slot, SlotStatus


class RecruiterAdmin(ModelView, model=Recruiter):
    name = "Recruiter"
    name_plural = "Recruiters"
    icon = "fa-solid fa-user-tie"

    column_list = [Recruiter.id, Recruiter.name, Recruiter.tg_chat_id, Recruiter.tz, Recruiter.active]
    column_searchable_list = [Recruiter.name]
    column_sortable_list = [Recruiter.id, Recruiter.name, Recruiter.active]
    form_columns = [Recruiter.name, Recruiter.tg_chat_id, Recruiter.tz, Recruiter.telemost_url, Recruiter.active]


class CityAdmin(ModelView, model=City):
    name = "City"
    name_plural = "Cities"
    icon = "fa-solid fa-city"

    column_list = [City.id, City.name, City.tz, City.active]
    column_searchable_list = [City.name]
    column_sortable_list = [City.id, City.name, City.active]
    form_columns = [City.name, City.tz, City.active]


class TemplateAdmin(ModelView, model=Template):
    name = "Template"
    name_plural = "Templates"
    icon = "fa-regular fa-message"

    column_list = [Template.id, Template.city_id, Template.key]
    column_searchable_list = [Template.key]
    form_columns = [Template.city_id, Template.key, Template.content]


class SlotAdmin(ModelView, model=Slot):
    name = "Slot"
    name_plural = "Slots"
    icon = "fa-regular fa-calendar"

    column_list = [
        Slot.id,
        Slot.recruiter_id,
        Slot.city_id,
        Slot.start_utc,
        Slot.duration_min,
        Slot.status,
        Slot.candidate_fio,
    ]
    column_sortable_list = [Slot.id, Slot.start_utc, Slot.status]
    form_columns = [
        Slot.recruiter_id,
        Slot.city_id,
        Slot.start_utc,
        Slot.duration_min,
        Slot.status,
        Slot.candidate_tg_id,
        Slot.candidate_fio,
        Slot.candidate_tz,
    ]

    form_choices = {
        "status": [
            (SlotStatus.FREE, "free"),
            (SlotStatus.PENDING, "pending"),
            (SlotStatus.BOOKED, "booked"),
            (SlotStatus.CONFIRMED_BY_CANDIDATE, "confirmed_by_candidate"),
            (SlotStatus.CANCELED, "canceled"),
        ]
    }


def mount_admin(app, engine: AsyncEngine):
    admin = Admin(app, engine)
    admin.add_view(RecruiterAdmin)
    admin.add_view(CityAdmin)
    admin.add_view(TemplateAdmin)
    admin.add_view(SlotAdmin)
    return admin
