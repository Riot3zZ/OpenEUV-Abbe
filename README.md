# OpenEUV Abbe

OpenEUV Abbe is a desktop tool for learning and checking EUV lithography aerial-image simulations. The project has only the **Abbe imaging model**: mask near-field and diffraction responses are computed by the strict vector electromagnetic-field solver from [ELitho](https://github.com/takahashi-edalab/elitho), which is referenced by the [EUVlitho](https://github.com/takahashi-edalab/EUVlitho) project, and the returned `Ex/Ey/Ez` components are then accumulated over discrete source points using Abbe imaging.

## 1. Purpose

This software is intended to provide a small, readable, GUI-based EUV aerial-image simulator for educational use, early algorithm checks, and comparison against other imaging results. It is useful when you want to inspect how Abbe imaging changes with illumination, polarization, defocus, absorber parameters, and a simplified periodic Mo/Si multilayer stack while still relying on a strict electromagnetic-field calculation for the mask response.

OpenEUV Abbe is not a calibrated production lithography simulator. It does not model photoresist, post-exposure bake, development, OPC, stochastic effects, scanner-specific calibration, or process-window behavior.

## 2. Default Parameters

The default settings are demonstration values chosen for a small EUV aerial-image test case:

- Wavelength: `13.5 nm`.
- Numerical aperture: `0.33`.
- Magnification: `4x` in X and Y.
- Incidence angle: `-6 deg`; azimuthal angle: `90 deg`.
- Focal condition: ideal focal plane, equivalent to `defocus_nm = 0`.
- Illumination: quadrupole, with `sigma_in = 0.6`, `sigma_out = 0.8`, pole opening `40 deg`, and source mesh `0.5 deg`.
- Polarization: unpolarized.
- Mask grid: `512 nm x 512 nm`; mask threshold: `0.5`.
- Absorber: single layer, `100 nm`, `n = 0.93245`, `k = 0.03888`.
- Multilayer: periodic Mo/Si stack with `40` periods; Mo `2.9 nm`, `n = 0.92108`, `k = 0.00644`; Si `4.0 nm`, `n = 0.99932`, `k = 0.00183`.

These defaults are not recommended process parameters. Treat them as a reproducible starting point, then replace the material, stack, illumination, and numerical settings with values appropriate for your study.

## 3. Suitable Use Cases

- Learning the Abbe imaging workflow for EUV lithography.
- Checking how source shape, polarization, NA, defocus, absorber thickness, or Mo/Si multilayer values affect aerial images.
- Producing small reference examples for code development or teaching.
- Comparing this project's Abbe result with other algorithm results after blank-mask normalization.
- Exploring early research ideas before building a more complete and independently validated simulator.

This project is less suitable for calibrated process prediction, resist-level simulation, equipment qualification, or decisions that require validated industrial accuracy.

> [!IMPORTANT]
> This is a preliminary open-source project. Both the code and the physics model may still contain mistakes or missing assumptions. Issues, Discussions, Pull Requests, reproducible benchmarks, and corrections are very welcome.

OpenEUV Abbe is not an official EUVlitho project and is not endorsed by the EUVlitho or ELitho authors. Upstream copyrights remain with their authors. See [Third-party notices](THIRD_PARTY_NOTICES.md) for attribution, license, and pinned-version information.

## 4. Features

- 2D mask input from PNG/JPG/BMP/TIFF, DAT/TXT, and NPY/NPZ files.
- A single, explicit Abbe imaging workflow.
- Strict vector electromagnetic-field calculation through EUVlitho/ELitho.
- Ideal focal-plane simulation through `defocus_nm = 0`, or out-of-focus simulation through nonzero defocus.
- Circular, annular, and quadrupole illumination.
- Unpolarized, linear, X-polarized, and Y-polarized incident fields.
- Editable periodic Mo/Si multilayer parameters: period count, Mo/Si thicknesses, and each material's `n` and `k`.
- Editable single absorber layer thickness and `n/k`.
- Aerial image, cutline, and source-point visualization.
- PNG, DAT, and JSON export.
- Comparison with other algorithm results, including blank-mask normalization, NRMSE, RMSE, MAE, max error, correlation, difference maps, and cutline plots.

## 5. Installation

OpenEUV Abbe requires Python 3.10+, Git, and a Python build with Tk support. The first installation downloads the pinned ELitho commit from GitHub:

Clone the repository from GitHub, or download and unpack the source archive. Then enter the project directory and create a virtual environment:

```bash
cd open-euv-abbe
python -m venv .venv
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e .
python -m openeuv_abbe
```

Linux/macOS:

```bash
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e .
python -m openeuv_abbe
```

On Windows, after `pip install -e .`, you can also start the program by double-clicking `launch.bat`.

If you already have a local ELitho checkout, set `EUVLITHO_ELITHO_PATH` to that repository root. Record the exact commit used so that results remain reproducible.

## 6. Quick Start

1. On the Simulation tab, choose a mask file. The repository includes the example file `open-euv-abbe/examples/masks/center_rectangle_128.png`.
2. On the Mask/Stack page, edit the absorber and Mo/Si multilayer parameters.
3. Choose illumination, polarization, NA, and numerical settings. Keep `Ideal focal plane (defocus = 0 nm)` enabled for the ideal focal plane, or disable it and set `Defocus [nm]` for an out-of-focus image.
4. Click `Run Simulation`.
5. Export the aerial image and the JSON summary with the full parameter set.
6. For comparison, open the Comparison tab and provide this project's result, another algorithm's result, and the corresponding blank-mask results.

Strict field calculation can require substantial time and memory. Start with a coarse source mesh or a small mask size when checking a new setup.

## 7. Model Scope And Limitations

- Only Abbe aerial imaging is implemented. Photoresist, PEB, development, OPC, and process-window models are outside the current scope.
- The GUI exposes a simplified periodic Mo/Si multilayer based on ELitho's fixed layer topology. Intermix and cap-layer thicknesses in the upstream topology are set to zero.
- The complex refractive index convention is `n + ik`, with positive `k` representing absorption.
- Default numerical values are demonstration starting points, not calibrated parameters for any specific scanner or process.
- Results are intended for learning, research checks, and numerical comparison. They should not be used directly for production decisions.

For implementation details, see [docs/PHYSICS.md](docs/PHYSICS.md).

## 8. Citation And Attribution

If you use, modify, compare against, or cite OpenEUV Abbe, please clearly identify this project by name and provide a link to the repository. Because the strict electromagnetic-field calculation is performed through EUVlitho/ELitho, please also preserve the upstream EUVlitho/ELitho attribution, license notices, and citation information listed in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## 9. Development And Tests

```bash
pip install -e .[dev]
pytest
```

The current tests cover parameter validation, input/output, and comparison logic. Full strict-field simulation is not included in CI because it is computationally heavier; this is one of the current limitations of the preliminary project.

## 10. Contributing

Please read [CONTRIBUTING.md](CONTRIBUTING.md). When reporting an issue, include the operating system, Python version, ELitho commit, full parameter JSON, minimal mask, and expected result whenever possible.

## 11. License

OpenEUV Abbe is released under the [MIT License](LICENSE). EUVlitho and ELitho are also MIT-licensed, with independent copyrights and notices that must be preserved.
