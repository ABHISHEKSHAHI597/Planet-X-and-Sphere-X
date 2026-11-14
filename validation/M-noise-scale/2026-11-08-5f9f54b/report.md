# M-noise-scale — INCONCLUSIVE (L3)

# M-noise-scale (r2) — F5 with the VARIANCE plane calibrated on blank sky

Verdict **inconclusive** (rule in the module docstring). Robust F5 failure (every estimator > 3): none. Detectors > 3 under at least one estimator: [1, 4]. Antisymmetric residual replicated in both fields (p < 0.01, difference estimator): none.

## Noise scale s and median χ²ᵣ by estimator (stars judged)

| D | χ²ᵣ VARIANCE | block12: s / χ²ᵣ (n) | block16: s / χ²ᵣ (n) | block24: s / χ²ᵣ (n) | diff: s / χ²ᵣ (n) |
|---|---|---|---|---|---|
| 1 | 4.46 | 1.103 / 2.08 (58) | 1.206 / 3.59 (34) | 1.231 / 3.98 (63) | 1.122 / 3.21 (87) |
| 2 | 3.57 | 1.167 / 1.23 (53) | 1.172 / 1.24 (53) | 1.248 / 1.50 (77) | 1.185 / 2.62 (103) |
| 3 | 3.27 | 1.105 / 1.50 (55) | 1.206 / 1.48 (72) | 1.282 / 1.85 (42) | 1.189 / 2.41 (101) |
| 4 | 3.60 | 1.147 / 1.75 (20) | — / — (0) | 1.252 / 3.25 (23) | 1.164 / 2.66 (63) |
| 5 | 1.43 | 1.019 / 1.45 (28) | 1.032 / 1.38 (28) | 1.063 / 1.23 (28) | 1.053 / 1.33 (28) |
| 6 | 1.19 | 1.014 / 1.15 (9) | 1.038 / 1.11 (9) | 1.032 / 1.12 (9) | 1.032 / 1.07 (9) |

## Antisymmetric residual, sign-flip permutation (difference estimator)

| D | Barnard's Star | eps Ind B |
|---|---|---|
| 1 | rms 0.279, p = 0.0272 (n=63) | rms 0.405, p = 0.0002 (n=24) |
| 2 | rms 0.163, p = 0.9853 (n=50) | rms 0.245, p = 0.0017 (n=53) |
| 3 | rms 0.225, p = 0.6593 (n=46) | rms 0.259, p = 0.0002 (n=55) |
| 4 | rms 0.249, p = 0.1482 (n=43) | rms 0.313, p = 0.1307 (n=20) |
| 5 | rms 0.199, p = 0.5016 (n=16) | rms 0.191, p = 0.8035 (n=12) |
| 6 | rms 0.390, p = 0.4214 (n=5) | n=4 |

```json
{
 "summary": {
  "1": {
   "n": 87,
   "frames": 3,
   "median_rchi2_variance": 4.456420146569784,
   "block12": {
    "scale": 1.1033473061641377,
    "frames": 2,
    "n": 58,
    "median_rchi2": 2.0788653571752977,
    "antisymmetry": {
     "Barnard's Star": {
      "n": 34,
      "antisym_rms": 0.26611211018930425,
      "p": 0.2644338915271182
     },
     "eps Ind B": {
      "n": 24,
      "antisym_rms": 0.41988370121419494,
      "p": 0.00024993751562109475
     }
    }
   },
   "block16": {
    "scale": 1.2059901612665371,
    "frames": 1,
    "n": 34,
    "median_rchi2": 3.5943222249757545,
    "antisymmetry": {
     "Barnard's Star": {
      "n": 34,
      "antisym_rms": 0.2734651669700371,
      "p": 0.24343914021494625
     },
     "eps Ind B": {
      "n": 0
     }
    }
   },
   "block24": {
    "scale": 1.231409772247538,
    "frames": 2,
    "n": 63,
    "median_rchi2": 3.9825577853208878,
    "antisymmetry": {
     "Barnard's Star": {
      "n": 63,
      "antisym_rms": 0.2610561307883609,
      "p": 0.03399150212446888
     },
     "eps Ind B": {
      "n": 0
     }
    }
   },
   "diff": {
    "scale": 1.1218133303877302,
    "frames": 3,
    "n": 87,
    "median_rchi2": 3.212380486851846,
    "antisymmetry": {
     "Barnard's Star": {
      "n": 63,
      "antisym_rms": 0.2794925515055596,
      "p": 0.027243189202699324
     },
     "eps Ind B": {
      "n": 24,
      "antisym_rms": 0.4052624043591739,
      "p": 0.00024993751562109475
     }
    }
   }
  },
  "2": {
   "n": 103,
   "frames": 4,
   "median_rchi2_variance": 3.5716844928040548,
   "block12": {
    "scale": 1.1665393925965928,
    "frames": 2,
    "n": 53,
    "median_rchi2": 1.2343033072703737,
    "antisymmetry": {
     "Barnard's Star": {
      "n": 0
     },
     "eps Ind B": {
      "n": 53,
      "antisym_rms": 0.2501764954119852,
      "p": 0.000999750062484379
     }
    }
   },
   "block16": {
    "scale": 1.1716911052326626,
    "frames": 2,
    "n": 53,
    "median_rchi2": 1.2400794487093263,
    "antisymmetry": {
     "Barnard's Star": {
      "n": 0
     },
     "eps Ind B": {
      "n": 53,
      "antisym_rms": 0.25010456907573003,
      "p": 0.0004998750312421895
     }
    }
   },
   "block24": {
    "scale": 1.247550783418357,
    "frames": 3,
    "n": 77,
    "median_rchi2": 1.5007699997107964,
    "antisymmetry": {
     "Barnard's Star": {
      "n": 24,
      "antisym_rms": 0.2880157405461903,
      "p": 0.7208197950512372
     },
     "eps Ind B": {
      "n": 53,
      "antisym_rms": 0.24288093423585183,
      "p": 0.000999750062484379
     }
    }
   },
   "diff": {
    "scale": 1.1851074479908341,
    "frames": 4,
    "n": 103,
    "median_rchi2": 2.620023857378682,
    "antisymmetry": {
     "Barnard's Star": {
      "n": 50,
      "antisym_rms": 0.16304034091501268,
      "p": 0.9852536865783554
     },
     "eps Ind B": {
      "n": 53,
      "antisym_rms": 0.24530844330406618,
      "p": 0.0017495626093476631
     }
    }
   }
  },
  "3": {
   "n": 101,
   "frames": 4,
   "median_rchi2_variance": 3.272483795270477,
   "block12": {
    "scale": 1.1053302255784532,
    "frames": 2,
    "n": 55,
    "median_rchi2": 1.5024953013872866,
    "antisymmetry": {
     "Barnard's Star": {
      "n": 0
     },
     "eps Ind B": {
      "n": 55,
      "antisym_rms": 0.2566070398795931,
      "p": 0.00024993751562109475
     }
    }
   },
   "block16": {
    "scale": 1.2063690776215608,
    "frames": 3,
    "n": 72,
    "median_rchi2": 1.4811127567758047,
    "antisymmetry": {
     "Barnard's Star": {
      "n": 17,
      "antisym_rms": 0.3336181114090679,
      "p": 0.6268432891777056
     },
     "eps Ind B": {
      "n": 55,
      "antisym_rms": 0.24591649826143214,
      "p": 0.0004998750312421895
     }
    }
   },
   "block24": {
    "scale": 1.281922346069082,
    "frames": 2,
    "n": 42,
    "median_rchi2": 1.8519941072390398,
    "antisymmetry": {
     "Barnard's Star": {
      "n": 17,
      "antisym_rms": 0.33135523723879834,
      "p": 0.625343664083979
     },
     "eps Ind B": {
      "n": 25,
      "antisym_rms": 0.29682661030100765,
      "p": 0.01849537615596101
     }
    }
   },
   "diff": {
    "scale": 1.1886777322819633,
    "frames": 4,
    "n": 101,
    "median_rchi2": 2.4099325764907102,
    "antisymmetry": {
     "Barnard's Star": {
      "n": 46,
      "antisym_rms": 0.22521502967405402,
      "p": 0.6593351662084479
     },
     "eps Ind B": {
      "n": 55,
      "antisym_rms": 0.259066144212046,
      "p": 0.00024993751562109475
     }
    }
   }
  },
  "4": {
   "n": 63,
   "frames": 3,
   "median_rchi2_variance": 3.6029875333983488,
   "block12": {
    "scale": 1.1465327545004165,
    "frames": 1,
    "n": 20,
    "median_rchi2": 1.7465516421777654,
    "antisymmetry": {
     "Barnard's Star": {
      "n": 0
     },
     "eps Ind B": {
      "n": 20,
      "antisym_rms": 0.2946998972425543,
      "p": 0.13396650837290677
     }
    }
   },
   "block16": {
    "scale": null,
    "frames": 0,
    "n": 0,
    "median_rchi2": null,
    "antisymmetry": {
     "Barnard's Star": {
      "n": 0
     },
     "eps Ind B": {
      "n": 0
     }
    }
   },
   "block24": {
    "scale": 1.2516009336793232,
    "frames": 1,
    "n": 23,
    "median_rchi2": 3.2508168265961093,
    "antisymmetry": {
     "Barnard's Star": {
      "n": 23,
      "antisym_rms": 0.3050451957941378,
      "p": 0.39965008747813047
     },
     "eps Ind B": {
      "n": 0
     }
    }
   },
   "diff": {
    "scale": 1.1635292098453638,
    "frames": 3,
    "n": 63,
    "median_rchi2": 2.6613879023012457,
    "antisymmetry": {
     "Barnard's Star": {
      "n": 43,
      "antisym_rms": 0.2490085214926446,
      "p": 0.14821294676330918
     },
     "eps Ind B": {
      "n": 20,
      "antisym_rms": 0.312732438668307,
      "p": 0.13071732066983255
     }
    }
   }
  },
  "5": {
   "n": 28,
   "frames": 4,
   "median_rchi2_variance": 1.4255384850999997,
   "block12": {
    "scale": 1.0187931462078468,
    "frames": 4,
    "n": 28,
    "median_rchi2": 1.4541868460354364,
    "antisymmetry": {
     "Barnard's Star": {
      "n": 16,
      "antisym_rms": 0.20882322416815552,
      "p": 0.49562609347663084
     },
     "eps Ind B": {
      "n": 12,
      "antisym_rms": 0.1972873606800833,
      "p": 0.7873031742064484
     }
    }
   },
   "block16": {
    "scale": 1.0320323196577177,
    "frames": 4,
    "n": 28,
    "median_rchi2": 1.377725517321727,
    "antisymmetry": {
     "Barnard's Star": {
      "n": 16,
      "antisym_rms": 0.20732324611844918,
      "p": 0.4928767808047988
     },
     "eps Ind B": {
      "n": 12,
      "antisym_rms": 0.1955735149549454,
      "p": 0.7988002999250188
     }
    }
   },
   "block24": {
    "scale": 1.062650463755062,
    "frames": 4,
    "n": 28,
    "median_rchi2": 1.2288733732526296,
    "antisymmetry": {
     "Barnard's Star": {
      "n": 16,
      "antisym_rms": 0.18970079237265827,
      "p": 0.4891277180704824
     },
     "eps Ind B": {
      "n": 12,
      "antisym_rms": 0.19335205949629916,
      "p": 0.8035491127218195
     }
    }
   },
   "diff": {
    "scale": 1.0529124052778656,
    "frames": 4,
    "n": 28,
    "median_rchi2": 1.3347346865408507,
    "antisymmetry": {
     "Barnard's Star": {
      "n": 16,
      "antisym_rms": 0.19944574735502008,
      "p": 0.5016245938515371
     },
     "eps Ind B": {
      "n": 12,
      "antisym_rms": 0.19141689073339838,
      "p": 0.8035491127218195
     }
    }
   }
  },
  "6": {
   "n": 9,
   "frames": 4,
   "median_rchi2_variance": 1.1889379575260355,
   "block12": {
    "scale": 1.0141971597171047,
    "frames": 4,
    "n": 9,
    "median_rchi2": 1.1533512183134755,
    "antisymmetry": {
     "Barnard's Star": {
      "n": 5,
      "antisym_rms": 0.4042201597321093,
      "p": 0.4361409647588103
     },
     "eps Ind B": {
      "n": 4
     }
    }
   },
   "block16": {
    "scale": 1.0382737907620303,
    "frames": 4,
    "n": 9,
    "median_rchi2": 1.1149467980818968,
    "antisymmetry": {
     "Barnard's Star": {
      "n": 5,
      "antisym_rms": 0.38914826359500454,
      "p": 0.44188952761809547
     },
     "eps Ind B": {
      "n": 4
     }
    }
   },
   "block24": {
    "scale": 1.0321456598362455,
    "frames": 4,
    "n": 9,
    "median_rchi2": 1.1244872686012453,
    "antisymmetry": {
     "Barnard's Star": {
      "n": 5,
      "antisym_rms": 0.3959589410528302,
      "p": 0.43064233941514624
     },
     "eps Ind B": {
      "n": 4
     }
    }
   },
   "diff": {
    "scale": 1.0318558306618675,
    "frames": 4,
    "n": 9,
    "median_rchi2": 1.0684931892324507,
    "antisymmetry": {
     "Barnard's Star": {
      "n": 5,
      "antisym_rms": 0.38963126774705364,
      "p": 0.4213946513371657
     },
     "eps Ind B": {
      "n": 4
     }
    }
   }
  }
 },
 "frames": [
  {
   "frame": "level2_2025W40_1A_0441_1D1_spx_l2b-v20-2025-277.fits",
   "field": "Barnard's Star",
   "detector": 1,
   "release": "qr2",
   "block12": 1.2393133878749953,
   "block16": 1.2059901612665371,
   "block24": 1.2084403333089178,
   "diff": 1.1218133303877302
  },
  {
   "frame": "level2_2026W35_1A_0375_1D1_spx_l2b-v27-2026-243.fits",
   "field": "Barnard's Star",
   "detector": 1,
   "release": "qr3",
   "block12": NaN,
   "block16": NaN,
   "block24": 1.254379211186158,
   "diff": 1.1787395161291534
  },
  {
   "frame": "level2_2026W11_2A_0501_1D2_spx_l2b-v24-2026-094.fits",
   "field": "Barnard's Star",
   "detector": 2,
   "release": "qr2",
   "block12": NaN,
   "block16": NaN,
   "block24": 1.3822706148488628,
   "diff": 1.308362487675705
  },
  {
   "frame": "level2_2026W34_2A_0233_1D2_spx_l2b-v27-2026-243.fits",
   "field": "Barnard's Star",
   "detector": 2,
   "release": "qr3",
   "block12": NaN,
   "block16": NaN,
   "block24": NaN,
   "diff": 1.1324867704985186
  },
  {
   "frame": "level2_2026W12_1A_0598_4D3_spx_l2b-v24-2026-082.fits",
   "field": "Barnard's Star",
   "detector": 3,
   "release": "qr2",
   "block12": NaN,
   "block16": 1.4319261492821842,
   "block24": 1.4417049855822794,
   "diff": 1.3499463867890957
  },
  {
   "frame": "level2_2026W34_1A_0308_1D3_spx_l2b-v27-2026-243.fits",
   "field": "Barnard's Star",
   "detector": 3,
   "release": "qr3",
   "block12": NaN,
   "block16": NaN,
   "block24": NaN,
   "diff": 1.2764053467137784
  },
  {
   "frame": "level2_2025W40_1A_0441_1D4_spx_l2b-v20-2025-277.fits",
   "field": "Barnard's Star",
   "detector": 4,
   "release": "qr2",
   "block12": NaN,
   "block16": NaN,
   "block24": 1.2516009336793232,
   "diff": 1.2617099304060198
  },
  {
   "frame": "level2_2026W35_1A_0375_1D4_spx_l2b-v27-2026-243.fits",
   "field": "Barnard's Star",
   "detector": 4,
   "release": "qr3",
   "block12": NaN,
   "block16": NaN,
   "block24": NaN,
   "diff": 1.1635292098453638
  },
  {
   "frame": "level2_2026W11_2A_0501_1D5_spx_l2b-v24-2026-094.fits",
   "field": "Barnard's Star",
   "detector": 5,
   "release": "qr2",
   "block12": 1.0102238433550845,
   "block16": 1.082560644334234,
   "block24": 1.0676879207561418,
   "diff": 1.0532831861532537
  },
  {
   "frame": "level2_2026W34_2A_0233_2D5_spx_l2b-v27-2026-243.fits",
   "field": "Barnard's Star",
   "detector": 5,
   "release": "qr3",
   "block12": 0.9708422755363285,
   "block16": 0.9362482904654337,
   "block24": 1.1064001174487998,
   "diff": 1.019879572607922
  },
  {
   "frame": "level2_2026W12_1A_0598_4D6_spx_l2b-v24-2026-082.fits",
   "field": "Barnard's Star",
   "detector": 6,
   "release": "qr2",
   "block12": 1.003521712188445,
   "block16": 1.0803922243255693,
   "block24": 1.0552957031816923,
   "diff": 1.0311492448723005
  },
  {
   "frame": "level2_2026W34_1A_0308_1D6_spx_l2b-v27-2026-243.fits",
   "field": "Barnard's Star",
   "detector": 6,
   "release": "qr3",
   "block12": 0.9694267148169995,
   "block16": 1.0017439164171713,
   "block24": 0.985371947038769,
   "diff": 1.0071864948801412
  },
  {
   "frame": "level2_2025W46_1A_0287_1D1_spx_l2b-v20-2025-318.fits",
   "field": "eps Ind B",
   "detector": 1,
   "release": "qr2",
   "block12": 0.96738122445328,
   "block16": NaN,
   "block24": NaN,
   "diff": 1.002282976662714
  },
  {
   "frame": "level2_2025W40_1A_0661_1D2_spx_l2b-v20-2025-277.fits",
   "field": "eps Ind B",
   "detector": 2,
   "release": "qr2",
   "block12": 1.231686973402381,
   "block16": 1.2445584681293498,
   "block24": 1.247550783418357,
   "diff": 1.2377281254831498
  },
  {
   "frame": "level2_2026W40_1A_0721_2D2_spx_l2b-v27-2026-276.fits",
   "field": "eps Ind B",
   "detector": 2,
   "release": "qr3",
   "block12": 1.1013918117908044,
   "block16": 1.0988237423359757,
   "block24": 1.139546498219877,
   "diff": 1.1276508224348982
  },
  {
   "frame": "level2_2025W40_1A_0067_2D3_spx_l2b-v20-2025-277.fits",
   "field": "eps Ind B",
   "detector": 3,
   "release": "qr2",
   "block12": 1.103732787718594,
   "block16": 1.2063690776215608,
   "block24": NaN,
   "diff": 1.0887392907701552
  },
  {
   "frame": "level2_2026W39_2A_0398_1D3_spx_l2b-v27-2026-271.fits",
   "field": "eps Ind B",
   "detector": 3,
   "release": "qr3",
   "block12": 1.1069276634383123,
   "block16": 1.1056792612472086,
   "block24": 1.122139706555885,
   "diff": 1.1009501178501482
  },
  {
   "frame": "level2_2025W46_1A_0348_1D4_spx_l2b-v20-2025-318.fits",
   "field": "eps Ind B",
   "detector": 4,
   "release": "qr2",
   "block12": 1.1465327545004165,
   "block16": NaN,
   "block24": NaN,
   "diff": 1.080422249707612
  },
  {
   "frame": "level2_2025W40_1A_0661_3D5_spx_l2b-v20-2025-277.fits",
   "field": "eps Ind B",
   "detector": 5,
   "release": "qr2",
   "block12": 1.0273624490606088,
   "block16": 1.0506752280476952,
   "block24": 1.057613006753982,
   "diff": 1.0655883354043119
  },
  {
   "frame": "level2_2026W40_1A_0721_2D5_spx_l2b-v27-2026-276.fits",
   "field": "eps Ind B",
   "detector": 5,
   "release": "qr3",
   "block12": 1.0363169637321716,
   "block16": 1.01338941126774,
   "block24": 1.0360380644300111,
   "diff": 1.0525416244024774
  },
  {
   "frame": "level2_2025W40_1A_0067_3D6_spx_l2b-v20-2025-277.fits",
   "field": "eps Ind B",
   "detector": 6,
   "release": "qr2",
   "block12": 1.0248726072457646,
   "block16": 1.032648512682201,
   "block24": 1.0282585392333545,
   "diff": 1.0569420416006727
  },
  {
   "frame": "level2_2026W39_2A_0398_1D6_spx_l2b-v27-2026-271.fits",
   "field": "eps Ind B",
   "detector": 6,
   "release": "qr3",
   "block12": 1.0270401301140941,
   "block16": 1.0438990688418595,
   "block24": 1.0360327804391367,
   "diff": 1.0325624164514342
  }
 ]
}
```

## Metrics

| metric | value | threshold | pass |
|---|---|---|---|
| D1_median_rchi2_range | [2.0788653571752977, 3.9825577853208878] | <= 3 under every estimator (m_native.py F5 rule) | None |
| D2_median_rchi2_range | [1.2343033072703737, 2.620023857378682] | <= 3 under every estimator (m_native.py F5 rule) | True |
| D3_median_rchi2_range | [1.4811127567758047, 2.4099325764907102] | <= 3 under every estimator (m_native.py F5 rule) | True |
| D4_median_rchi2_range | [1.7465516421777654, 3.2508168265961093] | <= 3 under every estimator (m_native.py F5 rule) | None |
| D5_median_rchi2_range | [1.2288733732526296, 1.4541868460354364] | <= 3 under every estimator (m_native.py F5 rule) | True |
| D6_median_rchi2_range | [1.0684931892324507, 1.1533512183134755] | <= 3 under every estimator (m_native.py F5 rule) | True |
| replicated_antisymmetry_detectors | [] | none (p < 0.01 in both fields) | True |

## Caveats

- Revision 2 after a reviewer aid found the r1 verdict depended on the block size and on a miscalibrated antisymmetry yardstick; the r1 record is kept as superseded.
- Two fields only; D4 has few sky blocks in 12′ cutouts.
- recorded on a dirty working tree: code_digest identifies the exact code

git 5f9f54b (dirty) · contracts {'spherex.types': '0.1.0', 'http-api': '0.1.0'} · calibration 94e18b883fdc9b28 · author M · reviewer pending
