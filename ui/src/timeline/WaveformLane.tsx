// WaveformLane.tsx — the Waveform Anchor lane body.
//
// wavesurfer.js does the drawing; this component only hosts the render surface
// the transport hook owns (so the instance survives collapse/hide) and shows a
// loading state until the first-load mp3 decode finishes. No peaks artifact —
// wavesurfer decodes the full mp3 on song load (accepted; `/api/peaks/<song>`
// precompute is out of scope for ui-v2).
//
// The lane's own cursor is disabled in the hook (`cursorWidth: 0`) — the shared
// accent playhead is drawn by TimelineGrid over every lane. Colours are Nocturne
// blurple (design notes §3a), set in the hook.

import { useEffect, useRef } from "react";

interface WaveformLaneProps {
  /** the wavesurfer render surface, created and owned by useTransport */
  surface: HTMLDivElement | null;
  ready: boolean;
  error: string | null;
  /** body width in px (= coords.timelineW) */
  width: number;
}

export function WaveformLane({
  surface,
  ready,
  error,
  width,
}: WaveformLaneProps): React.JSX.Element {
  const mountRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const mount = mountRef.current;
    if (mount && surface && surface.parentElement !== mount) {
      mount.appendChild(surface);
    }
  }, [surface]);

  return (
    <div className="tl-waveform" style={{ width }}>
      <div ref={mountRef} className="tl-waveform__mount" aria-hidden={!ready} />
      {!ready && !error && (
        <div className="tl-waveform__state">Decoding audio…</div>
      )}
      {error && (
        <div className="tl-waveform__state tl-waveform__state--error">
          Audio failed to load: {error}
        </div>
      )}
    </div>
  );
}
