"""
Quick Simulation & DSP Benchmark Script.
Validates end-to-end simulation stepping, telemetry generation, and execution speed.
"""

import time
import numpy as np
from backend.simulation.configuration import SystemConfiguration
from backend.simulation.engine import SimulationEngine

def run_benchmark(num_steps: int = 20):
    print("=" * 80)
    print("EC261 DIRECTION-FINDING SIMULATION ENGINE BENCHMARK")
    print("=" * 80)
    
    engine = SimulationEngine()
    engine.clock.play()
    
    t0 = time.time()
    for i in range(num_steps):
        engine.clock.tick()
        telem, diag = engine.step()
        if i % 4 == 0 or i == num_steps - 1:
            uav = telem["uav"]
            rf = telem["rf"]
            dsp = telem["dsp"]
            print(
                f"Step {i:2d} | t={telem['sim_time']:.2f}s | "
                f"Hop={rf['active_freq_mhz']:5.1f} MHz | "
                f"True Az={uav['true_azimuth_deg']:6.1f} deg | "
                f"Comp={dsp['est_compensated_deg']:6.1f} deg | "
                f"Err={dsp['error_comp_deg']:5.1f} deg | "
                f"Track={dsp['accepted_track_deg']:6.1f} deg | "
                f"Ratio={dsp['eigenvalue_ratio']:5.1f} | "
                f"Gate={dsp['gate_status']}"
            )
    
    elapsed = time.time() - t0
    rate = num_steps / elapsed
    print("-" * 80)
    print(f"Executed {num_steps} simulation steps in {elapsed:.3f} s ({rate:.1f} steps/second)")
    print("=" * 80)

def test_modes():
    print("\n--- Testing MODE A (Simultaneous) vs MODE B (Switched) across frequencies ---")
    for mode in ["MODE_A_SIMULTANEOUS", "MODE_B_SWITCHED"]:
        for f in [433.0e6, 868.0e6, 915.0e6]:
            cfg = SystemConfiguration()
            cfg.sdr.receiver_mode = mode
            cfg.rf.multipath_enabled = False  # Pure LoS test
            engine = SimulationEngine(cfg)
            engine.transmitter.set_mode("FIXED", fixed_freq_hz=f)
            engine.clock.play()
            engine.clock.tick()
            telem, _ = engine.step()
            uav = telem["uav"]
            dsp = telem["dsp"]
            print(f"[{mode:20s}] Freq={f/1e6:5.1f} MHz | True={uav['true_azimuth_deg']:5.1f} deg | Comp={dsp['est_compensated_deg']:5.1f} deg | Err={dsp['error_comp_deg']:5.1f} deg | BB={dsp['detected_baseband_khz']:5.1f} kHz")

if __name__ == "__main__":
    run_benchmark(15)
    test_modes()
