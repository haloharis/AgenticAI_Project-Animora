from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class Mood(str, Enum):
    happy = "happy"
    sad = "sad"
    tense = "tense"
    calm = "calm"
    mysterious = "mysterious"
    epic = "epic"
    romantic = "romantic"
    horror = "horror"
    cartoon = "cartoon"


class PhaseStatus(str, Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class EditIntent(str, Enum):
    audio = "audio"
    video_frame = "video_frame"
    video = "video"
    script = "script"


class TransitionType(str, Enum):
    fade = "fade"
    cut = "cut"
    dissolve = "dissolve"


class Character(BaseModel):
    id: str = Field(default_factory=lambda: f"char_{uuid.uuid4().hex[:8]}")
    name: str
    role: str = "supporting"
    description: str
    voice_id: str = "aura-asteria-en"
    personality: str = ""


class DialogueLine(BaseModel):
    character_id: str
    text: str
    emotion: str = "neutral"
    duration_estimate_ms: int = 0


class Scene(BaseModel):
    id: str = Field(default_factory=lambda: f"scene_{uuid.uuid4().hex[:8]}")
    scene_number: int
    title: str
    description: str
    visual_prompt: str = ""
    dialogue: List[DialogueLine] = Field(default_factory=list)
    mood: Mood = Mood.calm
    duration_ms: int = 5000
    transition: TransitionType = TransitionType.fade
    image_path: Optional[str] = None


class Story(BaseModel):
    id: str = Field(default_factory=lambda: f"story_{uuid.uuid4().hex[:8]}")
    title: str
    narrative: str
    scenes: List[Scene]
    characters: List[Character]
    total_duration_ms: int = 0
    style: str = "cinematic"


class AudioSegment(BaseModel):
    scene_id: str
    character_id: Optional[str] = None
    text: Optional[str] = None
    audio_file: str
    segment_type: str = "dialogue"
    duration_ms: int = 0


class TimingManifest(BaseModel):
    job_id: str
    segments: List[AudioSegment] = Field(default_factory=list)
    scene_timings: Dict[str, Dict[str, int]] = Field(default_factory=dict)


class PhaseInfo(BaseModel):
    status: PhaseStatus = PhaseStatus.pending
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    progress_pct: int = 0


def _default_phases() -> Dict[str, PhaseInfo]:
    return {
        "story": PhaseInfo(),
        "audio": PhaseInfo(),
        "video": PhaseInfo(),
    }


class PipelineState(BaseModel):
    job_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    user_prompt: str
    style: str = "cinematic"
    story: Optional[Story] = None
    timing_manifest: Optional[TimingManifest] = None
    final_video_path: Optional[str] = None
    phases: Dict[str, PhaseInfo] = Field(default_factory=_default_phases)
    version: int = 0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class EditRequest(BaseModel):
    job_id: str
    query: str


class EditAction(BaseModel):
    intent: EditIntent
    target: str
    scope: str = "single"
    parameters: Dict[str, Any] = Field(default_factory=dict)
    confidence: float = 1.0


class EditResult(BaseModel):
    job_id: str
    action: EditAction
    success: bool
    message: str
    new_version: int = 0
