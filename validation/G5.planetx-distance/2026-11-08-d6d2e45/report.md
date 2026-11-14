# G5.planetx-distance — INCONCLUSIVE (L4)

# Horizons geometry comparison
```json
{
  "Makemake": {
    "inferred": 52.78206916746814,
    "horizons_distance": 52.7504575499453,
    "fractional_error": 0.0005992671720980169
  },
  "Haumea": {
    "inferred": 49.847848778334196,
    "horizons_distance": 49.87833800312915,
    "fractional_error": 0.0006112718670185924
  },
  "Eris": {
    "inferred": 95.54716156784166,
    "horizons_distance": 95.53041816189474,
    "fractional_error": 0.0001752677970960903
  }
}
```
This tests geometry against independent ephemerides, not recovery of per-day image orphans. The real-image gate remains unaccepted.

## Metrics

| metric | value | threshold | pass |
|---|---|---|---|

## Caveats

- recorded on a dirty working tree: code_digest identifies the exact code

git d6d2e45 (dirty) · contracts {'spherex.types': '0.1.0', 'http-api': '0.1.0'} · calibration 94e18b883fdc9b28 · author M · reviewer pending
