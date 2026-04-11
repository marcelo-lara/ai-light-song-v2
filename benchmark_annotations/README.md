# Event Benchmark Annotations

This folder stores seed benchmark annotations for Epic 5 event validation.

Files in this folder are human-curated review inputs. They are not generated fallback data and are never copied into analyzer outputs.

Annotation status values:

- `pending_review`: placeholder or draft annotation; benchmarking skips scoring.
- `reviewed`: validated annotation set; benchmarking compares machine or merged events against it.

Each song annotation file should follow this shape:

```json
{
  "schema_version": "1.0",
  "song_name": "Song - Artist",
  "annotation_status": "reviewed",
  "events": [
    {
      "type": "drop",
      "start_time": 62.5,
      "end_time": 64.0,
      "notes": "Human-reviewed reference event"
    }
  ]
}
```