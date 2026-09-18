# Drop Proposals (`drop_detection`) — hand-built role-change detector

[← archive index](experiments_archive.md)

**Archived** 2026-09-14 — ran, measured, negative. v3.6 item 3 settles the
orphan lane (`experiments/drop_detection/` was never given its own queue
entry — see `experiments.md` "Loose ends"). Its stage-1 candidate proposals
score **4/7 @±0.5s** (tighter tolerance than gestures.py's own ±1.0s) but at
precision 0.048 — 84 predictions across 4 songs for 7 true impacts. The
shipped `gestures.py` stage matches its recall at a *looser* tolerance for a
fraction of the false-positive rate: **4/7 @±1.0s at 4.5-10.3 events/min**
(all event types) against drop_detection's ~20+ candidates/song. `gestures.py`
beats it outright; the model survey in this directory's own README already
recommended `allin1`/MERT over the hand-built detector. `experiments/
drop_detection/` stays in the tree as a cache other experiments still read
(item 7 decides its fate); code and the `drop_impacts` lane are untouched
here.
