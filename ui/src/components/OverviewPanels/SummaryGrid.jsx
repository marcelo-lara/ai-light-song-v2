export default function SummaryGrid({ timeline }) {
  if (!timeline) {
    return <div className="summary-grid empty">Load a song to summarize harmonic, symbolic, energy, pattern, and event artifacts.</div>;
  }

  const cards = [
    ["Chord Regions", timeline.chords.length],
    ["Phrase Windows", timeline.phrases.length],
    ["Pattern Occurrences", timeline.patterns.length],
    ["Machine Events", timeline.machineEvents.length],
    ["Drum Events", timeline.drums.length],
    ["Beat Drift Flags", timeline.validationDrift.filter((row) => row.within_tolerance === false).length],
  ];

  return (
    <div className="summary-grid">
      {cards.map(([label, value]) => (
        <div className="summary-card" key={label}><span className="stat-label">{label}</span><strong>{value}</strong></div>
      ))}
    </div>
  );
}