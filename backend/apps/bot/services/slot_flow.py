"""Slot scheduling and attendance flow services."""

from . import base as _base

for _name in dir(_base):
    if _name.startswith("__") and _name.endswith("__"):
        continue
    globals()[_name] = getattr(_base, _name)

from .broadcast import notify_recruiters_manual_availability
from .notification_flow import get_notification_service

async def capture_slot_snapshot(slot: Slot) -> SlotSnapshot:
    """Return a lightweight snapshot of slot and candidate data."""

    return await _build_slot_snapshot(slot)


async def cancel_slot_reminders(slot_id: int) -> None:
    """Cancel reminder jobs for the provided slot."""

    await _cancel_reminders_for_slot(slot_id)


async def notify_reschedule(snapshot: SlotSnapshot) -> bool:
    """Notify candidate about reschedule request."""

    return await _send_reschedule_prompt(snapshot)


async def notify_rejection(snapshot: SlotSnapshot) -> bool:
    """Notify candidate about rejection."""

    return await _send_final_rejection_notice(snapshot)

def _clamp(value: int, *, low: int, high: int) -> int:
    return max(low, min(value, high))


def _parse_manual_availability_window(
    text: str,
    tz_label: Optional[str],
) -> Tuple[Optional[datetime], Optional[datetime]]:
    """Attempt to parse candidate-provided availability window."""

    cleaned = (text or "").strip()
    if not cleaned:
        return None, None

    range_match = _AVAILABILITY_RANGE_RE.search(cleaned)
    if not range_match:
        return None, None

    try:
        start_hour = _clamp(int(range_match.group("from_h")), low=0, high=23)
    except (TypeError, ValueError):
        start_hour = 0
    try:
        start_min = _clamp(int(range_match.group("from_m") or 0), low=0, high=59)
    except (TypeError, ValueError):
        start_min = 0
    try:
        end_hour = _clamp(int(range_match.group("to_h")), low=0, high=23)
    except (TypeError, ValueError):
        end_hour = 0
    try:
        end_min = _clamp(int(range_match.group("to_m") or 0), low=0, high=59)
    except (TypeError, ValueError):
        end_min = 0

    tzinfo = _safe_zone(tz_label or DEFAULT_TZ)
    now_local = datetime.now(tzinfo)
    target_date = None

    date_match = _AVAILABILITY_DATE_RE.search(cleaned)
    if date_match:
        try:
            day = int(date_match.group("day"))
            month = int(date_match.group("month"))
            year_raw = date_match.group("year")
            if year_raw:
                year = int(year_raw)
                if year < 100:
                    year += 2000
            else:
                year = now_local.year
            candidate_date = date(year, month, day)
            if not year_raw and candidate_date < now_local.date():
                candidate_date = date(year + 1, month, day)
            target_date = candidate_date
        except ValueError:
            target_date = None

    if target_date is None:
        lowered = cleaned.lower()
        for keyword, offset in _KEYWORD_DATE_OFFSETS.items():
            if keyword in lowered:
                target_date = (now_local + timedelta(days=offset)).date()
                break

    if target_date is None:
        target_date = now_local.date()
        candidate_start = datetime.combine(target_date, time(start_hour, start_min), tzinfo=tzinfo)
        if candidate_start <= now_local - timedelta(minutes=30):
            target_date = target_date + timedelta(days=1)

    start_dt = datetime.combine(target_date, datetime_time(start_hour, start_min), tzinfo=tzinfo)
    end_date = target_date
    end_dt = datetime.combine(end_date, datetime_time(end_hour, end_min), tzinfo=tzinfo)
    if end_dt <= start_dt:
        end_dt = datetime.combine(
            target_date + timedelta(days=1),
            datetime_time(end_hour, end_min),
            tzinfo=tzinfo,
        )

    return start_dt, end_dt


async def send_manual_scheduling_prompt(user_id: int, *, notice: Optional[str] = None) -> bool:
    """Prompt the candidate to reach out when no automatic slots are available.

    Returns ``True`` when a new prompt was sent and ``False`` when the candidate
    has already received the manual contact instructions earlier.
    """

    bot = get_bot()
    state_manager = get_state_manager()
    try:
        state = await state_manager.get(user_id)
    except Exception:
        state = None

    city_id: Optional[int] = None
    manual_prompt_sent = False
    if isinstance(state, dict):
        city_id = state.get("city_id")
        manual_prompt_sent = bool(state.get("manual_contact_prompt_sent"))

    if manual_prompt_sent:
        return False

    message = await _render_tpl(city_id, "manual_schedule_prompt")
    if not message:
        message = (
            "Свободных слотов в вашем городе сейчас нет.\n"
            "Напишите, пожалуйста, когда вам удобно, и мы постараемся выделить время.\n"
            "Чтобы ускорить назначение, укажите диапазон времени: например, 25.07 12:00-16:00 "
            "или завтра 10:00-13:00."
        )

    payload = message
    if notice:
        payload = f"{notice}\n\n{message}"

    await bot.send_message(
        user_id,
        payload,
        reply_markup=ForceReply(selective=True, input_field_placeholder="25.07 12:00-16:00"),
    )

    def _mark_prompt_sent(st: State) -> Tuple[State, None]:
        st["manual_contact_prompt_sent"] = True
        st["manual_availability_expected"] = True
        return st, None

    await state_manager.atomic_update(user_id, _mark_prompt_sent)

    return True


def _format_manual_window_label(
    start_dt: Optional[datetime],
    end_dt: Optional[datetime],
    tz_label: Optional[str],
) -> Optional[str]:
    if not start_dt or not end_dt:
        return None
    tzinfo = _safe_zone(tz_label or DEFAULT_TZ)
    start_local = start_dt.astimezone(tzinfo)
    end_local = end_dt.astimezone(tzinfo)
    if start_local.date() == end_local.date():
        date_part = start_local.strftime("%d.%m")
        return f"{date_part} {start_local.strftime('%H:%M')}–{end_local.strftime('%H:%M')}"
    return f"{start_local.strftime('%d.%m %H:%M')} – {end_local.strftime('%d.%m %H:%M')}"


async def record_manual_availability_response(user_id: int, text: str) -> bool:
    """Persist candidate-provided availability window from manual prompt."""
    payload = (text or "").strip()
    if not payload:
        return False

    state_manager = get_state_manager()
    try:
        state = await state_manager.get(user_id)
    except Exception:
        state = None
    if not isinstance(state, dict):
        state = {}

    tz_label = state.get("candidate_tz") or DEFAULT_TZ
    start_local, end_local = _parse_manual_availability_window(payload, tz_label)
    start_utc = start_local.astimezone(timezone.utc) if start_local else None
    end_utc = end_local.astimezone(timezone.utc) if end_local else None

    db_user = await candidate_services.save_manual_slot_response(
        telegram_id=user_id,
        window_start=start_utc,
        window_end=end_utc,
        note=payload[:1000],
        timezone_label=tz_label,
    )

    if db_user and db_user.candidate_status not in {
        CandidateStatus.WAITING_SLOT,
        CandidateStatus.STALLED_WAITING_SLOT,
    }:
        try:
            await set_status_waiting_slot(user_id)
        except Exception:
            logger.exception("Failed to mark candidate %s as waiting_slot", user_id)

    window_label = _format_manual_window_label(start_local, end_local, tz_label)
    safe_window = html.escape(window_label) if window_label else None
    safe_payload = html.escape(payload)
    if safe_window:
        ack = (
            f"✅ Спасибо! Зафиксировали диапазон <b>{safe_window}</b>.\n"
            "Рекрутёр свяжется, как только появится свободное окно."
        )
    else:
        ack = (
            "✅ Спасибо! Мы передали ваши пожелания рекрутёрам.\n"
            f"<code>{safe_payload}</code>"
        )

    bot = get_bot()
    await bot.send_message(user_id, ack)

    # Notify recruiters about updated availability so the reschedule/manual slot
    # flow doesn't get "stuck" waiting for someone to open the candidate profile.
    try:
        city_id: Optional[int] = state.get("city_id") if isinstance(state, dict) else None
        city_name = (state.get("city_name") if isinstance(state, dict) else None) or (db_user.city if db_user else None)
        candidate_name = (state.get("fio") if isinstance(state, dict) else None) or (db_user.fio if db_user else str(user_id))
        if city_id is None and db_user and db_user.city:
            try:
                city_record = await find_city_by_plain_name(db_user.city)
            except Exception:
                city_record = None
            if city_record is not None:
                city_id = city_record.id
                if not city_name:
                    city_name = city_record.name

        if city_id is not None:
            await notify_recruiters_manual_availability(
                candidate_tg_id=user_id,
                candidate_name=candidate_name,
                city_name=city_name or "—",
                city_id=int(city_id),
                availability_window=window_label,
                availability_note=payload,
                candidate_db_id=(db_user.id if db_user else None),
                responsible_recruiter_id=(db_user.responsible_recruiter_id if db_user else None),
            )
    except Exception:  # pragma: no cover - best-effort side effect
        logger.exception("Failed to notify recruiters about manual availability response")

    def _clear_prompt(st: State) -> Tuple[State, None]:
        st["manual_availability_expected"] = False
        st["manual_contact_prompt_sent"] = True
        st["manual_availability_last_note"] = payload
        return st, None

    await state_manager.atomic_update(user_id, _clear_prompt)
    return True

async def handle_pick_recruiter(callback: CallbackQuery) -> None:
    user_id = callback.from_user.id
    payload = verify_callback_data(callback.data, expected_prefix="pick_rec:")
    if not payload:
        await callback.answer("Невалидная ссылка. Откройте меню заново.", show_alert=True)
        logger.warning(
            "Invalid pick_rec callback signature",
            extra={"user_id": user_id, "callback_data": callback.data},
        )
        return
    rid_s = payload.split(":", 1)[1]

    state_manager = get_state_manager()
    state = await state_manager.get(user_id)

    if rid_s == "__again__":
        tz_label = (state or {}).get("candidate_tz", DEFAULT_TZ)
        kb = await kb_recruiters(tz_label, city_id=(state or {}).get("city_id"))
        text = await _render_tpl(state.get("city_id") if state else None, "choose_recruiter")
        if state is not None:
            def _clear_pick(st: State) -> Tuple[State, None]:
                st["picked_recruiter_id"] = None
                return st, None

            await state_manager.atomic_update(user_id, _clear_pick)
        try:
            await callback.message.edit_text(text, reply_markup=kb)
        except TelegramBadRequest:
            await callback.message.edit_text(text)
            await callback.message.edit_reply_markup(reply_markup=kb)
        await callback.answer()
        return

    try:
        rid = int(rid_s)
    except ValueError:
        await callback.answer("Некорректный рекрутёр", show_alert=True)
        return

    rec = await get_recruiter(rid)
    if not rec or not getattr(rec, "active", True):
        await callback.answer("Рекрутёр не найден/не активен", show_alert=True)
        return

    if not state:
        await callback.answer("Сессия истекла. Введите /start", show_alert=True)
        return

    city_id = state.get("city_id")
    if city_id:
        allowed = await get_active_recruiters_for_city(city_id)
        if rid not in {r.id for r in allowed}:
            await callback.answer("Этот рекрутёр не работает с вашим городом", show_alert=True)
            await show_recruiter_menu(user_id)
            return

    def _pick(st: State) -> Tuple[State, None]:
        st["picked_recruiter_id"] = rid
        return st, None

    await state_manager.atomic_update(user_id, _pick)
    tz_label = state.get("candidate_tz", DEFAULT_TZ)
    slots_list = await get_free_slots_by_recruiter(rid, city_id=city_id)
    kb = await kb_slots_for_recruiter(rid, tz_label, slots=slots_list, city_id=city_id)
    text = _recruiter_header(rec.name, tz_label)
    if not slots_list:
        text = f"{text}\n\n{await _render_tpl(state.get('city_id'), 'no_slots')}"
    try:
        await callback.message.edit_text(text, reply_markup=kb)
    except TelegramBadRequest:
        await callback.message.edit_text(text)
        await callback.message.edit_reply_markup(reply_markup=kb)
    await callback.answer()


async def handle_refresh_slots(callback: CallbackQuery) -> None:
    user_id = callback.from_user.id
    payload = verify_callback_data(callback.data, expected_prefix="refresh_slots:")
    if not payload:
        await callback.answer("Ссылка устарела, откройте список слотов заново.", show_alert=True)
        logger.warning(
            "Invalid refresh_slots callback signature",
            extra={"user_id": user_id, "callback_data": callback.data},
        )
        return
    _, rid_s = payload.split(":", 1)
    try:
        rid = int(rid_s)
    except ValueError:
        await callback.answer("Рекрутёр не найден", show_alert=True)
        return

    state = await get_state_manager().get(user_id)
    if not state:
        await callback.answer("Сессия истекла. Введите /start", show_alert=True)
        return

    tz_label = state.get("candidate_tz", DEFAULT_TZ)
    city_id = state.get("city_id")
    slots_list = await get_free_slots_by_recruiter(rid, city_id=city_id)
    kb = await kb_slots_for_recruiter(rid, tz_label, slots=slots_list, city_id=city_id)
    rec = await get_recruiter(rid)
    text = _recruiter_header(rec.name if rec else str(rid), tz_label)
    if not slots_list:
        text = f"{text}\n\n{await _render_tpl(state.get('city_id'), 'no_slots')}"
    try:
        await callback.message.edit_text(text, reply_markup=kb)
    except TelegramBadRequest:
        await callback.message.edit_text(text)
        await callback.message.edit_reply_markup(reply_markup=kb)
    await callback.answer("Обновлено")


async def handle_pick_slot(callback: CallbackQuery) -> None:
    user_id = callback.from_user.id
    payload = verify_callback_data(callback.data, expected_prefix="pick_slot:")
    if not payload:
        await callback.answer("Ссылка устарела. Выберите слот из меню.", show_alert=True)
        logger.warning(
            "Invalid pick_slot callback signature",
            extra={"user_id": user_id, "callback_data": callback.data},
        )
        return
    _, rid_s, slot_id_s = payload.split(":", 2)

    try:
        recruiter_id = int(rid_s)
    except ValueError:
        await callback.answer("Рекрутёр не найден", show_alert=True)
        return

    try:
        slot_id = int(slot_id_s)
    except ValueError:
        await callback.answer("Слот не найден", show_alert=True)
        return

    state_manager = get_state_manager()
    state = await state_manager.get(user_id)
    if not state:
        await callback.answer("Сессия истекла. Введите /start", show_alert=True)
        return

    # Update username if available (for existing users)
    username = getattr(callback.from_user, "username", None)
    if username and state.get("username") != username:
        def _update_username(st: State) -> Tuple[State, None]:
            st["username"] = username
            return st, None
        await state_manager.atomic_update(user_id, _update_username)
        state["username"] = username  # Update local state copy

    is_intro = state.get("flow") == "intro"
    city_id = state.get("city_id")
    candidate = await candidate_services.get_user_by_telegram_id(user_id)
    reservation = await reserve_slot(
        slot_id,
        candidate_tg_id=user_id,
        candidate_fio=state.get("fio", str(user_id)),
        candidate_tz=state.get("candidate_tz", DEFAULT_TZ),
        candidate_id=candidate.candidate_id if candidate else None,
        candidate_city_id=state.get("city_id"),
        candidate_username=state.get("username"),  # Pass username to reserve_slot
        purpose="intro_day" if is_intro else "interview",
        expected_recruiter_id=recruiter_id,
        expected_city_id=city_id,
        allow_candidate_replace=True,
    )

    if reservation.status == "slot_taken":
        text = await _render_tpl(state.get("city_id"), "slot_taken")
        if is_intro:
            try:
                await callback.message.edit_text(text)
                await callback.message.edit_reply_markup(reply_markup=None)
            except TelegramBadRequest:
                pass
            await show_recruiter_menu(user_id, notice=text)
        else:
            kb = await kb_slots_for_recruiter(
                recruiter_id,
                state.get("candidate_tz", DEFAULT_TZ),
                city_id=city_id,
            )
            try:
                await callback.message.edit_text(text, reply_markup=kb)
            except TelegramBadRequest:
                await callback.message.edit_text(text)
                await callback.message.edit_reply_markup(reply_markup=kb)

        await callback.answer("Слот уже занят.")
        return

    slot = reservation.slot
    if slot is None:
        await callback.answer("Ошибка бронирования.", show_alert=True)
        return

    if reservation.status in {"duplicate_candidate", "already_reserved"}:
        await _notify_existing_reservation(callback, slot)
        return

    rec = await get_recruiter(slot.recruiter_id)
    purpose = "ознакомительный день" if is_intro else "видео-интервью"
    bot = get_bot()
    caption = _format_recruiter_slot_caption(
        candidate_label=slot.candidate_fio or str(user_id),
        city_label=state.get("city_name", "—"),
        dt_label=fmt_dt_local(slot.start_utc, (rec.tz if rec else DEFAULT_TZ) or DEFAULT_TZ),
        purpose=purpose,
    )

    # Build CRM deep link for the approve keyboard
    _crm_url: Optional[str] = None
    try:
        _candidate_rec = await candidate_services.get_user_by_telegram_id(user_id)
        if _candidate_rec is not None:
            settings = get_settings()
            _crm_base = ((settings.crm_public_url or settings.bot_backend_url) or "").rstrip("/")
            if _crm_base:
                _crm_url = f"{_crm_base}/app/candidates/{_candidate_rec.id}"
    except Exception:
        logger.debug("Could not build CRM URL for kb_approve", exc_info=True)

    attached = False
    for path in [
        TEST1_DIR / f"test1_{state.get('fio') or user_id}.txt",
        REPORTS_DIR / f"report_{state.get('fio') or user_id}.txt",
    ]:
        if path.exists():
            try:
                if rec and rec.tg_chat_id:
                    await bot.send_document(
                        rec.tg_chat_id,
                        FSInputFile(str(path)),
                        caption=caption,
                        reply_markup=kb_approve(slot.id, crm_url=_crm_url),
                    )
                    attached = True

                    # Mark that test1 form has been shared to prevent duplicate sending
                    def _mark_test1_shared(st: State) -> Tuple[State, None]:
                        st["t1_notified"] = True
                        return st, None
                    await state_manager.atomic_update(user_id, _mark_test1_shared)
            except Exception:
                logger.warning(
                    "bot.send_document_failed",
                    extra={"recruiter_id": rec.id if rec else None, "slot_id": slot.id},
                    exc_info=True,
                )
            break

    if rec and rec.tg_chat_id and not attached:
        try:
            await bot.send_message(
                rec.tg_chat_id, caption, reply_markup=kb_approve(slot.id, crm_url=_crm_url)
            )
        except Exception:
            logger.warning(
                "bot.send_message_to_recruiter_failed",
                extra={"recruiter_id": rec.id if rec else None, "slot_id": slot.id},
                exc_info=True,
            )
    elif not rec or not rec.tg_chat_id:
        await bot.send_message(
            user_id,
            "ℹ️ Рекрутёр ещё не активировал DM с ботом (/iam_mih) или не указан tg_chat_id.\n"
            "Заявка создана, но уведомление не отправлено.",
        )

    await callback.message.edit_text(
        await _render_tpl(state.get("city_id"), "slot_sent")
    )
    try:
        city_name = state.get("city_name")
        slot_tz = getattr(slot, "tz_name", None)
        if not city_name and city_id:
            city_obj = await get_city(city_id)
            if city_obj is not None:
                city_name = getattr(city_obj, "name_plain", None) or getattr(city_obj, "name", "")
                slot_tz = slot_tz or getattr(city_obj, "tz", None)
        slot_tz = slot_tz or (rec.tz if rec and rec.tz else DEFAULT_TZ)
        candidate_tz = state.get("candidate_tz", DEFAULT_TZ)
        candidate_labels = slot_local_labels(slot.start_utc, candidate_tz)
        city_labels = slot_local_labels(slot.start_utc, slot_tz)
        candidate_time = candidate_labels.get("slot_time_local") or fmt_dt_local(slot.start_utc, candidate_tz)
        city_time = city_labels.get("slot_time_local") or fmt_dt_local(slot.start_utc, slot_tz)
        summary = f"Ваше время: {candidate_time}"
        if city_name:
            if city_time == candidate_time:
                summary += f" (по местному времени города {city_name})"
            else:
                summary += f" (по местному времени города {city_name} — {city_time})"
        else:
            if city_time == candidate_time:
                summary += f" (по часовому поясу {slot_tz})"
            else:
                summary += f" (по часовому поясу {slot_tz} — {city_time})"
        await bot.send_message(user_id, summary)
    except Exception:
        logger.exception("Failed to send slot time summary", exc_info=True)
    await callback.answer()

async def approve_slot_and_notify(slot_id: int, *, force_notify: bool = False) -> SlotApprovalResult:
    slot = await get_slot(slot_id)
    if not slot:
        return SlotApprovalResult(
            status="not_found",
            message="Заявка уже обработана или слот не найден.",
        )

    status_value = (slot.status or "").lower()
    already_booked = status_value in {SlotStatus.BOOKED, SlotStatus.CONFIRMED_BY_CANDIDATE}
    if already_booked and not force_notify:
        return SlotApprovalResult(
            status="already",
            message="Слот уже согласован.",
            slot=slot,
        )
    if already_booked and slot.candidate_tg_id is not None:
        try:
            await set_status_interview_scheduled(slot.candidate_tg_id)
        except Exception:
            logger.exception(
                "Failed to sync candidate status for booked slot",
                extra={"slot_id": slot.id, "candidate_tg_id": slot.candidate_tg_id},
            )
    if status_value == SlotStatus.FREE:
        return SlotApprovalResult(
            status="slot_free",
            message="Слот уже освобождён.",
            slot=slot,
        )
    if slot.candidate_tg_id is None:
        return SlotApprovalResult(
            status="missing_candidate",
            message="Слот не привязан к кандидату.",
            slot=slot,
        )

    if not already_booked:
        slot = await approve_slot(slot_id)
        if not slot:
            return SlotApprovalResult(
                status="error",
                message="Не удалось согласовать слот.",
            )

    if slot.candidate_tg_id is not None:
        try:
            await clear_candidate_chat_state(slot.candidate_tg_id)
        except Exception:
            logger.exception(
                "Failed to clear candidate chat state after approval",
                extra={"slot_id": slot.id, "candidate_tg_id": slot.candidate_tg_id},
            )

    candidate_label = (
        slot.candidate_fio
        or (str(slot.candidate_tg_id) if slot.candidate_tg_id is not None else "—")
    )
    message_text, candidate_tz, candidate_city, template_key, template_version = await _render_candidate_notification(
        slot
    )

    try:
        reminder_service = get_reminder_service()
    except RuntimeError:
        reminder_service = None

    already_sent = await notification_log_exists(
        "candidate_interview_confirmed",
        slot.id,
        candidate_tg_id=slot.candidate_tg_id,
    )
    if not already_sent:
        already_sent = await notification_log_exists(
            "interview_confirmed_candidate",
            slot.id,
            candidate_tg_id=slot.candidate_tg_id,
        )

    should_notify = force_notify or (not already_sent)

    if should_notify:
        notify_status: Optional[str] = None
        notify_note: Optional[str] = None
        try:
            notification_service = get_notification_service()
        except RuntimeError:
            notification_service = None

        if notification_service is not None:
            try:
                snapshot = await capture_slot_snapshot(slot)
                notify_result = await notification_service.on_booking_status_changed(
                    slot.id,
                    BookingNotificationStatus.APPROVED,
                    snapshot=snapshot,
                )
            except Exception:
                logger.exception("Failed to enqueue approval notification")
                notify_result = None
            if notify_result and notify_result.status in {"queued", "sent"}:
                notify_status = "sent"
                notify_note = "queued" if notify_result.status == "queued" else "sent"
            else:
                notify_status = "failed"
        else:
            bot = None
            try:
                bot = get_bot()
            except RuntimeError:
                logger.warning("Bot is not configured; cannot send approval notification.")

            if bot is None:
                failure_parts = [
                    "⚠️ Слот подтверждён, но бот недоступен и отправить сообщение кандидату невозможно.",
                    f"👤 {html.escape(candidate_label)}",
                    f"🕒 {fmt_dt_local(slot.start_utc, candidate_tz)} ({candidate_tz})",
                ]
                if candidate_city:
                    failure_parts.append(f"📍 {html.escape(candidate_city)}")
                failure_parts.extend(
                    [
                        "",
                        "<b>Текст сообщения:</b>",
                        f"<blockquote>{message_text}</blockquote>",
                        "Свяжитесь с кандидатом вручную и передайте детали встречи.",
                    ]
                )
                return SlotApprovalResult(
                    status="notify_failed",
                    message="Слот подтверждён, но бот недоступен. Свяжитесь с кандидатом вручную.",
                    slot=slot,
                    summary_html="\n".join(failure_parts),
                )

            try:
                await _send_with_retry(
                    bot,
                    SendMessage(chat_id=slot.candidate_tg_id, text=message_text),
                    correlation_id=f"approve:{slot.id}:{uuid.uuid4().hex}",
                )
                notify_status = "sent"
            except Exception:
                logger.exception("Failed to send approval message to candidate")
                notify_status = "failed"

            if notify_status == "sent":
                logged = await add_notification_log(
                    "candidate_interview_confirmed",
                    slot.id,
                    candidate_tg_id=slot.candidate_tg_id,
                    payload=message_text,
                    template_key=template_key,
                    template_version=template_version,
                    overwrite=force_notify,
                )
                if not logged:
                    logger.warning("Notification log already exists for slot %s", slot.id)

                await mark_outbox_notification_sent(
                    "interview_confirmed_candidate",
                    slot.id,
                    candidate_tg_id=slot.candidate_tg_id,
                )

                if reminder_service is not None:
                    await reminder_service.schedule_for_slot(slot.id)

        if notify_status != "sent":
            failure_parts = [
                "⚠️ Слот подтверждён, но отправить сообщение кандидату не удалось.",
                f"👤 {html.escape(candidate_label)}",
                f"🕒 {fmt_dt_local(slot.start_utc, candidate_tz)} ({candidate_tz})",
            ]
            if candidate_city:
                failure_parts.append(f"📍 {html.escape(candidate_city)}")
            failure_parts.extend(
                [
                    "",
                    "<b>Текст сообщения:</b>",
                    f"<blockquote>{message_text}</blockquote>",
                    "Свяжитесь с кандидатом вручную.",
                ]
            )
            return SlotApprovalResult(
                status="notify_failed",
                message="Слот подтверждён, но отправить сообщение кандидату не удалось. Свяжитесь вручную.",
                slot=slot,
                summary_html="\n".join(failure_parts),
            )

        summary_head = (
            "✅ Слот подтверждён. Сообщение поставлено в очередь на отправку."
            if notify_note == "queued"
            else "✅ Слот подтверждён. Сообщение отправлено кандидату автоматически."
        )
        summary_parts = [
            summary_head,
            f"👤 {html.escape(candidate_label)}",
            f"🕒 {fmt_dt_local(slot.start_utc, candidate_tz)} ({candidate_tz})",
        ]
        if candidate_city:
            summary_parts.append(f"📍 {html.escape(candidate_city)}")
        summary_parts.extend(
            [
                "",
                "<b>Текст сообщения:</b>",
                f"<blockquote>{message_text}</blockquote>",
            ]
        )
    else:
        summary_parts = [
            "ℹ️ Слот уже был подтверждён ранее — повторная отправка сообщения не выполнялась.",
            f"👤 {html.escape(candidate_label)}",
            f"🕒 {fmt_dt_local(slot.start_utc, candidate_tz)} ({candidate_tz})",
        ]
        if candidate_city:
            summary_parts.append(f"📍 {html.escape(candidate_city)}")

    return SlotApprovalResult(
        status="approved" if should_notify else "already",
        message="Интервью согласовано, кандидат уведомлён." if should_notify else "Слот уже был согласован ранее.",
        slot=slot,
        summary_html="\n".join(summary_parts),
    )


async def handle_approve_slot(callback: CallbackQuery) -> None:
    slot_id = int(callback.data.split(":", 1)[1])
    result = await approve_slot_and_notify(slot_id)

    if result.status == "not_found":
        await callback.answer("Заявка уже обработана.", show_alert=True)
        await safe_remove_reply_markup(callback.message)
        return

    if result.status == "slot_free":
        await callback.answer("Слот уже освобождён.", show_alert=True)
        await safe_remove_reply_markup(callback.message)
        return

    if result.status == "missing_candidate":
        await callback.answer("Кандидат не найден.", show_alert=True)
        await safe_remove_reply_markup(callback.message)
        return

    if result.status == "error":
        await callback.answer("Не удалось согласовать.", show_alert=True)
        return

    if result.status == "notify_failed":
        await safe_edit_text_or_caption(
            callback.message,
            result.summary_html or result.message,
        )
        await safe_remove_reply_markup(callback.message)
        await callback.answer("Не удалось отправить сообщение кандидату.", show_alert=True)
        return

    if result.status == "approved":
        await safe_edit_text_or_caption(
            callback.message,
            result.summary_html or result.message,
        )
        await safe_remove_reply_markup(callback.message)
        await callback.answer("Сообщение отправлено кандидату.")
        return

    await callback.answer("Уже согласовано ✔️")
    await safe_remove_reply_markup(callback.message)
    return


if not hasattr(builtins, "handle_approve_slot"):
    builtins.handle_approve_slot = handle_approve_slot


async def handle_send_slot_message(callback: CallbackQuery) -> None:
    slot_id = int(callback.data.split(":", 1)[1])
    slot = await get_slot(slot_id)
    if not slot:
        await callback.answer("Заявка уже обработана.", show_alert=True)
        await safe_remove_reply_markup(callback.message)
        return

    if slot.candidate_tg_id is None:
        await callback.answer("Кандидат не найден.", show_alert=True)
        await safe_remove_reply_markup(callback.message)
        return

    status_value = (slot.status or "").lower()
    if status_value not in {SlotStatus.BOOKED, SlotStatus.CONFIRMED_BY_CANDIDATE}:
        await callback.answer("Слот ещё не подтверждён.", show_alert=True)
        await safe_remove_reply_markup(callback.message)
        return

    message_text, candidate_tz, candidate_city, _, _ = await _render_candidate_notification(slot)
    bot = get_bot()
    try:
        await bot.send_message(slot.candidate_tg_id, message_text)
    except Exception:
        logger.exception("Failed to send approval message to candidate")
        await callback.answer("Не удалось отправить сообщение кандидату.", show_alert=True)
        return

    try:
        reminder_service = get_reminder_service()
    except RuntimeError:
        reminder_service = None
    if reminder_service is not None:
        await reminder_service.schedule_for_slot(slot.id)

    candidate_label = (
        slot.candidate_fio
        or (str(slot.candidate_tg_id) if slot.candidate_tg_id is not None else "—")
    )
    summary_parts = [
        "✅ Сообщение отправлено кандидату.",
        f"👤 {html.escape(candidate_label)}",
        f"🕒 {fmt_dt_local(slot.start_utc, candidate_tz)} ({candidate_tz})",
    ]
    if candidate_city:
        summary_parts.append(f"📍 {html.escape(candidate_city)}")
    summary_parts.extend(
        [
            "",
            "<b>Текст сообщения:</b>",
            f"<blockquote>{message_text}</blockquote>",
        ]
    )
    summary_text = "\n".join(summary_parts)

    await safe_edit_text_or_caption(callback.message, summary_text)
    await safe_remove_reply_markup(callback.message)
    await callback.answer("Сообщение отправлено.")


async def handle_reject_slot(callback: CallbackQuery) -> None:
    slot_id = int(callback.data.split(":", 1)[1])
    slot = await get_slot(slot_id)
    if not slot:
        await callback.answer("Заявка уже обработана.")
        await safe_remove_reply_markup(callback.message)
        return

    status_value = (slot.status or "").lower()
    if status_value == SlotStatus.FREE or slot.candidate_tg_id is None:
        await callback.answer("Слот уже освобождён.", show_alert=True)
        await safe_remove_reply_markup(callback.message)
        return

    snapshot = await _build_slot_snapshot(slot)
    await reject_slot(slot_id)
    await _cancel_reminders_for_slot(slot_id)

    sent = await _send_final_rejection_notice(snapshot)
    status_text = (
        "⛔️ Отказано. Кандидат уведомлён."
        if sent
        else "⛔️ Отказано. Сообщите кандидату вручную — бот недоступен."
    )

    await safe_edit_text_or_caption(callback.message, status_text)
    await safe_remove_reply_markup(callback.message)
    await callback.answer(
        "Отказано" if sent else "Бот недоступен — свяжитесь с кандидатом.",
        show_alert=not sent,
    )


async def handle_reschedule_slot(callback: CallbackQuery) -> None:
    slot_id = int(callback.data.split(":", 1)[1])
    slot = await get_slot(slot_id)
    if not slot:
        await callback.answer("Заявка уже обработана.")
        await safe_remove_reply_markup(callback.message)
        return

    if slot.candidate_tg_id is None:
        await callback.answer("Кандидат не найден.", show_alert=True)
        await safe_remove_reply_markup(callback.message)
        return

    snapshot = await _build_slot_snapshot(slot)
    await reject_slot(slot_id)
    await _cancel_reminders_for_slot(slot_id)

    sent = await _send_reschedule_prompt(snapshot)
    status_text = (
        "🔁 Перенос: кандидат подберёт новое время."
        if sent
        else "🔁 Слот освобождён. Бот недоступен — свяжитесь с кандидатом."
    )

    await safe_edit_text_or_caption(callback.message, status_text)
    await safe_remove_reply_markup(callback.message)
    await callback.answer(
        "Перенос оформлен." if sent else "Слот освобождён, бот недоступен.",
        show_alert=not sent,
    )


async def handle_attendance_yes(callback: CallbackQuery) -> None:
    slot_id = int(callback.data.split(":", 1)[1])

    if not await register_callback(callback.id):
        await callback.answer("Уже подтверждено")
        await safe_remove_reply_markup(callback.message)
        return

    result = await confirm_slot_by_candidate(slot_id)
    slot = result.slot
    if slot is None:
        await callback.answer(
            "Заявка не найдена или ещё не подтверждена рекрутёром.",
            show_alert=True,
        )
        await safe_remove_reply_markup(callback.message)
        return

    if result.status == "invalid_status":
        await callback.answer(
            "Заявка не найдена или ещё не подтверждена рекрутёром.",
            show_alert=True,
        )
        return

    rec = await get_recruiter(slot.recruiter_id)
    link = (
        rec.telemost_url if rec and rec.telemost_url else "https://telemost.yandex.ru/j/REPLACE_ME"
    )
    tz = _slot_timezone(slot, rec.tz if rec else None)
    dt_local = fmt_dt_local(slot.start_utc, tz)
    city_id = getattr(slot, "candidate_city_id", None)
    labels = slot_local_labels(slot.start_utc, tz)
    link_text = await _render_tpl(
        city_id,
        "att_confirmed_link",
        link=link,
        dt=dt_local,
        **labels,
    )
    bot = get_bot()

    if result.status == "confirmed":
        try:
            if getattr(slot, "purpose", "interview") != "intro_day":
                await _send_with_retry(
                    bot,
                    SendMessage(chat_id=slot.candidate_tg_id, text=link_text),
                    correlation_id=f"attendance:{slot.id}:{uuid.uuid4().hex}",
                )
        except Exception:
            logger.exception("Failed to send attendance confirmation to candidate")
            await callback.answer("Не удалось отправить ссылку.", show_alert=True)
            return

        try:
            reminder_service = get_reminder_service()
        except RuntimeError:
            reminder_service = None
        if reminder_service is not None:
            await reminder_service.cancel_for_slot(slot_id)
            await reminder_service.schedule_for_slot(
                slot_id, skip_confirmation_prompts=True
            )

        # Update candidate status for intro day confirmations
        if slot.candidate_tg_id and getattr(slot, "purpose", "interview") == "intro_day":
            try:
                from backend.domain.candidates.status_service import (
                    set_status_intro_day_confirmed_preliminary,
                    set_status_intro_day_confirmed_day_of,
                )

                if _is_slot_confirmation_on_local_day(
                    slot,
                    recruiter_tz=rec.tz if rec else None,
                ):
                    await set_status_intro_day_confirmed_day_of(slot.candidate_tg_id, force=True)
                else:
                    await set_status_intro_day_confirmed_preliminary(slot.candidate_tg_id, force=True)
            except Exception:
                logger.exception("Failed to update intro day confirmation status for candidate %s", slot.candidate_tg_id)

        is_intro_day = getattr(slot, "purpose", "interview") == "intro_day"
        ack_text = await _render_tpl(
            city_id,
            "att_confirmed_ack",
            dt=dt_local,
            **labels,
        )
        if ack_text:
            try:
                if is_intro_day:
                    await bot.send_message(slot.candidate_tg_id, ack_text)
                else:
                    await callback.message.edit_text(ack_text)
            except TelegramBadRequest:
                pass
        await safe_remove_reply_markup(callback.message)
        await callback.answer("Подтверждено")
        return

    await safe_remove_reply_markup(callback.message)
    await callback.answer("Уже подтверждено")


async def handle_attendance_no(callback: CallbackQuery) -> None:
    slot_id = int(callback.data.split(":", 1)[1])
    slot = await get_slot(slot_id)
    if not slot:
        await callback.answer("Заявка уже обработана.")
        await safe_remove_reply_markup(callback.message)
        return

    await reject_slot(slot_id)

    try:
        reminder_service = get_reminder_service()
    except RuntimeError:
        reminder_service = None
    if reminder_service is not None:
        await reminder_service.cancel_for_slot(slot_id)

    rec = await get_recruiter(slot.recruiter_id)
    bot = get_bot()
    if rec and rec.tg_chat_id:
        try:
            candidate_label = escape_html(slot.candidate_fio or str(slot.candidate_tg_id or ""))
            await bot.send_message(
                rec.tg_chat_id,
                f"❌ Кандидат {candidate_label} отказался от слота "
                f"{fmt_dt_local(slot.start_utc, rec.tz or DEFAULT_TZ)}. Слот освобождён.",
            )
        except Exception:
            logger.warning(
                "bot.slot_rejection_notify_failed",
                extra={"recruiter_id": rec.id, "slot_id": slot.id},
                exc_info=True,
            )

    st = await get_state_manager().get(callback.from_user.id) or {}
    prompt = await _render_tpl(
        getattr(slot, "candidate_city_id", None),
        "att_declined_reason_prompt",
    )
    if not prompt:
        prompt = (
            "Понимаю. Напишите, пожалуйста, коротко причину отказа, "
            "чтобы мы могли предложить другой день."
        )
    reason_state = {
        "slot_id": slot.id,
        "city_id": getattr(slot, "candidate_city_id", None),
        "recruiter_id": slot.recruiter_id,
        "start_local": fmt_dt_local(slot.start_utc, slot.candidate_tz or DEFAULT_TZ),
        "candidate_fio": slot.candidate_fio or "",
    }
    try:
        state_manager = get_state_manager()
        await state_manager.update(callback.from_user.id, {"awaiting_intro_decline_reason": reason_state})
    except Exception:
        logger.exception("Failed to set intro decline reason state", extra={"candidate": callback.from_user.id})
    await bot.send_message(
        callback.from_user.id,
        prompt,
        reply_markup=ForceReply(selective=True),
    )

    try:
        await callback.message.edit_text("Вы отказались от участия. Слот освобождён.")
    except TelegramBadRequest:
        pass
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except TelegramBadRequest:
        pass

    await callback.answer("Отменено")


async def capture_intro_decline_reason(message, state) -> bool:
    """Handle free-text reason when candidate declines intro day."""
    reason_payload = state.get("awaiting_intro_decline_reason") or {}
    slot_id = reason_payload.get("slot_id")
    if not slot_id:
        return False

    text = (message.text or message.caption or "").strip()
    if not text:
        await message.answer("Напишите, пожалуйста, коротко причину отказа.")
        return True

    # Persist reason on the candidate profile for analytics
    try:
        from backend.core.db import async_session
        from backend.domain.candidates.models import User
        async with async_session() as session:
            user = await session.scalar(select(User).where(User.telegram_id == message.from_user.id))
            if user:
                user.intro_decline_reason = text
                await session.commit()
    except Exception:
        logger.exception("Failed to save intro decline reason", extra={"candidate": message.from_user.id})

    slot = await get_slot(slot_id)
    bot = get_bot()
    recruiter_note_sent = False
    try:
        if slot and slot.recruiter_id:
            recruiter = await get_recruiter(slot.recruiter_id)
        else:
            recruiter = None
        if recruiter and recruiter.tg_chat_id:
            dt_label = reason_payload.get("start_local") or (
                fmt_dt_local(slot.start_utc, recruiter.tz or DEFAULT_TZ) if slot else ""
            )
            candidate_label = reason_payload.get("candidate_fio") or getattr(slot, "candidate_fio", "") or str(message.from_user.id)
            reason_text = (
                "❌ Кандидат отказался от ознакомительного дня.\n"
                f"👤 {escape_html(candidate_label)}\n"
                f"🗓 {dt_label}\n"
                f"Причина: {escape_html(text)}"
            )
            try:
                await bot.send_message(recruiter.tg_chat_id, reason_text)
                recruiter_note_sent = True
            except Exception:
                logger.exception("Failed to send intro decline reason to recruiter", extra={"slot_id": slot_id})
    except Exception:
        logger.exception("Failed to resolve recruiter for intro decline reason", extra={"slot_id": slot_id})

    ack = "Спасибо, передали информацию рекрутеру."
    if not recruiter_note_sent:
        ack = "Спасибо, получили ответ."
    await message.answer(ack)

    try:
        state_manager = get_state_manager()
        def _clear(st: State) -> Tuple[State, None]:
            st = dict(st or {})
            st.pop("awaiting_intro_decline_reason", None)
            return st, None
        await state_manager.atomic_update(message.from_user.id, _clear)
    except Exception:
        logger.exception("Failed to clear intro decline reason state", extra={"candidate": message.from_user.id})

    return True

__all__ = [
    'BookingNotificationStatus',
    'SlotApprovalResult',
    'SlotSnapshot',
    'approve_slot_and_notify',
    'cancel_slot_reminders',
    'capture_intro_decline_reason',
    'capture_slot_snapshot',
    'handle_approve_slot',
    'handle_attendance_no',
    'handle_attendance_yes',
    'handle_pick_recruiter',
    'handle_pick_slot',
    'handle_refresh_slots',
    'handle_reject_slot',
    'handle_reschedule_slot',
    'handle_send_slot_message',
    'notify_rejection',
    'notify_reschedule',
    'record_manual_availability_response',
    'send_manual_scheduling_prompt',
]
