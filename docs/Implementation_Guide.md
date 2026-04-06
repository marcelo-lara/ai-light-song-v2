# 🎵 Audio → Lighting Pipeline (Implementation Guide)

## 🧭 Overview

This document defines the full pipeline to transform audio into structured, LLM-ready data for DMX lighting generation.

Architecture is divided into **4 Layers (Epics)**:

- EPIC 1 → Audio Preprocessing
- EPIC 2 → Harmonic Summary
- EPIC 3 → Symbolic Event Summary
- EPIC 4 → Audio Energy Summary

---

# 🧱 EPIC 1 — Audio Preprocessing Pipeline

## 🎯 Goal
Prepare clean, structured inputs for feature extraction.

## 🧩 Story 1.1 — Stem Separation

### Tools
- Demucs

### Tasks
- Split audio into vocals, drums, bass, harmonic
- Normalize stems
- Cache results

### Output
```json
  "stems": {
    "bass": "path",
    "drums": "path",
    "harmonic": "path",
    "vocals": "path"
  }
}
```

---

## 🧩 Story 1.2 — Beat & Tempo Detection

### Tools
- Essentia

### Tasks
- Detect BPM
- Extract beats
- Compute bars

### Output
```json
{ 
  "tempo": 124, 
  "beats": [...], 
  "bars": [...] 
}
```

---

# 🎼 EPIC 2 — Harmonic Summary

## 🎯 Goal
Provide harmonic context

## 🧩 Story 2.1 — HPCP Feature Extraction

### Tools
- Essentia

### Tasks
- Extract HPCP from harmonic stem 
- Apply tuning correction 
- Aggregate per beat

### Acceptance
- Stable chroma representation across time

## 🧩 Story 2.2 — Chords

Phase 1: template matching + HMM 
Phase 2: CRNN model

### Tools
- Template + HMM
- Viterbi decoding

### Tasks 
- Generate chord probabilities 
- Decode with Viterbi 

### Output 
```json
  { "chords": [ {"time": 0.0, "label": "Am", "confidence": 0.82} ] } 
```
### Acceptance 
- Progression matches human expectation for test songs

## 🧩 Story 2.3 — Key & Tonal Center Detection
Detect global key

### Tools 
- Essentia key detection 

### Tasks 
- Detect global key 
- Optional: local key per section 

### Output 
```json
{ "key": "A minor" }
```

## 🧩 Story 2.4 — Harmonic Features

- tension
- cadence

### Tasks 
Extract: 
- root 
- chord quality 
- cadence detection 
- harmonic tension score 

### Output
```json
 { "harmonic_features": { "tension": 0.7, "cadence": "V-I" } }
```

---

# 🎹 EPIC 3 — Symbolic Event Summary

## 🎯 Goal
Translate audio into musical behavior

## 🧩 Story 3.1 — MIDI-like Transcription (CORE)

### Tools
- Basic Pitch (Spotify)

### Tasks
- Run transcription on:
  - harmonic stem (`other.wav` in current Demucs output)
  - bass stem (`bass.wav`)

- Extract:
  - note onsets
  - pitch (MIDI)
  - duration
  - velocity
  - confidence (optional)
- Merge note events into a unified timeline aligned to the canonical beat grid

### Output
```json
{
  "notes": [
    {"time": 1.23, "pitch": 64, "duration": 0.2, "velocity": 0.5, "confidence": 0.8}
  ]
}
```

### Acceptance
- Captures main harmonic structure from the harmonic stem
- Captures bass line movement clearly from the bass stem
- Timing aligns with the beat grid and analyzer section windows
- Feeds Story 3.2 feature engineering for density, contour, repetition, sustain, and bass motion

## 🧩 Story 3.2 — Feature Engineering

- density
- contour
- repetition
- bass motion

### Tasks
Compute:
- note density (per beat/bar) 
- active note count 
- pitch range 
- register centroid 
- melodic contour (slope) 
- bass movement 
- repetition score 
- sustain ratio 
- pitch bend activity

### Output
```json
Output { "symbolic_features": { "density": 0.65, "melodic_contour": "rising", "bass_motion": "stepwise" } }
```
## 🧩 Story 3.3 — Temporal Alignment

### Tasks
Snap notes to:
- beat grid (from EPIC 1.2)
- bars

## 🧩 Story 3.4 — LLM-Friendly Abstraction

### Tasks 
Convert raw features → descriptors 

### Output (IMPORTANT)
```json
{ "description": "Repeated staccato mid-register pattern with rising melodic contour and stable bass" } 
```

### Acceptance 
- Description is understandable by a musician
---

# 🔊 EPIC 4 — Audio Energy Summary

## 🎯 Goal
Capture physical intensity & motion

## 🧩 Story 4.1 — Features

### Tools
- Essentia

### Tasks
Extract:
- loudness
- spectral centroid
- spectral flux
- onset strength

### Output

see `4.1.energy_feature_schema.md`

## 🧩 Story 4.2 — Section Segmentation

see `4.2.section_segmentation_story.md`

## 🧩 Story 4.3 — Energy Features

- energy curve 
- intensity score 
- transient density

## 🔗 Final IR
```json
{
  "tempo": {},
  "beats": [],
  "bars": [],
  "chords": [],
  "key": "",
  "notes": [],
  "symbolic_features": {},
  "description": "",
  "energy": {},
  "sections": []
}
```

---

# 💡 EPIC 5 — Light Show Design

## 🧩 Story 5.1 
Translate analyzed audio energy and musical features into **DMX lighting behaviors**.
see `5.1.energy_to_lighting_mapping.md`

## 🧩 Story 5.2
Translate analyzed musical + energy features into:
1. Fixture-specific lighting behaviors (DMX-ready)
2. A fully populated `lighting_score_template.md` for LLM + human refinement

see `5.2.fixture_aware_mapping_story`
