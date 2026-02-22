from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import select

from backend.core.db import async_session
from backend.domain.models import BotRuntimeConfig
from backend.domain.tests.models import Question, Test

from .questions import reorder_test_questions


GRAPH_KEY_PREFIX = "test_builder_graph:"


def _graph_key(test_id: str) -> str:
    return f"{GRAPH_KEY_PREFIX}{test_id}"


def _is_xyflow_graph(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    nodes = value.get("nodes")
    edges = value.get("edges")
    return isinstance(nodes, list) and isinstance(edges, list)


async def _load_test_questions_ids(test_id: str) -> Tuple[Optional[int], List[int]]:
    async with async_session() as session:
        test = await session.scalar(select(Test).where(Test.slug == test_id))
        if test is None:
            return None, []
        ids = (
            await session.scalars(
                select(Question.id)
                .where(Question.test_id == test.id)
                .order_by(Question.order.asc())
            )
        ).all()
        return int(test.id), [int(x) for x in ids]


async def get_test_builder_graph(
    *,
    test_id: str,
) -> Tuple[Dict[str, Any], Optional[datetime]]:
    """Return stored graph for a test, or build a default one from current question order."""

    clean = str(test_id or "").strip()
    if not clean:
        return {"schema": "xyflow_v1", "nodes": [], "edges": []}, None

    async with async_session() as session:
        row = await session.get(BotRuntimeConfig, _graph_key(clean))
        if row is not None and _is_xyflow_graph(row.value_json):
            return dict(row.value_json), row.updated_at

    _, question_ids = await _load_test_questions_ids(clean)
    # Default linear graph: start -> q1 -> q2 -> ... -> end
    nodes: List[Dict[str, Any]] = [
        {"id": "start", "type": "start", "position": {"x": 0, "y": 0}, "data": {"label": "Start"}},
    ]
    edges: List[Dict[str, Any]] = []
    y = 120
    prev = "start"
    for qid in question_ids:
        node_id = f"q_{qid}"
        nodes.append(
            {
                "id": node_id,
                "type": "question",
                "position": {"x": 0, "y": y},
                "data": {"question_id": int(qid)},
            }
        )
        edges.append({"id": f"e_{prev}_{node_id}", "source": prev, "target": node_id})
        prev = node_id
        y += 120
    nodes.append({"id": "end", "type": "end", "position": {"x": 0, "y": y}, "data": {"label": "End"}})
    edges.append({"id": f"e_{prev}_end", "source": prev, "target": "end"})
    return {"schema": "xyflow_v1", "nodes": nodes, "edges": edges}, None


async def save_test_builder_graph(
    *,
    test_id: str,
    graph: Dict[str, Any],
) -> Tuple[bool, Optional[str], Optional[datetime]]:
    """Persist graph as BotRuntimeConfig (best effort validation)."""

    clean = str(test_id or "").strip()
    if not clean:
        return False, "test_required", None
    if not _is_xyflow_graph(graph):
        return False, "invalid_graph", None

    async with async_session() as session:
        row = await session.get(BotRuntimeConfig, _graph_key(clean))
        if row is None:
            row = BotRuntimeConfig(key=_graph_key(clean), value_json=dict(graph))
            session.add(row)
        else:
            row.value_json = dict(graph)
        await session.commit()
        await session.refresh(row)
        return True, None, row.updated_at


@dataclass(frozen=True)
class _GraphNode:
    id: str
    type: str
    question_id: Optional[int]


def _compile_linear_question_order(graph: Dict[str, Any]) -> Tuple[Optional[List[int]], Optional[str]]:
    """Compile a linear XYFlow graph into question_id order.

    Only supports: start -> question* -> end, with exactly one outgoing edge per node.
    """

    if not _is_xyflow_graph(graph):
        return None, "invalid_graph"
    nodes_raw = graph.get("nodes") or []
    edges_raw = graph.get("edges") or []

    nodes: dict[str, _GraphNode] = {}
    start_ids: list[str] = []
    end_ids: list[str] = []
    question_nodes: list[str] = []

    for item in nodes_raw:
        if not isinstance(item, dict):
            continue
        node_id = str(item.get("id") or "").strip()
        node_type = str(item.get("type") or "").strip()
        data = item.get("data") if isinstance(item.get("data"), dict) else {}
        qid = data.get("question_id") if isinstance(data, dict) else None
        qid_value: Optional[int] = None
        if qid is not None:
            try:
                qid_value = int(qid)
            except (TypeError, ValueError):
                qid_value = None

        if not node_id or not node_type:
            continue
        if node_type == "start":
            start_ids.append(node_id)
        elif node_type == "end":
            end_ids.append(node_id)
        elif node_type == "question":
            question_nodes.append(node_id)
        else:
            return None, "unknown_node_type"
        nodes[node_id] = _GraphNode(id=node_id, type=node_type, question_id=qid_value)

    if len(start_ids) != 1 or len(end_ids) != 1:
        return None, "invalid_graph"
    start_id = start_ids[0]
    end_id = end_ids[0]

    outgoing: dict[str, list[str]] = {nid: [] for nid in nodes.keys()}
    incoming: dict[str, int] = {nid: 0 for nid in nodes.keys()}
    for edge in edges_raw:
        if not isinstance(edge, dict):
            continue
        src = str(edge.get("source") or "").strip()
        dst = str(edge.get("target") or "").strip()
        if not src or not dst:
            continue
        if src not in nodes or dst not in nodes:
            continue
        outgoing[src].append(dst)
        incoming[dst] = incoming.get(dst, 0) + 1

    # Linear constraints
    if incoming.get(start_id, 0) != 0:
        return None, "invalid_graph"
    if len(outgoing.get(start_id) or []) != 1:
        return None, "graph_not_linear"
    if len(outgoing.get(end_id) or []) != 0:
        return None, "invalid_graph"
    if incoming.get(end_id, 0) != 1:
        return None, "graph_not_linear"

    for nid in question_nodes:
        if incoming.get(nid, 0) != 1:
            return None, "graph_not_linear"
        if len(outgoing.get(nid) or []) != 1:
            return None, "graph_not_linear"
        if nodes[nid].question_id is None:
            return None, "invalid_graph"

    # Walk from start to end
    order: list[int] = []
    visited: set[str] = set()
    cur = start_id
    while True:
        if cur in visited:
            return None, "graph_not_linear"
        visited.add(cur)
        next_list = outgoing.get(cur) or []
        if not next_list:
            return None, "invalid_graph"
        nxt = next_list[0]
        if nxt == end_id:
            break
        node = nodes.get(nxt)
        if node is None or node.type != "question" or node.question_id is None:
            return None, "invalid_graph"
        order.append(int(node.question_id))
        cur = nxt

    if len(order) != len(question_nodes):
        return None, "graph_not_linear"
    if len(set(order)) != len(order):
        return None, "graph_not_linear"
    return order, None


async def apply_test_builder_graph(
    *,
    test_id: str,
    graph: Dict[str, Any],
) -> Tuple[bool, Optional[str]]:
    """Save graph + apply compiled order to DB questions (so the bot sees changes immediately)."""

    clean = str(test_id or "").strip()
    if not clean:
        return False, "test_required"

    order, err = _compile_linear_question_order(graph)
    if err is not None or order is None:
        return False, err or "invalid_graph"

    _test_db_id, existing_ids = await _load_test_questions_ids(clean)
    if not existing_ids:
        return False, "test_not_found"
    if set(order) != set(existing_ids):
        return False, "order_mismatch"

    ok, error, _updated_at = await save_test_builder_graph(test_id=clean, graph=graph)
    if not ok:
        return False, error

    ok2, error2 = await reorder_test_questions(test_id=clean, order=order)
    if not ok2:
        return False, error2
    return True, None


__all__ = [
    "apply_test_builder_graph",
    "get_test_builder_graph",
    "save_test_builder_graph",
]

