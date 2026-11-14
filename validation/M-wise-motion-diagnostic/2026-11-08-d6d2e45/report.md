# M-wise-motion-diagnostic — INCONCLUSIVE (L3)

# Retained native WISE motion audit
```json
{
  "visits": [
    {
      "visit": "V2",
      "n": 16,
      "mjd": 60991.54001316038,
      "mean": [
        -0.4915455443320363,
        -0.7079234600888419
      ],
      "predicted": [
        0.07127272269368636,
        0.0011560316923038892
      ],
      "covariance": [
        [
          0.3041446735199785,
          -0.056824620015853866
        ],
        [
          -0.05682462001585388,
          0.25168359175911886
        ]
      ],
      "chi2": 90.13502281991677,
      "dof": 30,
      "arithmetic": [
        -0.1377528847918164,
        -0.6570310725623857
      ]
    },
    {
      "visit": "V4",
      "n": 19,
      "mjd": 61156.73773724616,
      "mean": [
        -5.573044189540608,
        2.7888551202692327
      ],
      "predicted": [
        -4.480972170805055,
        0.5801221156684434
      ],
      "covariance": [
        [
          0.13595377361535374,
          -0.09279431768200172
        ],
        [
          -0.09279431768200169,
          0.07020390475336089
        ]
      ],
      "chi2": 102.96510795128202,
      "dof": 36,
      "arithmetic": [
        -4.801292782621531,
        0.9920339290557587
      ]
    }
  ],
  "delta_arcsec": [
    -5.081498645208572,
    3.4967785803580744
  ],
  "displacement_px": 1.0029909520656253,
  "pa_deg": 304.5333858339147,
  "pa_error_deg": 4.358049618564393,
  "predicted_delta_arcsec": [
    -4.552244893498742,
    0.5789660839761395
  ],
  "predicted_pa_deg": 277.2481097682017,
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
