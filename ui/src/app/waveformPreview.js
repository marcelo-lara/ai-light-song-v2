import { buildWaveformEnvelope, getAudioDecodeContext } from "./audio.js";

export function createEnsureWaveform({ audioDecodeContextRef, waveformCacheRef, latestSongRef, setWaveformStatus, setWaveformPeaks }) {
  return async function ensureWaveform(song, audioPath) {
    const audioDecodeContext = getAudioDecodeContext(audioDecodeContextRef.current);
    audioDecodeContextRef.current = audioDecodeContext;
    if (!audioDecodeContext) {
      setWaveformStatus("Waveform preview loads in the browser when audio is available.");
      setWaveformPeaks(null);
      return;
    }
    if (waveformCacheRef.current.has(song)) {
      setWaveformPeaks(waveformCacheRef.current.get(song));
      setWaveformStatus("Waveform decoded in the browser from the mounted song file.");
      return;
    }
    setWaveformStatus("Decoding audio in the browser for waveform anchoring...");
    try {
      const response = await fetch(audioPath, { cache: "force-cache" });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const audioBuffer = await audioDecodeContext.decodeAudioData((await response.arrayBuffer()).slice(0));
      const peaks = buildWaveformEnvelope(audioBuffer);
      waveformCacheRef.current.set(song, peaks);
      if (latestSongRef.current === song) {
        setWaveformPeaks(peaks);
        setWaveformStatus("Waveform decoded in the browser from the mounted song file.");
      }
    } catch (error) {
      if (latestSongRef.current === song) {
        setWaveformPeaks(null);
        setWaveformStatus(`Waveform unavailable: ${error.message}. Falling back to beat pulses.`);
      }
    }
  };
}