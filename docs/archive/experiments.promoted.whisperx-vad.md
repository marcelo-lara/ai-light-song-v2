# WhisperX VAD — speech-VAD front-end promoted as `arrangement_state.json`'s `vocals_phrase`

[← archive index](experiments_archive.md)

v3.5 item 7. Full evidence trail in
[`../experiments/whisperx_vad/README.md`](../experiments/whisperx_vad/README.md).

**Promoted 2026-09-13**, operator decision, not a threshold gate. Best
candidate of items 4-7 by a wide margin: balanced accuracy `_test_song` 0.866,
`ayuni` 0.971 (arrangement_state's own RMS method: 0.942 / 0.921). Rescored on
the three-class scorer, `ayuni` frame_acc 0.9881 / false_vocal 0.0056 — its tell
is the residual class: 0.24 firing on "audible but not vocal" spans against the
incumbent's 0.82, because a speech VAD reads a flute leak or plucked-guitar
bleed as clearly not-speech where an RMS threshold cannot. Two known,
un-fixed weaknesses stay real: sustained/filtered vocals (band-limiting strips
consonant energy) and background chatter (which genuinely is speech).
`Cinderella - Ella Lee`'s rhythmic plucked-string leaks were its one loss
(frame_acc 0.8427; **0.8134 / false_vocal 0.0510** rescored 2026-09-13 against
the repaired 7-positive / 5-negative class map, where `arrangement_state` scores
0.9369 / 0.0040) — an absolute stem-floor fusion (`whisperX >= 0.2 AND stem
>= -38 dBFS`) fixes it (+0.039 frame_acc) but was fit to 3 songs and not
carried into the promotion. The other three scoreable songs cannot separate
detectors: `Armin` and `In da name of love` declare no negatives and
`What a Feeling` has 2 s evaluable — see `experiments/whisperx_vad/out/score.txt`.

**Promoted shape**: `arrangement_state.json`'s new `vocals_phrase` field —
whisperX's phrase spans (library-default hysteresis, never swept — sweeping
degrades boundary F1 monotonically), each with **`confidence` hardcoded
`1.0`**, by direct operator instruction ("when 'phrase' is detected the chances
that it happens is true") — collapsing whisperX's own graded per-span
confidence (0.56-0.98 measured) into an asserted-certain boolean. Published
additively alongside the existing RMS-based `blocks`, never merged into them —
a wrong call on one stem-presence method must never mask the other.

**Runs as its own service before `./analyze` (v3.6 item 2).** whisperX pins
torch~=2.8.0; the `app` image is pinned to torch==2.1.2 with
`natten==0.15.1+torch210cu121` (breaks on any torch bump) — merging is a real,
unresolved cost. Promoted out of `experiments/whisperx_vad/` into its own
top-level module (`whisperx_vad/`) and Compose service (`whisperx`):
`docker compose run --rm whisperx --song <path>` writes
`artifacts/whisperx-vad/whisperx_vad.json`; `src/`'s
`ui_data._whisperx_vocal_phrase` reads it and raises (never a guess, never a
silent `null`) if the song hasn't been run through that service yet.
Diarization was never attempted — gated checkpoint, no HF token in this
environment, and lead-plus-backing is simultaneous rather than turn-taking,
which defeats the diarization premise regardless.
