from __future__ import annotations

from collections import deque
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


@dataclass(frozen=True)
class _GraphEdge:
    id: str
    source: str
    target: str
    data: Dict[str, Any]


def _parse_graph_nodes_edges(
    graph: Dict[str, Any],
) -> Tuple[
    Optional[dict[str, _GraphNode]],
    Optional[list[_GraphEdge]],
    Optional[str],
    Optional[str],
    Optional[str],
]:
    if not _is_xyflow_graph(graph):
        return None, None, None, None, "invalid_graph"

    nodes_raw = graph.get("nodes") or []
    edges_raw = graph.get("edges") or []

    nodes: dict[str, _GraphNode] = {}
    start_ids: list[str] = []
    end_ids: list[str] = []

    for item in nodes_raw:
        if not isinstance(item, dict):
            continue
        node_id = str(item.get("id") or "").strip()
        node_type = str(item.get("type") or "").strip()
        data = item.get("data") if isinstance(item.get("data"), dict) else {}

        qid_value: Optional[int] = None
        if isinstance(data, dict):
            raw_qid = data.get("question_id")
            if raw_qid not in (None, ""):
                try:
                    qid_value = int(raw_qid)
                except (TypeError, ValueError):
                    return None, None, None, None, "invalid_graph"

        if not node_id or not node_type:
            continue
        if node_type not in {"start", "end", "question"}:
            return None, None, None, None, "unknown_node_type"
        if node_id in nodes:
            return None, None, None, None, "invalid_graph"

        if node_type == "start":
            start_ids.append(node_id)
        elif node_type == "end":
            end_ids.append(node_id)

        nodes[node_id] = _GraphNode(id=node_id, type=node_type, question_id=qid_value)

    if len(start_ids) != 1 or len(end_ids) != 1:
        return None, None, None, None, "invalid_graph"
    if not nodes:
        return None, None, None, None, "invalid_graph"

    edges: list[_GraphEdge] = []
    for idx, item in enumerate(edges_raw):
        if not isinstance(item, dict):
            continue
        src = str(item.get("source") or "").strip()
        dst = str(item.get("target") or "").strip()
        if not src or not dst:
            continue
        if src not in nodes or dst not in nodes:
            return None, None, None, None, "invalid_graph"
        edge_id = str(item.get("id") or f"e_{src}_{dst}_{idx}")
        data = item.get("data") if isinstance(item.get("data"), dict) else {}
        edges.append(_GraphEdge(id=edge_id, source=src, target=dst, data=dict(data)))

    return nodes, edges, start_ids[0], end_ids[0], None


def _has_cycle(start_id: str, outgoing: dict[str, list[str]]) -> bool:
    color: dict[str, int] = {}

    def dfs(node_id: str) -> bool:
        color[node_id] = 1
        for nxt in outgoing.get(node_id, []):
            state = color.get(nxt, 0)
            if state == 1:
                return True
            if state == 0 and dfs(nxt):
                return True
        color[node_id] = 2
        return False

    return dfs(start_id)


def validate_test_builder_graph(graph: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """Validate graph as a branching questionnaire flow.

    Rules:
    - exactly one `start` and one `end`
    - all question nodes reachable from start
    - every question has at least one outgoing edge
    - graph must be acyclic
    - end must be reachable
    - each question must have a path to end
    """

    nodes, edges, start_id, end_id, error = _parse_graph_nodes_edges(graph)
    if error is not None or nodes is None or edges is None or start_id is None or end_id is None:
        return False, error or "invalid_graph"

    outgoing: dict[str, list[str]] = {nid: [] for nid in nodes.keys()}
    incoming: dict[str, list[str]] = {nid: [] for nid in nodes.keys()}
    for edge in edges:
        outgoing[edge.source].append(edge.target)
        incoming[edge.target].append(edge.source)

    if len(outgoing.get(start_id) or []) == 0:
        return False, "graph_not_linear"

    for node in nodes.values():
        if node.type == "question" and len(outgoing.get(node.id) or []) == 0:
            return False, "graph_dead_end"

    if _has_cycle(start_id, outgoing):
        return False, "graph_cycle"

    reachable: set[str] = set()
    q: deque[str] = deque([start_id])
    while q:
        node_id = q.popleft()
        if node_id in reachable:
            continue
        reachable.add(node_id)
        for nxt in outgoing.get(node_id, []):
            if nxt not in reachable:
                q.append(nxt)

    if end_id not in reachable:
        return False, "graph_dead_end"

    for node in nodes.values():
        if node.type == "question" and node.id not in reachable:
            return False, "graph_unreachable_node"

    can_reach_end: set[str] = set()
    back_q: deque[str] = deque([end_id])
    while back_q:
        node_id = back_q.popleft()
        if node_id in can_reach_end:
            continue
        can_reach_end.add(node_id)
        for prev in incoming.get(node_id, []):
            if prev not in can_reach_end:
                back_q.append(prev)

    for node in nodes.values():
        if node.type == "question" and node.id not in can_reach_end:
            return False, "graph_dead_end"

    return True, None


def extract_question_ids_from_graph(graph: Dict[str, Any]) -> Tuple[Optional[List[int]], Optional[str]]:
    nodes, _edges, _start_id, _end_id, error = _parse_graph_nodes_edges(graph)
    if error is not None or nodes is None:
        return None, error or "invalid_graph"

    ids: list[int] = []
    seen: set[int] = set()
    for node in nodes.values():
        if node.type != "question":
            continue
        if node.question_id is None:
            continue
        if node.question_id in seen:
            continue
        seen.add(node.question_id)
        ids.append(int(node.question_id))
    return ids, None


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

    valid, validation_error = validate_test_builder_graph(graph)
    if not valid:
        return False, validation_error or "invalid_graph"

    question_ids_in_graph, ids_error = extract_question_ids_from_graph(graph)
    if ids_error is not None or question_ids_in_graph is None:
        return False, ids_error or "invalid_graph"
    _test_db_id, existing_ids = await _load_test_questions_ids(clean)
    if not existing_ids:
        return False, "test_not_found"
    if set(question_ids_in_graph) != set(existing_ids):
        return False, "order_mismatch"

    ok, error, _updated_at = await save_test_builder_graph(test_id=clean, graph=graph)
    if not ok:
        return False, error

    # Keep legacy behavior for linear graphs: synchronize DB order to match graph.
    # For branching graphs the order in DB stays as-is; runtime uses graph structure.
    order, err = _compile_linear_question_order(graph)
    if err is None and order is not None:
        ok2, error2 = await reorder_test_questions(test_id=clean, order=order)
        if not ok2:
            return False, error2
    return True, None


__all__ = [
    "apply_test_builder_graph",
    "get_test_builder_graph",
    "save_test_builder_graph",
]
