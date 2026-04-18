import { coreArtifactKeys } from "../lib/config.js";
import { formatPercent, formatRange, roundNumber, summarizeValidation, formatDuration } from "../lib/utils.js";

function SummaryGrid({ timeline }) {
  if (!timeline) {
    return <div className="summary-grid empty">Load a song to summarize harmonic, symbolic, energy, pattern, and event artifacts.</div>;
  }
  const summaryCards = [
    { label: "Chord Regions", value: timeline.chords.length },
    { label: "Phrase Windows", value: timeline.phrases.length },
    { label: "Pattern Occurrences", value: timeline.patterns.length },
    { label: "Machine Events", value: timeline.machineEvents.length },
    { label: "Drum Events", value: timeline.drums.length },
    { label: "Beat Drift Flags", value: timeline.validationDrift.filter((row) => row.within_tolerance === false).length },
  ];
  return (
    <div className="summary-grid">
      {summaryCards.map((card) => (
        <div className="summary-card" key={card.label}>
          <span className="stat-label">{card.label}</span>
          <strong>{card.value}</strong>
        </div>
      ))}
    </div>
  );
}

function ValidationSnapshot({ report, timeline }) {
  if (!report || typeof report !== "object") {
    return <div className="empty">No validation report loaded.</div>;
  }
  const targets = Object.entries(report.validation || {});
  const beatsStatus = report.validation?.beats || {};
  const comparisonCounts = (timeline?.eventComparisons || []).reduce((accumulator, row) => {
    accumulator[row.status] = (accumulator[row.status] || 0) + 1;
    return accumulator;
  }, {});
  return (
    <div>
      <p><strong>Status:</strong> {report.status || "unknown"}</p>
      <p><strong>Command:</strong> {report.command || "-"}</p>
      <p><strong>Beat Match Ratio:</strong> {formatPercent(beatsStatus.match_ratio)}</p>
      <p><strong>Event Comparison:</strong> exact={comparisonCounts.exact || 0} shifted={comparisonCounts.shifted || 0} not_exported={comparisonCounts.not_exported || 0} output_only={comparisonCounts.output_only || 0}</p>
      <ul className="preview-list">
        {targets.length ? targets.map(([key, value]) => <li key={key}><strong>{key}</strong>: {value.status || "present"}</li>) : <li>No per-target validation details.</li>}
      </ul>
    </div>
  );
}

function SectionsPreview({ timeline }) {
  if (!timeline?.sections?.length) {
    return <div className="empty">No section artifact loaded.</div>;
  }
  return (
    <ul className="preview-list">
      {timeline.sections.slice(0, 8).map((section) => (
        <li key={section.id}>
          <strong>{section.label}</strong>
          <span>{formatRange(section.start_s, section.end_s)}</span>
        </li>
      ))}
    </ul>
  );
}

export default function OverviewPanels({
  loadedSong,
  data,
  timeline,
  artifactRecords,
  visibleWindowLabel,
  waveformStatus,
  audioStatus,
  audioRef,
  onAudioTimeUpdate,
  onAudioPlay,
  onAudioPause,
  onAudioLoadedMetadata,
}) {
  const missingCore = artifactRecords.filter((status) => coreArtifactKeys.includes(status.key) && !status.ok);
  return (
    <>
      <section className="hero panel">
        <div>
          <p className="eyebrow">Inference Viewer</p>
          <h2>{loadedSong || "No song loaded"}</h2>
          <p className="lede">{loadedSong ? "Artifact lanes remain primary. Output helper projections are overlaid only when useful for comparison." : <>Choose a discovered per-song directory from <code>data/artifacts</code>.</>}</p>
        </div>
        <div className="hero-meta">
          <div className="stat-card">
            <span className="stat-label">BPM</span>
            <strong>{timeline && Number.isFinite(timeline.bpm) && timeline.bpm > 0 ? roundNumber(timeline.bpm, 1) : "-"}</strong>
          </div>
          <div className="stat-card">
            <span className="stat-label">Duration</span>
            <strong>{timeline ? formatDuration(timeline.duration) : "-"}</strong>
          </div>
          <div className="stat-card">
            <span className="stat-label">Validation</span>
            <strong>{summarizeValidation(data.validation)}</strong>
          </div>
          <div className="stat-card">
            <span className="stat-label">Viewport</span>
            <strong>{visibleWindowLabel}</strong>
          </div>
        </div>
      </section>

      <section className="grid two-up">
        <article className="panel">
          <div className="panel-header compact-header">
            <h2>Audio Anchor</h2>
            <span className="hint">{waveformStatus}</span>
          </div>
          <audio ref={audioRef} controls preload="none" onTimeUpdate={onAudioTimeUpdate} onPlay={onAudioPlay} onPause={onAudioPause} onLoadedMetadata={onAudioLoadedMetadata}></audio>
          <p className="hint">{audioStatus}</p>
        </article>

        <article className="panel">
          <h2>Artifact Summary</h2>
          {missingCore.length > 0 ? (
            <div className="empty-state-card" aria-live="polite">
              <strong>Core artifacts are incomplete for this song.</strong>
              <span>The debugger stays read-only and loads what it can, but some lanes and overlays will remain partial.</span>
              <ul>
                {missingCore.map((status) => <li key={status.key}><strong>{status.label}</strong> <span>{status.error || "missing"}</span></li>)}
              </ul>
            </div>
          ) : null}
          <SummaryGrid timeline={timeline} />
        </article>
      </section>

      <section className="grid two-up">
        <article className="panel">
          <h2>Validation Snapshot</h2>
          <ValidationSnapshot report={data.validation} timeline={timeline} />
        </article>

        <article className="panel">
          <h2>Sections</h2>
          <SectionsPreview timeline={timeline} />
        </article>
      </section>
    </>
  );
}