# Drop detection and song dynamics — exploration harness

Two experiments live in this directory.

* **`./`** — the hand-built role-change detector (v2.2 items 3–7). Level
  statistics over the demucs stems. Written up under
  [Part 1](#part-1--the-hand-built-role-change-detector).
* **`research/`** — a survey of pretrained models, run 2026-09-01, asking
  whether a learned representation reads song dynamics better than hand-built
  level statistics, and what *else* it can read. Written up first, below,
  because it changes the recommended direction.

Neither is imported by `src/analyzer`. Both read the artifacts the pipeline
already produces plus the human marks in `reference/human/human_hints.json`.

---

# Part 2 — model survey (2026-09-01)

## The short version

**Inferred drops are not good enough because "drop" is the wrong primitive.**
Every measurement below points the same way: the thing the models get right is
*sections* — where a song changes part, which part it is, and which other parts
are the same part. A drop is not an independent event to be detected; on all
seven labelled impacts it is a **transition between two named sections**, and
the models that read it best are the ones that were never asked about drops.

Three concrete replacements, in order of how well they held up:

1. **`allin1` (All-In-One) for named functional structure.** Gives
   `intro / verse / chorus / bridge / inst / solo / outro` boundaries quantised
   to the 8-bar phrase, plus its own beats and downbeats, from one model. On
   Titanium it names all three human "drop impacts" exactly right and lands
   them within 0.6 s — as `chorus → inst`, `chorus → inst`, `chorus → outro`.
   Non-degenerate labels on **18 of 21** corpus songs.
2. **MERT self-similarity for section *identity*.** Clusters beats into
   repeating parts. On Titanium all three drops enter the *same* cluster, which
   appears nowhere else in the song; on Armin both drops enter the same cluster.
   This is the "the chorus is back, reuse the look" signal the pipeline has no
   equivalent of today.
3. **CLAP as a *differential* probe, never an absolute one.** Its response
   across a boundary is informative; its top-scoring sentence for a segment is
   not. And the sentence that responds most reliably to a drop is *not* the one
   containing the word "drop".

And one finding that is worth acting on regardless of which model wins:

> **The current pipeline's `sections.json` boundaries land near a human drop
> impact 0 times out of 7 at ±1.0 s, and 1 out of 7 at ±2.0 s.** Whatever it
> is segmenting, it is not the song's form. It is also worse than a plain
> librosa CQT baseline built with the same peak-picking code (1/7 and 4/7).

## What was tried

| model | what it gives | cost per song | verdict |
| --- | --- | --- | --- |
| [`allin1`](https://github.com/mir-aidj/all-in-one) (Harmonix-trained) | named functional segments, beats, downbeats, tempo | ~6 s GPU (stems pre-seeded) | **adopt** |
| [`MERT-v1-95M`](https://huggingface.co/m-a-p/MERT-v1-95M) | 75 Hz × 768 frame embeddings, 13 layers | ~9 s GPU | **adopt** for boundaries + identity |
| [`laion/larger_clap_music`](https://huggingface.co/laion/larger_clap_music) | audio↔text similarity over sliding windows | ~35 s GPU | **partial** — differentials only |
| [`beat-this`](https://github.com/CPJKU/beat_this) (`final0`, DBN) | beats, downbeats | ~2 s GPU | **no** — no better than essentia here |
| librosa CQT + the same novelty code | boundaries | CPU only | baseline, clearly beaten |
| current `sections.json` | boundaries + mood adjectives | — | baseline, beaten by everything |

All four fit on the 4 GB GTX 1650. Nothing here needed training, which was the
binding constraint: the corpus has **seven** labelled instants across four
songs, so every method that had to be *fitted* was ruled out before it started.

## Measurement 1 — structural boundaries against the seven impacts

A drop impact is a major structural transition, so "does this representation
put a boundary there" is a fair, label-cheap proxy for structural quality.
Precision cannot be measured (a song has many real boundaries and only the
impacts are labelled), so the boundary *budget* is reported as the precision
axis: how many boundaries per minute a method is allowed to spend.

Full output: [`research/out/boundaries.txt`](research/out/boundaries.txt),
[`research/out/sweep.txt`](research/out/sweep.txt).

| representation | ±0.5 s | ±1.0 s | ±2.0 s | boundaries/min |
| --- | --- | --- | --- | --- |
| **MERT layer 2, beat-sync SSM** | 2/7 | **5/7** | **7/7** | 4.4 |
| MERT layer 2+4+6+8 | 2/7 | 4/7 | 6/7 | 4.5 |
| MERT layer 6 | 2/7 | 4/7 | 6/7 | 4.5 |
| MERT layer 9 | 1/7 | 3/7 | 4/7 | 4.6 |
| **CLAP semantic novelty** | 2/7 | 4/7 | 5/7 | **3.8** |
| CLAP window SSM | 1/7 | 2/7 | 2/7 | 4.2 |
| MERT + CLAP novelty, summed | 2/7 | 3/7 | 6/7 | 4.4 |
| `allin1` segment starts | **3/7** | 4/7 | 6/7 | 4.0 |
| librosa CQT (classical baseline) | 0/7 | 1/7 | 4/7 | 4.4 |
| **current pipeline `sections.json`** | **0/7** | **0/7** | **1/7** | 4.6 |

Two things to read off this table:

* The learned representations are not marginally better than the current
  segmentation, they are categorically better. `sections.json` is at chance.
* CLAP's semantic novelty is the most *efficient*: it reaches 4/7 while
  emitting fewer boundaries, and its score does not change when the budget is
  cut from 6/min to 1.5/min, because it simply does not propose many. That
  makes it a good second opinion, not a good primary detector.

A MERT layer sweep ([`research/out/layers.txt`](research/out/layers.txt)) puts
the best structural signal in the **low-middle layers (2–5)**, not the top. The
last four layers are measurably worse (4/7 at ±2.0 s versus 7/7). Anything
built on "just take the final hidden state" would have left most of this on the
table.

## Measurement 2 — `allin1` names the transition, not just its position

This is the result that matters most. On Titanium the segmentation is textbook:

```
   0.00 –  14.30  intro
  14.30 –  44.77  verse          (2 phrases)
  44.77 –  75.25  chorus         (2 phrases)
  75.25 –  90.49  inst    <<< human drop impact 74.66
  90.49 – 120.97  verse          (2 phrases)
 120.97 – 151.44  chorus         (2 phrases)
 151.44 – 166.67  inst    <<< human drop impact 151.26
 166.67 – 181.92  bridge
 181.92 – 212.39  chorus         (2 phrases)
 212.39 – 232.44  outro   <<< human drop impact 212.01
```

All three hand-placed impacts are `chorus → inst` or `chorus → outro`
boundaries, hit at +0.59 / +0.18 / +0.38 s. The drop is not a separate thing
the model had to find; it *is* the section change, and the label pair says what
kind of change it is — which is exactly what decides the lighting look.

Boundaries come out quantised to the 8-bar phrase (15.24 s at 125 BPM = 32
beats), which is why they are so clean: the model is not localising an event,
it is placing a phrase edge.

Across the whole corpus ([`research/out/corpus.txt`](research/out/corpus.txt)),
`allin1` produced a varied functional read on 18 of 21 songs. It degenerates
on three:

| song | labels produced |
| --- | --- |
| Armin - Revolution | `intro`, `inst` only — 82 % one label |
| Chimera - Hana | `intro`, `inst` only |
| `_test_song` | `intro`, `chorus` — but it is a 58 s excerpt, so this is arguably correct |

> **Superseded, 2026-09-02.** This degeneracy is an artifact of the source
> separation, not a property of the model. The cache these three rows were
> computed from let `allin1` run its own `demucs`, whose output is not
> reproducible; re-run against the pipeline's fixed stems, Armin comes back as
> `intro verse inst verse chorus inst` and Chimera as eight sections with six
> distinct labels. Only `_test_song` still degenerates. Measurement and cause in
> [`../allin1/README.md`](../allin1/README.md) "Measurement 2". The paragraph
> below is kept because the *detector* it describes is still the right idea.

The pattern in the two real failures is instrumental trance with no
verse/chorus vocal contrast — outside the Harmonix pop distribution the model
was trained on. **This is detectable without labels** (count distinct labels,
check the dominant label's share), so the artifact can honestly say
`function: unknown` on those songs instead of writing `intro` nine times. That
matches the constitution's "fail explicitly or mark `unknown`" rule.

Armin is also the one song where the boundary is genuinely missed: the 57.83 s
impact has no `allin1` boundary within 8.6 s. MERT layer 2 finds it at −1.78 s.
The two methods fail on different songs, which is an argument for keeping both.

## Measurement 3 — MERT recovers section *identity*

Spectral clustering of the MERT beat-synchronous recurrence graph
(McFee & Ellis style, [`research/structure.py`](research/structure.py)) labels
each beat with a part id. Full output:
[`research/out/identity.txt`](research/out/identity.txt).

On Titanium, with five clusters over MERT layers 4+6+8+10 and no supervision:

* cluster 2 occupies 75.2–91.4, 151.4–163.8 and 212.4–228.1 — **all three drop
  sections and nothing else**;
* cluster 3 covers both verses (14.8–25.7, 30.5–41.0, 95.7–101.9, 106.2–117.6)
  and appears nowhere else;
* the sung choruses do **not** come out clean. The first two split half and
  half across clusters 0 and 1; the third is cluster 1 throughout, and cluster
  0 also covers the bridge. "One section, one id" is not what five free-running
  clusters produce here.

On Armin both drops enter the same cluster. On Hideaway and `_test_song` the
run boundaries are 1–3 s off, and the identity is less clean.

Pooled *inside* `allin1`'s segments instead — layers 2+4+6+8, majority cluster
per segment ([`research/out/describe.txt`](research/out/describe.txt)) — the
two models agree without being told to on every segment of Titanium:

| `allin1` says | MERT identity |
| --- | --- |
| `verse` ×2 | 2, 2 |
| `chorus` ×3 | 1, 1, 1 |
| `inst` ×2 | 3, 3 |
| `bridge` | 0 |
| `outro` | 3 — the same id as the two `inst` drops, which is musically right: Titanium's outro *is* the instrumental drop one more time |

Two models trained on different objectives converging on the same partition is
the strongest evidence in this survey. It also shows the right way to combine
them: let `allin1` set the boundaries and let MERT vote on identity *within*
them, rather than letting MERT find its own runs.

This is the piece with no counterpart in the current artifacts. In
`sections.json` the section covering Titanium's first chorus is "004 Vocal
Spotlight (0.75)" and the one covering its second is "010 Groove Plateau
(0.78)" — nothing in the file says they are the same part of the song, so
nothing downstream can reuse a look when it comes back.

## Measurement 4 — the bar grid is not trustworthy from any single tracker

Full output: [`research/out/downbeats.txt`](research/out/downbeats.txt).

| grid | median \|err\| to the 7 impacts | within 0.1 s | within 0.25 s |
| --- | --- | --- | --- |
| essentia **beat** | 0.135 s | 1/7 | **7/7** |
| beat-this **beat** (DBN) | 0.125 s | 2/7 | **7/7** |
| essentia **downbeat** | 0.317 s | 0/7 | 3/7 |
| beat-this **downbeat** (DBN) | 0.390 s | 1/7 | 3/7 |
| `allin1` **downbeat** | 0.240 s | 1/7 | **4/7** |

Every impact is on *a* beat on every tracker. No tracker agrees with the
others about which beat is beat 1, and they disagree in different places:
essentia has Titanium's bar phase right at 74.66 s and 212.01 s and one beat
out at 151.26 s; beat-this is right at 151.26 s and one beat out at the other
two. Adding a second neural tracker did **not** fix the v2.2 bar-grid problem.

Two consequences:

* Keep snapping cue instants to the **beat** grid, as
  [`candidates.localize`](candidates.py) already does. Do not gate anything on
  the downbeat.
* If a bar grid is needed, derive it from **agreement between trackers plus the
  phrase boundaries** (`allin1` already emits 8-bar-quantised segment edges),
  not from any one tracker's `beat_position` field. Record it with an explicit
  confidence, and mark it `unknown` where they disagree.

Note also that `beat-this` without its DBN post-processor halves its tempo
inside sparse passages — 264 beats against essentia's 415 on Armin. `dbn=True`
is mandatory, and it is off by default.

## Measurement 5 — what CLAP can and cannot be asked

CLAP is the only model here that can be asked a question in words, so it got
the most attention, and it produced the survey's most counter-intuitive result.

**Raw cosines are unusable.** Scored directly, "a verse …" outranks every other
role sentence at every instant on all four songs, and "no drums at all" wins on
Titanium, which is four-on-the-floor throughout. The offset is a property of
the sentence, not the music. Even after z-scoring each sentence over time, all
thirteen curves still moved *together* — at Titanium 151.26 s, `drop`,
`breakdown`, `build-up`, `vocals` and `no-beat` all fell by ~1.5σ at once,
which says nothing. Two centrings are required, in this order: across sentences
within a window, then across time within a sentence
([`research/clap.py`](research/clap.py) `zscored`).

**With that fixed, differentials are informative — but not the ones you'd
expect.** Ranking 26 sentences by how consistently their response changes
across the seven impacts ([`research/out/vocab.txt`](research/out/vocab.txt)):

| sign agreement | mean Δ | sentence |
| --- | --- | --- |
| **7/7** | **+1.12** | *the chorus, the biggest and catchiest part of the song* |
| **7/7** | **−0.69** | *a long filter sweep rising towards something* |
| **7/7** | −0.68 | *a verse, the singer telling the story over a light backing* |
| 6/7 | +1.76 | *a dense wall of sound, everything playing at once* |
| 6/7 | −1.17 | *a breakdown where the drums drop out …* |
| 5/7 | −0.77 | *a build-up with a rising riser and a snare roll, tension increasing* |
| 5/7 | −0.68 | *the drop, the beat slams back in at full power* |
| 4/7 | −0.06 | *an impact hit with a crash cymbal on the downbeat* |

The literal drop sentence is near the bottom, and its mean response is
*negative* — CLAP scores a drop as slightly **less** "the drop" after it
happens than before. The reliable readings are "the filter sweep stopped" and
"the chorus arrived". Re-running with a 4 s analysis window instead of 10 s
changes the ranking barely at all — the top two sentences are the same, with
the same signs ([`research/out/vocab-window4.txt`](research/out/vocab-window4.txt)).
So this is CLAP's semantics, not a resolution artefact. Both runs guard the
before/after windows by half the analysis window, which is easy to forget: with
a 10 s window centred on its timestamp, "one second before the impact" already
contains four seconds of the drop.

**Absolute per-segment naming does not work.** Asking for the top-scoring
sentence per `allin1` segment produces plausible-looking nonsense — Titanium's
sung choruses come back as "a sudden silence right before the beat returns"
([`research/out/describe.txt`](research/out/describe.txt)). Do not put CLAP's
argmax in an artifact.

**Composite "tension" and "intensity" curves did not survive contact with the
labels.** Averaging the three riser sentences into a tension curve and checking
its percentile in the eight guarded seconds before each impact gives 66, 28,
79, 34, 37, 59, 52 — no signal. The intensity curve is only slightly better:
it rises across five of the seven impacts and falls across two
([`research/out/dynamics.txt`](research/out/dynamics.txt)).
This was the most attractive idea going in (a continuous, named intensity
envelope to drive fixture brightness) and it is the one that failed hardest.
If a continuous energy curve is wanted, derive it from the stems, which
already work; do not derive it from CLAP.

## Measurement 6 — does a learned region fix the ±0.5 s problem? Partly

The existing stage-3 localiser ([`candidates.localize`](candidates.py)) was
built to place an instant on the beat grid given a region, and its measured
weakness was the regions it was given. Feeding it `allin1` and MERT regions
instead ([`research/out/hybrid.txt`](research/out/hybrid.txt)):

* raw proposed region within 0.5 s: **8 / 18** (song, impact, source) trials;
* after localisation: **10 / 18**;
* per impact, best over sources: **4 / 7** — the same as Part 1's end-to-end
  score.

So the localiser helps on average but is not the missing piece, and twice it
actively hurts: it drags Titanium's 212.01 s impact from a correct +0.38 s
region out to −1.53 s, and pushes `_test_song`'s from +0.72 s to +1.64 s.
Snapping the `allin1` boundary to the essentia beat grid or
to `allin1`'s own downbeats changes nothing (median |err| 0.578 / 0.595 s
against 0.595 s raw).

**The honest reading is that ±0.5 s is at the noise floor of the labels.** The
human marks sit a median 0.135 s off the nearest beat and up to 0.23 s off;
they were placed by clicking, not by locating a bar line. Before any more
effort goes into localisation, the ground truth should be re-derived as *the
downbeat of the bar in which the section changes*, so that the target is a
musical fact rather than a hand position.

## What this suggests the artifact should be

Not a list of `drop approach / build / tension / impact / release` hints. A
**section table with identity, plus explicitly-typed transitions between
sections**:

```jsonc
{
  "sections": [
    {
      "start": 44.77, "end": 75.25,
      "function": "chorus",          // allin1, with confidence
      "identity": "B",               // MERT cluster: which other sections are this one
      "phrase_bars": 16,             // from the 8-bar quantised grid
      "confidence": 0.81
    },
    {
      "start": 75.25, "end": 90.49,
      "function": "inst", "identity": "C", "phrase_bars": 8, "confidence": 0.74
    }
  ],
  "transitions": [
    {
      "at": 75.25,                   // snapped to the beat grid
      "from": "chorus", "to": "inst",
      "kind": "drop",                // derived from the label pair + stem evidence
      "lead_in": { "start": 60.01, "kind": "build" },
      "confidence": 0.74
    }
  ]
}
```

The properties that make this better than the current shape:

* **`function` and `identity` are separate.** One says what part this is, the
  other says which other parts are the same. The current file has neither, and
  a light show needs both — the first to choose a look, the second to reuse it.
* **`kind: "drop"` is derived, not detected.** `chorus → inst` in an EDM track
  is a drop; `chorus → verse` is not. Deriving it from the label pair means the
  three acoustic classes Part 1 identified (bass re-entry, handover into a
  void, vocal hook entry) no longer need a detector each — they are all just
  "the section changed".
* **A section carries a span, so the composite gesture survives.** The pinned
  requirement that a drop has internal phases is served by `lead_in` pointing at
  the preceding section rather than by five sibling hints that have to be
  re-grouped by adjacency.
* **Confidence is per-field and can be `unknown`.** `allin1` degenerating on
  Armin becomes `function: unknown, identity: A/B/C` rather than a wrong label,
  and the boundary and identity survive even when the naming does not.

Suggested build order, cheapest first:

1. Add `allin1` to the pipeline as a segmentation stage. It reuses the demucs
   stems that already exist, so the marginal cost is ~6 s per song.
2. Add the MERT identity clustering over the same boundaries. ~9 s per song.
3. Emit the section table above and mark the current mood-adjective labels as
   derived-and-optional. Their measured alignment with song form is zero, so
   nothing should depend on them.
4. Re-derive the human ground truth as bar-aligned section transitions, then
   revisit localisation. Not before.
5. Leave CLAP out of the shipped artifact for now, or use it only for the two
   differentials that held up (`chorus` rising, `filter sweep` falling) as a
   confidence signal on a transition — never as a label.

## Things that cost time and are worth not rediscovering

* **MERT in fp16 returns all-NaN on this GPU.** Every one of the 13 hidden
  states, including layer 0, so the conv feature extractor is where it
  overflows. It must run in fp32 (843 MB peak, comfortably inside 4 GB).
* **MERT's positional convolution is silently randomly initialised.** The
  checkpoint stores `encoder.pos_conv_embed.conv.weight_{g,v}`; torch ≥ 2.1
  renamed those to `parametrizations.weight.original{0,1}` and MERT's
  `trust_remote_code` modelling file misses the rename that transformers
  applies to in-library Wav2Vec2 checkpoints. You get a warning, not an error,
  and a music encoder with a random positional embedding.
  [`research/mert.py`](research/mert.py) `_restore_weight_norm` repairs it.
* **Beat-synchronous pooling silently produces NaN** when the beat grid runs
  past the last frame — `np.median` of an empty slice. It poisons the whole SSM
  and every downstream number, and the first symptom is "all layers score
  identically", which looks like a modelling result rather than a bug.
* **`allin1` needs natten 0.15**, whose only wheels are built against torch
  2.1 — it calls `natten.functional.natten1dqkrpb`, removed in natten 0.17. It
  therefore cannot share an environment with `beat_this`, which pulls torch
  2.13. Hence two sandbox images.
* **`allin1` shells out to `demucs.separate` on the GPU while holding its own
  model resident**, which OOMs a 4 GB card partway through a corpus run (7 of
  21 songs). Seeding `demix_dir/htdemucs/<stem>/` with the repo's existing
  stems (`harmonic` → `other`) skips it entirely and cuts the per-song cost
  from ~57 s to ~6 s.
* **A peak picker that takes "everything above a threshold, NMS'd" degenerates
  into a uniform grid** when the curve spends most of its time above the
  threshold. The first layer sweep returned identical numbers for all 13 MERT
  layers for this reason. Require an actual local maximum with a prominence.

## Reproducing

Two sandbox images, neither of which touches the analyzer image:

```bash
docker build -f experiments/drop_detection/research/Dockerfile        -t ai-light-song-v2-research:dev .
docker build -f experiments/drop_detection/research/Dockerfile.allin1 -t ai-light-song-v2-allin1:dev  .
```

```bash
R=experiments/drop_detection/research/run_in_container.sh
M="python -m experiments.drop_detection.research.run"

$R          $M cache          # MERT + CLAP + beat-this for the 4 gold songs
$R --allin1 $M cache-allin1   # allin1 over all 21 songs, in the other image

$R $M boundaries            # the comparison table
$R $M sweep                 # recall against boundary budget
$R $M layers                # MERT layer sweep
$R $M downbeats             # bar-grid agreement
$R $M identity              # MERT repetition clustering
$R $M describe              # the synthesis: function + identity + texture
$R $M corpus                # allin1 label quality over all 21 songs
$R $M hybrid                # learned regions + the existing localiser
$R $M vocab [window_s]      # which CLAP sentences respond to a drop
$R $M dynamics              # the tension/intensity curves that did not work
$R $M narrate               # the whole song as a CLAP read, 5 s at a time
```

Saved outputs are in [`research/out/`](research/out/). Model caches are in
`research/cache/` (the MERT and CLAP caches are gitignored; the `allin1` and
`beat-this` ones are small JSON/NPZ and are kept).

---

# Part 1 — the hand-built role-change detector

Standalone experiment scripts for rebuilding drop detection (v2.2 items 3–7).
Nothing here is imported by `src/analyzer`; it reads the same artifacts the
pipeline produces (`artifacts/stems/*.wav`, `artifacts/essentia/beats.json`)
plus the human ground truth in `reference/human/human_hints.json`.

Run everything inside the project container:

    docker compose run --rm --no-deps app python -m experiments.drop_detection.run <cmd>

Commands: `cache`, `gt`, `propose`, `eval`.

## Ground-truth caveats (measured 2026-09-01)

Only the seven `drop impact` **start instants** are trustworthy ground truth.
The surrounding phase boundaries are not:

- Titanium's three sequences carry byte-identical phase durations
  (7.661 / 11.881 / 3.186 / 0.542 / 0.445 s) — they were generated as fixed
  offsets from each hand-placed impact, not observed.
- Hideaway has a 2.119 s gap between `approach` end and `build` start, so the
  "phases tile contiguously" model is not true of the labels as authored.
- The essentia **bar phase** disagrees with the human impacts on 3 of 7
  (−0.66 / +0.77 / +0.88 s), while the nearest **beat** is within 0.23 s on all
  seven. Snap to beat; do not gate on downbeat until the bar grid is fixed.
  (Part 2 confirms this and shows a second neural tracker does not fix it.)

So the harness scores impact detection and impact localisation only.

## Why the v2.1 detector finds nothing on two of four tracks

Per-stem level change across each labelled impact (mean dB over −4→−0.3 s vs
+0.1→+2.5 s), measured from the demucs stems:

| impact | bass | drums | vocals | mix |
| --- | --- | --- | --- | --- |
| `_test_song` 28.4 | +14.7 | +6.9 | −4.1 | +3.4 |
| Titanium 74.7 / 151.3 / 212.0 | +37.9 / +11.8 / +18.1 | +7.5 / +7.7 / +8.0 | −12.9 / −21.5 / −1.7 | +2.9 / +2.2 / +3.3 |
| Armin 57.8 / 154.0 | +9.0 / +12.7 | **−20.7** / −2.8 | **−47.2 / −38.8** | **−7.4 / −3.2** |
| Hideaway 62.4 | **−3.3** | −3.5 | **+24.3** | −1.7 |

There are three acoustic classes here, not one: bass re-entry, a lead handover
into a void where the mix gets *quieter*, and a vocal hook entry where the bass
does not move. `DROP_EVIDENCE_PROFILE` puts 0.58 of its weight on bass re-entry
plus energy jump, so it can only express the first. Armin and Hideaway are not a
threshold failure — the model has no term that can fire on them.

The invariant across six of the seven is not "energy rises" but **the lead role
changes hands on a beat**: vocals out, bass in. Hideaway is the mirror image of
the same gesture. (Part 2's reframing subsumes this: all three classes are the
same event — a section boundary — seen through different instrumentation.)

## Stage structure

Region proposal and instant placement are separate problems and are separated
here. Conflating them is what makes the v2.1 impact land ~1.5 s late: the
accumulated evidence peaks a bar *inside* the new section, not at its edge.

1. **`candidates.propose`** — a bank of one-sided role-change channels
   (`bass_in`, `voc_out`, `voc_in`, `drums_in`, `drums_out`, `handover`,
   `after_build`, `after_suck`, `sub_in`), each contributing its top peaks after
   8 s NMS. Recall-oriented.
2. *(not built)* a re-ranker over the candidate descriptors. Needs more labels.
3. **`candidates.localize`** — places the instant on the beat grid from short
   adjacent windows gated on the broadband transient.

## Measured, gold set only (7 impacts)

| metric | result |
| --- | --- |
| stage 1 region recall (±2.5 s) | **7 / 7** |
| stage 1 candidates emitted | 84 across 4 songs (precision 0.083) |
| stage 3, oracle region, ±0.5 s | 13 / 21 trials (7 impacts × 3 region offsets) |
| stage 3 localisation \|err\| | median 0.225 s, and ≤0.23 s on the 5 impacts it places correctly |
| end-to-end ±0.5 s | 4 / 7 |

So region proposal is solved on this set and the bottlenecks are precision
(stage 2, blocked on labels) and localisation on three impacts.

### Two impacts where the label and the audio disagree

`_test_song` 28.40 and Titanium 74.66 are the localiser's failures, and in both
the acoustic transition genuinely happens later than the human mark: on
`_test_song` the bass step is at ~29.6 (the v2.1 detector's "1.5 s late" 30.0 s
is close to the audio), and the human mark sits between two bar lines. These are
worth re-checking against the audio before any more detector tuning is spent on
them.

### Things tried that made it worse

- Clipping each channel to [0, 1]: saturates whole regions at exactly 1.0 and
  leaves top-K selection to break ties by array order. Lost all three Titanium
  impacts. Channels are kept in raw dB.
- A `min` over the pre-window as the bass floor: every sidechain trough wins it,
  so `bass_reentry` is large at every beat. Replaced with the 25th percentile of
  the bar-median-filtered level.
- Two-segment changepoint localisation (3.5 s segments): 9/21, and unstable
  under region jitter. It smears across the build.
- Leading-edge selection (earliest beat within 85–90 % of the peak score, which
  is what v2.2 item 4 asks for): 9/21 vs 13/21 for the plain argmax. During a
  build the score is already within 15 % of its peak, so the rule walks
  backwards into the riser.

## Against the v2.1 baseline

| | v2.1 recorded baseline | this harness |
| --- | --- | --- |
| `_test_song` | 2 composites, impacts 30.0 / 37.0 s | region found; instant 1.6 s late |
| `Hideaway` | none detected | detected, −0.22 s |
| `Armin` | none detected | 2 / 2, +0.13 / −0.08 s |
| `Titanium` | 1 detected, matching no human impact | 3 / 3 regions; 1 / 3 within 0.5 s |
| impacts within ±0.5 s | 0 / 7 | 4 / 7 |
| regions found (±2.5 s) | 1 / 7 | **7 / 7** |

## Next

1. **Labels.** `run export` writes eight ranked draft `drop impact` hints per
   track to `proposals/` for all 21 corpus tracks (168 to triage). Keep/delete
   in the hint editor, copy survivors into each track's `human_hints.json`.
   Part 2 revises what should be labelled: bar-aligned **section transitions**
   are a better target than hand-clicked impact instants, and are what the
   models are actually good at.
2. **Stage 2 re-ranker** over the candidate descriptors, once there are enough
   labels for leave-one-song-out to mean something. Part 2 suggests this may be
   unnecessary: deriving the drop from a named `chorus → inst` transition needs
   no re-ranker.
3. **Bar grid.** Confirmed still broken in Part 2, and *not* fixed by
   `beat-this`. `allin1` is installable and its 8-bar phrase grid is the most
   promising basis for a corrected bar grid.

## The Drop Proposals timeline lane

`run export` writes each song's candidates to
`data/analysis/<song>/reference/proposals/drop_impacts.json` — inside the tree
the UI dev server mounts at `/data` — and the UI renders them in a **Drop
Proposals** lane sitting directly beneath **Human Hints**, expanded by default,
so a candidate can be auditioned against the hand-authored hint while the song
plays.

- A candidate already within 0.5 s of a human `drop impact` is drawn **teal** and
  labelled `✓`; an unconfirmed one is **magenta** and labelled `?`. At
  song-overview zoom the 0.5 s blocks are far too narrow for their labels, so the
  colour is what makes the lane readable as a triage queue.
- The block label names the role-change channels that fired (`handover ·
  voc_out`); clicking it opens the block inspector with the per-stem dB
  evidence and the raw row.
- The file is optional: a song the exporter has not been run over loads as an
  empty lane, not an error.

Nothing in the UI writes this file, and nothing writes `human_hints.json` from
it — survivors are copied across by hand in the hint editor.
