"""
Pydantic Schemas for API Requests, Responses, and WebSocket Messages.
"""

from typing import Any, Dict, List, Literal, Optional, Tuple
from pydantic import BaseModel, Field

class ControlCommand(BaseModel):
    """Command sent to control the simulation execution."""
    action: Literal[
        "PLAY", "PAUSE", "STEP", "RESET", "SET_SPEED", "SET_SNR",
        "SET_TRAJECTORY", "SET_RECEIVER_MODE", "SET_TRACKER_TYPE",
        "SET_GATE_THRESHOLD", "SET_FOLIAGE_DENSITY", "SET_ENVIRONMENT",
        "SET_BUILDINGS_ENABLED"
    ]
    speed_multiplier: Optional[float] = None
    snr_db: Optional[float] = None
    trajectory: Optional[str] = None
    receiver_mode: Optional[Literal["MODE_A_SIMULTANEOUS", "MODE_B_SWITCHED"]] = None
    tracker_type: Optional[Literal["GATED_HOLD", "KALMAN_FILTER"]] = None
    gate_threshold: Optional[float] = None
    foliage_density: Optional[float] = None
    preset: Optional[str] = None
    buildings_enabled: Optional[bool] = None
    seed: Optional[int] = None

class StatusResponse(BaseModel):
    """Overall status of simulation engine."""
    sim_time: float
    frame_count: int
    is_paused: bool
    speed_multiplier: float
    snr_db: float
    receiver_mode: str
    active_trajectory: str
    active_frequency_mhz: float
    true_azimuth_deg: float
    accepted_track_deg: float
    gate_status: str

class ExperimentRunRequest(BaseModel):
    """Request to execute an experiment preset."""
    preset_id: str = Field(..., description="E.g. PRESET_A_FREQUENCY_HOPPING")
    seed: int = Field(default=42, description="Random seed")

class ExperimentRunResponse(BaseModel):
    """Response containing experiment benchmark metrics."""
    preset_id: str
    title: str
    description: str
    parameter_name: str
    seed: int
    results: List[Dict[str, Any]]

