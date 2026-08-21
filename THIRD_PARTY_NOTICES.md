# Third-party Notices

## EUVlitho / ELitho

OpenEUV Abbe explicitly references and calls the following upstream open-source projects for strict electromagnetic-field simulation:

- EUVlitho: <https://github.com/takahashi-edalab/EUVlitho>
- ELitho, the lithography simulation solver referenced by the EUVlitho README: <https://github.com/takahashi-edalab/elitho>
- Default pinned ELitho commit used by this project: `d9895cabe0557ab144d1cd0566e65888c215a7d1`
- Upstream license: MIT
- EUVlitho license copyright notice: Copyright (c) 2024 Hiroyoshi Tanabe
- ELitho pinned-version license copyright notice: Copyright (c) 2026 Hiroyoshi Tanabe
- Upstream strict electromagnetic-field paper: H. Tanabe, M. Shimode and A. Takahashi, "Rigorous electromagnetic simulator for extreme ultraviolet lithography and convolutional neural network reproducing electromagnetic simulations," *Journal of Micro/Nanopatterning, Materials, and Metrology* 24(2), 024201 (2025), <https://doi.org/10.1117/1.JMM.24.2.024201>

The file `openeuv_abbe/euvlitho_adapter.py` contains this project's parameter adapter and Abbe intensity assembly code. The strict vector electromagnetic field of the mask is computed by the upstream `elitho` package. This repository does not copy the ELitho source code; installation downloads the pinned commit from the official GitHub repository through `pyproject.toml`.

If this project is used in research or a publication, please also check the upstream repositories for their latest citation, paper, and license requirements, and cite the exact version that was actually used.

OpenEUV Abbe is not officially affiliated with or endorsed by the EUVlitho/ELitho authors or maintainers.

If OpenEUV Abbe is used as a reference, dependency, comparison target, or basis for another project, please clearly state that OpenEUV Abbe was used and include the repository link together with the EUVlitho/ELitho attribution above.
