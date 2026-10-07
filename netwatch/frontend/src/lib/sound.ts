let ctx: AudioContext | null = null
/** Discreet tone per alert level (off by default; enabled in the UI). INFO low, VIGILANCE medium, CRITICAL double beep. */
export function playAlert(level: string) {
  try {
    ctx = ctx || new AudioContext()
    const beep = (f: number, at: number) => { const o = ctx!.createOscillator(); const g = ctx!.createGain(); o.frequency.value = f; g.gain.value = 0.04; o.connect(g); g.connect(ctx!.destination); o.start(ctx!.currentTime + at); o.stop(ctx!.currentTime + at + 0.12) }
    if (level === 'CRITICAL') { beep(880, 0); beep(660, 0.18) }
    else if (level === 'VIGILANCE') beep(660, 0)
    else beep(440, 0)
  } catch { /* audio unavailable */ }
}
