"""Contrastive text probes — what CLAP can say about a moment's *character*.

The sibling survey established that CLAP's absolute answers are unusable: raw
cosines are dominated by a per-sentence offset, and the top-scoring sentence per
segment is plausible-looking nonsense. What survived was **differentials**.

So nothing here asks CLAP an open question. Every axis is a *pair* of opposed
sentences, and the reading is the difference between them after two centrings
(across sentences within a window, then across time within a sentence). A pair
cancels what a single sentence cannot: both halves carry the same kind of
sentence-level offset, and both move with the same dominant audio direction.

The axes were chosen from the vocabulary the operator's own hints use —
"Vocal - no intense section", "volume drops to restart melody", "drum and bass
leaves" — not from what CLAP might plausibly know.
"""
from __future__ import annotations

import numpy as np

#: (positive sentence, negative sentence) per axis. A positive score means the
#: first sentence describes this moment better than the second, *relative to the
#: rest of this song* — never in absolute terms.
PAIRS: dict[str, tuple[str, str]] = {
    "vocal": ("a singer singing a melody, lead vocals in front",
              "purely instrumental music, nobody singing"),
    "drums": ("a loud drum beat with kick and snare driving the music",
              "no drums at all, only sustained tones"),
    "bass": ("a deep heavy sub bass line you can feel",
             "no bass at all, only mid and high frequencies"),
    "sparse": ("a sparse quiet passage, very little going on, lots of space",
               "a dense wall of sound, everything playing at once"),
    "calm": ("calm gentle floating music, relaxed and soft",
             "aggressive intense energetic music at full power"),
    "pads": ("sustained atmospheric synth pads and long reverb",
             "short percussive stabs and tight rhythmic hits"),
}

SENTENCES = [s for pair in PAIRS.values() for s in pair]


def text_embeddings(device: str = "cpu") -> np.ndarray:
    """One forward pass of the text tower. CPU by default — a dozen short
    sentences, and the GPU is usually busy with the audio side."""
    import torch
    from transformers import ClapModel, ClapProcessor

    from .model import MODEL_ID

    model = ClapModel.from_pretrained(MODEL_ID).to(device).eval()
    processor = ClapProcessor.from_pretrained(MODEL_ID)
    with torch.no_grad():
        inputs = processor(text=SENTENCES, return_tensors="pt", padding=True).to(device)
        emb = torch.nn.functional.normalize(model.get_text_features(**inputs), dim=-1)
    return emb.cpu().numpy().astype(np.float32)


def axes(audio_emb: np.ndarray, text_emb: np.ndarray) -> dict[str, np.ndarray]:
    """Per-window score on each axis, in standard deviations of that axis.

    Both centrings are mandatory and their order matters (survey Measurement 5):
    without the first, every sentence's curve rises and falls together with the
    audio embedding's dominant direction; without the second, the sentence's own
    offset swamps the music.
    """
    sim = audio_emb @ text_emb.T
    sim = sim - sim.mean(axis=1, keepdims=True)
    sim = (sim - sim.mean(axis=0, keepdims=True)) / (sim.std(axis=0, keepdims=True) + 1e-8)
    out = {}
    for index, name in enumerate(PAIRS):
        raw = sim[:, 2 * index] - sim[:, 2 * index + 1]
        out[name] = ((raw - raw.mean()) / (raw.std() + 1e-8)).astype(np.float32)
    return out
