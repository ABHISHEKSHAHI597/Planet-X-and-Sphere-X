# M-planetx-synthetic — PASS (L1)

# Synthetic image tracking and orphan recovery
```text
...                                                                      [100%]
3 passed in 22.77s

```
Shared table PSF, fixed spectrum, native white noise; 2000 independent noise draws check bilinear variance, centroid/total flux and ambiguous daily branch recovery at known distance. Initial 200-draw seed produced empirical variance .02974 vs .04180 prediction, outside unchanged 25% tolerance; increased Monte Carlo sample to 2000 to resolve sampling variability, with no formula/tolerance adjustment. Not proof of real TNO detection or false-positive rates.

## Metrics

| metric | value | threshold | pass |
|---|---|---|---|

## Caveats

- recorded on a dirty working tree: code_digest identifies the exact code

git d6d2e45 (dirty) · contracts {'spherex.types': '0.1.0', 'http-api': '0.1.0'} · calibration 94e18b883fdc9b28 · author M · reviewer pending
