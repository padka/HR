from backend.apps.bot import services


def test_recruiter_caption_escapes_html():
    fio = 'Миша <b>bold</b> <a href="http://evil">link</a>'
    city = 'Москва <script>alert(1)</script>'
    text = services._format_recruiter_slot_caption(
        candidate_label=fio,
        city_label=city,
        dt_label="01.01 10:00",
        purpose="видео-интервью",
    )

    assert "&lt;b&gt;bold&lt;/b&gt;" in text
    assert "&lt;a href=&quot;http://evil&quot;&gt;link&lt;/a&gt;" in text
    assert "<b>bold</b>" not in text
    assert '<a href="http://evil">link</a>' not in text
