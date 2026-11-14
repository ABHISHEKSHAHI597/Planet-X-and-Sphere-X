# M-lightcurve-covariance — PASS (L1)

# Synthetic covariance validation
```
..                                                                       [100%]
2 passed in 1.75s

```
Not real-data acceptance or a calibrated periodogram FAP.

## Metrics

| metric | value | threshold | pass |
|---|---|---|---|
| noise_trials | 500 | variances agree within 20%, PSD and no detector leakage | True |

## Caveats

- recorded on a dirty working tree: code_digest identifies the exact code

git d6d2e45 (dirty) · contracts {'spherex.types': '0.1.0', 'http-api': '0.1.0'} · calibration 94e18b883fdc9b28 · author M · reviewer pending
