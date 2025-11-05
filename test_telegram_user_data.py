#!/usr/bin/env python
"""Test script to demonstrate automatic Telegram user data parsing.

This script shows what data is automatically available from Telegram API
when a user sends a message to the bot.
"""

from aiogram.types import User


def demo_automatic_user_data():
    """Demonstrate what data Telegram provides automatically."""

    # Пример 1: Пользователь С @username
    user_with_username = User(
        id=123456789,
        is_bot=False,
        first_name="Иван",
        last_name="Петров",
        username="ivan_petrov",  # ✅ Автоматически парсится из Telegram
        language_code="ru",
    )

    print("=" * 60)
    print("Пример 1: Пользователь С @username")
    print("=" * 60)
    print(f"ID: {user_with_username.id}")
    print(f"Username: @{user_with_username.username}")  # ✅ ivan_petrov
    print(f"Имя: {user_with_username.first_name}")
    print(f"Фамилия: {user_with_username.last_name}")
    print(f"Язык: {user_with_username.language_code}")
    print(f"Ссылка для чата: https://t.me/{user_with_username.username}")  # ✅ Работает!
    print()

    # Пример 2: Пользователь БЕЗ @username
    user_without_username = User(
        id=987654321,
        is_bot=False,
        first_name="Мария",
        last_name="Иванова",
        username=None,  # ❌ Нет @username в Telegram
        language_code="ru",
    )

    print("=" * 60)
    print("Пример 2: Пользователь БЕЗ @username")
    print("=" * 60)
    print(f"ID: {user_without_username.id}")
    print(f"Username: {user_without_username.username}")  # None
    print(f"Имя: {user_without_username.first_name}")
    print(f"Фамилия: {user_without_username.last_name}")
    print(f"Ссылка для чата: ❌ Невозможно создать (нет username)")
    print()

    # Пример 3: Как код обрабатывает оба случая
    print("=" * 60)
    print("Как код обрабатывает оба случая")
    print("=" * 60)

    for user in [user_with_username, user_without_username]:
        username = getattr(user, "username", None)  # ✅ Безопасное получение

        if username:
            chat_link = f"https://t.me/{username}"
            button_html = f'<a href="{chat_link}">Открыть чат</a>'
            print(f"User {user.id}: {button_html}")
        else:
            button_html = '<span>(нет username)</span>'
            print(f"User {user.id}: {button_html}")

    print()
    print("=" * 60)
    print("ВЫВОД:")
    print("=" * 60)
    print("✅ Username парсится АВТОМАТИЧЕСКИ из Telegram")
    print("✅ Кандидату НЕ нужно ничего вводить вручную")
    print("✅ Telegram сам предоставляет эту информацию")
    print("⚠️  Если у кандидата нет @username - показываем пояснение")
    print("=" * 60)


if __name__ == "__main__":
    demo_automatic_user_data()
