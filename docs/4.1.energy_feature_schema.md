# 🔊 EPIC 4 — Story 4.1 Feature Schema (Audio Energy)

## 🎯 Goal
Define a normalized schema for low-level audio features extracted with Essentia.

---

# 📦 Feature Frame Schema

Each feature is computed over time and aligned to frames or beats.

```json
{
  "time": 1.230,
  "frame_index": 123,

  "loudness": 0.82,
  "spectral_centroid": 2450.5,
  "spectral_flux": 0.34,
  "onset_strength": 0.67
}
```

---

# 📚 Full Collection Schema

```json
{
  "features": [
    {
      "time": 0.00,
      "loudness": 0.10,
      "spectral_centroid": 1200,
      "spectral_flux": 0.05,
      "onset_strength": 0.02
    }
  ],
  "metadata": {
    "frame_rate": 100,
    "total_frames": 18000,
    "duration": 180.0
  }
}
```

---

# 🧩 Field Definitions

## ⏱ Time

| Field | Type | Description |
|------|------|------------|
| time | float | Timestamp in seconds |
| frame_index | int | Index of analysis frame |

---

## 🔊 Loudness

| Field | Type | Description |
|------|------|------------|
| loudness | float | Normalized (0–1) perceived loudness |

---

## 🎼 Spectral Centroid

| Field | Type | Description |
|------|------|------------|
| spectral_centroid | float | Frequency center of mass (Hz) |

👉 Interprets brightness:
- low → warm / bass-heavy
- high → bright / sharp

---

## ⚡ Spectral Flux

| Field | Type | Description |
|------|------|------------|
| spectral_flux | float | Frame-to-frame spectral change |

👉 Detects motion / change intensity

---

## 🥁 Onset Strength

| Field | Type | Description |
|------|------|------------|
| onset_strength | float | Strength of detected transients |

👉 Correlates with hits/kicks/snare

---

# 🔁 Beat-Aligned Variant (Recommended)

```json
{
  "beat": 12,
  "time": 24.0,

  "loudness_avg": 0.75,
  "centroid_avg": 2100,
  "flux_avg": 0.40,
  "onset_density": 3.2
}
```

---

# ⚙️ Implementation Notes

- Normalize all values to consistent ranges
- Store both:
  - frame-level (high resolution)
  - beat-level (LLM-friendly)

---

# 🚀 Derived Metrics (Next Step)

From this schema you can compute:

- energy curve
- intensity score
- drop detection
- build-up detection

---

# 🎯 Key Insight

This layer represents **physical energy**, not musical meaning.

👉 It drives:
- strobes
- intensity
- movement speed
