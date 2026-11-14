# G3-gaia — INCONCLUSIVE (L3)

# Three-target retained catalogue comparison
```json
{
  "barnard": {
    "track_block": "Historical extraction lacks tangent_origin; rerun native API",
    "reference_name": "Barnard's Star",
    "extraction": "retained JSON; not a fresh pixel extraction",
    "visits": [],
    "catalogue_comparison": {
      "measured_mu": 12.205262484503866,
      "catalogue_mu": 10.393348518010786,
      "measured_pa": 358.4166128049205,
      "catalogue_pa": 355.576869477875,
      "mu_difference": 1.81191396649308,
      "pa_difference": 2.8397433270454826,
      "fit_chi2": 2225.2052405365343,
      "fit_dof": 78,
      "catalogue_source": "manifest catalogue"
    }
  },
  "epsindb": {
    "track_block": "Historical extraction lacks tangent_origin; rerun native API",
    "reference_name": "eps Ind B",
    "extraction": "retained JSON; not a fresh pixel extraction",
    "visits": [],
    "catalogue_comparison": {
      "measured_mu": 4.627931236896367,
      "catalogue_mu": 4.684164914342043,
      "measured_pa": 121.63511995141627,
      "catalogue_pa": 121.7781862182898,
      "mu_difference": -0.0562336774456762,
      "pa_difference": -0.1430662668735181,
      "fit_chi2": 3035.1612296355415,
      "fit_dof": 712,
      "catalogue_source": "Gaia DR3 6412596012146801152"
    }
  },
  "wise0855": {
    "track_block": null,
    "reference_name": "WISE 0855\u22120714",
    "extraction": "retained JSON; not a fresh pixel extraction",
    "visits": [
      {
        "visit": "V2",
        "n": 1,
        "offset_arcsec": [
          -0.7600285527124702,
          0.40411275363711696
        ],
        "covariance": [
          [
            0.1154798849966111,
            -0.019450784234238593
          ],
          [
            -0.01945078423423859,
            0.11277365515447911
          ]
        ],
        "normalized_axes": [
          -2.236540344790056,
          1.2033687478579678
        ],
        "mahalanobis2": 5.698293144269664,
        "excess_chi2": 1.1911207279263698e-31,
        "dof": 0
      },
      {
        "visit": "V4",
        "n": 1,
        "offset_arcsec": [
          0.13965961892563336,
          0.14538271037120465
        ],
        "covariance": [
          [
            0.10975363735349548,
            -0.03215738918938546
          ],
          [
            -0.03215738918938546,
            0.09998540595495704
          ]
        ],
        "normalized_axes": [
          0.4215619372680804,
          0.459774048221595
        ],
        "mahalanobis2": 0.5609663274180733,
        "excess_chi2": 7.749351744502913e-33,
        "dof": 0
      }
    ],
    "catalogue_comparison": {
      "measured_mu": 6.14958162340497,
      "catalogue_mu": 8.151545861368872,
      "measured_pa": 270.9904501899367,
      "catalogue_pa": 274.7371995341568,
      "mu_difference": -2.001964237963902,
      "pa_difference": -3.7467493442200634,
      "fit_chi2": 2.1693674893577825e-29,
      "fit_dof": 0,
      "catalogue_source": "SIMBAD J2000 (linear)"
    }
  }
}
```
This is a retained-output comparison, not a fresh independent L4 catalogue acquisition. Barnard central PM mismatch/excess chi-square and F5/F15 failures prevent acceptance; epsilon Indi central agreement alone does not validate errors. I review and an authentic provenance-bearing external astrometric comparison remain required.

## Metrics

| metric | value | threshold | pass |
|---|---|---|---|

## Caveats

- recorded on a dirty working tree: code_digest identifies the exact code

git d6d2e45 (dirty) · contracts {'spherex.types': '0.1.0', 'http-api': '0.1.0'} · calibration 94e18b883fdc9b28 · author M · reviewer pending
