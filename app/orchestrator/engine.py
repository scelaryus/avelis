"""GFI Platform - LangGraph-like Agent Orchestrator Engine.

Provides a graph-based workflow engine where each node is an agent
that transforms a shared WorkflowState and produces artifacts.
"""
from __future__ import annotations
import hashlib
import json
import structlog
from datetime import datetime
from typing import Any, Callable, Awaitable, Optional
from dataclasses import dataclass, field

from app.schemas.artifacts import WorkflowState, NodeResult

logger = structlog.get_logger(__name__)


@dataclass
class RunContext:
    """Context object passed to every node at execution time."""
    db_session: Any  # AsyncSession
    storage: Any  # ObjectStorageService
    settings: Any  # app Settings
    tenant_id: str
    user_id: str
    workflow_id: str
    cache: dict = field(default_factory=dict)


# Type alias for node functions
NodeFn = Callable[[WorkflowState, RunContext], Awaitable[NodeResult]]


@dataclass
class Edge:
    """Directed edge between graph nodes."""
    source: str
    target: str
    condition: Optional[Callable[[WorkflowState, NodeResult], bool]] = None  # if None → always


@dataclass
class GraphNode:
    """A node in the orchestration graph."""
    name: str
    fn: NodeFn
    description: str = ""
    parallel_key: Optional[str] = None  # for page-level parallelism


class OrchestrationGraph:
    """
    A directed acyclic graph (with optional conditional edges) of agent nodes.
    Executes nodes sequentially by default, with support for:
    - conditional routing
    - blocking / error states
    - caching via doc_sha256 + node_name + versions
    """

    def __init__(self, name: str):
        self.name = name
        self.nodes: dict[str, GraphNode] = {}
        self.edges: list[Edge] = []
        self.entry_node: Optional[str] = None

    def add_node(self, name: str, fn: NodeFn, description: str = "", parallel_key: str = None):
        self.nodes[name] = GraphNode(name=name, fn=fn, description=description, parallel_key=parallel_key)

    def add_edge(self, source: str, target: str, condition=None):
        self.edges.append(Edge(source=source, target=target, condition=condition))

    def set_entry(self, name: str):
        self.entry_node = name

    def get_next_nodes(self, current: str, state: WorkflowState, result: NodeResult) -> list[str]:
        """Determine next nodes after current node completion."""
        # If the node result specifies a next override
        if result.next:
            return [result.next]

        # Find all edges from current node
        candidates = [e for e in self.edges if e.source == current]
        next_nodes = []
        for edge in candidates:
            if edge.condition is None or edge.condition(state, result):
                next_nodes.append(edge.target)

        return next_nodes

    def _compute_cache_key(self, node_name: str, state: WorkflowState, ctx: RunContext) -> str:
        """Compute deterministic cache key for a node execution."""
        key_parts = {
            "node": node_name,
            "doc_ids": sorted(state.doc_ids),
            "algo_version": "v3.0",
        }
        return hashlib.sha256(json.dumps(key_parts, sort_keys=True).encode()).hexdigest()

    async def execute(self, state: WorkflowState, ctx: RunContext) -> WorkflowState:
        """Execute the full graph from entry node."""
        if not self.entry_node:
            raise ValueError("No entry node set for graph")

        state.status = "RUNNING"
        current_nodes = [self.entry_node]

        while current_nodes:
            next_batch = []

            for node_name in current_nodes:
                if node_name not in self.nodes:
                    state.errors.append({
                        "code": "UNKNOWN_NODE",
                        "message": f"Node '{node_name}' not found in graph",
                        "timestamp": datetime.utcnow().isoformat()
                    })
                    state.status = "FAILED"
                    return state

                node = self.nodes[node_name]
                state.current_node = node_name

                logger.info("executing_node", node=node_name, workflow_id=state.workflow_id)

                try:
                    # Execute the agent node
                    result = await node.fn(state, ctx)

                    # Record node in history
                    state.node_history.append({
                        "node": node_name,
                        "status": result.status,
                        "artifacts_created": result.artifacts_created,
                        "timestamp": datetime.utcnow().isoformat(),
                    })

                    # Register artifacts
                    for aid in result.artifacts_created:
                        # We store IDs grouped by node for traceability
                        if node_name not in state.artifacts:
                            state.artifacts[node_name] = []
                        state.artifacts[node_name].append(aid)

                    # Collect warnings
                    if result.warnings:
                        state.warnings.extend(result.warnings)

                    # Handle BLOCK
                    if result.status == "BLOCK":
                        state.status = "BLOCKED"
                        state.blocking_reasons.extend(
                            [e.get("message", str(e)) for e in result.errors]
                        )
                        logger.warning("node_blocked", node=node_name, reasons=result.errors)
                        return state

                    # Handle ERROR
                    if result.status == "ERROR":
                        state.status = "FAILED"
                        state.errors.extend(result.errors)
                        logger.error("node_error", node=node_name, errors=result.errors)
                        return state

                    # Determine next nodes
                    nexts = self.get_next_nodes(node_name, state, result)
                    next_batch.extend(nexts)

                except Exception as exc:
                    state.status = "FAILED"
                    state.errors.append({
                        "code": "NODE_EXCEPTION",
                        "node": node_name,
                        "message": str(exc),
                        "timestamp": datetime.utcnow().isoformat(),
                    })
                    logger.exception("node_exception", node=node_name)
                    return state

            current_nodes = next_batch

        # If we reach here, all nodes completed
        if state.status == "RUNNING":
            state.status = "READY_TO_COMMIT"

        return state
