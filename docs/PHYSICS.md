# Physics Notes

## Workflow

1. The input image is thresholded into a binary mask and resized to the mask grid with nearest-neighbor interpolation.
2. Each discrete source point and required incident polarization is passed to EUVlitho/ELitho, which computes the complex vector electromagnetic-field spectrum for the mask and multilayer structure.
3. For each source point, the `Ex`, `Ey`, and `Ez` spectra are mapped to the imaging pupil, defocus phase is applied, and a 2D inverse FFT is used to form fields in the image plane.
4. The three vector components are summed by intensity. Mutually incoherent source points, and the two orthogonal incident polarizations used for unpolarized light, are also summed by intensity. This step is the Abbe imaging model used by this project.

`defocus_nm = 0` represents the ideal focal plane used by the current model. Nonzero `defocus_nm` applies an additional defocus phase and produces an out-of-focus aerial image.

## Multilayer Model

The GUI exposes the period count plus the thickness, `n`, and `k` values for Mo and Si. The complex refractive index is written as `n + ik`, with positive `k` representing absorption. The adapter maps these parameters to ELitho's `NML`, `thickness_mo`, `thickness_si`, `n_mo`, and `n_si` values, then updates the corresponding complex permittivities.

This version is not a general thin-film editor for arbitrary materials or arbitrary layer order. It uses a simplified periodic Mo/Si structure and sets the intermix and cap-layer thicknesses in ELitho's fixed topology to zero. Studying interdiffusion, roughness, cap layers, substrates, or arbitrary stacks requires extending the upstream transfer-matrix interface and adding independent validation.

## Comparison Page

The two results are each divided by the mean intensity of their own blank-mask result. No additional linear amplitude fitting is applied. If grid sizes differ, this project's result is bilinearly resized to the other algorithm result's size. Rotation and interpolation both affect error metrics, so export settings should be recorded with any comparison.

## Validation Still Needed

- Material data sources and wavelength interpolation.
- Coordinate and polarization conventions for high-NA and anamorphic cases.
- Nonzero intermix layers, cap layers, and substrate models.
- Systematic comparison with public benchmarks and other rigorous solvers.
- Performance and memory behavior for large masks.

Reproducible benchmarks and corrections are welcome.
