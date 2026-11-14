# M-noise-scale — FAIL (L3)

# M-noise-scale — F5 with the VARIANCE plane calibrated on blank sky

Verdict **fail**. F5 rule (`m_native.py`, unchanged): fail if any detector median χ²ᵣ > 3. With VARIANCE: **fail**. With the flag-mask scale (primary; detectors with ≥ 5 judged stars: [1, 2, 3, 5, 6]): **fail**. Residual antisymmetry above 2× its noise level in any judged detector keeps the verdict at best inconclusive.

| D | stars (judged) | s flag mask | s Gaia mask (upper bound) | χ²ᵣ VARIANCE | χ²ᵣ VARIANCE, judged stars | χ²ᵣ flag scale | χ²ᵣ Gaia scale (lower bound) | core / wing pull rms | antisym. / noise | mean core pull |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 87 (34) | 1.206 | 2.254 | 4.46 | 5.23 | 3.59 | 0.96 | 1.14 / 1.79 | 0.273 / 0.121 | -0.31 |
| 2 | 103 (53) | 1.172 | 2.097 | 3.57 | 1.59 | 1.24 | 1.10 | 0.86 / 1.09 | 0.250 / 0.097 | -0.20 |
| 3 | 101 (72) | 1.206 | 2.121 | 3.27 | 2.15 | 1.48 | 1.06 | 0.73 / 1.23 | 0.196 / 0.083 | 0.02 |
| 4 | 63 (0) | — | 2.314 | 3.60 | — | — | 0.92 | — | — | — |
| 5 | 28 (28) | 1.032 | 1.202 | 1.43 | 1.43 | 1.38 | 0.91 | 0.79 / 1.19 | 0.138 / 0.134 | -0.03 |
| 6 | 9 (9) | 1.038 | 1.134 | 1.19 | 1.19 | 1.11 | 0.94 | 0.72 / 1.07 | 0.242 / 0.236 | -0.04 |

Procedure and pre-registered rule: module docstring of `scripts/verify/m_noise_scale.py`.

```json
{
 "summary": {
  "1": {
   "n": 87,
   "n_flag": 34,
   "frames": 3,
   "s_flag_median": 1.2059901612665371,
   "s_gaia_median": 2.2542339901406203,
   "median_rchi2_variance": 4.456420146569784,
   "median_rchi2_flag": 3.5943222249757545,
   "median_rchi2_variance_same_stars": 5.227626343001808,
   "median_rchi2_gaia_upper_bound_scale": 0.9621026246135151,
   "core_pull_rms": 1.1446093671057191,
   "wing_pull_rms": 1.7900207716721122,
   "antisymmetric_rms": 0.2734651669700371,
   "antisymmetric_noise_rms": 0.12126781251816648,
   "mean_core_pull": -0.3086143568477273
  },
  "2": {
   "n": 103,
   "n_flag": 53,
   "frames": 4,
   "s_flag_median": 1.1716911052326626,
   "s_gaia_median": 2.0969004444406,
   "median_rchi2_variance": 3.5716844928040548,
   "median_rchi2_flag": 1.2400794487093263,
   "median_rchi2_variance_same_stars": 1.5937258261922618,
   "median_rchi2_gaia_upper_bound_scale": 1.103913317336754,
   "core_pull_rms": 0.8639974837132707,
   "wing_pull_rms": 1.0945834310719131,
   "antisymmetric_rms": 0.25010456907573003,
   "antisymmetric_noise_rms": 0.09712858623572641,
   "mean_core_pull": -0.19527704688272063
  },
  "3": {
   "n": 101,
   "n_flag": 72,
   "frames": 4,
   "s_flag_median": 1.2063690776215608,
   "s_gaia_median": 2.120652335797123,
   "median_rchi2_variance": 3.272483795270477,
   "median_rchi2_flag": 1.4811127567758047,
   "median_rchi2_variance_same_stars": 2.15092336336565,
   "median_rchi2_gaia_upper_bound_scale": 1.0639711000150431,
   "core_pull_rms": 0.7269750390730237,
   "wing_pull_rms": 1.2276405962410266,
   "antisymmetric_rms": 0.19584136059503873,
   "antisymmetric_noise_rms": 0.08333333333333333,
   "mean_core_pull": 0.01880822694340004
  },
  "4": {
   "n": 63,
   "n_flag": 0,
   "frames": 3,
   "s_flag_median": null,
   "s_gaia_median": 2.313523842378846,
   "median_rchi2_variance": 3.6029875333983488,
   "median_rchi2_flag": null,
   "median_rchi2_variance_same_stars": null,
   "median_rchi2_gaia_upper_bound_scale": 0.9157214357458554
  },
  "5": {
   "n": 28,
   "n_flag": 28,
   "frames": 4,
   "s_flag_median": 1.0320323196577177,
   "s_gaia_median": 1.2021658448640427,
   "median_rchi2_variance": 1.4255384850999997,
   "median_rchi2_flag": 1.377725517321727,
   "median_rchi2_variance_same_stars": 1.4255384850999997,
   "median_rchi2_gaia_upper_bound_scale": 0.906871692806654,
   "core_pull_rms": 0.7879524970119259,
   "wing_pull_rms": 1.19491713719321,
   "antisymmetric_rms": 0.13767869283835044,
   "antisymmetric_noise_rms": 0.1336306209562122,
   "mean_core_pull": -0.027666879008595
  },
  "6": {
   "n": 9,
   "n_flag": 9,
   "frames": 4,
   "s_flag_median": 1.0382737907620303,
   "s_gaia_median": 1.1336967791753474,
   "median_rchi2_variance": 1.1889379575260355,
   "median_rchi2_flag": 1.1149467980818968,
   "median_rchi2_variance_same_stars": 1.1889379575260355,
   "median_rchi2_gaia_upper_bound_scale": 0.9434041921893347,
   "core_pull_rms": 0.7231257625248669,
   "wing_pull_rms": 1.0699613200641356,
   "antisymmetric_rms": 0.24190816007825675,
   "antisymmetric_noise_rms": 0.23570226039551584,
   "mean_core_pull": -0.04080215140197674
  }
 },
 "frames": [
  {
   "frame": "level2_2025W40_1A_0441_1D1_spx_l2b-v20-2025-277.fits",
   "detector": 1,
   "release": "qr2",
   "s_flag": 1.2059901612665371,
   "s_gaia": 2.2542339901406203
  },
  {
   "frame": "level2_2026W35_1A_0375_1D1_spx_l2b-v27-2026-243.fits",
   "detector": 1,
   "release": "qr3",
   "s_flag": NaN,
   "s_gaia": 2.5778787389819886
  },
  {
   "frame": "level2_2026W11_2A_0501_1D2_spx_l2b-v24-2026-094.fits",
   "detector": 2,
   "release": "qr2",
   "s_flag": NaN,
   "s_gaia": 2.866568106606435
  },
  {
   "frame": "level2_2026W34_2A_0233_1D2_spx_l2b-v27-2026-243.fits",
   "detector": 2,
   "release": "qr3",
   "s_flag": NaN,
   "s_gaia": 2.961292363646586
  },
  {
   "frame": "level2_2026W12_1A_0598_4D3_spx_l2b-v24-2026-082.fits",
   "detector": 3,
   "release": "qr2",
   "s_flag": 1.4319261492821842,
   "s_gaia": 2.946262375592654
  },
  {
   "frame": "level2_2026W34_1A_0308_1D3_spx_l2b-v27-2026-243.fits",
   "detector": 3,
   "release": "qr3",
   "s_flag": NaN,
   "s_gaia": 3.2031140845827117
  },
  {
   "frame": "level2_2025W40_1A_0441_1D4_spx_l2b-v20-2025-277.fits",
   "detector": 4,
   "release": "qr2",
   "s_flag": NaN,
   "s_gaia": 2.5742168045966594
  },
  {
   "frame": "level2_2026W35_1A_0375_1D4_spx_l2b-v27-2026-243.fits",
   "detector": 4,
   "release": "qr3",
   "s_flag": NaN,
   "s_gaia": 2.313523842378846
  },
  {
   "frame": "level2_2026W11_2A_0501_1D5_spx_l2b-v24-2026-094.fits",
   "detector": 5,
   "release": "qr2",
   "s_flag": 1.082560644334234,
   "s_gaia": 1.280490127470391
  },
  {
   "frame": "level2_2026W34_2A_0233_2D5_spx_l2b-v27-2026-243.fits",
   "detector": 5,
   "release": "qr3",
   "s_flag": 0.9362482904654337,
   "s_gaia": 1.3199936027271035
  },
  {
   "frame": "level2_2026W12_1A_0598_4D6_spx_l2b-v24-2026-082.fits",
   "detector": 6,
   "release": "qr2",
   "s_flag": 1.0803922243255693,
   "s_gaia": 1.195806278397268
  },
  {
   "frame": "level2_2026W34_1A_0308_1D6_spx_l2b-v27-2026-243.fits",
   "detector": 6,
   "release": "qr3",
   "s_flag": 1.0017439164171713,
   "s_gaia": 1.1805458963849444
  },
  {
   "frame": "level2_2025W46_1A_0287_1D1_spx_l2b-v20-2025-318.fits",
   "detector": 1,
   "release": "qr2",
   "s_flag": NaN,
   "s_gaia": 1.2741086098847387
  },
  {
   "frame": "level2_2025W40_1A_0661_1D2_spx_l2b-v20-2025-277.fits",
   "detector": 2,
   "release": "qr2",
   "s_flag": 1.2445584681293498,
   "s_gaia": 1.2015430034603671
  },
  {
   "frame": "level2_2026W40_1A_0721_2D2_spx_l2b-v27-2026-276.fits",
   "detector": 2,
   "release": "qr3",
   "s_flag": 1.0988237423359757,
   "s_gaia": 1.3272327822747654
  },
  {
   "frame": "level2_2025W40_1A_0067_2D3_spx_l2b-v20-2025-277.fits",
   "detector": 3,
   "release": "qr2",
   "s_flag": 1.2063690776215608,
   "s_gaia": 1.2536347858830421
  },
  {
   "frame": "level2_2026W39_2A_0398_1D3_spx_l2b-v27-2026-271.fits",
   "detector": 3,
   "release": "qr3",
   "s_flag": 1.1056792612472086,
   "s_gaia": 1.2950422960015924
  },
  {
   "frame": "level2_2025W46_1A_0348_1D4_spx_l2b-v20-2025-318.fits",
   "detector": 4,
   "release": "qr2",
   "s_flag": NaN,
   "s_gaia": 1.2809842255346655
  },
  {
   "frame": "level2_2025W40_1A_0661_3D5_spx_l2b-v20-2025-277.fits",
   "detector": 5,
   "release": "qr2",
   "s_flag": 1.0506752280476952,
   "s_gaia": 1.1238415622576943
  },
  {
   "frame": "level2_2026W40_1A_0721_2D5_spx_l2b-v27-2026-276.fits",
   "detector": 5,
   "release": "qr3",
   "s_flag": 1.01338941126774,
   "s_gaia": 1.0970233496316004
  },
  {
   "frame": "level2_2025W40_1A_0067_3D6_spx_l2b-v20-2025-277.fits",
   "detector": 6,
   "release": "qr2",
   "s_flag": 1.032648512682201,
   "s_gaia": 1.0737993384543592
  },
  {
   "frame": "level2_2026W39_2A_0398_1D6_spx_l2b-v27-2026-271.fits",
   "detector": 6,
   "release": "qr3",
   "s_flag": 1.0438990688418595,
   "s_gaia": 1.0868476619657503
  }
 ]
}
```

## Metrics

| metric | value | threshold | pass |
|---|---|---|---|
| D1_median_rchi2_flag_scale | 3.5943222249757545 | <= 3 (m_native.py F5 rule; flag-mask noise scale) | False |
| D2_median_rchi2_flag_scale | 1.2400794487093263 | <= 3 (m_native.py F5 rule; flag-mask noise scale) | True |
| D3_median_rchi2_flag_scale | 1.4811127567758047 | <= 3 (m_native.py F5 rule; flag-mask noise scale) | True |
| D4_median_rchi2_flag_scale | None | <= 3 (m_native.py F5 rule; flag-mask noise scale) | None |
| D5_median_rchi2_flag_scale | 1.377725517321727 | <= 3 (m_native.py F5 rule; flag-mask noise scale) | True |
| D6_median_rchi2_flag_scale | 1.1149467980818968 | <= 3 (m_native.py F5 rule; flag-mask noise scale) | True |
| D1_antisymmetry_over_noise | 2.2550515366892654 | <= 2 (proposed) | False |
| D2_antisymmetry_over_noise | 2.5749841397746516 | <= 2 (proposed) | False |
| D3_antisymmetry_over_noise | 2.350096327140465 | <= 2 (proposed) | False |
| D5_antisymmetry_over_noise | 1.030292996119989 | <= 2 (proposed) | True |
| D6_antisymmetry_over_noise | 1.0263294024941771 | <= 2 (proposed) | True |

## Caveats

- recorded on a dirty working tree: code_digest identifies the exact code

git 3ae8487 (dirty) · contracts {'spherex.types': '0.1.0', 'http-api': '0.1.0'} · calibration 94e18b883fdc9b28 · author M · reviewer pending
