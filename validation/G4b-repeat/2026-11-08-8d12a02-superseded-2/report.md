# G4b-repeat — INCONCLUSIVE (L3)

# Dedicated field-star repeatability experiment
Native D6 field stars, same release, 3% floor per measurement. Each pair fits its own unknown constant flux (one residual degree of freedom). All eligible pairs retained.
```json
[
  {
    "source_id": 6412592370014523776,
    "release": "qr2",
    "channel_gap": 0.0,
    "fluxes": [
      [
        2217.2153922414686,
        197.0857910640419
      ],
      [
        2039.9327832951249,
        169.99235997721317
      ]
    ],
    "chi2": 0.41403224706452846,
    "dof": 1,
    "inputs": [
      {
        "url": "https://irsa.ipac.caltech.edu/ibe/data/spherex/qr2/level2/2025W18_1B/l2b-v20-2025-240/6/level2_2025W18_1B_0238_1D6_spx_l2b-v20-2025-240.fits",
        "box": "331.10332,-56.80000,0.30829",
        "sha256": "addc961d2bf82bc5bb3509cd5a36deae0d6cbd9f95c8f1774cb98cbe3bf0735d"
      },
      {
        "url": "https://irsa.ipac.caltech.edu/ibe/data/spherex/qr2/level2/2026W18_1A/l2b-v24-2026-124/6/level2_2026W18_1A_0457_2D6_spx_l2b-v24-2026-124.fits",
        "box": "331.10332,-56.80000,0.30829",
        "sha256": "702fd8f6d8a56ac27a6d72d94f89be9135fb907aba6a2eba70c0c653eee2c136"
      }
    ]
  },
  {
    "source_id": 6412595771628639616,
    "release": "qr2",
    "channel_gap": 0.00021435049340908866,
    "fluxes": [
      [
        2085.4026845417693,
        196.12692196124533
      ],
      [
        2307.207410564267,
        167.65022238525682
      ]
    ],
    "chi2": 0.6535483970327077,
    "dof": 1,
    "inputs": [
      {
        "url": "https://irsa.ipac.caltech.edu/ibe/data/spherex/qr2/level2/2025W18_1B/l2b-v20-2025-240/6/level2_2025W18_1B_0238_2D6_spx_l2b-v20-2025-240.fits",
        "box": "331.10332,-56.80000,0.30829",
        "sha256": "550a1a26971e765ae2537151f847c65f4f4c05209a788886668e1cad7bc0a113"
      },
      {
        "url": "https://irsa.ipac.caltech.edu/ibe/data/spherex/qr2/level2/2026W18_1A/l2b-v24-2026-124/6/level2_2026W18_1A_0475_1D6_spx_l2b-v24-2026-124.fits",
        "box": "331.10332,-56.80000,0.30829",
        "sha256": "bb79499c7533ed622604c958e3edf4a1e8e86c1f49156df0716c11d437a71a1f"
      }
    ]
  }
]
```
These are candidate controls, not catalog-certified nonvariables. Sparse one-channel pairs cannot establish full-spectrum reduced chi-square approximately one. No acceptance inferred.

## Metrics

| metric | value | threshold | pass |
|---|---|---|---|
| matched_same_scale_pairs | 2 | same release, matching wavelength, >60 days apart | True |

## Caveats

- recorded on a dirty working tree: code_digest identifies the exact code

git 8d12a02 (dirty) · contracts {'spherex.types': '0.1.0', 'http-api': '0.1.0'} · calibration 94e18b883fdc9b28 · author M · reviewer pending
