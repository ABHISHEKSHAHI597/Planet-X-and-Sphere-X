# M-epsf-residuals — INCONCLUSIVE (L3)

# Native residual and blank-sky diagnostics
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
    "median_chi": 3.5716844928040556,
    "core_rms": 1.299440321181809,
    "wing_rms": 1.8778768091542763,
    "blank_rms": 5.773095576621162,
    "blank_mad": 2.0969004444406,
    "chi_flux_spearman": 0.6351535386372623,
    "chi_wave_spearman": 0.08901506831261258
  },
  "3": {
    "n": 101,
    "median_chi": 3.272483795270477,
    "core_rms": 1.055129454924836,
    "wing_rms": 1.7789672255746263,
    "blank_rms": 5.7743035801232985,
    "blank_mad": 2.120652335797123,
    "chi_flux_spearman": 0.5017821782178218,
    "chi_wave_spearman": 0.04194525334886429
  },
  "4": {
    "n": 63,
    "median_chi": 3.6029875333983488,
    "core_rms": 1.1812277310638948,
    "wing_rms": 1.8470082483453858,
    "blank_rms": 5.589518123998044,
    "blank_mad": 2.313523842378846,
    "chi_flux_spearman": 0.6453533026113671,
    "chi_wave_spearman": 0.3001152073732719
  },
  "5": {
    "n": 28,
    "median_chi": 1.4255384851000004,
    "core_rms": 0.8405849002402734,
    "wing_rms": 1.1853456271925182,
    "blank_rms": 1.8102179312920192,
    "blank_mad": 1.2021658448640427,
    "chi_flux_spearman": 0.2326217843459223,
    "chi_wave_spearman": -0.17569786535303775
  },
  "6": {
    "n": 9,
    "median_chi": 1.1889379575260355,
    "core_rms": 0.7467347431753928,
    "wing_rms": 1.0882595045267076,
    "blank_rms": 1.4359468267934203,
    "blank_mad": 1.1336967791753474,
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
