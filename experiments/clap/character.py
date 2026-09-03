"""Character blocks — what a moment *is like*, as distinct from where it sits in
the arrangement.

The operator marks these by hand and gives each its own fixture behaviour. The
worked example, and the thing this module is built to find, is `hint-006` of
`Armin - Revolution`:

    "Breath", 81.395-96.326, "Vocal - no intense section"
    lighting: "soft motion of moving heads. parcans slow violet waves"

That is not a verse/chorus fact. It is a texture fact, and it is the kind of
fact §1.2 calls "what happens inside a part".

Three sources contribute, on a shared 10 Hz grid, and each is used for what it
is actually good at:

* **stems** (`essentia/rms_loudness.json`) — physical presence of voice, drums
  and bass. Already in the trusted half of the pipeline, exact, and free. Any
  claim about whether an instrument is playing comes from here.
* **CLAP** — the perceptual axes the stems cannot give: calm vs intense, sparse
  vs dense. Measured, this is the only place CLAP adds anything: its own drum
  and bass probes are wrong (it reports drums present through the Armin block
  where the drum stem sits at 0.03) while its calm axis separates the operator's
  own "no intense section" and "max intensity" blocks correctly.
* **allin1's frame-level posterior** — shadow labels, read from the sibling
  experiment's proposal file. A `break` holding sustained mass inside a stretch
  the segmentation published as `inst` is a breakdown the 8-bar argmax could
  not express.

Every threshold below is a stated constant on a per-song z-score or percentile,
never an absolute level: the stems are peak-normalised per song and the CLAP
axes are per-song z-scores, so nothing here transfers a level between songs.
"""
from __future__ import annotations

import json

import numpy as np

from .paths import ANALYSIS_ROOT, allin1_path

GRID_HZ = 10.0

#: A stem is judged against **its own loud level** in this song — its 90th
#: percentile — not against a rank of frames. "The drums are at a fifth of where
#: they normally sit" is a musical statement; "the drums are below the 25th
#: percentile of frames" is not, and on a track whose drums are quiet throughout
#: it is true a quarter of the time by construction. Measured on the Armin
#: "Breath" block, the rank rule fired on 67 % of its frames and this one on
#: 82 %.
#:
#: Two thresholds with a gap between them, so a source hovering at the boundary
#: produces neither claim rather than flickering between both.
PRESENT_FRACTION = 0.35
OUT_FRACTION = 0.25
REFERENCE_PCT = 90

#: CLAP axis thresholds, in standard deviations of that axis within the song.
CALM_Z = 0.5
INTENSE_Z = -0.5

#: Stem RMS is a 10 ms measurement; at 10 Hz it still swings wildly frame to
#: frame, and a per-frame threshold on it flickers and never yields a run long
#: enough to be a block. Smoothed over two seconds it becomes what a listener
#: actually hears as "the drums are out here". Two seconds is the same window
#: the pipeline's own `rms_loudness.json` already carries as `history.mean_2s`.
SMOOTH_S = 2.0

#: Shortest run worth calling a block. Below about a bar there is no cue to hang
#: on it, and the 5 s CLAP window cannot resolve it anyway.
MIN_BLOCK_S = 4.0

#: Gaps shorter than this are closed before runs are measured. A vocal that
#: pauses for breath, or a single bar without a hat, does not end the passage —
#: without this a real 15 s block arrives as four fragments, none long enough to
#: survive MIN_BLOCK_S.
CLOSE_GAP_S = 2.0


def stem_grid(song: str) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    """Per-stem normalised RMS, decimated from 100 Hz to the shared 10 Hz grid."""
    path = ANALYSIS_ROOT / song / "artifacts" / "essentia" / "rms_loudness.json"
    payload = json.loads(path.read_text())
    order = payload["metadata"]["source_order"]
    values = np.array([f["normalized_values"] for f in payload["frames"]], dtype=np.float32)
    factor = int(round(100.0 / GRID_HZ))
    usable = (len(values) // factor) * factor
    block = values[:usable].reshape(usable // factor, factor, values.shape[1]).mean(axis=1)
    times = (np.arange(len(block)) / GRID_HZ).astype(np.float32)
    return times, {name: block[:, i] for i, name in enumerate(order)}


def smooth(curve: np.ndarray, seconds: float = SMOOTH_S) -> np.ndarray:
    """Centred moving average over `seconds`, edges included."""
    width = max(1, int(round(seconds * GRID_HZ)))
    if width <= 1:
        return curve
    kernel = np.ones(width, dtype=np.float32) / width
    padded = np.pad(curve, (width // 2, width - 1 - width // 2), mode="edge")
    return np.convolve(padded, kernel, mode="valid").astype(np.float32)


def resample(times_from: np.ndarray, values: np.ndarray, times_to: np.ndarray) -> np.ndarray:
    """Linear interpolation onto the shared grid. CLAP sits on a 1 s hop and the
    stems on 10 ms; both describe the same seconds, so the join is by time."""
    return np.interp(times_to, times_from, values).astype(np.float32)


#: The block vocabulary. Each entry is (name, predicate, what a light show does
#: with it). Deliberately four: every one of them appears in the operator's own
#: hand-marked hints, and none of them is a verse/chorus fact.
def classify(stems: dict[str, np.ndarray], clap: dict[str, np.ndarray],
             *, use_clap: bool = True) -> dict[str, np.ndarray]:
    """Per-frame boolean for each character kind.

    `use_clap=False` drops the two CLAP terms and leaves the stem rules intact.
    That is the ablation the experiment turns on: the stems are already in the
    trusted half of the pipeline and cost nothing, so CLAP has to earn its GPU
    pass by making these blocks more specific, not merely by being present.
    """
    level = {name: smooth(curve) for name, curve in stems.items()}
    reference = {name: float(np.percentile(curve, REFERENCE_PCT))
                 for name, curve in level.items()}

    def present(name: str) -> np.ndarray:
        return level[name] >= PRESENT_FRACTION * reference[name]

    def out(name: str) -> np.ndarray:
        return level[name] <= OUT_FRACTION * reference[name]

    vocal_present, drums_out, drums_in = present("vocals"), out("drums"), present("drums")
    bass_out, bass_in = out("bass"), present("bass")
    ones = np.ones_like(level["vocals"], dtype=bool)
    calm = (clap["calm"] >= CALM_Z) if use_clap else ones
    intense = (clap["calm"] <= INTENSE_Z) if use_clap else ones

    return {
        # The Armin "Breath": a voice carrying a passage with the rhythm section
        # out. Needs both sources — the stems say the drums left and the voice
        # stayed, CLAP says it feels calm rather than tense.
        "breath": vocal_present & drums_out & calm,
        # Rhythm section gone and nobody singing — the "Spacer" / "drum and bass
        # leaves" shape. Stems alone; CLAP adds nothing here.
        "void": drums_out & bass_out & ~vocal_present,
        # A voice out front over a section that is not calm.
        "vocal lead": vocal_present & drums_in & ~calm,
        # Everything playing, and it feels like it — the "Finale" shape.
        "full power": drums_in & bass_in & intense,
    }


def close_gaps(mask: np.ndarray, seconds: float = CLOSE_GAP_S) -> np.ndarray:
    """Fill false gaps shorter than `seconds`. See CLOSE_GAP_S."""
    width = max(1, int(round(seconds * GRID_HZ)))
    filled = mask.copy()
    start = None
    for i, on in enumerate(mask):
        if not on and start is None:
            start = i
        elif on and start is not None:
            if start > 0 and i - start <= width:
                filled[start:i] = True
            start = None
    return filled


def runs(mask: np.ndarray, times: np.ndarray, *, min_s: float = MIN_BLOCK_S) -> list[tuple[float, float]]:
    """Contiguous true runs, as (start, end) seconds, shorter ones dropped."""
    mask = close_gaps(mask)
    out, start = [], None
    for i, on in enumerate(mask):
        if on and start is None:
            start = i
        elif not on and start is not None:
            out.append((start, i))
            start = None
    if start is not None:
        out.append((start, len(mask)))
    step = 1.0 / GRID_HZ
    return [
        (round(float(times[i]), 2), round(float(times[min(j, len(times) - 1)]), 2))
        for i, j in out if (j - i) * step >= min_s
    ]


def shadow_blocks(song: str) -> list[dict]:
    """allin1's shadow labels, read from the sibling experiment's proposal file.

    A data dependency on a file, not an import — either experiment can be
    deleted without breaking the other's code.
    """
    path = allin1_path(song)
    if not path.exists():
        return []
    payload = json.loads(path.read_text())
    frames = payload.get("frame_labels")
    if not frames:
        return []
    return frames.get("shadow_labels", [])


def blocks(song: str, times: np.ndarray, stems: dict[str, np.ndarray],
           clap: dict[str, np.ndarray], *, use_clap: bool = True,
           include_shadow: bool = True) -> list[dict]:
    """Every character block in one song, from all three sources, in time order."""
    masks = classify(stems, clap, use_clap=use_clap)
    out: list[dict] = []
    for kind, mask in masks.items():
        for start, end in runs(mask, times):
            span = (times >= start) & (times <= end)
            out.append({
                "kind": kind,
                "source": "stems+clap" if kind in ("breath", "full power") else "stems",
                "start_s": start,
                "end_s": end,
                "evidence": {
                    "vocals": round(float(stems["vocals"][span].mean()), 3),
                    "drums": round(float(stems["drums"][span].mean()), 3),
                    "bass": round(float(stems["bass"][span].mean()), 3),
                    "calm_z": round(float(clap["calm"][span].mean()), 2),
                    "sparse_z": round(float(clap["sparse"][span].mean()), 2),
                },
            })
    for row in (shadow_blocks(song) if include_shadow else []):
        # allin1's contribution beyond the arrangement: a label with sustained
        # posterior mass that its own published segmentation never used.
        out.append({
            "kind": f"shadow {row['label']}",
            "source": "allin1",
            "start_s": row["start_s"],
            "end_s": row["end_s"],
            "evidence": {
                "peak_share": row["peak_share"],
                "mean_share": row["mean_share"],
            },
        })
    out.sort(key=lambda r: (r["start_s"], r["kind"]))
    for index, row in enumerate(out, 1):
        row["id"] = f"char-{index:03d}"
    return out
