from pathlib import Path

import numpy as np
import pytest

from openeuv_abbe.backend import SimulationParams, compare_result_images, load_image_array, save_dat


def test_default_params_validate():
    SimulationParams().validate()


@pytest.mark.parametrize(
    "kwargs",
    [
        {"wavelength_nm": 0},
        {"na": 1.1},
        {"sigma_in": 0.9, "sigma_out": 0.8},
        {"mask_threshold": -0.1},
        {"multilayer_periods": 0},
        {"mo_thickness_nm": 0},
        {"si_k": -0.1},
    ],
)
def test_invalid_params(kwargs):
    with pytest.raises(ValueError):
        SimulationParams(**kwargs).validate()


def test_dat_round_trip(tmp_path: Path):
    expected = np.arange(12, dtype=float).reshape(3, 4)
    path = tmp_path / "image.dat"
    save_dat(path, expected, pixel_size_nm=2.0)
    np.testing.assert_allclose(load_image_array(path), expected)


def test_comparison_uses_independent_blank_normalization(tmp_path: Path):
    project = np.array([[1.0, 2.0], [3.0, 4.0]])
    other = project * 7.0
    for name, array in {
        "project.npy": project,
        "project_blank.npy": np.full((2, 2), 2.0),
        "other.npy": other,
        "other_blank.npy": np.full((2, 2), 14.0),
    }.items():
        np.save(tmp_path / name, array)
    result = compare_result_images(
        tmp_path / "project.npy",
        tmp_path / "other.npy",
        tmp_path / "project_blank.npy",
        tmp_path / "other_blank.npy",
    )
    np.testing.assert_allclose(result["diff"], 0.0)
    assert result["metrics"]["rmse"] == pytest.approx(0.0)
