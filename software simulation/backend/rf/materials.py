"""
Electromagnetic Material Properties and Wave Physics Engine.
Calculates complex permittivity, refractive index, frequency-dependent attenuation,
complex Fresnel reflection/transmission coefficients, two-ray ground reflection,
and ITU-R P.526 knife-edge diffraction.
"""

from typing import Dict, Optional, Tuple
import numpy as np
from pydantic import BaseModel, Field

from backend.simulation.configuration import SPEED_OF_LIGHT

EPSILON_0 = 8.8541878128e-12  # F/m
MU_0 = 4.0 * np.pi * 1e-7      # H/m


class MaterialProperties(BaseModel):
    """Electromagnetic material constitutive parameters."""
    name: str
    epsilon_r: float = Field(..., description="Relative permittivity (dielectric constant)")
    conductivity_s_m: float = Field(..., description="Electrical conductivity sigma in S/m")
    mu_r: float = Field(default=1.0, description="Relative magnetic permeability")
    tan_delta_e: float = Field(default=0.02, description="Dielectric loss tangent")
    tan_delta_m: float = Field(default=0.0001, description="Magnetic loss tangent")
    moisture_pct: float = Field(default=0.0, description="Volumetric moisture content %")


# Standard RF Material Reference Library (near 400 MHz - 2.4 GHz)
MATERIAL_DATABASE: Dict[str, MaterialProperties] = {
    "CONCRETE": MaterialProperties(
        name="Standard Concrete",
        epsilon_r=5.5,
        conductivity_s_m=0.025,
        mu_r=1.0,
        tan_delta_e=0.03,
        moisture_pct=5.0
    ),
    "REINFORCED_CONCRETE": MaterialProperties(
        name="Reinforced Concrete",
        epsilon_r=7.5,
        conductivity_s_m=0.08,
        mu_r=1.02,
        tan_delta_e=0.06,
        moisture_pct=8.0
    ),
    "DRY_SOIL": MaterialProperties(
        name="Dry Sandy Soil",
        epsilon_r=4.5,
        conductivity_s_m=0.002,
        mu_r=1.001,
        tan_delta_e=0.025,
        moisture_pct=4.0
    ),
    "MOIST_SOIL": MaterialProperties(
        name="Moist Soil / Grassland",
        epsilon_r=14.0,
        conductivity_s_m=0.025,
        mu_r=1.005,
        tan_delta_e=0.055,
        moisture_pct=18.0
    ),
    "WET_SOIL": MaterialProperties(
        name="Wet Mud / Rain Puddle",
        epsilon_r=24.0,
        conductivity_s_m=0.15,
        mu_r=1.02,
        tan_delta_e=0.12,
        moisture_pct=32.0
    ),
    "ROCK": MaterialProperties(
        name="Dense Granite Rock",
        epsilon_r=7.0,
        conductivity_s_m=0.008,
        mu_r=1.015,
        tan_delta_e=0.035,
        moisture_pct=2.0
    ),
    "METAL": MaterialProperties(
        name="Conductive Metal / Rebar",
        epsilon_r=1.0,
        conductivity_s_m=1.0e6,
        mu_r=1.0,
        tan_delta_e=0.0,
        moisture_pct=0.0
    ),
    "BRICK": MaterialProperties(
        name="Masonry Brick",
        epsilon_r=4.2,
        conductivity_s_m=0.015,
        mu_r=1.0,
        tan_delta_e=0.028,
        moisture_pct=6.0
    ),
}


class ElectromagneticsEngine:
    """Rigorous electromagnetic boundary and propagation physics."""

    @staticmethod
    def complex_permittivity(mat: MaterialProperties, freq_hz: float) -> complex:
        """
        Calculates complex permittivity eps_c = eps_0 * eps_r - j * (eps_0 * eps_r * tan_delta + sigma / omega).
        """
        omega = 2.0 * np.pi * max(1e6, freq_hz)
        eps_prime = EPSILON_0 * mat.epsilon_r
        eps_loss = eps_prime * mat.tan_delta_e + mat.conductivity_s_m / omega
        return complex(eps_prime, -eps_loss)

    @staticmethod
    def complex_permeability(mat: MaterialProperties) -> complex:
        """Calculates complex permeability mu_c = mu_0 * mu_r * (1 - j * tan_delta_m)."""
        mu_prime = MU_0 * mat.mu_r
        return complex(mu_prime, -mu_prime * mat.tan_delta_m)

    @classmethod
    def propagation_parameters(cls, mat: MaterialProperties, freq_hz: float) -> Dict[str, float]:
        """
        Derives intrinsic impedance, propagation constant, phase constant, attenuation (dB/m),
        and skin depth for a given material and RF frequency.
        """
        omega = 2.0 * np.pi * max(1e6, freq_hz)
        eps_c = cls.complex_permittivity(mat, freq_hz)
        mu_c = cls.complex_permeability(mat)

        # Propagation constant gamma = alpha + j*beta = j*omega*sqrt(mu*eps)
        gamma = 1j * omega * np.sqrt(mu_c * eps_c)
        alpha_np_m = float(np.real(gamma))     # Neper/meter
        beta_rad_m = float(np.imag(gamma))     # Rad/meter
        attenuation_db_m = float(alpha_np_m * 8.686)

        # Intrinsic wave impedance eta = sqrt(mu / eps)
        eta = np.sqrt(mu_c / eps_c)
        eta_mag = float(np.abs(eta))

        # Skin depth delta = 1 / alpha (for lossy medium)
        skin_depth_m = float(1.0 / max(1e-6, alpha_np_m)) if alpha_np_m > 1e-6 else float('inf')
        refractive_index = float(np.real(np.sqrt((eps_c / EPSILON_0) * (mu_c / MU_0))))

        return {
            "attenuation_db_m": round(attenuation_db_m, 2),
            "phase_constant_rad_m": round(beta_rad_m, 3),
            "intrinsic_impedance_ohm": round(eta_mag, 1),
            "skin_depth_m": round(min(999.0, skin_depth_m), 3),
            "refractive_index": round(refractive_index, 3)
        }

    @classmethod
    def fresnel_reflection(
        cls,
        mat: MaterialProperties,
        freq_hz: float,
        incident_angle_deg: float
    ) -> Tuple[complex, complex, float]:
        """
        Calculates complex Fresnel reflection coefficients for TE (perpendicular) and TM (parallel)
        polarization, along with the Brewster angle.
        
        Args:
            mat: Material of the reflecting obstacle/ground
            freq_hz: Operating frequency
            incident_angle_deg: Angle of incidence from surface normal in degrees (0 = normal)
            
        Returns:
            (gamma_te, gamma_tm, brewster_angle_deg)
        """
        theta_i = np.radians(np.clip(incident_angle_deg, 0.0, 89.99))
        eps_1 = complex(EPSILON_0, 0.0)  # Air
        mu_1 = complex(MU_0, 0.0)
        eta_1 = np.sqrt(mu_1 / eps_1)

        eps_2 = cls.complex_permittivity(mat, freq_hz)
        mu_2 = cls.complex_permeability(mat)
        eta_2 = np.sqrt(mu_2 / eps_2)

        # Snell's Law: sin(theta_t) = sin(theta_i) * sqrt(eps_1*mu_1 / (eps_2*mu_2))
        n1_over_n2 = np.sqrt((eps_1 * mu_1) / (eps_2 * mu_2))
        sin_theta_t = np.sin(theta_i) * n1_over_n2
        cos_theta_t = np.sqrt(1.0 - sin_theta_t ** 2)
        cos_theta_i = np.cos(theta_i)

        # TE Polarization (Perpendicular / Horizontal)
        num_te = eta_2 * cos_theta_i - eta_1 * cos_theta_t
        den_te = eta_2 * cos_theta_i + eta_1 * cos_theta_t
        gamma_te = num_te / den_te

        # TM Polarization (Parallel / Vertical)
        num_tm = eta_1 * cos_theta_i - eta_2 * cos_theta_t
        den_tm = eta_1 * cos_theta_i + eta_2 * cos_theta_t
        gamma_tm = num_tm / den_tm

        # Brewster angle theta_b = arctan(sqrt(eps2/eps1)) for non-magnetic media
        brewster_deg = float(np.degrees(np.arctan(np.sqrt(mat.epsilon_r))))

        return gamma_te, gamma_tm, brewster_deg

    @staticmethod
    def knife_edge_diffraction_db(
        height_diff_m: float,
        dist_src_to_edge_m: float,
        dist_edge_to_rx_m: float,
        wavelength_m: float
    ) -> float:
        """
        ITU-R P.526 analytical knife-edge diffraction loss over building roof or corner.
        
        Args:
            height_diff_m: Height of obstacle edge above the line-of-sight ray (m)
            dist_src_to_edge_m: Distance from UAV to obstacle edge (m)
            dist_edge_to_rx_m: Distance from obstacle edge to antenna array (m)
            wavelength_m: RF wavelength in meters
            
        Returns:
            Diffraction attenuation in dB (positive loss >= 0 dB)
        """
        d1 = max(1.0, dist_src_to_edge_m)
        d2 = max(1.0, dist_edge_to_rx_m)
        lam = max(1e-4, wavelength_m)

        # Fresnel-Kirchhoff dimensionless diffraction parameter nu
        nu = float(height_diff_m * np.sqrt(2.0 * (d1 + d2) / (lam * d1 * d2)))

        if nu <= -0.78:
            return 0.0
        
        # Lee approximation of Fresnel integral for ITU-R P.526
        loss_db = 6.9 + 20.0 * np.log10(np.sqrt((nu - 0.1) ** 2 + 1.0) + (nu - 0.1))
        return float(max(0.0, loss_db))

    @classmethod
    def two_ray_ground_reflection(
        cls,
        tx_pos: Tuple[float, float, float],
        rx_pos: Tuple[float, float, float],
        freq_hz: float,
        ground_mat: MaterialProperties
    ) -> Tuple[complex, float]:
        """
        Two-Ray Ground Reflection Model combining direct ray and Fresnel ground bounce.
        
        Returns:
            (composite_gain: complex, total_path_loss_db: float)
        """
        tx_x, tx_y, tx_z = tx_pos
        rx_x, rx_y, rx_z = rx_pos

        dx = tx_x - rx_x
        dz = tx_z - rx_z
        d_ground = float(np.sqrt(dx * dx + dz * dz))

        d_direct = float(np.sqrt(d_ground ** 2 + (tx_y - rx_y) ** 2))
        d_reflected = float(np.sqrt(d_ground ** 2 + (tx_y + rx_y) ** 2))

        # Grazing angle psi relative to ground plane
        psi_rad = np.arctan2(tx_y + rx_y, max(0.1, d_ground))
        incident_angle_deg = 90.0 - float(np.degrees(psi_rad))

        # Complex reflection coefficient for vertical/horizontal composite
        gamma_te, gamma_tm, _ = cls.fresnel_reflection(ground_mat, freq_hz, incident_angle_deg)
        gamma_avg = 0.5 * (gamma_te + gamma_tm)

        wavelength = SPEED_OF_LIGHT / freq_hz
        k0 = 2.0 * np.pi / wavelength

        # Phase difference delta_phi = k0 * (d_reflected - d_direct)
        delta_phi = k0 * (d_reflected - d_direct)

        # Direct ray amplitude and reflected ray amplitude (1/d spherical wave)
        e_direct = 1.0 / max(1.0, d_direct)
        e_refl = (abs(gamma_avg) / max(1.0, d_reflected)) * np.exp(1j * (delta_phi + np.angle(gamma_avg)))

        composite_field = e_direct + e_refl
        comp_power = float(np.abs(composite_field) ** 2)

        # Standard Friis reference
        fspl_db = 20.0 * np.log10(4.0 * np.pi * d_direct / wavelength)
        multipath_factor_db = float(10.0 * np.log10(max(1e-6, comp_power * (d_direct ** 2))))

        total_loss_db = fspl_db - multipath_factor_db
        return composite_field, float(total_loss_db)

