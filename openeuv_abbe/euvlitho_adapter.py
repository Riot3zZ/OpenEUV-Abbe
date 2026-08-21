"""Thin adapter from OpenEUV Abbe to the ELitho solver in EUVlitho.

The electromagnetic field calculation is performed by the upstream ELitho
code.  This module only translates GUI parameters and assembles the vector
Abbe intensity from the returned complex electric fields.
"""

from __future__ import annotations

import importlib
import math
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType

import numpy as np


@dataclass(frozen=True)
class SourceFamily:
    name: str
    illumination: object
    nominal_weight: float = 1.0


def import_elitho() -> tuple[ModuleType, ...]:
    """Import ELitho, with optional local checkout support for developers."""
    candidates: list[Path] = []
    configured = os.environ.get("EUVLITHO_ELITHO_PATH")
    if configured:
        candidates.append(Path(configured).expanduser())
    # Convenient fallback for the original research workspace layout.
    candidates.append(Path(__file__).resolve().parents[2] / "external_elitho")
    for candidate in candidates:
        if (candidate / "elitho").is_dir() and str(candidate) not in sys.path:
            sys.path.insert(0, str(candidate))
            break

    try:
        modules = tuple(
            importlib.import_module(f"elitho.{name}")
            for name in ("config", "intensity", "source", "descriptors", "diffraction_order", "pupil")
        )
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "The ELitho solver from EUVlitho was not found. Run pip install -e ., "
            "or set EUVLITHO_ELITHO_PATH to the elitho repository."
        ) from exc
    return modules


def make_source_families(config_mod, name: str, sigma_in: float, sigma_out: float, opening: float):
    key = name.lower()
    if key == "circular":
        return [SourceFamily("circular", config_mod.CircularIllumination(outer_sigma=sigma_out))]
    if key == "annular":
        return [SourceFamily("annular", config_mod.AnnularIllumination(inner_sigma=sigma_in, outer_sigma=sigma_out))]
    if key == "quadrupole":
        return [
            SourceFamily(
                "dipole_x",
                config_mod.DipoleIllumination(
                    type=config_mod.IlluminationType.DIPOLE_X,
                    inner_sigma=sigma_in,
                    outer_sigma=sigma_out,
                    open_angle=opening,
                ),
            ),
            SourceFamily(
                "dipole_y",
                config_mod.DipoleIllumination(
                    type=config_mod.IlluminationType.DIPOLE_Y,
                    inner_sigma=sigma_in,
                    outer_sigma=sigma_out,
                    open_angle=opening,
                ),
            ),
        ]
    raise ValueError(f"Unsupported illumination type: {name}")


def source_count(source_mod, simulation_config) -> int:
    _l0s, _m0s, divisions = source_mod.abbe_division_sampling(simulation_config)
    return int(sum(divisions.values()))


def apply_multilayer(config_mod, params) -> dict:
    """Apply the editable periodic Mo/Si mirror to ELitho's global constants."""
    values = (
        params.multilayer_periods,
        params.mo_thickness_nm,
        params.mo_n,
        params.mo_k,
        params.si_thickness_nm,
        params.si_n,
        params.si_k,
    )
    if params.multilayer_periods < 1:
        raise ValueError("Multilayer period count must be at least 1.")
    if params.mo_thickness_nm <= 0 or params.si_thickness_nm <= 0:
        raise ValueError("Mo/Si layer thickness must be greater than 0.")
    if not all(np.isfinite(float(v)) for v in values):
        raise ValueError("Multilayer parameters must be finite numbers.")
    if min(params.mo_n, params.mo_k, params.si_n, params.si_k) < 0:
        raise ValueError("n and k values cannot be negative.")

    config_mod.NML = int(params.multilayer_periods)
    config_mod.n_mo = complex(params.mo_n, params.mo_k)
    config_mod.n_si = complex(params.si_n, params.si_k)
    config_mod.thickness_mo = float(params.mo_thickness_nm)
    config_mod.thickness_si = float(params.si_thickness_nm)

    # The upstream solver has fixed slots for intermix/cap layers. Setting their
    # thicknesses to zero yields the user-facing periodic Mo/Si model.
    config_mod.thickness_mo_si = 0.0
    config_mod.thickness_si_mo = 0.0
    config_mod.thickness_si_ru = 0.0
    config_mod.thickness_ru = 0.0
    config_mod.n_mo_si2 = config_mod.n_mo
    config_mod.n_ru = config_mod.n_si
    config_mod.n_ru_si = config_mod.n_si
    config_mod.n_si_o2 = config_mod.n_si
    for name in ("mo", "si", "mo_si2", "ru", "ru_si", "si_o2"):
        setattr(config_mod, f"epsilon_{name}", getattr(config_mod, f"n_{name}") ** 2)

    return {
        "model": "periodic_mo_si",
        "periods": int(params.multilayer_periods),
        "mo": {"thickness_nm": float(params.mo_thickness_nm), "n": float(params.mo_n), "k": float(params.mo_k)},
        "si": {"thickness_nm": float(params.si_thickness_nm), "n": float(params.si_n), "k": float(params.si_k)},
    }


def make_absorber_layers(config_mod, params):
    if params.absorber_thickness_nm <= 0:
        raise ValueError("Absorber thickness must be greater than 0.")
    if min(params.absorber_n, params.absorber_k) < 0:
        raise ValueError("Absorber n and k values cannot be negative.")
    layers = config_mod.AbsorberLayers(
        thicknesses=[float(params.absorber_thickness_nm)],
        complex_refractive_indices=[complex(params.absorber_n, params.absorber_k)],
    )
    return layers, {
        "layers": [{
            "thickness_nm": float(params.absorber_thickness_nm),
            "n": float(params.absorber_n),
            "k": float(params.absorber_k),
        }]
    }


def build_frequency_rows(
    simulation_config,
    modules,
    efield_x,
    efield_y,
    family_weight: float,
    polarization: str,
    polarization_angle_deg: float,
    defocus_nm: float,
    cutoff_factor: float,
) -> np.ndarray:
    """Convert ELitho fields to incoherently weighted vector-Abbe rows."""
    _config, _intensity, source, descriptors, diffraction_order, pupil = modules
    l0s, m0s, divisions = source.abbe_division_sampling(simulation_config)
    source_sum = int(sum(divisions.values()))
    if source_sum == 0:
        raise RuntimeError("The current illumination has no valid source points.")
    descriptor = descriptors.DiffractionOrderDescriptor(simulation_config, cutoff_factor)
    coordinates = diffraction_order.DiffractionOrderCoordinate(
        descriptor.max_diffraction_order_x,
        descriptor.max_diffraction_order_y,
        diffraction_order.rounded_diamond,
    )
    shape = (simulation_config.exposure_field_width, simulation_config.exposure_field_height)
    rows: list[np.ndarray] = []
    pol = polarization.lower()
    theta = math.radians(polarization_angle_deg)

    for nsx in range(-simulation_config.ndivX + 1, simulation_config.ndivX):
        for nsy in range(-simulation_config.ndivY + 1, simulation_config.ndivY):
            count = divisions[(nsx, nsy)]
            if count == 0:
                continue
            pupil_coords = pupil.PupilCoordinates(simulation_config, coordinates.num_valid_diffraction_orders, nsx, nsy)
            data_x = efield_x.get((nsx, nsy)) if efield_x is not None else None
            data_y = efield_y.get((nsx, nsy)) if efield_y is not None else None
            for index in range(count):
                offset_x = simulation_config.dkx * nsx / simulation_config.ndivX + simulation_config.dkx * l0s[(nsx, nsy)][index]
                offset_y = simulation_config.dky * nsy / simulation_config.ndivY + simulation_config.dky * m0s[(nsx, nsy)][index]
                if pol == "linear":
                    if data_x is None or data_y is None:
                        raise RuntimeError("Linear polarization requires both X and Y electromagnetic fields.")
                    components = [
                        math.cos(theta) * data_x[j][index] + math.sin(theta) * data_y[j][index]
                        for j in range(3)
                    ]
                    _append_rows(rows, simulation_config, pupil_coords, components, offset_x, offset_y, defocus_nm, family_weight / source_sum, shape)
                else:
                    if pol == "x":
                        field_sets = [(1.0, data_x)]
                    elif pol == "y":
                        field_sets = [(1.0, data_y)]
                    elif pol == "unpolarized":
                        field_sets = [(math.sqrt(0.5), data_x), (math.sqrt(0.5), data_y)]
                    else:
                        raise ValueError(f"Unsupported polarization type: {polarization}")
                    for scale, data in field_sets:
                        if data is None:
                            raise RuntimeError("The required polarized electromagnetic field was not generated.")
                        components = [scale * data[j][index] for j in range(3)]
                        _append_rows(rows, simulation_config, pupil_coords, components, offset_x, offset_y, defocus_nm, family_weight / source_sum, shape)
    return np.asarray(rows, dtype=np.complex128)


def _append_rows(rows, sc, pupil_coords, components, offset_x, offset_y, defocus, source_weight, shape):
    grids = [np.zeros(shape, dtype=np.complex128) for _ in range(3)]
    for index in range(pupil_coords.n_coordinates):
        kxn = offset_x + sc.dkx * pupil_coords.linput[index]
        kyn = offset_y + sc.dky * pupil_coords.minput[index]
        pupil_radius_sq = sc.magnification_x**2 * kxn**2 + sc.magnification_y**2 * kyn**2
        lower_ok = (sc.NA * sc.k * sc.central_obscuration) ** 2 <= pupil_radius_sq if sc.is_high_na else True
        if not lower_ok or pupil_radius_sq > (sc.NA * sc.k) ** 2:
            continue
        phase = np.exp(
            1j * ((kxn + sc.kx0) ** 2 + (kyn + sc.ky0) ** 2) / (2.0 * sc.k) * sc.absorber_layers.z_ref_from_abs_top
            + 1j * pupil_radius_sq / (2.0 * sc.k) * defocus
        )
        px = (pupil_coords.linput[index] + shape[0]) % shape[0]
        py = (pupil_coords.minput[index] + shape[1]) % shape[1]
        for component, grid in zip(components, grids):
            grid[px, py] = component[index] * phase
    scale = math.sqrt(source_weight)
    rows.extend((scale * grid).reshape(-1, order="F") for grid in grids)


def image_from_frequency_rows(rows: np.ndarray, shape: tuple[int, int]) -> np.ndarray:
    image = np.zeros(shape, dtype=np.float64)
    for row in rows:
        field = np.fft.ifft2(row.reshape(shape, order="F"), norm="forward")
        image += np.abs(field) ** 2
    return image
