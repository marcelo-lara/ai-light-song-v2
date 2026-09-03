# Experiment — what CLAP can infer *beyond* the arrangement

**Status: measured. Character layer works and is reviewable; section identity
failed.** Nothing in `src/` reads anything in here. Queue entry:
[`../../docs/experiments_pending.md`](../../docs/experiments_pending.md)
(constitution §3.4).

## The question

Not "where does the song change" — [`../allin1/`](../allin1/README.md) answers
that. This asks what can be said about a passage's **character**, which is a
different kind of fact and often the one that earns a cue.

The worked example is the operator's own ground truth. `Armin - Revolution`
carries a hand-marked hint that is not a section boundary:

```
hint-006  "Breath"  81.395 – 96.326   "Vocal - no intense section"
          lighting: "soft motion of moving heads. parcans slow violet waves"
```

A voice carrying a passage with the rhythm section out. Undoubtable by ear,
worth its own look, and invisible to any verse/chorus label. `_test_song` shows
the same pattern at finer grain — `Spacer` ("volume drops to restart melody"),
`Outro start` ("drum and bass leaves"), three separate `Vocal outro` phrases,
`Finale` ("all fixtures to max intensity").

> Can these models find that kind of block, and does CLAP add anything the stems
> the pipeline already produces do not?

## How to run it

```bash
docker build -f experiments/drop_detection/research/Dockerfile \
             -t ai-light-song-v2-research:dev .

./experiments/clap/run_in_container.sh python -m experiments.clap.run cache
./experiments/clap/run_in_container.sh python -m experiments.clap.run cache-baseline
./experiments/clap/run_in_container.sh python -m experiments.clap.run character  # export
./experiments/clap/run_in_container.sh python -m experiments.clap.run hints      # score
./experiments/clap/run_in_container.sh python -m experiments.clap.run score      # identity
```

The character layer also reads `reference/proposals/allin1.json`, so run that
experiment's `export` (with `cache-activations`) first. Caches are gitignored;
[`out/character.txt`](out/character.txt) and [`out/score.txt`](out/score.txt)
are the committed evidence.

## How the character layer is built

Three sources on a shared 10 Hz grid, each used for what it is actually good at.

| source | contributes | why this one |
| --- | --- | --- |
| **stems** (`essentia/rms_loudness.json`) | what is physically playing — voice, drums, bass | already in the trusted half of the pipeline, exact, free |
| **CLAP** | the perceptual axes: calm ↔ intense, sparse ↔ dense | the stems cannot give these, and the operator's own hint language is made of them |
| **allin1 frame posterior** | shadow labels — see below | says something its own published segmentation cannot express |

Nothing asks CLAP an open question. Every axis is a **contrastive pair** of
opposed sentences, read as a differential after the two centrings the survey
established as mandatory. A pair cancels the per-sentence offset that made
absolute CLAP readings useless.

Four block kinds, each drawn from the operator's own hints and each mapping to a
different look:

| kind | rule | the hint it comes from |
| --- | --- | --- |
| **breath** | voice present, drums out, CLAP calm | Armin "Breath" |
| **void** | drums and bass out, nobody singing | `_test_song` "Spacer", "Outro start" |
| **vocal lead** | voice present, drums in, not calm | `_test_song` "Vocal outro" |
| **full power** | drums and bass in, CLAP intense | `_test_song` "Finale" |

Every threshold is relative to the song's own levels — a stem is judged against
its **90th percentile in this song**, and CLAP axes are per-song z-scores — so
no level transfers between tracks.

## Measurement 1 — it finds the block

```
char-004  breath  83.50 – 95.00   stems+clap
          vocals 0.238  drums 0.004  bass 0.005  calm_z 1.77  sparse_z 1.26
hand-marked        81.40 – 96.33
```

Inside the hand-marked span, covering 11.5 s of its 14.9 s. Both edges are inset
by a second or two, which is what a 2 s smoothing window and a 5 s CLAP window
cost you; the block is unambiguous and lands where a cue would.

Across the 10 hand-marked non-drop hints in the corpus, **7 are covered** by a
character block of some kind. Coverage is a weak test on its own — a block
spanning half the song covers everything — so the per-axis table in
[`out/character.txt`](out/character.txt) is the substance. The pattern in it:

* CLAP's **calm** axis tracks the operator's own intensity judgement. Positive
  (calm) on `Breath` +1.65, `Outro start` +1.80, `Spacer` +1.26; strongly
  negative (intense) on `prepare for end` −2.54 and `Finale` −2.35, which are
  precisely the two hints whose lighting note is "max intensity". One clear
  miss: `Vocal Outro 3` reads −1.11 where it should be calm.
* CLAP's **vocal** axis is weak (+0.36 … +1.18 on the three vocal outros) while
  the **vocal stem** is unambiguous (+1.5, +1.6, +1.2). Take voice presence from
  the stems.
* CLAP's **drums** and **bass** axes are wrong. It reports drums *present*
  through the Armin block (+0.77) where the drum stem sits at 0.03 of its own
  loud level. Do not ask CLAP what is playing.

## Measurement 2 — the ablation: does CLAP earn its GPU pass?

The stems are free and trusted, so the question is not whether the combined rule
works, but whether dropping the CLAP terms changes the answer.

| rule | breath blocks | breath seconds | full-power blocks | share of corpus claimed | Armin block found |
| --- | --- | --- | --- | --- | --- |
| stems + CLAP calm | **28** | **241 s** | **46** | **41 %** | yes |
| stems alone | 81 | 973 s | 68 | 73 % | yes |

Both find the Armin block. The difference is specificity: without the calm term
`breath` degenerates into "any voice with the drums down" and `full power` into
"drums and bass both playing", which is most of a dance track. **The claimed
territory falls from 73 % of the corpus to 41 % with no loss on the one block
big enough to measure.** The stems say what is playing; CLAP says how it feels,
and only the second distinguishes a breath from a verse.

## Measurement 3 — allin1 beyond the arrangement: shadow labels

`allin1.analyze(..., include_activations=True)` returns far more than the
segment list: `beat`, `downbeat`, `segment` and a **per-frame posterior over all
ten labels** at 100 Hz. The published segmentation is an argmax of the last of
those, quantised to an 8-bar phrase, and throws the rest away. Two things come
back out of it ([`../allin1/activations.py`](../allin1/activations.py)):

* **Per-section confidence.** Normalised entropy of the posterior inside each
  committed section. On Armin it averages 0.78 — the model names that song
  while being close to opinion-less about it, which the segment list has no room
  to say.
* **Shadow labels.** Sustained posterior mass on a label the committed
  segmentation never used *anywhere in the song*. On Armin, `break` never
  appears in the published sections, yet holds 24 % of the mass across
  68.6–75.9 s and **30 % across 143.4–175.0 s**, peaking at 0.40. The second run
  sits exactly where the drum stem drops to 0.011–0.037 and the vocal to 0.003:
  a real breakdown that the 8-bar argmax could not express.

On `_test_song`, whose published segmentation is only `intro chorus`, the
shadow labels are `inst` and `outro` — and the `outro` runs cover four of the
five hand-marked outro hints. The model knew; the segment list could not say it.

## Measurement 4 — section identity (negative, kept for the record)

Before the question above was settled, the same embeddings were pointed at
section *identity* — which arrangement sections are the same part. That failed
and the lane built for it has been removed (§3.2). The numbers are worth
keeping, because the baseline they establish is the number any future identity
attempt has to beat. Full table in [`out/score.txt`](out/score.txt).

| representation | mean pair AUC over 20 songs |
| --- | --- |
| **MFCC 20, mean+std (classical baseline)** | **0.73** |
| CLAP 512-d, raw | 0.68 |
| chroma 12 | 0.62 |
| CLAP 512-d, song-centred | 0.61 |
| *control: pair duration* | 0.59 |
| *control: pair time distance* | 0.46 |

Twenty MFCC coefficients beat the 512-dimensional embedding. The useful finding
is the split: CLAP scores **0.83** at telling a section from *itself*
(label-free split-half) and **0.68** at matching two occurrences of the same
part. Identity needs a representation trained for invariance between
occurrences, not a bigger general-purpose one.

Also measured and negative: CLAP semantic novelty places boundaries at 3/7
impacts (±1.0 s) on twice allin1's budget — better than the incumbent, no better
than an evenly spaced grid. And whole-song catalog matching works after corpus
centring (raw, every song is every other song's neighbour at ~0.998, total
spread 0.089) but reaches no projected file, so §1.3 rules it out.

## Review it

The **Character** lane sits beneath **allin1 Sections**. Blocks are tinted by
kind, so a song's texture reads as a colour strip before any label does — violet
for `breath` is not arbitrary, it is the look the operator wrote for the block
this lane was built to find. Each block names the sources that had to agree
(`stems`, `stems+clap`, `allin1`) and carries its evidence in the inspector.

## Conclusion

**CLAP is worth keeping for one thing: a perceptual intensity axis.** It cannot
tell you what is playing — the stems already do that, better and for free — and
it cannot recognise a returning part. What it can do is say whether a passage
feels calm or intense, and that is exactly the axis the operator's own hints are
written in ("no intense section", "max intensity"). Combined with the stems it
cuts a texture detector's false territory nearly in half.

**allin1 has a second, unused output that is worth more than expected.** Its
frame-level posterior finds breakdowns and outros its own published segmentation
cannot name. That costs no extra model — it is the same forward pass, with
`include_activations=True`.

Neither is promoted. What a promotion would need is in the queue entry.

## Negative results worth not rediscovering

* **Ask CLAP how it feels, not what is playing.** Its drum and bass probes are
  confidently wrong where the stems are exactly right.
* **Contrastive pairs, never single sentences.** Absolute CLAP readings are
  dominated by a per-sentence offset; a pair cancels it. Both centrings are
  still required, in order.
* **Percentile-rank thresholds on a stem are not musical.** "Below the 25th
  percentile of frames" is true a quarter of the time by construction. Judging a
  stem against its own 90th percentile — "at a fifth of where it normally sits"
  — took the Armin block from 67 % of frames firing to 82 %.
* **Smooth before thresholding, and close short gaps.** Unsmoothed 10 Hz stem
  RMS flickers so much that a real 15 s block arrives as fragments, none long
  enough to survive a minimum-duration filter. The first run of this detector
  found zero breath blocks for exactly that reason.
* **Check the ablation, not the demo.** The stems-alone rule also finds the
  Armin block. It just also claims 73 % of the corpus.
