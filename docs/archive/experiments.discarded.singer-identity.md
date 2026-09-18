# Singer Identity — ECAPA-TDNN speaker embeddings for "is this a voice, and whose?"

[← archive index](experiments_archive.md)

v3.5 item 8. `experiments/singer_identity/` deleted — this entry carries the
numbers.

**Discarded 2026-09-13** by the operator: the declared lead-vocalist counts
proved useless — they add noise to validation. Do not reintroduce singer
counts as ground truth.

**Method.** ECAPA-TDNN (`speechbrain/spkrec-ecapa-voxceleb`) embeddings over
1.5 s / 0.25 s vocal-stem windows gated by whisperX VAD >= 0.2, agglomerative
clustering, k chosen by silhouette with a k=1 collapse test; two outputs,
`voice_similarity` (voiceness) and `singer_change` (cluster-switch points).

**Singer count 4/9** on the 9 declared songs. All 5 misses are one-singer
songs over-split: `Chimera` k=2, `Titanium` k=3 (39 changes, 10.07/min),
`Sash` k=2, `Rapture` k=2 (9.47/min), `Born Slippy` k=2. Max centroid
similarity 0.33-0.48, silhouette 0.12-0.35 — no gate separates hits from
misses. A `MERGE_SIMILARITY` sweep reached 8/9 at 0.15-0.25, but that setting
then collapsed the duet `Only this moment` (0.438) — no single value works.

**`Armin`'s one marked singer handoff (~81.6 s) was missed** — its only two
change points fell at 12.6 s and 14.1 s.

**Voiceness also failed its own kill condition** (frame_acc / false_vocal
rate vs whisperX): `ayuni` 0.8905 / 0.0160 vs **0.9881 / 0.0056**;
`Cinderella - Ella Lee` 0.5918 / 0.0925 vs **0.8134 / 0.0510**.
