# M-wise-motion-diagnostic — INCONCLUSIVE (L3)

# Retained native WISE motion audit
```json
{
  "visits": [
    {
      "visit": "V2",
      "n": 3,
      "mjd": 60990.70289362767,
      "mean": [
        -1.099000489644975,
        -0.24985677225140587
      ],
      "predicted": [
        0.0792668485863989,
        0.003569361800474416
      ],
      "covariance": [
        [
          0.39343887255008536,
          -0.10347829244326384
        ],
        [
          -0.10347829244326383,
          0.3154795887964964
        ]
      ],
      "chi2": 3.605893912248812,
      "dof": 4,
      "arithmetic": [
        -1.2867833931170658,
        0.033747892875777584
      ]
    },
    {
      "visit": "V4",
      "n": 1,
      "mjd": 61152.757969777,
      "mean": [
        -4.762231700116119,
        2.207114880997902
      ],
      "predicted": [
        -4.370035309049607,
        0.514486240096634
      ],
      "covariance": [
        [
          0.9790183302491297,
          -0.39043479140850856
        ],
        [
          -0.3904347914085086,
          0.7706703575329107
        ]
      ],
      "chi2": 1.009784116265551e-30,
      "dof": 0,
      "arithmetic": [
        -4.76223170011612,
        2.207114880997902
      ]
    }
  ],
  "delta_arcsec": [
    -3.6632312104711438,
    2.4569716532493078
  ],
  "displacement_px": 0.7172182919398341,
  "pa_deg": 303.8502155625175,
  "pa_error_deg": 11.006804161738653,
  "predicted_delta_arcsec": [
    -4.449302157636006,
    0.5109168782961596
  ],
  "predicted_pa_deg": 276.55062769774304,
  "convention": "xi east, eta north; atan2(east,north), later minus earlier. Visit covariances inflated for excess scatter; not shared systematics."
}
```
No coordinate flip, epoch swap, new rejection or threshold change. Not a fresh native extraction. F5/F15 and visit-correlated systematic uncertainties remain open.

## Metrics

| metric | value | threshold | pass |
|---|---|---|---|

## Caveats

- recorded on a dirty working tree: code_digest identifies the exact code

git d6d2e45 (dirty) · contracts {'spherex.types': '0.1.0', 'http-api': '0.1.0'} · calibration 94e18b883fdc9b28 · author M · reviewer pending
