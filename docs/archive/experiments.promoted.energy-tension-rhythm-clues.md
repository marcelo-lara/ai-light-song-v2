# Energy / tension / rhythm clue producers — promoted into `section_clues.py`

[← archive index](experiments_archive.md)

v3.6 item 10. Full evidence trail (now historical) in each experiment's
`README.md` under `experiments/{rhythm_drum_ioi,rhythm_stem_autocorr,
rhythm_vocal_onsets,energy_level,tension_shape}/`.

**Promoted 2026-09-14**, per the plan's pre-approval (item 10 status), not a
threshold gate — item 6 had already ruled all five "keep (provisional), never
archived while truth is seed-only" and the port itself is what item 10 is.
Corpus exact-match against `segments.seed.json` (self-consistency scores,
since the seed shares each method — not independent accuracy):
`rhythm_drum_ioi` drums 0.6415 (34/53); `rhythm_stem_autocorr` bass 1.0000,
harmonic 1.0000, vocals 0.9811, drums 0.1698 (weaker than the IOI method on
the same field); `rhythm_vocal_onsets` vocals 0.0377 (2/53, weakest of the
three rhythm candidates — whisper-large-v3 on CPU over short spans yields
sparse onsets); `energy_level` energy 0.9811 (52/53) seed, 0/2 exact but 1/2
within-1 against the 2 human rows; `tension_shape` tension 0.7547 (40/53)
seed, 0.5000 (1/2) exact / 1.0000 (2/2) within-1 human — the best-agreeing
candidate against human rows and the strongest seed exact-match of the five.

**Promoted shape.** `src/analyzer/stages/section_clues.py` (a new phase-3
stage, registered as `section-clues` in `STAGE_PIPELINE_IDS`, run after
`contest-section-function`) ports all four `app`-image producers' math
directly (not an import — CLAUDE.md: `src/` never imports `experiments/`).
`rhythm_vocal_onsets` is the exception: its compute (whisper-large-v3 word
onsets over the vocal stem) moved into `whisperx_vad/vocal_onsets.py`
instead, a second output of the `whisperx` Compose service, writing
`artifacts/whisperx-vad/vocal_onsets.json` — `section_clues` reads that file
and raises if it is missing (D10.1, never a silent skip). The stage fuses all
five into `sections.json`'s new `energy`, `energy_confidence`, `tension`,
`tension_confidence` and `rhythm` fields by a precedence chain (`segments.json`
human value > highest-confidence producer > `segments.seed.json` seed,
`confidence: null`, source `seed_unreviewed` > absent) — still provisional
until the operator reviews the seeds, same rule item 6 stated. Deleted:
`experiments/{rhythm_drum_ioi,rhythm_stem_autocorr,energy_level,
tension_shape,rhythm_vocal_onsets}/{compute,export,paths,run,score}.py` and
their `experiments/queue.toml` rows — `README.md` kept in each directory as
the historical record.
