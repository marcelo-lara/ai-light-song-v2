import ArtifactSummaryPanel from "./ArtifactSummaryPanel.jsx";
import AudioAnchorPanel from "./AudioAnchorPanel.jsx";
import HeroPanel from "./HeroPanel.jsx";
import SectionsPreviewPanel from "./SectionsPreviewPanel.jsx";
import ValidationSnapshotPanel from "./ValidationSnapshotPanel.jsx";

export default function OverviewPanels(props) {
  return (
    <>
      <HeroPanel loadedSong={props.loadedSong} timeline={props.timeline} validation={props.data.validation} visibleWindowLabel={props.visibleWindowLabel} />
      <section className="grid two-up">
        <AudioAnchorPanel waveformStatus={props.waveformStatus} audioStatus={props.audioStatus} audioRef={props.audioRef} onAudioTimeUpdate={props.onAudioTimeUpdate} onAudioPlay={props.onAudioPlay} onAudioPause={props.onAudioPause} onAudioLoadedMetadata={props.onAudioLoadedMetadata} />
        <ArtifactSummaryPanel artifactRecords={props.artifactRecords} timeline={props.timeline} />
      </section>
      <section className="grid two-up">
        <ValidationSnapshotPanel report={props.data.validation} timeline={props.timeline} />
        <SectionsPreviewPanel timeline={props.timeline} />
      </section>
    </>
  );
}