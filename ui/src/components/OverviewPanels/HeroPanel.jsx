import { formatDuration, roundNumber, summarizeValidation } from "../../lib/utils.js";

export default function HeroPanel({ loadedSong, timeline, validation, visibleWindowLabel }) {
  return (
    <section className="hero panel">
      <div>
        <p className="eyebrow">Inference Viewer</p>
        <h2>{loadedSong || "No song loaded"}</h2>
        <p className="lede">{loadedSong ? "Artifact lanes remain primary. Output helper projections are overlaid only when useful for comparison." : <>Choose a discovered per-song directory from <code>data/artifacts</code>.</>}</p>
      </div>
      <div className="hero-meta">
        <div className="stat-card"><span className="stat-label">BPM</span><strong>{timeline && Number.isFinite(timeline.bpm) && timeline.bpm > 0 ? roundNumber(timeline.bpm, 1) : "-"}</strong></div>
        <div className="stat-card"><span className="stat-label">Duration</span><strong>{timeline ? formatDuration(timeline.duration) : "-"}</strong></div>
        <div className="stat-card"><span className="stat-label">Validation</span><strong>{summarizeValidation(validation)}</strong></div>
        <div className="stat-card"><span className="stat-label">Viewport</span><strong>{visibleWindowLabel}</strong></div>
      </div>
    </section>
  );
}