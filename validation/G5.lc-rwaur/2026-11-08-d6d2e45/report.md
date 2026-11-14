# G5.lc-rwaur — INCONCLUSIVE (L3)

# Native target acceptance
Complete measurements and rejected frames:
```json
{
  "bands": {
    "1": [
      {
        "mjd": 60920.03138900333,
        "rel": 0.7552411443040541,
        "err": 0.021705402603731543,
        "bin": "B0"
      },
      {
        "mjd": 61108.654863924654,
        "rel": 1.24944397582936,
        "err": 0.021825386643228216,
        "bin": "B13"
      }
    ]
  },
  "covariance": [
    [
      0.0004711245021900761,
      -0.00044926673922232585
    ],
    [
      -0.00044926673922232585,
      0.00047634750212640454
    ]
  ],
  "covariance_order": [
    [
      "1",
      "B0"
    ],
    [
      "1",
      "B13"
    ]
  ],
  "reference_spectrum": [
    {
      "detector": 1,
      "channel": 1,
      "flux": 100702.82358029264
    },
    {
      "detector": 1,
      "channel": 2,
      "flux": 100429.2021852353
    }
  ],
  "uncertainty": "First-order measurement-noise propagation through sample medians and [1,2,1] channel smoothing; includes shared reference covariance. Conditional on median ordering; not temporal sampling or PSF systematics. Periodogram peak uses marginal errors; analytic FAP suppressed because epochs share a reference.",
  "periodogram": null,
  "method": "psf",
  "label": "relative, spectrally normalized",
  "validity": "unvalidated",
  "photometric_scales": [
    "qr2"
  ],
  "pin": "177ce03ed2a6",
  "native_frames": [
    "level2_2025W36_1A_0095_1D1_spx_l2b-v20-2025-271.fits",
    "level2_2025W36_1A_0095_1D4_spx_l2b-v20-2025-271.fits",
    "level2_2025W36_1A_0095_2D1_spx_l2b-v20-2025-271.fits",
    "level2_2025W36_1A_0095_2D4_spx_l2b-v20-2025-271.fits",
    "level2_2025W36_1A_0155_1D1_spx_l2b-v20-2025-271.fits",
    "level2_2025W36_1A_0155_1D4_spx_l2b-v20-2025-271.fits",
    "level2_2025W36_1A_0233_2D1_spx_l2b-v20-2025-271.fits",
    "level2_2025W36_1A_0233_2D4_spx_l2b-v20-2025-271.fits",
    "level2_2025W36_1A_0233_3D1_spx_l2b-v20-2025-271.fits",
    "level2_2025W36_1A_0233_3D4_spx_l2b-v20-2025-271.fits",
    "level2_2025W36_1A_0446_1D1_spx_l2b-v20-2025-271.fits",
    "level2_2025W36_1A_0446_1D4_spx_l2b-v20-2025-271.fits",
    "level2_2025W36_1A_0446_2D1_spx_l2b-v20-2025-271.fits",
    "level2_2025W36_1A_0446_2D4_spx_l2b-v20-2025-271.fits",
    "level2_2025W36_1A_0446_3D1_spx_l2b-v20-2025-271.fits",
    "level2_2025W36_1A_0446_3D4_spx_l2b-v20-2025-271.fits",
    "level2_2025W36_1A_0446_4D1_spx_l2b-v20-2025-271.fits",
    "level2_2025W36_1A_0446_4D4_spx_l2b-v20-2025-271.fits",
    "level2_2025W36_1A_0606_1D1_spx_l2b-v20-2025-271.fits",
    "level2_2025W36_1A_0606_1D4_spx_l2b-v20-2025-271.fits",
    "level2_2025W36_1A_0606_2D1_spx_l2b-v20-2025-271.fits",
    "level2_2025W36_1A_0606_2D4_spx_l2b-v20-2025-271.fits",
    "level2_2025W36_1A_0606_3D1_spx_l2b-v20-2025-271.fits",
    "level2_2025W36_1A_0606_3D4_spx_l2b-v20-2025-271.fits",
    "level2_2025W36_1A_0606_4D1_spx_l2b-v20-2025-271.fits",
    "level2_2025W36_1A_0606_4D4_spx_l2b-v20-2025-271.fits",
    "level2_2025W36_1A_0663_1D1_spx_l2b-v20-2025-271.fits",
    "level2_2025W36_1A_0663_1D4_spx_l2b-v20-2025-271.fits",
    "level2_2025W36_1A_0663_2D1_spx_l2b-v20-2025-271.fits",
    "level2_2025W36_1A_0663_2D4_spx_l2b-v20-2025-271.fits",
    "level2_2025W36_1A_0663_3D1_spx_l2b-v20-2025-271.fits",
    "level2_2025W36_1A_0663_3D4_spx_l2b-v20-2025-271.fits",
    "level2_2025W36_1A_0663_4D1_spx_l2b-v20-2025-271.fits",
    "level2_2025W36_1A_0663_4D4_spx_l2b-v20-2025-271.fits",
    "level2_2025W36_1A_0677_1D1_spx_l2b-v20-2025-271.fits",
    "level2_2025W36_1A_0677_1D4_spx_l2b-v20-2025-271.fits",
    "level2_2025W36_1A_0677_2D1_spx_l2b-v20-2025-271.fits",
    "level2_2025W36_1A_0677_2D4_spx_l2b-v20-2025-271.fits",
    "level2_2025W37_1A_0068_1D2_spx_l2b-v20-2025-272.fits",
    "level2_2025W37_1A_0068_1D5_spx_l2b-v20-2025-272.fits",
    "level2_2025W37_1A_0068_2D2_spx_l2b-v20-2025-272.fits",
    "level2_2025W37_1A_0068_2D5_spx_l2b-v20-2025-272.fits",
    "level2_2025W37_1A_0068_3D2_spx_l2b-v20-2025-272.fits",
    "level2_2025W37_1A_0068_3D5_spx_l2b-v20-2025-272.fits",
    "level2_2025W37_1A_0068_4D2_spx_l2b-v20-2025-272.fits",
    "level2_2025W37_1A_0068_4D5_spx_l2b-v20-2025-272.fits",
    "level2_2025W37_1A_0124_1D2_spx_l2b-v20-2025-272.fits",
    "level2_2025W37_1A_0124_1D5_spx_l2b-v20-2025-272.fits",
    "level2_2025W37_1A_0124_2D2_spx_l2b-v20-2025-272.fits",
    "level2_2025W37_1A_0124_2D5_spx_l2b-v20-2025-272.fits",
    "level2_2025W37_1A_0124_3D2_spx_l2b-v20-2025-272.fits",
    "level2_2025W37_1A_0124_3D5_spx_l2b-v20-2025-272.fits",
    "level2_2025W37_1A_0366_1D2_spx_l2b-v20-2025-272.fits",
    "level2_2025W37_1A_0366_1D5_spx_l2b-v20-2025-272.fits",
    "level2_2025W37_1A_0366_2D2_spx_l2b-v20-2025-272.fits",
    "level2_2025W37_1A_0366_2D5_spx_l2b-v20-2025-272.fits",
    "level2_2025W37_1A_0366_3D2_spx_l2b-v20-2025-272.fits",
    "level2_2025W37_1A_0366_3D5_spx_l2b-v20-2025-272.fits",
    "level2_2025W37_1A_0366_4D2_spx_l2b-v20-2025-272.fits",
    "level2_2025W37_1A_0366_4D5_spx_l2b-v20-2025-272.fits",
    "level2_2025W37_1A_0379_1D2_spx_l2b-v20-2025-272.fits",
    "level2_2025W37_1A_0379_1D5_spx_l2b-v20-2025-272.fits",
    "level2_2025W37_1A_0379_2D2_spx_l2b-v20-2025-272.fits",
    "level2_2025W37_1A_0379_2D5_spx_l2b-v20-2025-272.fits",
    "level2_2025W37_1A_0379_3D2_spx_l2b-v20-2025-272.fits",
    "level2_2025W37_1A_0379_3D5_spx_l2b-v20-2025-272.fits",
    "level2_2025W37_1A_0379_4D2_spx_l2b-v20-2025-272.fits",
    "level2_2025W37_1A_0379_4D5_spx_l2b-v20-2025-272.fits",
    "level2_2025W37_1A_0496_1D2_spx_l2b-v20-2025-272.fits",
    "level2_2025W37_1A_0496_1D5_spx_l2b-v20-2025-272.fits",
    "level2_2025W37_1A_0496_2D2_spx_l2b-v20-2025-272.fits",
    "level2_2025W37_1A_0496_2D5_spx_l2b-v20-2025-272.fits",
    "level2_2025W37_1A_0553_1D2_spx_l2b-v20-2025-272.fits",
    "level2_2025W37_1A_0553_1D5_spx_l2b-v20-2025-272.fits",
    "level2_2025W37_2A_0051_1D3_spx_l2b-v20-2025-267.fits",
    "level2_2025W37_2A_0051_1D6_spx_l2b-v20-2025-267.fits",
    "level2_2025W38_1A_0538_1D3_spx_l2b-v20-2025-268.fits",
    "level2_2025W38_1A_0538_1D6_spx_l2b-v20-2025-268.fits",
    "level2_2025W38_1A_0538_2D3_spx_l2b-v20-2025-268.fits",
    "level2_2025W38_1A_0538_2D6_spx_l2b-v20-2025-268.fits",
    "level2_2025W38_1A_0538_3D3_spx_l2b-v20-2025-268.fits",
    "level2_2025W38_1A_0538_3D6_spx_l2b-v20-2025-268.fits",
    "level2_2025W38_1A_0691_1D3_spx_l2b-v20-2025-268.fits",
    "level2_2025W38_1A_0691_1D6_spx_l2b-v20-2025-268.fits",
    "level2_2025W38_1A_0691_2D3_spx_l2b-v20-2025-268.fits",
    "level2_2025W38_1A_0691_2D6_spx_l2b-v20-2025-268.fits",
    "level2_2025W38_1A_0691_3D3_spx_l2b-v20-2025-268.fits",
    "level2_2025W38_1A_0691_3D6_spx_l2b-v20-2025-268.fits",
    "level2_2025W38_1A_0691_4D3_spx_l2b-v20-2025-268.fits",
    "level2_2025W38_1A_0691_4D6_spx_l2b-v20-2025-268.fits",
    "level2_2025W38_1A_0738_1D3_spx_l2b-v20-2025-268.fits",
    "level2_2025W38_1A_0738_1D6_spx_l2b-v20-2025-268.fits",
    "level2_2025W38_1A_0738_2D3_spx_l2b-v20-2025-268.fits",
    "level2_2025W38_1A_0738_3D3_spx_l2b-v20-2025-268.fits",
    "level2_2025W38_1A_0738_3D6_spx_l2b-v20-2025-268.fits",
    "level2_2025W38_1A_0738_4D3_spx_l2b-v20-2025-268.fits",
    "level2_2025W38_1A_0738_4D6_spx_l2b-v20-2025-268.fits",
    "level2_2025W38_2C_0023_1D3_spx_l2b-v20-2025-269.fits",
    "level2_2025W38_2C_0023_1D6_spx_l2b-v20-2025-269.fits",
    "level2_2025W38_2C_0023_2D3_spx_l2b-v20-2025-269.fits",
    "level2_2025W38_2C_0023_2D6_spx_l2b-v20-2025-269.fits",
    "level2_2025W38_2C_0023_3D3_spx_l2b-v20-2025-269.fits",
    "level2_2025W38_2C_0023_3D6_spx_l2b-v20-2025-269.fits",
    "level2_2025W38_2C_0023_4D3_spx_l2b-v20-2025-269.fits",
    "level2_2025W38_2C_0023_4D6_spx_l2b-v20-2025-269.fits",
    "level2_2025W38_2C_0124_1D3_spx_l2b-v20-2025-269.fits",
    "level2_2025W38_2C_0342_1D3_spx_l2b-v20-2025-269.fits",
    "level2_2025W38_2C_0342_1D6_spx_l2b-v20-2025-269.fits",
    "level2_2025W38_2C_0342_2D3_spx_l2b-v20-2025-269.fits",
    "level2_2025W38_2C_0342_2D6_spx_l2b-v20-2025-269.fits",
    "level2_2026W08_2A_0233_1D3_spx_l2b-v24-2026-089.fits",
    "level2_2026W08_2A_0233_1D6_spx_l2b-v24-2026-089.fits",
    "level2_2026W08_2A_0233_2D3_spx_l2b-v24-2026-089.fits",
    "level2_2026W08_2A_0233_2D6_spx_l2b-v24-2026-089.fits",
    "level2_2026W08_2A_0233_3D3_spx_l2b-v24-2026-089.fits",
    "level2_2026W08_2A_0233_3D6_spx_l2b-v24-2026-089.fits",
    "level2_2026W08_2A_0233_4D3_spx_l2b-v24-2026-089.fits",
    "level2_2026W08_2A_0233_4D6_spx_l2b-v24-2026-089.fits",
    "level2_2026W08_2A_0361_1D3_spx_l2b-v24-2026-089.fits",
    "level2_2026W08_2A_0361_1D6_spx_l2b-v24-2026-089.fits",
    "level2_2026W08_2A_0361_2D3_spx_l2b-v24-2026-089.fits",
    "level2_2026W08_2A_0361_2D6_spx_l2b-v24-2026-089.fits",
    "level2_2026W08_2A_0361_3D3_spx_l2b-v24-2026-089.fits",
    "level2_2026W08_2A_0361_3D6_spx_l2b-v24-2026-089.fits",
    "level2_2026W08_2A_0361_4D3_spx_l2b-v24-2026-089.fits",
    "level2_2026W08_2A_0361_4D6_spx_l2b-v24-2026-089.fits",
    "level2_2026W09_2A_0224_2D3_spx_l2b-v24-2026-094.fits",
    "level2_2026W09_2A_0224_2D6_spx_l2b-v24-2026-094.fits",
    "level2_2026W09_2A_0224_3D3_spx_l2b-v24-2026-094.fits",
    "level2_2026W09_2A_0224_3D6_spx_l2b-v24-2026-094.fits",
    "level2_2026W09_2A_0224_4D3_spx_l2b-v24-2026-094.fits",
    "level2_2026W09_2A_0224_4D6_spx_l2b-v24-2026-094.fits",
    "level2_2026W09_2A_0289_1D3_spx_l2b-v24-2026-094.fits",
    "level2_2026W09_2A_0289_1D6_spx_l2b-v24-2026-094.fits",
    "level2_2026W09_2A_0289_2D3_spx_l2b-v24-2026-094.fits",
    "level2_2026W09_2A_0289_2D6_spx_l2b-v24-2026-094.fits",
    "level2_2026W09_2A_0289_3D3_spx_l2b-v24-2026-094.fits",
    "level2_2026W09_2A_0289_3D6_spx_l2b-v24-2026-094.fits",
    "level2_2026W09_2A_0503_1D2_spx_l2b-v24-2026-094.fits",
    "level2_2026W09_2A_0503_1D5_spx_l2b-v24-2026-094.fits",
    "level2_2026W09_2A_0503_2D2_spx_l2b-v24-2026-094.fits",
    "level2_2026W09_2A_0503_2D5_spx_l2b-v24-2026-094.fits",
    "level2_2026W09_2A_0503_3D2_spx_l2b-v24-2026-094.fits",
    "level2_2026W09_2A_0503_3D5_spx_l2b-v24-2026-094.fits",
    "level2_2026W09_2A_0503_4D2_spx_l2b-v24-2026-094.fits",
    "level2_2026W09_2A_0503_4D5_spx_l2b-v24-2026-094.fits",
    "level2_2026W09_2A_0552_1D3_spx_l2b-v24-2026-094.fits",
    "level2_2026W09_2A_0552_1D6_spx_l2b-v24-2026-094.fits",
    "level2_2026W09_2A_0552_2D3_spx_l2b-v24-2026-094.fits",
    "level2_2026W09_2A_0552_2D6_spx_l2b-v24-2026-094.fits",
    "level2_2026W09_2A_0552_3D3_spx_l2b-v24-2026-094.fits",
    "level2_2026W09_2A_0552_3D6_spx_l2b-v24-2026-094.fits",
    "level2_2026W09_2A_0552_4D3_spx_l2b-v24-2026-094.fits",
    "level2_2026W09_2A_0552_4D6_spx_l2b-v24-2026-094.fits",
    "level2_2026W10_1A_0092_1D2_spx_l2b-v24-2026-094.fits",
    "level2_2026W10_1A_0092_1D5_spx_l2b-v24-2026-094.fits",
    "level2_2026W10_1A_0092_2D2_spx_l2b-v24-2026-094.fits",
    "level2_2026W10_1A_0092_2D5_spx_l2b-v24-2026-094.fits",
    "level2_2026W10_1A_0092_3D2_spx_l2b-v24-2026-094.fits",
    "level2_2026W10_1A_0092_3D5_spx_l2b-v24-2026-094.fits",
    "level2_2026W10_1A_0092_4D2_spx_l2b-v24-2026-094.fits",
    "level2_2026W10_1A_0092_4D5_spx_l2b-v24-2026-094.fits",
    "level2_2026W10_1A_0120_1D3_spx_l2b-v24-2026-094.fits",
    "level2_2026W10_1A_0120_1D6_spx_l2b-v24-2026-094.fits",
    "level2_2026W10_1A_0445_1D1_spx_l2b-v24-2026-094.fits",
    "level2_2026W10_1A_0445_1D4_spx_l2b-v24-2026-094.fits",
    "level2_2026W10_1A_0445_2D1_spx_l2b-v24-2026-094.fits",
    "level2_2026W10_1A_0445_2D4_spx_l2b-v24-2026-094.fits",
    "level2_2026W10_1A_0445_3D1_spx_l2b-v24-2026-094.fits",
    "level2_2026W10_1A_0445_3D4_spx_l2b-v24-2026-094.fits",
    "level2_2026W10_1A_0445_4D1_spx_l2b-v24-2026-094.fits",
    "level2_2026W10_1A_0445_4D4_spx_l2b-v24-2026-094.fits",
    "level2_2026W10_1A_0602_1D2_spx_l2b-v24-2026-094.fits",
    "level2_2026W10_1A_0602_1D5_spx_l2b-v24-2026-094.fits",
    "level2_2026W10_1A_0602_2D2_spx_l2b-v24-2026-094.fits",
    "level2_2026W10_1A_0602_2D5_spx_l2b-v24-2026-094.fits",
    "level2_2026W10_1A_0602_3D2_spx_l2b-v24-2026-094.fits",
    "level2_2026W10_1A_0602_3D5_spx_l2b-v24-2026-094.fits",
    "level2_2026W10_1A_0602_4D2_spx_l2b-v24-2026-094.fits",
    "level2_2026W10_1A_0602_4D5_spx_l2b-v24-2026-094.fits",
    "level2_2026W10_1A_0639_3D2_spx_l2b-v24-2026-094.fits",
    "level2_2026W10_1A_0639_3D5_spx_l2b-v24-2026-094.fits",
    "level2_2026W10_1A_0639_4D2_spx_l2b-v24-2026-094.fits",
    "level2_2026W10_1A_0639_4D5_spx_l2b-v24-2026-094.fits",
    "level2_2026W10_2B_0137_1D1_spx_l2b-v24-2026-094.fits",
    "level2_2026W10_2B_0137_1D4_spx_l2b-v24-2026-094.fits",
    "level2_2026W10_2B_0137_2D1_spx_l2b-v24-2026-094.fits",
    "level2_2026W10_2B_0137_2D4_spx_l2b-v24-2026-094.fits",
    "level2_2026W10_2B_0137_3D1_spx_l2b-v24-2026-094.fits",
    "level2_2026W10_2B_0137_3D4_spx_l2b-v24-2026-094.fits",
    "level2_2026W10_2B_0137_4D1_spx_l2b-v24-2026-094.fits",
    "level2_2026W10_2B_0137_4D4_spx_l2b-v24-2026-094.fits",
    "level2_2026W10_2B_0340_1D2_spx_l2b-v24-2026-094.fits",
    "level2_2026W10_2B_0340_1D5_spx_l2b-v24-2026-094.fits",
    "level2_2026W10_2B_0340_2D2_spx_l2b-v24-2026-094.fits",
    "level2_2026W10_2B_0340_2D5_spx_l2b-v24-2026-094.fits",
    "level2_2026W10_2B_0340_3D2_spx_l2b-v24-2026-094.fits",
    "level2_2026W10_2B_0340_3D5_spx_l2b-v24-2026-094.fits",
    "level2_2026W10_2B_0340_4D2_spx_l2b-v24-2026-094.fits",
    "level2_2026W10_2B_0340_4D5_spx_l2b-v24-2026-094.fits",
    "level2_2026W10_2B_0591_3D1_spx_l2b-v24-2026-094.fits",
    "level2_2026W10_2B_0591_3D4_spx_l2b-v24-2026-094.fits",
    "level2_2026W10_2B_0591_4D1_spx_l2b-v24-2026-094.fits",
    "level2_2026W10_2B_0591_4D4_spx_l2b-v24-2026-094.fits",
    "level2_2026W10_2B_0626_1D1_spx_l2b-v24-2026-094.fits",
    "level2_2026W10_2B_0626_1D4_spx_l2b-v24-2026-094.fits",
    "level2_2026W10_2B_0626_2D1_spx_l2b-v24-2026-094.fits",
    "level2_2026W10_2B_0626_2D4_spx_l2b-v24-2026-094.fits",
    "level2_2026W10_2B_0626_3D1_spx_l2b-v24-2026-094.fits",
    "level2_2026W10_2B_0626_3D4_spx_l2b-v24-2026-094.fits",
    "level2_2026W10_2B_0626_4D1_spx_l2b-v24-2026-094.fits",
    "level2_2026W10_2B_0626_4D4_spx_l2b-v24-2026-094.fits",
    "level2_2026W11_1A_0042_1D2_spx_l2b-v24-2026-094.fits",
    "level2_2026W11_1A_0042_1D5_spx_l2b-v24-2026-094.fits",
    "level2_2026W11_1A_0285_1D1_spx_l2b-v24-2026-094.fits",
    "level2_2026W11_1A_0285_1D4_spx_l2b-v24-2026-094.fits",
    "level2_2026W11_1A_0285_2D1_spx_l2b-v24-2026-094.fits",
    "level2_2026W11_1A_0285_2D4_spx_l2b-v24-2026-094.fits",
    "level2_2026W11_1A_0285_3D1_spx_l2b-v24-2026-094.fits",
    "level2_2026W11_1A_0285_3D4_spx_l2b-v24-2026-094.fits",
    "level2_2026W11_1A_0285_4D1_spx_l2b-v24-2026-094.fits",
    "level2_2026W11_1A_0285_4D4_spx_l2b-v24-2026-094.fits",
    "level2_2026W11_1A_0645_1D1_spx_l2b-v24-2026-094.fits",
    "level2_2026W11_1A_0645_1D4_spx_l2b-v24-2026-094.fits"
  ],
  "skipped": [
    [
      "2025W36_1A_0095_1",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2025W36_1A_0095_1",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2025W36_1A_0095_2",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2025W36_1A_0095_2",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2025W36_1A_0155_1",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2025W36_1A_0155_1",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2025W36_1A_0233_2",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2025W36_1A_0233_3",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2025W36_1A_0446_1",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2025W36_1A_0446_2",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2025W36_1A_0446_2",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2025W36_1A_0446_3",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2025W36_1A_0446_4",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2025W36_1A_0606_1",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2025W36_1A_0606_1",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2025W36_1A_0606_2",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2025W36_1A_0606_3",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2025W36_1A_0606_3",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2025W36_1A_0606_4",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2025W36_1A_0606_4",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2025W36_1A_0663_1",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2025W36_1A_0663_1",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2025W36_1A_0663_2",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2025W36_1A_0663_3",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2025W36_1A_0663_3",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2025W36_1A_0663_4",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2025W36_1A_0663_4",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2025W36_1A_0677_1",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2025W36_1A_0677_2",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2025W37_1A_0068_1",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2025W37_1A_0068_1",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2025W37_1A_0068_2",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2025W37_1A_0068_2",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2025W37_1A_0068_3",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2025W37_1A_0068_3",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2025W37_1A_0068_4",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2025W37_1A_0068_4",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2025W37_1A_0124_1",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2025W37_1A_0124_1",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2025W37_1A_0124_2",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2025W37_1A_0124_2",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2025W37_1A_0124_3",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2025W37_1A_0124_3",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2025W37_1A_0366_1",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2025W37_1A_0366_1",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2025W37_1A_0366_2",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2025W37_1A_0366_2",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2025W37_1A_0366_3",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2025W37_1A_0366_3",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2025W37_1A_0366_4",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2025W37_1A_0366_4",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2025W37_1A_0379_1",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2025W37_1A_0379_1",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2025W37_1A_0379_2",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2025W37_1A_0379_2",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2025W37_1A_0379_3",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2025W37_1A_0379_3",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2025W37_1A_0379_4",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2025W37_1A_0379_4",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2025W37_1A_0496_1",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2025W37_1A_0496_1",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2025W37_1A_0496_2",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2025W37_1A_0496_2",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2025W37_1A_0553_1",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2025W37_1A_0553_1",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2025W37_2A_0051_1",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2025W37_2A_0051_1",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2025W38_1A_0538_1",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2025W38_1A_0538_1",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2025W38_1A_0538_2",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2025W38_1A_0538_2",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2025W38_1A_0538_3",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2025W38_1A_0538_3",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2025W38_1A_0691_1",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2025W38_1A_0691_1",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2025W38_1A_0691_2",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2025W38_1A_0691_2",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2025W38_1A_0691_3",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2025W38_1A_0691_3",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2025W38_1A_0691_4",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2025W38_1A_0691_4",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2025W38_1A_0738_1",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2025W38_1A_0738_1",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2025W38_1A_0738_2",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2025W38_1A_0738_3",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2025W38_1A_0738_3",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2025W38_1A_0738_4",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2025W38_1A_0738_4",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2025W38_2C_0023_1",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2025W38_2C_0023_1",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2025W38_2C_0023_2",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2025W38_2C_0023_2",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2025W38_2C_0023_3",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2025W38_2C_0023_3",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2025W38_2C_0023_4",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2025W38_2C_0023_4",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2025W38_2C_0124_1",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2025W38_2C_0342_1",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2025W38_2C_0342_1",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2025W38_2C_0342_2",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2025W38_2C_0342_2",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2026W08_2A_0233_1",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2026W08_2A_0233_1",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2026W08_2A_0233_2",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2026W08_2A_0233_2",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2026W08_2A_0233_3",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2026W08_2A_0233_3",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2026W08_2A_0233_4",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2026W08_2A_0233_4",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2026W08_2A_0361_1",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2026W08_2A_0361_1",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2026W08_2A_0361_2",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2026W08_2A_0361_2",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2026W08_2A_0361_3",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2026W08_2A_0361_3",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2026W08_2A_0361_4",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2026W08_2A_0361_4",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2026W09_2A_0224_2",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2026W09_2A_0224_2",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2026W09_2A_0224_3",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2026W09_2A_0224_3",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2026W09_2A_0224_4",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2026W09_2A_0224_4",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2026W09_2A_0289_1",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2026W09_2A_0289_1",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2026W09_2A_0289_2",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2026W09_2A_0289_2",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2026W09_2A_0289_3",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2026W09_2A_0289_3",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2026W09_2A_0503_1",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2026W09_2A_0503_1",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2026W09_2A_0503_2",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2026W09_2A_0503_2",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2026W09_2A_0503_3",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2026W09_2A_0503_3",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2026W09_2A_0503_4",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2026W09_2A_0503_4",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2026W09_2A_0552_1",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2026W09_2A_0552_1",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2026W09_2A_0552_2",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2026W09_2A_0552_2",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2026W09_2A_0552_3",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2026W09_2A_0552_3",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2026W09_2A_0552_4",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2026W09_2A_0552_4",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2026W10_1A_0092_1",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2026W10_1A_0092_1",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2026W10_1A_0092_2",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2026W10_1A_0092_2",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2026W10_1A_0092_3",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2026W10_1A_0092_3",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2026W10_1A_0092_4",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2026W10_1A_0092_4",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2026W10_1A_0120_1",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2026W10_1A_0120_1",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2026W10_1A_0445_1",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2026W10_1A_0445_1",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2026W10_1A_0445_2",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2026W10_1A_0445_3",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2026W10_1A_0445_3",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2026W10_1A_0445_4",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2026W10_1A_0445_4",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2026W10_1A_0602_1",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2026W10_1A_0602_1",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2026W10_1A_0602_2",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2026W10_1A_0602_2",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2026W10_1A_0602_3",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2026W10_1A_0602_3",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2026W10_1A_0602_4",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2026W10_1A_0602_4",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2026W10_1A_0639_3",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2026W10_1A_0639_3",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2026W10_1A_0639_4",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2026W10_1A_0639_4",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2026W10_2B_0137_1",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2026W10_2B_0137_1",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2026W10_2B_0137_2",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2026W10_2B_0137_2",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2026W10_2B_0137_3",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2026W10_2B_0137_3",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2026W10_2B_0137_4",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2026W10_2B_0137_4",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2026W10_2B_0340_1",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2026W10_2B_0340_1",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2026W10_2B_0340_2",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2026W10_2B_0340_2",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2026W10_2B_0340_3",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2026W10_2B_0340_3",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2026W10_2B_0340_4",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2026W10_2B_0340_4",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2026W10_2B_0591_3",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2026W10_2B_0591_4",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2026W10_2B_0626_1",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2026W10_2B_0626_1",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2026W10_2B_0626_2",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2026W10_2B_0626_2",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2026W10_2B_0626_3",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2026W10_2B_0626_3",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2026W10_2B_0626_4",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2026W10_2B_0626_4",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2026W11_1A_0042_1",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2026W11_1A_0042_1",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2026W11_1A_0285_1",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2026W11_1A_0285_2",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2026W11_1A_0285_2",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2026W11_1A_0285_3",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2026W11_1A_0285_3",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2026W11_1A_0285_4",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2026W11_1A_0285_4",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2026W11_1A_0645_1",
      "invalid or contaminated ePSF fit"
    ],
    [
      "2026W11_1A_0645_1",
      "invalid or contaminated ePSF fit"
    ]
  ]
}
```
A passing numerical sample is still subject to foundations, external comparison and I review.

## Metrics

| metric | value | threshold | pass |
|---|---|---|---|
| points_by_band | {'1': 2} | at least three visits per band, not just time bins | None |

## Caveats

- recorded on a dirty working tree: code_digest identifies the exact code

## Figures

![measurements.png](figures/measurements.png)

git d6d2e45 (dirty) · contracts {'spherex.types': '0.1.0', 'http-api': '0.1.0'} · calibration 94e18b883fdc9b28 · author M · reviewer pending
