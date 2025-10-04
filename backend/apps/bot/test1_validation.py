"""Validation helpers for Test 1 answers."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, Iterable, Optional

from pydantic import BaseModel, ConfigDict, ValidationError, field_validator


_ALLOWED_FORMATS = {
    "Да, готов",
    "Нужен гибкий график",
    "Пока не готов",
}

_ALLOWED_STATUS = {
    "Учусь",
    "Работаю",
    "Ищу работу",
    "Предприниматель",
    "Другое",
}


class Test1Payload(BaseModel):
    """Normalized Test 1 answers validated via Pydantic."""

    fio: Optional[str] = None
    city_id: Optional[int] = None
    city_name: Optional[str] = None
    age: Optional[int] = None
    status: Optional[str] = None
    format_choice: Optional[str] = None
    study_mode: Optional[str] = None
    study_schedule: Optional[str] = None
    study_flex: Optional[str] = None

    model_config = ConfigDict(str_strip_whitespace=True, extra="allow")

    @field_validator("fio")
    @classmethod
    def _fio_must_be_cyrillic(cls, value: Optional[str]) -> Optional[str]:
        if value is None or not value:
            return value
        pattern = re.compile(r"^(?:[А-ЯЁ][а-яё]+(?:[-\s][А-ЯЁ][а-яё]+){1,3})$")
        if not pattern.match(value):
            raise ValueError(
                "ФИО должно содержать 2–4 части кириллицей, например: Иванов Иван Иванович."
            )
        return value

    @field_validator("age")
    @classmethod
    def _age_in_range(cls, value: Optional[int]) -> Optional[int]:
        if value is None:
            return value
        if not 18 <= value <= 60:
            raise ValueError("Возраст должен быть в диапазоне 18–60 лет.")
        return value

    @field_validator("status")
    @classmethod
    def _status_allowed(cls, value: Optional[str]) -> Optional[str]:
        if value is None or not value:
            return value
        if value not in _ALLOWED_STATUS:
            raise ValueError("Выберите вариант из списка.")
        return value

    @field_validator("format_choice")
    @classmethod
    def _format_allowed(cls, value: Optional[str]) -> Optional[str]:
        if value is None or not value:
            return value
        if value not in _ALLOWED_FORMATS:
            raise ValueError("Выберите вариант из предложенных.")
        return value


@dataclass
class ValidationHint:
    field: str
    message: str
    examples: Iterable[str]


def apply_partial_validation(payload: Dict[str, object]) -> Test1Payload:
    """Validate provided payload snippet and return normalized model."""

    return Test1Payload.model_validate(payload)


def convert_age(raw: str) -> int:
    """Parse and normalize age from user input."""

    cleaned = raw.strip()
    if not cleaned:
        raise ValueError("Укажите возраст цифрами.")
    digits = re.sub(r"[^0-9]", "", cleaned)
    if not digits:
        raise ValueError("Укажите возраст цифрами.")
    age = int(digits)
    return age


__all__ = ["Test1Payload", "ValidationHint", "apply_partial_validation", "convert_age"]
