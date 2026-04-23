from pathlib import Path
from analyzer.io import read_json
from analyzer.event_contracts import validate_event_payload, EventContractError

f = read_json(Path("/data/artifacts/Cinderella - Ella Lee/event_inference/rule_candidates.json"))
for i, ev in enumerate(f.get("events", [])):
    try:
        validate_event_payload(ev)
    except EventContractError as e:
        print(f"Error at event {i} id {ev['id']} type {ev['type']} confidence {ev.get('confidence')} intensity {ev.get('intensity')}: {e}")
