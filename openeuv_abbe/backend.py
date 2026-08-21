"""Computation and file I/O for OpenEUV Abbe."""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable

import matplotlib.image as mpimg
import numpy as np
from scipy.ndimage import zoom

from . import euvlitho_adapter as adapter

ProgressCB = Callable[[float, str], None]


@dataclass
class SimulationParams:
    wavelength_nm: float = 13.5
    na: float = 0.33
    magnification_x: int = 4
    magnification_y: int = 4
    central_obscuration: float = 0.0
    incidence_angle_deg: float = -6.0
    azimuthal_angle_deg: float = 90.0
    defocus_nm: float = 0.0
    illumination: str = "quadrupole"
    sigma_in: float = 0.6
    sigma_out: float = 0.8
    pole_open_angle_deg: float = 40.0
    source_mesh_deg: float = 0.5
    polarization: str = "unpolarized"
    pol_angle_deg: float = 0.0
    mask_width_nm: int = 512
    mask_height_nm: int = 512
    mask_threshold: float = 0.5
    invert_mask: bool = False
    absorber_thickness_nm: float = 100.0
    absorber_n: float = 0.93245
    absorber_k: float = 0.03888
    multilayer_periods: int = 40
    mo_thickness_nm: float = 2.9
    mo_n: float = 0.92108
    mo_k: float = 0.00644
    si_thickness_nm: float = 4.0
    si_n: float = 0.99932
    si_k: float = 0.00183
    cutoff_factor: float = 6.0

    def validate(self) -> None:
        if self.wavelength_nm <= 0:
            raise ValueError("Wavelength must be greater than 0.")
        if not 0 < self.na <= 1:
            raise ValueError("NA must be in the range (0, 1].")
        if self.magnification_x < 1 or self.magnification_y < 1:
            raise ValueError("Magnification must be at least 1.")
        if not 0 <= self.central_obscuration < 1:
            raise ValueError("Central obscuration must be in the range [0, 1).")
        if not 0 <= self.sigma_in <= self.sigma_out:
            raise ValueError("The source parameters must satisfy 0 <= sigma in <= sigma out.")
        if self.mask_width_nm < 1 or self.mask_height_nm < 1:
            raise ValueError("Mask width and height must be positive integers.")
        if not 0 <= self.mask_threshold <= 1:
            raise ValueError("Mask threshold must be in the range [0, 1].")
        if self.multilayer_periods < 1:
            raise ValueError("Multilayer period count must be at least 1.")
        if min(self.mo_thickness_nm, self.si_thickness_nm, self.absorber_thickness_nm) <= 0:
            raise ValueError("Multilayer and absorber thicknesses must be greater than 0.")
        if min(self.mo_n, self.mo_k, self.si_n, self.si_k, self.absorber_n, self.absorber_k) < 0:
            raise ValueError("Material n and k values cannot be negative.")


@dataclass
class SimulationResult:
    method: str
    image: np.ndarray
    cutline: np.ndarray
    x_nm: np.ndarray
    cutline_axis: str
    cutline_index: int
    timings_s: dict[str, float]
    summary: dict[str, Any]


def _read_raster_dat(path: Path) -> np.ndarray:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    marker = next((i for i, line in enumerate(lines) if line.strip().lower().startswith("array_2d:")), None)
    if marker is None:
        for delimiter in (None, ","):
            try:
                return np.loadtxt(path, dtype=float, delimiter=delimiter)
            except ValueError:
                pass
        raise ValueError(f"Could not read a 2D numeric file: {path}")
    dimensions = lines[marker].split(":", 1)[1].split()
    width, height = int(dimensions[0]), int(dimensions[1])
    values = np.fromstring(" ".join(lines[marker + 1 :]), sep=" ")
    if values.size != width * height:
        raise ValueError(f"DAT contains {values.size} values; expected {width * height}.")
    return values.reshape((height, width))


def load_image_array(path: Path) -> np.ndarray:
    suffix = path.suffix.lower()
    if suffix in (".dat", ".txt"):
        array = _read_raster_dat(path)
    elif suffix == ".npy":
        array = np.load(path)
    elif suffix == ".npz":
        data = np.load(path, allow_pickle=False)
        for key in ("image", "aerial_image", "abbe_image", "arr_0"):
            if key in data:
                array = data[key]
                break
        else:
            raise ValueError(f"No recognized image array was found in {path}.")
    else:
        array = mpimg.imread(path)
        if array.ndim == 3:
            array = array[..., :3].mean(axis=2)
    array = np.asarray(array, dtype=float)
    if array.ndim != 2:
        raise ValueError("Input must be a 2D image or a 2D numeric matrix.")
    if array.max(initial=0.0) > 1.5 and suffix not in (".dat", ".txt", ".npy", ".npz"):
        array /= 255.0
    return array


def _resize(array: np.ndarray, shape: tuple[int, int], order: int) -> np.ndarray:
    if array.shape == shape:
        return array.astype(float)
    return zoom(array, (shape[0] / array.shape[0], shape[1] / array.shape[1]), order=order).astype(float)


def read_mask(path: Path, shape: tuple[int, int], threshold: float, invert: bool) -> np.ndarray:
    array = load_image_array(path)
    if array.max(initial=0.0) > 1.5:
        array = array / 255.0
    mask = (array > threshold).astype(float)
    return _resize(1.0 - mask if invert else mask, shape, order=0)


def _make_config(config_mod, params: SimulationParams, illumination, absorber_layers):
    return config_mod.SimulationConfig(
        wavelength=params.wavelength_nm,
        NA=params.na,
        is_high_na=params.na >= 0.5,
        illumination=illumination,
        absorber_layers=absorber_layers,
        mask_width=int(params.mask_width_nm),
        mask_height=int(params.mask_height_nm),
        magnification_x=int(params.magnification_x),
        magnification_y=int(params.magnification_y),
        mesh=params.source_mesh_deg,
        incidence_angle=params.incidence_angle_deg,
        azimuthal_angle=params.azimuthal_angle_deg,
        central_obscuration=params.central_obscuration,
        defocus_min=params.defocus_nm,
    )


def _prepare(params: SimulationParams):
    params.validate()
    modules = adapter.import_elitho()
    config_mod, _intensity, source_mod, *_ = modules
    multilayer_meta = adapter.apply_multilayer(config_mod, params)
    absorber_layers, absorber_meta = adapter.make_absorber_layers(config_mod, params)
    families = adapter.make_source_families(config_mod, params.illumination, params.sigma_in, params.sigma_out, params.pole_open_angle_deg)
    configs = [_make_config(config_mod, params, family.illumination, absorber_layers) for family in families]
    counts = [adapter.source_count(source_mod, config) for config in configs]
    total = int(sum(family.nominal_weight * count for family, count in zip(families, counts)))
    if total <= 0:
        raise RuntimeError("The current parameters did not produce any valid source points.")
    weights = [family.nominal_weight * count / total for family, count in zip(families, counts)]
    return modules, families, configs, counts, weights, multilayer_meta, absorber_meta


def source_preview(params: SimulationParams) -> dict[str, Any]:
    modules, families, configs, counts, _weights, _ml, _absorber = _prepare(params)
    source_mod = modules[2]
    all_u, all_v, labels = [], [], []
    for family, config, count in zip(families, configs, counts):
        dkx, dky, *_ = source_mod.get_valid_source_points(config)
        all_u.append(np.asarray(dkx) / (config.k * config.NA))
        all_v.append(np.asarray(dky) / (config.k * config.NA))
        labels.extend([family.name] * count)
    return {
        "u": np.concatenate(all_u), "v": np.concatenate(all_v),
        "family": np.asarray(labels, dtype=object),
        "counts": dict(zip([family.name for family in families], counts)),
        "total_points": int(sum(counts)), "sigma_in": params.sigma_in,
        "sigma_out": params.sigma_out, "source_mesh_deg": params.source_mesh_deg,
        "illumination": params.illumination, "pole_open_angle_deg": params.pole_open_angle_deg,
    }


def make_cutline(image: np.ndarray, axis: str, index: int | None):
    height, width = image.shape
    if axis == "x":
        selected = height // 2 if index is None else int(np.clip(index, 0, height - 1))
        values = image[selected, :]
        coordinate = np.arange(width) - (width - 1) / 2.0
    else:
        selected = width // 2 if index is None else int(np.clip(index, 0, width - 1))
        values = image[:, selected]
        coordinate = np.arange(height) - (height - 1) / 2.0
    return coordinate, values, selected


def run_simulation(mask_path: Path, params: SimulationParams, cutline_axis: str = "x", cutline_index: int | None = None, progress: ProgressCB | None = None) -> SimulationResult:
    """Run strict vector electromagnetic fields followed by Abbe imaging."""
    progress = progress or (lambda _pct, _message: None)
    started = time.perf_counter()
    progress(3, "Loading the EUVlitho/ELitho strict electromagnetic-field solver...")
    modules, families, configs, counts, weights, multilayer_meta, absorber_meta = _prepare(params)
    config_mod, intensity_mod, *_ = modules
    mask_shape = (configs[0].mask_width, configs[0].mask_height)
    image_shape = (configs[0].exposure_field_width, configs[0].exposure_field_height)
    progress(8, f"Reading and resizing the mask to {mask_shape[0]} x {mask_shape[1]}...")
    mask = read_mask(mask_path, mask_shape, params.mask_threshold, params.invert_mask)
    need_x = params.polarization in ("x", "linear", "unpolarized")
    need_y = params.polarization in ("y", "linear", "unpolarized")
    jobs = len(families) * (int(need_x) + int(need_y))
    completed = 0
    all_rows: list[np.ndarray] = []
    timings: dict[str, float] = {}
    for family, config, count, weight in zip(families, configs, counts, weights):
        efield_x = efield_y = None
        if need_x:
            progress(10 + 58 * completed / jobs, f"{family.name}: solving strict electromagnetic fields for X polarization ({count} source points)...")
            t0 = time.perf_counter()
            efield_x = intensity_mod.compute_electric_fields(config, mask, config_mod.PolarizationDirection.X, params.cutoff_factor)
            timings[f"{family.name}_x_efield_s"] = time.perf_counter() - t0
            completed += 1
        if need_y:
            progress(10 + 58 * completed / jobs, f"{family.name}: solving strict electromagnetic fields for Y polarization ({count} source points)...")
            t0 = time.perf_counter()
            efield_y = intensity_mod.compute_electric_fields(config, mask, config_mod.PolarizationDirection.Y, params.cutoff_factor)
            timings[f"{family.name}_y_efield_s"] = time.perf_counter() - t0
            completed += 1
        all_rows.append(adapter.build_frequency_rows(config, modules, efield_x, efield_y, weight, params.polarization, params.pol_angle_deg, params.defocus_nm, params.cutoff_factor))
    progress(78, "Accumulating source points and vector components with Abbe incoherent imaging...")
    rows = np.vstack(all_rows)
    t0 = time.perf_counter()
    image = adapter.image_from_frequency_rows(rows, image_shape)
    timings["abbe_imaging_s"] = time.perf_counter() - t0
    timings["total_s"] = time.perf_counter() - started
    pixel_size_nm = (params.mask_width_nm / params.magnification_x) / image_shape[1]
    coordinate, cutline, selected = make_cutline(image, cutline_axis, cutline_index)
    coordinate *= pixel_size_nm
    summary = {
        "project": "OpenEUV Abbe", "solver": "EUVlitho/ELitho strict electromagnetic-field solver",
        "imaging_model": "Abbe", "params": asdict(params), "mask_path": str(mask_path),
        "mask_shape": list(mask_shape), "image_shape": list(image_shape),
        "source_counts": dict(zip([family.name for family in families], counts)),
        "total_source_points": int(sum(counts)), "frequency_response_shape": list(rows.shape),
        "multilayer": multilayer_meta, "absorber": absorber_meta,
    }
    progress(100, "Abbe imaging complete")
    return SimulationResult("Abbe", image, cutline, coordinate, cutline_axis, selected, timings, summary)


def save_png(path: Path, image: np.ndarray, cmap: str = "jet") -> None:
    import matplotlib.pyplot as plt
    path.parent.mkdir(parents=True, exist_ok=True)
    plt.imsave(path, image, cmap=cmap)


def save_dat(path: Path, image: np.ndarray, pixel_size_nm: float = 1.0) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    height, width = image.shape
    x0, x1 = -((width - 1) / 2) * pixel_size_nm / 1000, ((width - 1) / 2) * pixel_size_nm / 1000
    y0, y1 = -((height - 1) / 2) * pixel_size_nm / 1000, ((height - 1) / 2) * pixel_size_nm / 1000
    with path.open("w", encoding="utf-8") as stream:
        stream.write("# OpenEUV Abbe RasterData2D\nDataType: Image\nDataUnit: Intensity\n")
        stream.write(f"Corner_1: {x0:.12g} {y0:.12g} 0\nCorner_2: {x1:.12g} {y0:.12g} 0\n")
        stream.write(f"Corner_3: {x0:.12g} {y1:.12g} 0\nArray_2D: {width} {height}\n")
        for row in image:
            stream.write(" ".join(f"{value:.12g}" for value in row) + "\n")


def save_summary(path: Path, result: SimulationResult) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {**result.summary, "timings_s": result.timings_s, "image_stats": {
        "min": float(np.min(result.image)), "max": float(np.max(result.image)), "mean": float(np.mean(result.image)),
    }}
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _nrmse(candidate: np.ndarray, reference: np.ndarray) -> float:
    denominator = float(np.max(reference) - np.min(reference))
    rmse = float(np.sqrt(np.mean((candidate - reference) ** 2)))
    return rmse / denominator if denominator > np.finfo(float).eps else rmse


def compare_result_images(project_path: Path, other_path: Path, project_blank_path: Path, other_blank_path: Path, rotate_project_k: int = 0, rotate_other_k: int = 0, cutline_axis: str = "x", cutline_index: int | None = None) -> dict[str, Any]:
    """Compare this project's image with a result produced by another algorithm."""
    project = np.rot90(load_image_array(project_path), rotate_project_k)
    other = np.rot90(load_image_array(other_path), rotate_other_k)
    project_blank = np.rot90(load_image_array(project_blank_path), rotate_project_k)
    other_blank = np.rot90(load_image_array(other_blank_path), rotate_other_k)
    project = _resize(project, other.shape, 1)
    project_blank = _resize(project_blank, other.shape, 1)
    other_blank = _resize(other_blank, other.shape, 1)
    project_mean, other_mean = float(np.mean(project_blank)), float(np.mean(other_blank))
    if abs(project_mean) <= np.finfo(float).eps or abs(other_mean) <= np.finfo(float).eps:
        raise ValueError("Blank-mask mean intensity cannot be zero.")
    project_norm, other_norm = project / project_mean, other / other_mean
    difference = project_norm - other_norm
    coordinate, project_cutline, selected = make_cutline(project_norm, cutline_axis, cutline_index)
    _, other_cutline, _ = make_cutline(other_norm, cutline_axis, selected)
    return {
        "project_norm": project_norm, "other_norm": other_norm, "diff": difference,
        "coord_nm": coordinate, "project_cutline": project_cutline, "other_cutline": other_cutline,
        "cutline_index": selected,
        "metrics": {
            "nrmse_percent": 100 * _nrmse(project_norm, other_norm),
            "rmse": float(np.sqrt(np.mean(difference**2))), "mae": float(np.mean(np.abs(difference))),
            "max_abs": float(np.max(np.abs(difference))),
            "corr": float(np.corrcoef(project_norm.ravel(), other_norm.ravel())[0, 1]),
            "project_blank_mean": project_mean, "other_blank_mean": other_mean,
            "project_blank_cv_percent": float(np.std(project_blank) / abs(project_mean) * 100),
            "other_blank_cv_percent": float(np.std(other_blank) / abs(other_mean) * 100),
            "shape": list(other.shape),
        },
    }
