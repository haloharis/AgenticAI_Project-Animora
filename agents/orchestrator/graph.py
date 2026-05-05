from __future__ import annotations

import logging
from typing import Any, Dict

from langgraph.graph import END, StateGraph

from agents.orchestrator.state import OrchestratorState, update_phase_status
from shared.schemas.pipeline_schema import PhaseStatus

logger = logging.getLogger(__name__)


def build_orchestrator_graph():
    """Build the LangGraph orchestrator for sequential phase execution."""
    g = StateGraph(OrchestratorState)

    g.add_node("run_story_phase", _run_story_phase)
    g.add_node("run_audio_phase", _run_audio_phase)
    g.add_node("run_video_phase", _run_video_phase)
    g.add_node("handle_error", _handle_error)

    g.set_entry_point("run_story_phase")

    g.add_conditional_edges(
        "run_story_phase",
        _check_phase_success,
        {"success": "run_audio_phase", "error": "handle_error"},
    )
    g.add_conditional_edges(
        "run_audio_phase",
        _check_phase_success,
        {"success": "run_video_phase", "error": "handle_error"},
    )
    g.add_edge("run_video_phase", END)
    g.add_edge("handle_error", END)

    return g.compile()


def _check_phase_success(state: OrchestratorState) -> str:
    if state.get("error"):
        return "error"
    ps = state.get("pipeline_state")
    if ps is None:
        return "error"
    phase = state.get("current_phase", "")
    phase_info = ps.phases.get(phase)
    if phase_info and phase_info.status == PhaseStatus.failed:
        return "error"
    return "success"


def _run_story_phase(state: OrchestratorState) -> Dict[str, Any]:
    from agents.story_agent.agent import StoryAgent
    from mcp.tool_registry import ToolRegistry
    ToolRegistry.auto_register_all()

    ps = state["pipeline_state"]
    ps = update_phase_status(ps, "story", PhaseStatus.running, progress_pct=10)
    try:
        agent = StoryAgent()
        story = agent.run(state["user_prompt"], state["style"])
        ps.story = story
        ps = update_phase_status(ps, "story", PhaseStatus.completed, progress_pct=100)
        return {"pipeline_state": ps, "current_phase": "story", "error": ""}
    except Exception as e:
        logger.exception(f"Story phase failed: {e}")
        ps = update_phase_status(ps, "story", PhaseStatus.failed, error=str(e))
        return {"pipeline_state": ps, "current_phase": "story", "error": str(e)}


def _run_audio_phase(state: OrchestratorState) -> Dict[str, Any]:
    from agents.audio_agent.agent import AudioAgent

    ps = state["pipeline_state"]
    ps = update_phase_status(ps, "audio", PhaseStatus.running, progress_pct=10)
    try:
        agent = AudioAgent()
        manifest = agent.run(ps.story, ps.job_id)
        ps.timing_manifest = manifest
        ps = update_phase_status(ps, "audio", PhaseStatus.completed, progress_pct=100)
        return {"pipeline_state": ps, "current_phase": "audio", "error": ""}
    except Exception as e:
        logger.exception(f"Audio phase failed: {e}")
        ps = update_phase_status(ps, "audio", PhaseStatus.failed, error=str(e))
        return {"pipeline_state": ps, "current_phase": "audio", "error": str(e)}


def _run_video_phase(state: OrchestratorState) -> Dict[str, Any]:
    from agents.video_agent.agent import VideoAgent

    ps = state["pipeline_state"]
    ps = update_phase_status(ps, "video", PhaseStatus.running, progress_pct=10)
    try:
        agent = VideoAgent()
        video_path = agent.run(ps.story, ps.timing_manifest, ps.job_id)
        ps.final_video_path = video_path
        ps = update_phase_status(ps, "video", PhaseStatus.completed, progress_pct=100)
        return {"pipeline_state": ps, "current_phase": "video", "error": ""}
    except Exception as e:
        logger.exception(f"Video phase failed: {e}")
        ps = update_phase_status(ps, "video", PhaseStatus.failed, error=str(e))
        return {"pipeline_state": ps, "current_phase": "video", "error": str(e)}


def _handle_error(state: OrchestratorState) -> Dict[str, Any]:
    logger.error(f"Pipeline error in phase '{state.get('current_phase')}': {state.get('error')}")
    return state
