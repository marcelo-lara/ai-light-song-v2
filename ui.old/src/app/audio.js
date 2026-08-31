export function getAudioDecodeContext(existing) {
  if (existing) {
    return existing;
  }
  if (typeof window.AudioContext === "function") {
    return new window.AudioContext();
  }
  if (typeof window.webkitAudioContext === "function") {
    return new window.webkitAudioContext();
  }
  return null;
}

export function resolvedPlaybackTime(audioElement, currentTime) {
  const audioTime = Number(audioElement?.currentTime);
  const stateTime = Number(currentTime ?? 0);
  if (!Number.isFinite(audioTime)) {
    return stateTime;
  }
  if (Math.abs(audioTime - stateTime) <= 0.05) {
    return Math.max(audioTime, stateTime);
  }
  return audioTime;
}

export function buildWaveformEnvelope(audioBuffer) {
  const channelCount = Math.max(1, Number(audioBuffer.numberOfChannels || 1));
  const channels = Array.from({ length: channelCount }, (_, index) => audioBuffer.getChannelData(index));
  const sampleCount = Math.max(4096, Math.min(16384, Math.floor(audioBuffer.duration * 240)));
  const blockSize = Math.max(1, Math.floor(audioBuffer.length / sampleCount));
  const envelope = [];

  for (let index = 0; index < sampleCount; index += 1) {
    const start = index * blockSize;
    const end = Math.min(audioBuffer.length, start + blockSize);
    let min = 1;
    let max = -1;

    for (let offset = start; offset < end; offset += 1) {
      for (const channel of channels) {
        const sample = channel[offset] || 0;
        if (sample < min) {
          min = sample;
        }
        if (sample > max) {
          max = sample;
        }
      }
    }

    envelope.push({
      min: Math.max(-1, min),
      max: Math.min(1, max),
    });
  }

  return envelope;
}