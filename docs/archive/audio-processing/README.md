> **ARCHIVED — historical record, not a specification.**
> This document describes how something was *planned or built at the time*. It
> is **not** a description of current behaviour and may contradict the code.
> Do not treat it as a contract and do not implement from it: verify against
> `src/` first. For what the system does today, read `CLAUDE.md` at the repo
> root.

# Audio Processing (Pure Math)

Deterministic signal processing and feature derivation. Given the same audio and
engine version these stages produce byte-for-byte identical output. No trained
models. These are the trusted inputs to `../audio-inference/`.

| Epic | Docs |
|------|------|
| 1 – Preprocessing | 1.2 beat/tempo grid, 1.3 FFT bands, 1.4 mix & per-stem loudness |
| 2 – Harmonic | 2.1 HPCP/chroma extraction, 2.3 chord-pattern mining, 2.6 energy feature schema |
| 3 – Structure | 3.3 key & tonal center, 3.4 temporal alignment |
| 4 – Symbolic features | 4.1 energy derivation, 4.2 harmonic features, 4.3 symbolic feature engineering, 4.4 event-feature normalization |
