# CLAP — section identity

[← archive index](experiments_archive.md)

<https://github.com/LAION-AI/CLAP>

**Archived** — ran, measured, negative. Nothing was promoted for identity.

This was half of one experiment. The other half — a **character/texture layer**
— is a different question, measured positive, and is still open in
[`../experiments.md`](../experiments.md).

**The claim.** Can a CLAP embedding say which sections are the same part
returning, where `sections/form.py`'s `repetition_group` shipped `null` on every
section of all 21 songs?

**The result.** Mean pairwise AUC at matching two occurrences of the same
section:

| MFCC-20 | CLAP raw | chroma | CLAP centred | duration control | time control |
| --- | --- | --- | --- | --- | --- |
| **0.73** | 0.68 | 0.62 | 0.61 | 0.59 | 0.46 |

Twenty MFCC coefficients beat a 512-dimensional CLAP embedding.

**Worth not rediscovering.** CLAP scores 0.83 at telling a section from *itself*
and 0.68 at matching two occurrences of the same part. That gap is the diagnosis:
identity needs a representation trained for **invariance between occurrences**,
not a bigger general-purpose embedding. **MFCC's 0.73 is the number any next
attempt must beat** — and this is the standing example of why every experiment
here measures against a cheap classical baseline.

**Detail:** [`experiments/clap/README.md`](../../experiments/clap/README.md)
