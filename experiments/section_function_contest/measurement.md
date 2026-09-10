# Measurement — section-function energy contest (v3.4 item 3, step 1)

Scratch measurement (not a full experiment entry). Sets the **scope** of the
`contest-section-function` rule, not its design. Method: per allin1 section,
mean mix RMS + per-stem RMS from the published `loudness.json` (`values`, 20 ms
frames), plus the `arrangement_state.json` playing-stem count at the section
midpoint. For every `chorus` followed by a `verse` / `bridge`, the dB gap to
that next section.

Regenerate: `docker compose run --rm --no-deps -T --entrypoint python app \
/app/experiments/section_function_contest/measure.py` (reads `data/analysis/*/`
— run the pipeline first). The shipped thresholds live in
`src/analyzer/stages/section_function.py`; `measure.py` carries its own copy so
the scope check can be re-run without importing `src/`.

## Outcome — the contradiction is NOT corpus-wide

23 songs analysed (all have `loudness.json` + `sections.json`; none skipped).

With the shipped rule (chorus → verse/bridge, next-section drums ≥ 3 dB louder,
mix not > 1.5 dB quieter, arrangement_state stem count not clearly thinner,
allin1 `function_confidence` ≤ 0.9):

| song | section | function | next | drums gap | mix gap | function_confidence |
| --- | --- | --- | --- | --- | --- | --- |
| Queen of Kings - Alessandra | section-002 (1.1–16.4 s) | chorus | verse | **+17.2 dB** | +0.5 dB | 0.54 |
| Queen of Kings - Alessandra | section-004 (31.4–63.5 s) | chorus | verse | **+6.7 dB** | +1.2 dB | 0.74 |
| Queen of Kings - Alessandra | section-006 (79.2–111.6 s) | chorus | bridge | **+4.2 dB** | +0.0 dB | 0.60 |
| It's a fine day - Opus III | section-002 (30.7–61.4 s) | chorus | verse | **+5.0 dB** | +1.8 dB | 0.54 |

**4 sections across 2 songs. The other 21 songs flag nothing.** `Queen of
Kings` accounts for 3 of the 4 — it is the 2nd most extreme corr(harmonic,
drums) song in the corpus (`alessandra_findings.md`). `It's a fine day` is the
only other Eurovision-shaped inversion the rule catches.

Near-misses deliberately not flagged (conservative choice):

- `Only this moment` section-006 chorus → bridge: drums +0.15 dB — the bridge is
  not louder, no contradiction.
- `Pet Shop Boys` section-008 chorus → verse: drums +0.69 dB, mix −1.0 dB — the
  chorus is the louder passage in the mix.
- `ayuni` section-002 chorus → **inst** (drums +8.3 dB): next section is `inst`,
  not `verse`/`bridge`; `inst` carries no "should be quiet" prior, so it is out
  of scope.
- `Cinderella` section-006 chorus → **inst**: same — and `function_confidence`
  0.83 anyway.

## Margin chosen, and why conservative

Because the contradiction is essentially `Queen of Kings`-specific, the rule
ships **conservative** (`docs/implementation-plan-v3.4.md` item 3 step 1: "if it
is Queen-of-Kings-specific, the rule ships conservative"):

| constant | value | rationale |
| --- | --- | --- |
| `DRUMS_MARGIN_DB` | 3.0 | primary discriminator; every measured contradiction clears +4.2 dB, so 3.0 has headroom without inviting borderline flags |
| `MIX_MIN_GAP_DB` | −1.5 | a chorus that is clearly the louder passage in the mix is not "quieter" — vetoes it |
| `PLAY_TOLERANCE` | −1 | arrangement_state stem count sits at its own label noise floor; only vetoes a clearly-thickening chorus, never drives a flag |
| `FUNCTION_CONFIDENCE_CEILING` | 0.9 | allin1's confidently-labelled choruses (0.85+) are left alone; measured contradictions sit at 0.54–0.74 |
| scope | `chorus` → `{verse, bridge}` only | `inst` / `solo` / `break` carry no lower-energy prior |

A rule tuned to fire on every song is how the old segmenter reached F1 0.29.
The label is **kept and flagged**, never flipped, so a conservative miss costs
nothing — the authoring model still sees allin1's label plus, on the 4 flagged
sections, an honest "the energy contradicts this".
