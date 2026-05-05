from __future__ import annotations

from typing import Optional, TypedDict

from shared.schemas.pipeline_schema import PhaseInfo, PhaseStatus, PipelineState


class OrchestratorState(TypedDict):
    job_id: str
    user_prompt: str
    style: str
    pipeline_state: Optional[PipelineState]
    current_phase: str
    error: str


def update_phase_status(
    pipeline_state: PipelineState,
    phase: str,
    status: PhaseStatus,
    error: Optional[str] = None,
    progress_pct: int = 0,
) -> PipelineState:
    from datetime import datetime, timezone

    phase_info = pipeline_state.phases.get(phase, PhaseInfo())
    phase_info.status = status
    phase_info.progress_pct = progress_pct
    if error:
        phase_info.error = error
    if status == PhaseStatus.running and not phase_info.started_at:
        phase_info.started_at = datetime.now(timezone.utc)
    if status in (PhaseStatus.completed, PhaseStatus.failed):
        phase_info.completed_at = datetime.now(timezone.utc)
    pipeline_state.phases[phase] = phase_info
    return pipeline_state
