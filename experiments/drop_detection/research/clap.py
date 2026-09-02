"""CLAP zero-shot probes: continuous "what is happening musically" curves.

CLAP embeds audio and free text into one space, so a sliding window over the
song can be scored against a written vocabulary without a single label. That is
the property that matters here — the corpus has seven labelled instants in
total, so anything that needs training is out.

The probe answers a different question from an energy detector. Energy says how
loud; a text probe says *what kind of moment*, and it says it in the vocabulary
the show is authored in ("build-up", "breakdown", "instrumental").
"""
from __future__ import annotations

import numpy as np
import torch

from .common import cache_file, load_audio

MODEL_ID = "laion/larger_clap_music"
SR = 48000
WINDOW_S = 10.0
HOP_S = 0.5

# Grouped so each group can be softmaxed on its own: the groups are separate
# questions about the same window, not one flat classification.
PROMPT_GROUPS: dict[str, list[str]] = {
    "role": [
        "the intro of a song, before the beat comes in",
        "a verse, the singer telling the story over a light backing",
        "the chorus, the biggest and catchiest part of the song",
        "a breakdown where the drums drop out and the music opens up",
        "the outro of a song, the arrangement thinning out towards the end",
    ],
    "dynamics": [
        "a build-up with a rising riser and a snare roll, tension increasing",
        "the drop, the beat slams back in at full power",
        "a quiet sparse passage with very little going on",
        "a steady groove holding at full energy",
    ],
    "voice": [
        "loud lead vocals singing",
        "purely instrumental music with no singing",
    ],
    "drums": [
        "a strong four on the floor kick drum and a driving beat",
        "no drums at all, only sustained sounds",
    ],
}

PROMPTS = [p for group in PROMPT_GROUPS.values() for p in group]


# A wider bank, scored against the cached audio embeddings, used to find which
# sentences actually respond to a drop rather than to assume "the drop" does.
PROMPT_BANK: list[str] = [
    # gesture
    "a build-up with a rising riser and a snare roll, tension increasing",
    "a long filter sweep rising towards something",
    "a snare roll speeding up before an explosion",
    "the drop, the beat slams back in at full power",
    "the moment the bass drops and the whole club goes off",
    "a sudden silence right before the beat returns",
    "the music cuts out to almost nothing",
    "an impact hit with a crash cymbal on the downbeat",
    # density / energy
    "a quiet sparse passage with very little going on",
    "a steady groove holding at full energy",
    "a dense wall of sound, everything playing at once",
    "the arrangement thinning out, instruments dropping away",
    # role
    "the intro of a song, before the beat comes in",
    "a verse, the singer telling the story over a light backing",
    "the chorus, the biggest and catchiest part of the song",
    "a breakdown where the drums drop out and the music opens up",
    "an instrumental section with no singing, the synths take the lead",
    "the outro of a song, the arrangement thinning out towards the end",
    # texture
    "loud lead vocals singing",
    "purely instrumental music with no singing",
    "a strong four on the floor kick drum and a driving beat",
    "no drums at all, only sustained sounds",
    "a heavy sub bass line",
    "bright shimmering high frequencies and cymbals",
    "a lead synth playing the main melody",
    "sustained atmospheric pads and reverb",
]


def _load(device: str = "cuda"):
    from transformers import ClapModel, ClapProcessor

    model = ClapModel.from_pretrained(MODEL_ID).to(device).eval()
    processor = ClapProcessor.from_pretrained(MODEL_ID)
    return model, processor


def compute(song: str, *, device: str = "cuda", bundle=None,
            window_s: float = WINDOW_S) -> dict[str, np.ndarray]:
    model, processor = bundle or _load(device)
    wave = load_audio(song, SR)

    win = int(window_s * SR)
    hop = int(HOP_S * SR)
    starts = np.arange(0, max(1, len(wave) - win + hop), hop)
    centres = starts / SR + window_s / 2.0

    with torch.no_grad():
        text = processor(text=PROMPTS, return_tensors="pt", padding=True).to(device)
        text_emb = torch.nn.functional.normalize(model.get_text_features(**text), dim=-1)

        chunks = []
        for i in range(0, len(starts), 8):
            batch = []
            for s in starts[i:i + 8]:
                seg = wave[s:s + win]
                if len(seg) < win:
                    seg = np.pad(seg, (0, win - len(seg)))
                batch.append(seg)
            inputs = processor(audios=batch, sampling_rate=SR, return_tensors="pt").to(device)
            emb = model.get_audio_features(**inputs)
            chunks.append(torch.nn.functional.normalize(emb, dim=-1).cpu())
        audio_emb = torch.cat(chunks)

    sim = (audio_emb @ text_emb.cpu().T).numpy()          # (W, P) cosine
    return {"times": centres, "sim": sim.astype(np.float32),
            "audio_emb": audio_emb.numpy().astype(np.float16),
            "prompts": np.array(PROMPTS), "window_s": np.array(window_s)}


def load(song: str, *, rebuild: bool = False, bundle=None,
         window_s: float = WINDOW_S) -> dict[str, np.ndarray]:
    kind = "clap" if window_s == WINDOW_S else f"clap{window_s:g}"
    path = cache_file(kind, song)
    if rebuild or not path.exists():
        data = compute(song, bundle=bundle, window_s=window_s)
        np.savez_compressed(path, **data)
        return data
    return dict(np.load(path, allow_pickle=False))


def zscored(data: dict[str, np.ndarray]) -> np.ndarray:
    """Doubly-centred CLAP prompt response.

    Raw CLAP cosines are dominated by a per-prompt offset — "a verse" outscores
    every other role prompt on all four gold songs at every instant, and "no
    drums at all" wins on Titanium, which is four-on-the-floor throughout. The
    offset is a property of the sentence, not of the music, so the only usable
    reading is *relative to this song's own distribution for that same prompt*.

    Two normalisations are needed, in this order:

    1. **Across prompts, per window.** Every prompt's cosine rises and falls
       together with a single dominant direction of the audio embedding, so
       without this step all thirteen curves move the same way at a drop
       (measured: at Titanium 151.26 s, `drop`, `breakdown`, `build-up`,
       `vocals` and `no-beat` all fell by ~1.5 sigma together, which says
       nothing).
    2. **Across time, per prompt.** Removes the sentence's own offset.
    """
    sim = data["sim"].astype(np.float32)
    sim = sim - sim.mean(1, keepdims=True)
    return (sim - sim.mean(0, keepdims=True)) / (sim.std(0, keepdims=True) + 1e-8)


def grouped(data: dict[str, np.ndarray], temperature: float = 1.0) -> dict[str, np.ndarray]:
    """Per-group softmax over the z-scored prompt curves."""
    z = zscored(data)
    out = {}
    offset = 0
    for name, prompts in PROMPT_GROUPS.items():
        block = z[:, offset:offset + len(prompts)] / temperature
        block = block - block.max(axis=1, keepdims=True)
        exp = np.exp(block)
        out[name] = exp / exp.sum(axis=1, keepdims=True)
        offset += len(prompts)
    return out


def bank_response(song: str, prompts: list[str] | None = None, *,
                  bundle=None, window_s: float = WINDOW_S) -> tuple[np.ndarray, np.ndarray]:
    """(times, doubly-centred response) for an arbitrary prompt bank.

    The audio side is the expensive half and is already cached, so a new
    vocabulary costs one text forward pass.
    """
    prompts = prompts or PROMPT_BANK
    data = load(song, window_s=window_s)
    # CPU by default: only the text tower runs here, a few dozen short
    # sentences, and the GPU is usually busy with an audio pass.
    model, processor = bundle or _load("cpu")
    with torch.no_grad():
        inputs = processor(text=prompts, return_tensors="pt", padding=True).to(model.device)
        text_emb = torch.nn.functional.normalize(model.get_text_features(**inputs), dim=-1).cpu().numpy()
    emb = data["audio_emb"].astype(np.float32)
    emb /= np.linalg.norm(emb, axis=1, keepdims=True) + 1e-8
    sim = emb @ text_emb.T
    sim = sim - sim.mean(1, keepdims=True)
    sim = (sim - sim.mean(0, keepdims=True)) / (sim.std(0, keepdims=True) + 1e-8)
    return data["times"], sim


def semantic_novelty(data: dict[str, np.ndarray], lag_s: float = 4.0) -> np.ndarray:
    """Cosine distance between the CLAP window `lag_s` before and after each
    point — a text-free "the music became a different kind of thing" curve."""
    emb = data["audio_emb"].astype(np.float32)
    emb /= np.linalg.norm(emb, axis=1, keepdims=True) + 1e-8
    lag = max(1, int(round(lag_s / HOP_S)))
    out = np.zeros(len(emb))
    for i in range(len(emb)):
        a = emb[max(0, i - lag)]
        b = emb[min(len(emb) - 1, i + lag)]
        out[i] = 1.0 - float(a @ b)
    return out
