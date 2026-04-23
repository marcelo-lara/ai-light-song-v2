import re
with open("src/analyzer/stages/event_rules.py", "r") as f:
    content = f.read()

content = re.sub(
    r'intensity=min\(1\.0, (.*?)\),',
    r'intensity=_clamp01(\1),',
    content
)
content = re.sub(
    r'intensity=max\((.*?)\),',
    r'intensity=_clamp01(max(\1)),',
    content
)
content = re.sub(
    r'intensity=intensity,',
    r'intensity=_clamp01(intensity),',
    content
)
content = re.sub(
    r'intensity=float\((.*?)\),',
    r'intensity=_clamp01(float(\1)),',
    content
)
content = re.sub(
    r'intensity=energy_mean,',
    r'intensity=_clamp01(energy_mean),',
    content
)
content = re.sub(
    r'intensity=tension_mean,',
    r'intensity=_clamp01(tension_mean),',
    content
)
content = re.sub(
    r'confidence=min\(1\.0, (.*?)\),',
    r'confidence=_clamp01(\1),',
    content
)
content = re.sub(
    r'confidence=confidence,',
    r'confidence=_clamp01(confidence),',
    content
)

with open("src/analyzer/stages/event_rules.py", "w") as f:
    f.write(content)
