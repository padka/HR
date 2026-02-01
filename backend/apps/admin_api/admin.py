import secrets
from sqladmin import Admin, ModelView
from sqladmin.authentication import AuthenticationBackend
from starlette.requests import Request
from sqlalchemy.ext.asyncio import AsyncEngine

from backend.domain.models import Recruiter, City, Slot, SlotStatus
from backend.domain.cities.models import CityExpert, CityExecutive
from backend.apps.admin_ui.views.tests import TestAdmin, QuestionAdmin, AnswerOptionAdmin
from backend.core.settings import get_settings


class AdminAuth(AuthenticationBackend):
    async def login(self, request: Request) -> bool:
        form = await request.form()
        username = str(form.get("username") or "")
        password = str(form.get("password") or "")
        settings = get_settings()
        if not settings.admin_username or not settings.admin_password:
            return False
        user_ok = secrets.compare_digest(username, settings.admin_username)
        pass_ok = secrets.compare_digest(password, settings.admin_password)
        if user_ok and pass_ok:
            request.session["sqladmin_auth"] = True
            request.session["sqladmin_user"] = username
            return True
        return False

    async def logout(self, request: Request) -> bool:
        request.session.pop("sqladmin_auth", None)
        request.session.pop("sqladmin_user", None)
        return True

    async def authenticate(self, request: Request) -> bool:
        return bool(request.session.get("sqladmin_auth"))


class RecruiterAdmin(ModelView, model=Recruiter):
    name = "Recruiter"
    name_plural = "Recruiters"
    icon = "fa-solid fa-user-tie"

    column_list = [Recruiter.id, Recruiter.name, Recruiter.tg_chat_id, Recruiter.tz, Recruiter.active]
    column_searchable_list = [Recruiter.name]
    column_sortable_list = [Recruiter.id, Recruiter.name, Recruiter.active]
    form_columns = [Recruiter.name, Recruiter.tg_chat_id, Recruiter.tz, Recruiter.telemost_url, Recruiter.active]


class CityExpertAdmin(ModelView, model=CityExpert):
    name = "Expert"
    name_plural = "Experts"
    icon = "fa-solid fa-user-graduate"
    column_list = [CityExpert.name, CityExpert.city, CityExpert.is_active]
    form_columns = [CityExpert.name, CityExpert.city, CityExpert.is_active]


class CityExecutiveAdmin(ModelView, model=CityExecutive):
    name = "Executive"
    name_plural = "Executives"
    icon = "fa-solid fa-user-shield"
    column_list = [CityExecutive.name, CityExecutive.city, CityExecutive.is_active]
    form_columns = [CityExecutive.name, CityExecutive.city, CityExecutive.is_active]


class CityAdmin(ModelView, model=City):
    name = "City"
    name_plural = "Cities"
    icon = "fa-solid fa-city"

    column_list = [City.id, City.name, City.tz, City.active]
    column_searchable_list = [City.name]
    column_sortable_list = [City.id, City.name, City.active]
    form_columns = [City.name, City.tz, City.active]


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
    settings = get_settings()
    admin = Admin(app, engine, authentication_backend=AdminAuth(secret_key=settings.session_secret))
    admin.add_view(RecruiterAdmin)
    admin.add_view(CityAdmin)
    admin.add_view(CityExpertAdmin)
    admin.add_view(CityExecutiveAdmin)
    admin.add_view(SlotAdmin)
    admin.add_view(TestAdmin)
    admin.add_view(QuestionAdmin)
    admin.add_view(AnswerOptionAdmin)
    return admin
