// P1.3 audio helpers — HPP cap1, Web Audio Analyser (CEOGPT HUD pulse)
export function getSupportedMimeType(): string {
  const candidates = ["audio/webm;codecs=opus", "audio/webm", "audio/ogg;codecs=opus", "audio/wav"];
  for (const t of candidates) {
    try { if ((window as any).MediaRecorder && (window as any).MediaRecorder.isTypeSupported(t)) return t; } catch {}
  }
  return "audio/webm";
}
export function createAnalyser(stream: MediaStream): { ctx: AudioContext; analyser: AnalyserNode } {
  const ctx = new (window.AudioContext || (window as any).webkitAudioContext)();
  const source = ctx.createMediaStreamSource(stream);
  const analyser = ctx.createAnalyser();
  analyser.fftSize = 256;
  source.connect(analyser);
  return { ctx, analyser };
}
export function getAudioLevel(analyser: AnalyserNode): number {
  const data = new Uint8Array(analyser.frequencyBinCount);
  analyser.getByteFrequencyData(data);
  let sum = 0;
  for (let i=0;i<data.length;i++) sum += data[i];
  return sum / data.length / 255; // 0..1
}
