# M-epsf-scalar-sky — INCONCLUSIVE (L3)

# Native residual and blank-sky diagnostics (scalar_sky=True)
```json
{
  "1": {
    "n": 87,
    "median_chi": 4.456420146569782,
    "core_rms": 1.301577295098323,
    "wing_rms": 1.9680282775243187,
    "blank_rms": 7.646606300277495,
    "blank_mad": 2.2542339901406203,
    "chi_flux_spearman": 0.6144018371364,
    "chi_wave_spearman": 0.5513778523000655
  },
  "2": {
    "n": 103,
    "median_chi": 3.571233336582748,
    "core_rms": 1.2994438817594778,
    "wing_rms": 1.8778768091542763,
    "blank_rms": 5.7731677852125225,
    "blank_mad": 2.0965649946091136,
    "chi_flux_spearman": 0.6373061547247727,
    "chi_wave_spearman": 0.055089399464042524
  },
  "3": {
    "n": 101,
    "median_chi": 3.273374628087756,
    "core_rms": 1.055129454924836,
    "wing_rms": 1.7789811085101925,
    "blank_rms": 5.7746974811973075,
    "blank_mad": 2.120995099031698,
    "chi_flux_spearman": 0.5017705299941758,
    "chi_wave_spearman": 0.04281887012230634
  },
  "4": {
    "n": 63,
    "median_chi": 3.6029875333983488,
    "core_rms": 1.1812277310638948,
    "wing_rms": 1.8470082484628063,
    "blank_rms": 5.589518123998044,
    "blank_mad": 2.313523842378846,
    "chi_flux_spearman": 0.6453533026113671,
    "chi_wave_spearman": 0.3001152073732719
  },
  "5": {
    "n": 28,
    "median_chi": 1.4255384851000001,
    "core_rms": 0.8405676626607159,
    "wing_rms": 1.1853456271925182,
    "blank_rms": 1.8102249118489402,
    "blank_mad": 1.2027233356306852,
    "chi_flux_spearman": 0.2326217843459223,
    "chi_wave_spearman": -0.17569786535303775
  },
  "6": {
    "n": 9,
    "median_chi": 1.190670836963472,
    "core_rms": 0.7453454091821313,
    "wing_rms": 1.089054322660399,
    "blank_rms": 1.4364918117040817,
    "blank_mad": 1.1378829096572627,
    "chi_flux_spearman": 0.5166666666666667,
    "chi_wave_spearman": 0.06666666666666667
  }
}
```
All retained field stars; raw residual/pull stamps in attachment. Correlations are descriptive, confounded by zone, brightness and wavelength. Sky tiles can contain unresolved objects, diffuse gradients, Gaia-invisible sources and PSF wings. They do not justify global variance rescaling or a new PSF. F5 remains failed; independent fields/model validation required.

## Metrics

| metric | value | threshold | pass |
|---|---|---|---|

## Caveats

- recorded on a dirty working tree: code_digest identifies the exact code

git d6d2e45 (dirty) · contracts {'spherex.types': '0.1.0', 'http-api': '0.1.0'} · calibration 94e18b883fdc9b28 · author M · reviewer pending
