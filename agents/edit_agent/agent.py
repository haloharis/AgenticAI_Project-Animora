from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional, TypedDict, Union

from langgraph.graph import END, StateGraph

from agents.edit_agent.executor import EditExecutor
from agents.edit_agent.intent_classifier import IntentClassifier
from agents.edit_agent.planner import EditPlanner
from shared.schemas.pipeline_schema import EditAction, EditResult, PipelineState
from state_manager.state_manager import StateManager

logger = logging.getLogger(__name__)


class EditState(TypedDict):
    query: str
    pipeline_state: PipelineState
    edit_action: Optional[EditAction]
    plan: List[Dict[str, Any]]
    result: Optional[EditResult]
    needs_clarification: bool
    clarification_message: str


class EditAgent:
    def __init__(self, state_manager: Optional[StateManager] = None) -> None:
        self.classifier = IntentClassifier()
        self.planner = EditPlanner()
        self.executor = EditExecutor(state_manager)
        self.graph = self._build_graph()

    def _build_graph(self) -> Any:
        g = StateGraph(EditState)

        g.add_node("classify_intent", self._classify_intent_node)
        g.add_node("plan_edit", self._plan_edit_node)
        g.add_node("execute_edit", self._execute_edit_node)
        g.add_node("clarify", self._clarify_node)

        g.set_entry_point("classify_intent")
        g.add_conditional_edges(
            "classify_intent",
            self._route_after_classify,
            {"proceed": "plan_edit", "clarify": "clarify"},
        )
        g.add_edge("plan_edit", "execute_edit")
        g.add_edge("execute_edit", END)
        g.add_edge("clarify", END)

        return g.compile()

    def _classify_intent_node(self, state: EditState) -> Dict[str, Any]:
        action = self.classifier.classify(state["query"], state["pipeline_state"])
        needs_clarification = action.confidence < 0.4
        return {
            "edit_action": action,
            "needs_clarification": needs_clarification,
            "clarification_message": (
                f"I'm not sure what you want to change. Did you mean to edit the "
                f"{action.intent.value}? Please be more specific." if needs_clarification else ""
            ),
        }

    def _route_after_classify(self, state: EditState) -> str:
        return "clarify" if state.get("needs_clarification") else "proceed"

    def _plan_edit_node(self, state: EditState) -> Dict[str, Any]:
        plan = self.planner.plan(state["edit_action"], state["pipeline_state"])
        return {"plan": plan}

    def _execute_edit_node(self, state: EditState) -> Dict[str, Any]:
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(
                self.executor.execute(
                    state["plan"],
                    state["pipeline_state"],
                    state["edit_action"],
                )
            )
        finally:
            loop.close()
        return {"result": result}

    def _clarify_node(self, state: EditState) -> Dict[str, Any]:
        return {"result": None}

    def run(self, query: str, pipeline_state: PipelineState) -> Union[EditResult, str]:
        from mcp.tool_registry import ToolRegistry
        ToolRegistry.auto_register_all()

        initial: EditState = {
            "query": query,
            "pipeline_state": pipeline_state,
            "edit_action": None,
            "plan": [],
            "result": None,
            "needs_clarification": False,
            "clarification_message": "",
        }
        final = self.graph.invoke(initial)

        if final.get("needs_clarification"):
            return final.get("clarification_message", "Please clarify your edit request.")

        result = final.get("result")
        if result is None:
            return final.get("clarification_message", "Edit could not be processed.")
        return result
