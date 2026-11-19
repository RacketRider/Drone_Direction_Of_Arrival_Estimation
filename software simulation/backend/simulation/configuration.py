"""
Simulation and RF Configuration Models.
Defines all physical constants, array geometry, RF parameters, and simulation settings.
"""

from typing import List, Literal, Tuple
from pydantic import BaseModel, Field
import numpy as np

# Physical constants
SPEED_OF_LIGHT: float = 299792458.0  # m/s in vacuum/air

class ArrayGeometryConfig(BaseModel):
    """Uniform Circular Array (UCA) configuration."""
    num_elements: int = Field(default=4, description="Number of antenna elements (M)")
    radius: float = Field(default=0.072, description="Array radius in meters (r = 7.2 cm)")
    element_angles_deg: List[float] = Field(
        default=[0.0, 90.0, 180.0, 270.0],
        description="Azimuth angles of array elements in degrees"
    )
    center_pos: Tuple[float, float, float] = Field(
        default=(0.0, 0.0, 0.0),
        description="Array center 3D position (x, y_altitude, z)"
    )
    # Hardware impairments
    position_errors_m: List[Tuple[float, float]] = Field(
        default=[(0.0, 0.0), (0.0, 0.0), (0.0, 0.0), (0.0, 0.0)],
        description="Manufacturing element position perturbations (dx, dz) in meters"
    )
    phase_offsets_deg: List[float] = Field(
        default=[0.0, 0.0, 0.0, 0.0],
        description="RF channel phase mismatch in degrees"
    )
    amplitude_mismatch_db: List[float] = Field(
        default=[0.0, 0.0, 0.0, 0.0],
        description="RF channel gain mismatch in dB"
    )

class BuildingConfig(BaseModel):
    """Concrete building obstacle in the 120m x 120m arena."""
    id: int
    name: str
    x_min: float
    x_max: float
    z_min: float
    z_max: float
    height: float  # meters (y axis)
    relative_permittivity: float = Field(default=5.5, description="Concrete epsilon_r")
    conductivity: float = Field(default=0.02, description="Concrete conductivity sigma (S/m)")
    reflection_coefficient_mag: float = Field(default=0.75, description="Nominal specular reflection magnitude")

class RFPropagationConfig(BaseModel):
    """RF transmission, channel, and noise parameters."""
    sample_rate: float = Field(default=2.0e6, description="Baseband SDR sampling rate (2 MS/s)")
    burst_samples: int = Field(default=256, description="Number of baseband samples per burst (128 us)")
    total_stream_samples: int = Field(default=600, description="Total simulation stream window length")
    burst_start_sample: int = Field(default=150, description="Burst arrival index in stream")
    
    # Hop frequencies pool
    hop_frequencies_hz: List[float] = Field(
        default=[433.0e6, 868.0e6, 915.0e6, 920.0e6, 928.0e6],
        description="Allowed FHSS carrier frequencies"
    )
    reference_frequency_hz: float = Field(
        default=433.0e6,
        description="Static legacy reference frequency for uncompensated baseline (433 MHz)"
    )
    
    # Transmission characteristics
    tx_power_dbm: float = Field(default=20.0, description="UAV telemetry transmit power in dBm (100 mW)")
    nominal_snr_db: float = Field(default=15.0, description="Received Signal-to-Noise Ratio in dB")
    multipath_enabled: bool = Field(default=True, description="Enable building multipath reflections")
    multipath_strength_factor: float = Field(default=0.85, description="Wall reflection scattering multiplier")

class SwitchedSDRConfig(BaseModel):
    """HMC241 SP4T switch & RTL-SDR receiver hardware model."""
    receiver_mode: Literal["MODE_A_SIMULTANEOUS", "MODE_B_SWITCHED"] = Field(
        default="MODE_B_SWITCHED",
        description="Mode A = Ideal simultaneous 4-channel; Mode B = Sequential HMC241 switched single SDR"
    )
    lo_tuning_mode: Literal["SYNCHRONOUS", "STATIC_LO", "WIDEBAND"] = Field(
        default="SYNCHRONOUS",
        description="SDR Local Oscillator tuning behavior"
    )
    lo_frequency_hz: float = Field(default=915.0e6, description="Fixed receiver LO frequency when in STATIC_LO mode")
    baseband_bandwidth_hz: float = Field(default=2.0e6, description="SDR complex baseband filter bandwidth")
    switch_settling_samples: int = Field(default=4, description="Transient samples corrupted during switch transition")
    dwell_samples_per_antenna: int = Field(default=64, description="Samples collected per switch dwell slot (256/4=64)")
    phase_de_rotation_enabled: bool = Field(default=True, description="Correct temporal carrier evolution across slots")

class DSPOptionsConfig(BaseModel):
    """Direction-Finding and subspace estimation parameters."""
    power_envelope_window: int = Field(default=16, description="Sliding-window power smoothing kernel size")
    power_trigger_threshold_factor: float = Field(default=2.5, description="Burst trigger multiplier above noise floor")
    fft_size: int = Field(default=256, description="FFT length for hop frequency identification")
    eigenvalue_gate_threshold: float = Field(default=8.0, description="Multipath rejection ratio threshold gamma_th = lambda_1 / lambda_2")
    angle_grid_resolution_deg: float = Field(default=0.5, description="MUSIC pseudospectrum angular search step")
    angle_grid_min_deg: float = Field(default=-180.0, description="MUSIC minimum azimuth angle")
    angle_grid_max_deg: float = Field(default=180.0, description="MUSIC maximum azimuth angle")
    tracker_type: Literal["GATED_HOLD", "KALMAN_FILTER"] = Field(
        default="GATED_HOLD",
        description="Tracking filter strategy"
    )

class SystemConfiguration(BaseModel):
    """Top-level master configuration container."""
    seed: int = Field(default=42, description="Deterministic PRNG seed")
    arena_width_m: float = Field(default=120.0, description="Arena X width (-60 to +60 m)")
    arena_depth_m: float = Field(default=120.0, description="Arena Z depth (-60 to +60 m)")
    uav_speed_multiplier: float = Field(default=1.0, description="Time step rate multiplier")
    simulation_dt: float = Field(default=0.05, description="Simulation discrete time step in seconds (20 Hz)")
    
    array: ArrayGeometryConfig = Field(default_factory=ArrayGeometryConfig)
    rf: RFPropagationConfig = Field(default_factory=RFPropagationConfig)
    sdr: SwitchedSDRConfig = Field(default_factory=SwitchedSDRConfig)
    dsp: DSPOptionsConfig = Field(default_factory=DSPOptionsConfig)
    
    buildings: List[BuildingConfig] = Field(
        default=[
            BuildingConfig(
                id=0,
                name="Concrete Building Alpha",
                x_min=-38.0,
                x_max=-18.0,
                z_min=-35.0,
                z_max=-15.0,
                height=16.0
            ),
            BuildingConfig(
                id=1,
                name="Concrete Building Beta",
                x_min=18.0,
                x_max=38.0,
                z_min=-32.0,
                z_max=-12.0,
                height=19.0
            )
        ]
    )

DEFAULT_CONFIG = SystemConfiguration()

