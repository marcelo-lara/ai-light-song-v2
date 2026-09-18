# Archive — experiment index

One file per experiment: what it replaced (or would have), the numbers that
decided it, and the caveat it shipped or was dropped with.

**These are TLDRs.** The full writeup and the raw tables live in
`experiments/<topic>/README.md`, which stays in the tree as current material —
measured evidence does not go stale. Read that before extending a stage or
reviving a dropped candidate.

**A dropped un-run entry has no evidence behind it and must never be cited as
one.** It records a scoping decision, not a measurement.

Still open: [`../experiments.md`](../experiments.md).

## Promoted — beat the incumbent, moved into `src/`

| experiment | replaced | headline |
| --- | --- | --- |
| [All-In-One](experiments.promoted.all-in-one.md) | `stages/sections/`, 1,403 lines | boundary F1 **0.67** vs incumbent **0.29** |
| [Transition-FX gestures](experiments.promoted.transition-fx-gestures.md) | the `event_*` stack, ~3,800 lines | impacts **4/7** @±0.5 s vs incumbent **1/7** |
| [Arrangement state](experiments.promoted.arrangement-state.md) | nothing — new stage | `_test_song` F1 **0.59** @0.5 s vs `sections.json` **0.00** |
| [WhisperX VAD](experiments.promoted.whisperx-vad.md) | nothing — new `vocals_phrase` field | balanced accuracy 0.866–0.971 vs incumbent RMS 0.921–0.942 |
| [Energy / tension / rhythm clue producers](experiments.promoted.energy-tension-rhythm-clues.md) | nothing — new `section_clues.py` stage | best-agreeing seed exact-match 0.98 (energy) down to 0.04 (vocal onsets); still provisional |

## Discarded — tried and did not earn a place, or dropped before running

| experiment | verdict | what decided it |
| --- | --- | --- |
| [CLAP — section identity](experiments.discarded.clap-section-identity.md) | ran, negative | MFCC-20 **0.73** AUC vs CLAP **0.68** |
| [VocalParse](experiments.discarded.vocalparse.md) | ran, negative | 3 of 4 gold songs hallucinated as Mandarin |
| [Reactive band dynamics](experiments.discarded.reactive-band-dynamics.md) | ran, negative | at matched budget, incumbent **7/7** vs **4/7** @±0.5 s |
| [Bar grid by consensus](experiments.discarded.bar-grid-consensus.md) | ran, negative | consensus **3/7**, allin1 alone **4/7** |
| [Section identity embedding](experiments.discarded.section-identity-embedding.md) | dropped un-run | reopens a closed negative; 0.73 is the bar |
| [Music Flamingo](experiments.discarded.music-flamingo.md) | dropped un-run | non-commercial licence blocks promotion |
| [CLAP voiceness](experiments.discarded.clap-voiceness.md) | ran, negative | inverted, not merely weak: mean balanced accuracy 0.451 |
| [Singer Identity](experiments.discarded.singer-identity.md) | ran, negative | singer count **4/9** on declared songs; voiceness below whisperX on `Cinderella` |
| [SongFormer](experiments.discarded.songformer.md) | dropped un-run | third pending cycle, own stated rule; needs a new multi-GB sandbox image not built |
| [Texture Novelty](experiments.discarded.texture-novelty.md) | ran, negative | kill condition (P>0.5 @ R≥0.8) FAIL every feature set; best pooled F1 0.29 vs `sections.json` 0.27 |
| [Structural vs Micro](experiments.discarded.structural-vs-micro.md) | ran, negative | phrase-grid macro-F1 **0.38** vs duration-only baseline **0.82** |
| [Drop Proposals (`drop_detection`)](experiments.discarded.drop-proposals.md) | ran, negative | `gestures.py` **4/7 @±1.0s** at 4.5-10.3 events/min beats candidate proposals' 4/7 @±0.5s at precision 0.048 (84 fires for 7 true) |
| [Vocal Voiceness (remainder)](experiments.discarded.vocal-voiceness.md) | ran, negative except sibilance | frame_acc `ayuni`/`Cinderella` 0.8708/0.5480 vs `whisperx_vad`'s 0.9881/0.8614; sibilance cue already promoted separately |
| [SVD Tagger](experiments.discarded.svd-tagger.md) | ran, negative | best per-song-rescaled frame_acc 0.8538/0.5125 vs `whisperx_vad`'s 0.9881/0.8614, at the cost of its own sandbox image + 327 MB model pin |
| [Phrase Periodicity](experiments.discarded.phrase-periodicity.md) | ran, positive, not promoted | passed its kill condition (bass prominence **+0.158**/**+0.125** on the two known-8-bar songs vs **+0.075** max elsewhere) but classifies block character, not a top-level field |
| [Voice Multiplicity](experiments.discarded.voice-multiplicity.md) | ran, positive, not promoted | AUC **0.951** on `Queen of Kings`, the only song with `voices` labels — data-starved, not contradicted |
