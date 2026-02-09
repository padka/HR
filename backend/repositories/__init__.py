"""Repository implementations for domain models."""

from .recruiter import RecruiterRepository
from .city import CityRepository
from .slot import SlotRepository
from .template import MessageTemplateRepository
from .user import UserRepository, TestResultRepository, AutoMessageRepository

__all__ = [
    "RecruiterRepository",
    "CityRepository",
    "SlotRepository",
    "MessageTemplateRepository",
    "UserRepository",
    "TestResultRepository",
    "AutoMessageRepository",
]
