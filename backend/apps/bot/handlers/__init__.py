"""Router registrations for bot handlers."""

from __future__ import annotations

from aiogram import Dispatcher

from . import attendance, common, recruiter, slots, test1, test2, interview

__all__ = ["register_routers"]


def register_routers(dp: Dispatcher) -> None:
    """Include all bot routers into the dispatcher."""
    # common router contains generic commands such as /start and /iam
    dp.include_router(common.router)
    dp.include_router(test1.router)
    dp.include_router(test2.router)
    dp.include_router(slots.router)
    dp.include_router(recruiter.router)
    dp.include_router(attendance.router)
    dp.include_router(interview.router)
