# F13 — PASS (L2)

# F13
Locked IMAGE maps, exact values and sky orientation. OMEGA_MEDIAN comparisons use the actual native frame headers fetched by m_native.py for each detector, not an approximate pixel-scale constant.

## Metrics

| metric | value | threshold | pass |
|---|---|---|---|
| D1 | {'min': 37.45560836791992, 'median': 37.86044692993164, 'max': 38.37782287597656, 'relative_to_omega_median': [-0.010704469662180971, -1.1678986549856774e-05, 0.013653503164514191], 'frame_omega_median': 37.860889106746285, 'bunit': 'arcsec2', 'detcoord': 'sky'} | positive finite 2040x2040 arcsec^2 in sky orientation | True |
| D2 | {'min': 37.41252899169922, 'median': 37.69452667236328, 'max': 38.03976821899414, 'relative_to_omega_median': [-0.007505879490847467, -2.4935336593867596e-05, 0.009133766692414724], 'frame_omega_median': 37.69546662151155, 'bunit': 'arcsec2', 'detcoord': 'sky'} | positive finite 2040x2040 arcsec^2 in sky orientation | True |
| D3 | {'min': 37.446685791015625, 'median': 37.86412811279297, 'max': 38.380638122558594, 'relative_to_omega_median': [-0.010982993990524825, 4.22154918302553e-05, 0.013683934982928303], 'frame_omega_median': 37.86252972747859, 'bunit': 'arcsec2', 'detcoord': 'sky'} | positive finite 2040x2040 arcsec^2 in sky orientation | True |
| D4 | {'min': 37.53776931762695, 'median': 37.932926177978516, 'max': 38.46365737915039, 'relative_to_omega_median': [-0.010409289484349604, 8.046583001908303e-06, 0.013999465785790699], 'frame_omega_median': 37.93262094999556, 'bunit': 'arcsec2', 'detcoord': 'sky'} | positive finite 2040x2040 arcsec^2 in sky orientation | True |
| D5 | {'min': 37.49059295654297, 'median': 37.77254104614258, 'max': 38.12245178222656, 'relative_to_omega_median': [-0.00741401894353344, 5.0726184574356736e-05, 0.009314823225149427], 'frame_omega_median': 37.770625086442955, 'bunit': 'arcsec2', 'detcoord': 'sky'} | positive finite 2040x2040 arcsec^2 in sky orientation | True |
| D6 | {'min': 37.54255294799805, 'median': 37.935359954833984, 'max': 38.4864616394043, 'relative_to_omega_median': [-0.010435715337508755, -8.192332798728774e-05, 0.014444274318281103], 'frame_omega_median': 37.93846800039132, 'bunit': 'arcsec2', 'detcoord': 'sky'} | positive finite 2040x2040 arcsec^2 in sky orientation | True |

## Caveats

- recorded on a dirty working tree: code_digest identifies the exact code

git 8d12a02 (dirty) · contracts {'spherex.types': '0.1.0', 'http-api': '0.1.0'} · calibration 94e18b883fdc9b28 · author M · reviewer pending
