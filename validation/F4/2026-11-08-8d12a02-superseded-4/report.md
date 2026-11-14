# F4 — INCONCLUSIVE (L3)

# F4 empirical comparison
Header states multiplicative. Native D6 fits, wavelengths within 0.1 CBAND; no spectral colour correction.
```json
[
  {
    "source_id": 6412595771628639616,
    "channel_gap": 0.013574586467161118,
    "qr2_flux": [
      2.6832501443779466,
      0.18795726988567765
    ],
    "qr3_flux": [
      2.89363488654267,
      0.20960501756707753
    ],
    "factor": 0.9813380241394043,
    "uncorrected_ratio": 0.9272939571114681,
    "multiplied_ratio": 0.9099888196681777,
    "divided_ratio": 0.944928184072628,
    "qr2_path": "C:\\Users\\iamda\\Nasa-Space-Apps-2026\\.cache\\m-acceptance\\frames\\ce\\ce8253e0df0d8b4505ada87439ac6ac0b3a6e75f_20e68b65817b.fits",
    "qr3_path": "C:\\Users\\iamda\\Nasa-Space-Apps-2026\\.cache\\m-acceptance\\frames\\a3\\a375770faea15b5db1216ecb3680de5fb0dca7dd_20e68b65817b.fits"
  }
]
```
F5 residual failure and independent I review remain separate gate dependencies.

## Metrics

| metric | value | threshold | pass |
|---|---|---|---|
| matched_pairs | 1 | at least one isolated star at matching wavelength | True |
| multiplication_improves | False | corrected QR2 agrees better with QR3 | False |

## Caveats

- recorded on a dirty working tree: code_digest identifies the exact code

git 8d12a02 (dirty) · contracts {'spherex.types': '0.1.0', 'http-api': '0.1.0'} · calibration 94e18b883fdc9b28 · author M · reviewer pending
