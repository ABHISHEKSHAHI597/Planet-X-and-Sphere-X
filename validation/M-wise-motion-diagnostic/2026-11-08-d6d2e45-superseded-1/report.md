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
        -1.1409001697339456,
        -0.23433618924509353
      ],
      "predicted": [
        0.0791101888497272,
        0.0027811798024736005
      ],
      "covariance": [
        [
          0.41100178224077805,
          -0.11464483614692818
        ],
        [
          -0.11464483614692818,
          0.3180219014581495
        ]
      ],
      "chi2": 3.6317542008321255,
      "dof": 4,
      "arithmetic": [
        -1.3368744526156517,
        0.06354402303169134
      ]
    },
    {
      "visit": "V4",
      "n": 1,
      "mjd": 61152.757969777,
      "mean": [
        -4.733433948048825,
        2.170501014800113
      ],
      "predicted": [
        -4.370035309049607,
        0.5144862400966339
      ],
      "covariance": [
        [
          0.9616258299782399,
          -0.3582710770299483
        ],
        [
          -0.35827107702994837,
          0.7828976973700715
        ]
      ],
      "chi2": 9.889525444480505e-31,
      "dof": 0,
      "arithmetic": [
        -4.733433948048826,
        2.170501014800113
      ]
    }
  ],
  "delta_arcsec": [
    -3.5925337783148796,
    2.4048372040452066
  ],
  "displacement_px": 0.702949621078516,
  "pa_deg": 303.7982979912312,
  "pa_error_deg": 11.460633031160588,
  "predicted_delta_arcsec": [
    -4.449145497899334,
    0.5117050602941603
  ],
  "predicted_pa_deg": 276.56087419051903,
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
