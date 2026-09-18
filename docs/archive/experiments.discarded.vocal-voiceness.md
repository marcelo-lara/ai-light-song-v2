# Vocal Voiceness — vibrato + portamento + sibilance timbre discriminator, remainder

[← archive index](experiments_archive.md)

**Archived** 2026-09-17 — ran, measured. `sibilance` — the one cue that
separated true vocal from a pitched-instrument leak (AUC 0.990/0.959/0.813 on
`_test_song`/`ayuni`/`Queen of Kings`) — was already promoted into `src/`
(`vocals_phrase[].sibilance`, `arrangement_state.json`'s
`vocals_sibilance_song_mean`) and **stays promoted**; this closes out only
what was left open around it. Vibrato and portamento were always weaker
(AUC 0.70/0.72) and were never promoted. Frame-level presence (the noisy-OR
combination of all three) trails the shipped `whisperx_vad` on every song
measured: `ayuni` frame_acc/false_vocal 0.8708/0.0323 vs whisperX's
0.9881/0.0056; `Cinderella` 0.5480/0.0106 vs whisperX's 0.8614/0.0290. A
gated whisperX+sibilance fusion was tried and did not survive a leave-one-out
check (0.850 vs whisperX's own 0.845 — a wash, not a gain). `experiments/
vocal_voiceness/` stays in the tree as the record; the `4. Vocal Voiceness`
debugger lane was removed.
