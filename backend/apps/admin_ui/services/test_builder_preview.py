from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from backend.apps.admin_ui.services.builder_graph import validate_test_builder_graph
from backend.apps.bot.defaults import DEFAULT_TEMPLATES
from backend.apps.bot.test1_validation import apply_partial_validation, convert_age
from backend.core.db import async_session
from backend.domain.tests.models import AnswerOption, Question, Test


@dataclass(frozen=True)
class _NodeInfo:
    id: str
    type: str
    question_id: int | None
    data: dict[str, Any]


@dataclass(frozen=True)
class _EdgeRule:
    id: str
    source: str
    target: str
    when_values: tuple[str, ...]
    match: str
    fallback: bool
    action: str
    reason: str | None
    template_key: str | None
    label: str | None
    priority: int
    order: int


def _sorted_options(options: list[AnswerOption]) -> list[AnswerOption]:
    return sorted(
        options,
        key=lambda opt: (int(getattr(opt, "sort_order", 0)), int(getattr(opt, "id", 0))),
    )


def _question_to_payload(question: Question) -> dict[str, Any]:
    payload = dict(getattr(question, "payload", None) or {})
    key = str(getattr(question, "key", None) or payload.get("id") or f"q_{question.id}").strip()
    prompt = str(getattr(question, "text", "") or payload.get("prompt") or payload.get("text") or "")

    options: list[str] = []
    raw_options = list(getattr(question, "answer_options", []) or [])
    if raw_options:
        options = [str(opt.text or "") for opt in _sorted_options(raw_options)]
    else:
        payload_options = payload.get("options")
        if isinstance(payload_options, list):
            options = [str(item) for item in payload_options if item is not None]

    return {
        "question_id": int(question.id),
        "key": key,
        "prompt": prompt,
        "kind": "choice" if options else "text",
        "options": options,
        "placeholder": payload.get("placeholder"),
        "helper": payload.get("helper"),
        "is_active": bool(getattr(question, "is_active", True)),
    }


def _virtual_question_to_payload(node: _NodeInfo) -> dict[str, Any]:
    data = node.data
    raw_options = data.get("options")
    options = [str(item) for item in raw_options] if isinstance(raw_options, list) else []

    key = str(data.get("key") or data.get("id") or node.id).strip() or node.id
    prompt = str(data.get("prompt") or data.get("text") or data.get("title") or key).strip()
    return {
        "question_id": None,
        "key": key,
        "prompt": prompt,
        "kind": "choice" if options else "text",
        "options": options,
        "placeholder": data.get("placeholder"),
        "helper": data.get("helper"),
        "is_active": bool(data.get("is_active", True)),
    }


def _template_text(key: str | None) -> str:
    if not key:
        return ""
    return str(DEFAULT_TEMPLATES.get(key) or "").strip()


def _validation_feedback(qid: str, exc: ValidationError) -> tuple[str, list[str]]:
    hints: list[str] = []
    if qid == "fio":
        return (
            "Укажите полные фамилию, имя и отчество кириллицей.",
            ["Иванов Иван Иванович", "Петрова Мария Сергеевна"],
        )
    if qid == "age":
        return (
            "Возраст должен быть от 18 до 60 лет. Укажите возраст цифрами.",
            ["Например: 23"],
        )
    if qid in {"status", "format"}:
        return ("Выберите один из вариантов в списке.", hints)

    errors = exc.errors()
    if errors:
        return (str(errors[0].get("msg") or "Проверьте ответ."), hints)
    return ("Проверьте ответ.", hints)


def _parse_graph_runtime(
    graph: dict[str, Any],
) -> tuple[
    bool,
    dict[str, _NodeInfo],
    dict[str, list[_EdgeRule]],
    str | None,
    str | None,
    str | None,
]:
    if not isinstance(graph, dict):
        return False, {}, {}, None, None, "invalid_graph"

    nodes_raw = graph.get("nodes")
    edges_raw = graph.get("edges")
    if not isinstance(nodes_raw, list) or not isinstance(edges_raw, list):
        return False, {}, {}, None, None, "invalid_graph"

    nodes: dict[str, _NodeInfo] = {}
    start_id: str | None = None
    end_id: str | None = None

    for item in nodes_raw:
        if not isinstance(item, dict):
            continue
        node_id = str(item.get("id") or "").strip()
        node_type = str(item.get("type") or "").strip()
        data = item.get("data") if isinstance(item.get("data"), dict) else {}

        if not node_id or node_type not in {"start", "question", "end"}:
            continue

        question_id: int | None = None
        if node_type == "question":
            raw_qid = data.get("question_id")
            if raw_qid not in (None, ""):
                try:
                    question_id = int(raw_qid)
                except (TypeError, ValueError):
                    return False, {}, {}, None, None, "invalid_graph"

        if node_id in nodes:
            return False, {}, {}, None, None, "invalid_graph"
        nodes[node_id] = _NodeInfo(
            id=node_id,
            type=node_type,
            question_id=question_id,
            data=dict(data),
        )

        if node_type == "start":
            if start_id is not None:
                return False, {}, {}, None, None, "invalid_graph"
            start_id = node_id
        elif node_type == "end":
            if end_id is not None:
                return False, {}, {}, None, None, "invalid_graph"
            end_id = node_id

    if start_id is None or end_id is None:
        return False, {}, {}, None, None, "invalid_graph"

    outgoing: dict[str, list[_EdgeRule]] = {node_id: [] for node_id in nodes.keys()}

    for idx, item in enumerate(edges_raw):
        if not isinstance(item, dict):
            continue
        source = str(item.get("source") or "").strip()
        target = str(item.get("target") or "").strip()
        if source not in nodes or target not in nodes:
            return False, {}, {}, None, None, "invalid_graph"

        data = item.get("data") if isinstance(item.get("data"), dict) else {}
        when_raw = data.get("when")
        when_values: list[str] = []
        if isinstance(when_raw, str):
            value = when_raw.strip()
            if value:
                when_values = [value]
        elif isinstance(when_raw, list):
            when_values = [str(v).strip() for v in when_raw if str(v).strip()]

        match = str(data.get("match") or ("equals" if when_values else "always")).strip().lower()
        if match not in {"equals", "contains", "always"}:
            match = "equals" if when_values else "always"

        fallback = bool(data.get("fallback"))
        action = str(data.get("action") or "next").strip().lower()
        if action not in {"next", "reject"}:
            action = "next"

        priority = 0
        try:
            priority = int(data.get("priority") or 0)
        except (TypeError, ValueError):
            priority = 0

        reason_raw = str(data.get("reason") or "").strip()
        template_key_raw = str(data.get("template_key") or "").strip()
        label_raw = str(data.get("label") or "").strip()

        rule = _EdgeRule(
            id=str(item.get("id") or f"e_{source}_{target}_{idx}"),
            source=source,
            target=target,
            when_values=tuple(when_values),
            match=match,
            fallback=fallback,
            action=action,
            reason=reason_raw or None,
            template_key=template_key_raw or None,
            label=label_raw or None,
            priority=priority,
            order=idx,
        )
        outgoing[source].append(rule)

    return True, nodes, outgoing, start_id, end_id, None


async def _load_db_questions(
    *,
    test_id: str,
    question_ids: set[int],
) -> tuple[bool, dict[int, dict[str, Any]], str | None]:
    async with async_session() as session:
        test = await session.scalar(select(Test).where(Test.slug == test_id))
        if test is None:
            return False, {}, "test_not_found"

        if not question_ids:
            return True, {}, None

        rows = (
            await session.scalars(
                select(Question)
                .where(Question.test_id == test.id, Question.id.in_(question_ids))
                .options(selectinload(Question.answer_options))
                .order_by(Question.order.asc())
            )
        ).all()

    if len(rows) != len(question_ids):
        return False, {}, "order_mismatch"

    payloads: dict[int, dict[str, Any]] = {}
    for question in rows:
        payloads[int(question.id)] = _question_to_payload(question)
    return True, payloads, None


def _edge_matches(rule: _EdgeRule, answer: str) -> bool:
    if rule.match == "always":
        return True
    if not rule.when_values:
        return False

    candidate = answer.strip().lower()
    values = [val.strip().lower() for val in rule.when_values]

    if rule.match == "contains":
        return any(val in candidate for val in values)
    return candidate in values


def _pick_edge(rules: list[_EdgeRule], answer: str) -> _EdgeRule | None:
    if not rules:
        return None

    matched = [rule for rule in rules if rule.when_values and _edge_matches(rule, answer)]
    if matched:
        matched.sort(key=lambda rule: (-rule.priority, rule.order))
        return matched[0]

    fallbacks = [
        rule
        for rule in rules
        if rule.fallback or rule.match == "always" or not rule.when_values
    ]
    if fallbacks:
        fallbacks.sort(key=lambda rule: (-rule.priority, rule.order))
        return fallbacks[0]

    if len(rules) == 1:
        return rules[0]
    return None


def _question_payload_for_node(
    *,
    node: _NodeInfo,
    db_payloads: dict[int, dict[str, Any]],
) -> dict[str, Any] | None:
    if node.type != "question":
        return None
    if node.question_id is not None:
        return db_payloads.get(int(node.question_id))
    return _virtual_question_to_payload(node)


async def preview_test_builder_graph(
    *,
    test_id: str,
    graph: dict[str, Any],
    answers: list[str],
) -> tuple[bool, dict[str, Any], str | None]:
    clean_test_id = str(test_id or "").strip()
    if not clean_test_id:
        return False, {}, "test_required"

    graph_ok, graph_error = validate_test_builder_graph(graph)
    if not graph_ok:
        return False, {}, graph_error or "invalid_graph"

    ok, nodes, outgoing, start_id, end_id, parse_error = _parse_graph_runtime(graph)
    if not ok or start_id is None or end_id is None:
        return False, {}, parse_error or "invalid_graph"

    db_question_ids = {
        int(node.question_id)
        for node in nodes.values()
        if node.type == "question" and node.question_id is not None
    }
    loaded, db_payloads, load_error = await _load_db_questions(
        test_id=clean_test_id,
        question_ids=db_question_ids,
    )
    if not loaded:
        return False, {}, load_error

    question_by_node_id: dict[str, dict[str, Any]] = {}
    for node in nodes.values():
        if node.type != "question":
            continue
        payload = _question_payload_for_node(node=node, db_payloads=db_payloads)
        if payload is None:
            return False, {}, "order_mismatch"
        question_by_node_id[node.id] = payload

    start_rule = _pick_edge(outgoing.get(start_id, []), "")
    if start_rule is None:
        return False, {}, "invalid_graph"

    steps: list[dict[str, Any]] = []
    payload_data: dict[str, Any] = {}

    halted = False
    halt_reason: str | None = None
    done = False

    current_node_id: str | None
    if start_rule.action == "reject":
        halted = True
        halt_reason = "reject"
        current_node_id = None
    elif start_rule.target == end_id:
        done = True
        current_node_id = None
    else:
        current_node_id = start_rule.target

    normalized_answers = [str(item or "") for item in (answers or [])]

    for raw_answer in normalized_answers:
        if current_node_id is None:
            break

        question = question_by_node_id.get(current_node_id)
        if question is None:
            return False, {}, "invalid_graph"

        answer = raw_answer.strip()
        if not answer:
            steps.append(
                {
                    "question": question,
                    "answer": answer,
                    "status": "invalid",
                    "reaction": {
                        "message": "Введите ответ, чтобы продолжить.",
                        "hints": [],
                    },
                    "inserted_followups": [],
                }
            )
            halted = True
            halt_reason = "invalid"
            break

        options = question.get("options") or []
        if options and answer not in options:
            steps.append(
                {
                    "question": question,
                    "answer": answer,
                    "status": "invalid",
                    "reaction": {
                        "message": "Выберите один из вариантов в списке.",
                        "hints": [str(opt) for opt in options],
                    },
                    "inserted_followups": [],
                }
            )
            halted = True
            halt_reason = "invalid"
            break

        qid = str(question.get("key") or "")
        local_payload = dict(payload_data)
        if qid == "fio":
            local_payload["fio"] = answer
        elif qid == "city":
            local_payload["city_name"] = answer
        elif qid == "age":
            try:
                local_payload["age"] = convert_age(answer)
            except ValueError as exc:
                steps.append(
                    {
                        "question": question,
                        "answer": answer,
                        "status": "invalid",
                        "reaction": {
                            "message": str(exc),
                            "hints": ["Например: 23", "Возраст указываем цифрами"],
                        },
                        "inserted_followups": [],
                    }
                )
                halted = True
                halt_reason = "invalid"
                break
        elif qid == "status":
            local_payload["status"] = answer
        elif qid == "format":
            local_payload["format_choice"] = answer
        elif qid == "study_mode":
            local_payload["study_mode"] = answer
        elif qid == "study_schedule":
            local_payload["study_schedule"] = answer
        elif qid == "study_flex":
            local_payload["study_flex"] = answer

        try:
            validated = apply_partial_validation(local_payload)
            payload_data = validated.model_dump(exclude_none=True)
        except ValidationError as exc:
            message, hints = _validation_feedback(qid, exc)
            steps.append(
                {
                    "question": question,
                    "answer": answer,
                    "status": "invalid",
                    "reaction": {
                        "message": message,
                        "hints": hints,
                    },
                    "inserted_followups": [],
                }
            )
            halted = True
            halt_reason = "invalid"
            break

        rule = _pick_edge(outgoing.get(current_node_id, []), answer)
        if rule is None:
            steps.append(
                {
                    "question": question,
                    "answer": answer,
                    "status": "invalid",
                    "reaction": {
                        "message": "Для этого ответа не настроена ветка в графе.",
                        "hints": ["Добавьте fallback-ветку (else) или условие для этого варианта."],
                    },
                    "inserted_followups": [],
                }
            )
            halted = True
            halt_reason = "invalid"
            break

        if rule.action == "reject":
            steps.append(
                {
                    "question": question,
                    "answer": answer,
                    "status": "reject",
                    "reaction": {
                        "message": rule.reason or "Сценарий завершён с отказом.",
                        "reason": rule.reason,
                        "template_key": rule.template_key,
                        "template_text": _template_text(rule.template_key),
                    },
                    "inserted_followups": [],
                }
            )
            halted = True
            halt_reason = "reject"
            current_node_id = None
            break

        reaction: dict[str, Any] = {"message": "Ответ принят."}
        if rule.label:
            reaction["edge_label"] = rule.label
        if rule.template_key:
            reaction["template_key"] = rule.template_key
            reaction["template_text"] = _template_text(rule.template_key)

        steps.append(
            {
                "question": question,
                "answer": answer,
                "status": "ok",
                "reaction": reaction,
                "inserted_followups": [],
            }
        )

        if rule.target == end_id:
            current_node_id = None
            done = True
            break

        if rule.target not in question_by_node_id:
            return False, {}, "invalid_graph"
        current_node_id = rule.target

    next_question: dict[str, Any] | None = None
    if not halted and not done and current_node_id is not None:
        next_question = question_by_node_id.get(current_node_id)
    elif halted and halt_reason == "invalid" and current_node_id is not None:
        next_question = question_by_node_id.get(current_node_id)

    payload: dict[str, Any] = {
        "ok": True,
        "test_id": clean_test_id,
        "base_count": len(question_by_node_id),
        "sequence_count": len(question_by_node_id),
        "steps": steps,
        "next_question": next_question,
        "halted": halted,
        "halt_reason": halt_reason,
        "done": done,
    }
    return True, payload, None


__all__ = ["preview_test_builder_graph"]
