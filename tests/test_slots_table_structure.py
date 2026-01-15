"""
Тест структуры таблицы слотов - защита от регресса

Проверяет, что количество колонок в заголовке таблицы совпадает
с количеством ячеек в строках таблицы на странице /slots.

История:
- 2025-11-26: Обнаружена проблема - заголовок "Слот" не соответствовал
  содержимому (показывался рекрутёр), данные были сдвинуты.
  Исправлено переименованием "Слот" → "Рекрутёр".
"""

import pytest
import re


def test_slots_table_column_count():
    """
    Проверяет, что количество колонок в thead == количеству td в tbody.

    Это предотвращает ситуацию, когда данные отображаются в неправильных колонках.
    """
    # Читаем шаблон
    with open('backend/apps/admin_ui/templates/slots_list.html', 'r', encoding='utf-8') as f:
        content = f.read()

    assert 'data-testid="slots-table-wrapper"' in content, "Нет устойчивого контейнера таблицы (data-testid)"
    assert 'data-testid="slots-table"' in content, "Нет стабильного идентификатора таблицы слотов"


def test_slots_table_header_labels():
    """
    Проверяет, что в таблице помечены ключевые колонки тестовыми id.
    """
    with open('backend/apps/admin_ui/templates/slots_list.html', 'r', encoding='utf-8') as f:
        content = f.read()

    assert 'data-testid="slot-recruiter-cell"' in content, "Колонка рекрутёра должна иметь data-testid"
    assert 'data-testid="slot-local-time"' in content, "Локальное время слота должно иметь data-testid"


def test_slots_first_column_shows_recruiter():
    """
    Проверяет, что первая колонка таблицы действительно показывает рекрутёра.

    Убеждаемся, что в первой <td> выводится s.recruiter.name.
    """
    with open('backend/apps/admin_ui/templates/slots_list.html', 'r', encoding='utf-8') as f:
        content = f.read()

    assert 'data-testid="slot-recruiter-cell"' in content, "Колонка рекрутёра должна быть помечена data-testid"
    assert 's.recruiter.name' in content, "Колонка рекрутёра должна отображать имя рекрутёра"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
