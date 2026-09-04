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
// F6-2 chime 2.4s sintetizado (sine 440->880Hz) 1x/sessao
export function playChime(): void {
  try {
    if (typeof window === "undefined") return;
    if (sessionStorage.getItem("jefrey_chime") === "1") return;
    const AC: typeof AudioContext = (window as any).AudioContext || (window as any).webkitAudioContext;
    if (!AC) return;
    const ctx = new AC();
    const o = ctx.createOscillator();
    const g = ctx.createGain();
    o.type = "sine";
    o.frequency.setValueAtTime(440, ctx.currentTime);
    o.frequency.linearRampToValueAtTime(880, ctx.currentTime + 1.2);
    o.frequency.linearRampToValueAtTime(660, ctx.currentTime + 2.4);
    g.gain.setValueAtTime(0.12, ctx.currentTime);
    g.gain.linearRampToValueAtTime(0.08, ctx.currentTime + 1.2);
    g.gain.linearRampToValueAtTime(0.0, ctx.currentTime + 2.4);
    o.connect(g).connect(ctx.destination);
    o.start();
    o.stop(ctx.currentTime + 2.5);
    sessionStorage.setItem("jefrey_chime", "1");
    setTimeout(() => { try { ctx.close(); } catch {} }, 3000);
  } catch {}
}
