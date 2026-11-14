# F4 — INCONCLUSIVE (L3)

# F4 empirical comparison
Header states multiplicative. Native D6 Fnu (microJy, position-dependent pixel area), wavelengths within 0.1 CBAND; no spectral colour correction.
```json
[
  {
    "source_id": 6412595771628639616,
    "channel_gap": 0.013574586467161118,
    "qr2_flux": [
      2422.902248975232,
      169.72032699650822
    ],
    "qr3_flux": [
      2603.586447526548,
      188.59490034806774
    ],
    "factor": 0.9813380241394043,
    "uncorrected_ratio": 0.9306018055505823,
    "multiplied_ratio": 0.9132349371195705,
    "divided_ratio": 0.9482989374295205,
    "qr2_path": "C:\\Users\\iamda\\Nasa-Space-Apps-2026\\.cache\\m-acceptance\\frames\\ce\\ce8253e0df0d8b4505ada87439ac6ac0b3a6e75f_20e68b65817b.fits",
    "qr3_path": "C:\\Users\\iamda\\Nasa-Space-Apps-2026\\.cache\\m-acceptance\\frames\\a3\\a375770faea15b5db1216ecb3680de5fb0dca7dd_20e68b65817b.fits",
    "inputs": [
      {
        "url": "https://irsa.ipac.caltech.edu/ibe/data/spherex/qr2/level2/2026W18_2A/l2b-v24-2026-125/6/level2_2026W18_2A_0174_2D6_spx_l2b-v24-2026-125.fits",
        "box": "331.10332,-56.80000,0.30829",
        "sha256": "565710f17518dc22855fa452c4c491019f8222e395970e2451a7019a71685450"
      },
      {
        "url": "https://irsa.ipac.caltech.edu/ibe/data/spherex/qr3/level2/2026W39_2A/l2b-v27-2026-271/6/level2_2026W39_2A_0312_3D6_spx_l2b-v27-2026-271.fits",
        "box": "331.10332,-56.80000,0.30829",
        "sha256": "c025326508a8f675fc675c8d0cb7ddccd51d0d90dbacb859be95e7af5dfd78ba"
      }
    ]
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

git d6d2e45 (dirty) · contracts {'spherex.types': '0.1.0', 'http-api': '0.1.0'} · calibration 94e18b883fdc9b28 · author M · reviewer pending
