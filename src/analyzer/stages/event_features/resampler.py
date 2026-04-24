import numpy as np

def _resample_to_100ms_grid(
    normalized_rows: list[dict],
    duration_s: float,
) -> list[dict]:
    if not normalized_rows:
        return []
    grid_times = np.arange(0.0, duration_s + 0.05, 0.1)
    beat_time_array = np.array([float(row["start_time"]) for row in normalized_rows])
    grid_features = []
        
    for grid_time in grid_times:
        closest_idx = int(np.argmin(np.abs(beat_time_array - float(grid_time))))
        source_row = normalized_rows[closest_idx]
        grid_row = {
            "time_s": round(float(grid_time), 3),
            "source_beat": source_row["beat"],
            "section_id": source_row.get("section_id"),
            "section_name": source_row.get("section_name"),
            "normalized": dict(source_row["normalized"]),
            "derived": dict(source_row["derived"]),
            "rolling": dict(source_row.get("rolling", {})),
        }
        grid_features.append(grid_row)
    return grid_features
