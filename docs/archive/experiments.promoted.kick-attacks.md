# Kick Attacks — a kick measured as an attack, on the mix

[← archive index](experiments_archive.md)

**Promoted v3.12 item 32** (ported as plan item 32, not a separate operator
verdict), into `src/analyzer/stages/kick_attacks.py` (`detect-kick-attacks`,
2.6, `artifacts/kick_attacks/kick_attacks.json`). Replaced nothing:
omnizart's `kick` over-fires (toms, snares, sub pads) and stays as it is; this
feeds only `kick_present` in `bar_features.json`.

Steep 40-120 Hz rise with a coincident 2-5 kHz click on the mix, pitch drop as
tie-break; weaker, duller repeats at a recurring offset are `echo`; off-grid
survivors keep x0.4 confidence. **Medicine `kick_present` right on 13 of 14
bars (bar 18 missed).** Agreement with omnizart kicks (+-50 ms, 27-song mean):
precision 0.44, recall 0.32; near-zero recall on Armin, Sash, StealTheShow,
Charli-VonDutch, ChangedTheWayYouKissMe (a hat bed hides the click). 6,767
attacks, 715 echoes, 35 % off-grid. Thresholds were set on Medicine (not held
out). Open items: `docs/issues.md`.

The "Kick Attacks" debugger lane still reads `reference/proposals/kick_attacks.json`
until it is re-pointed or retired (`docs/issues.md`); `experiments/kick_attacks/`
stays in the tree as the reference.
