// Real-time Audio Spectrum Equalizer Canvas
export class AudioSpectrum {
  constructor(container) {
    this.container = container;
    this.render();
  }

  render() {
    this.container.innerHTML = `
      <div style="display:flex; align-items:center; gap:12px; width:100%;">
        <span class="mono-text" style="color:var(--text-dim); font-size:10px;">AUDIO SPECTRUM</span>
        <canvas id="spectrumCanvas" width="300" height="24" style="flex:1; background:transparent;"></canvas>
      </div>
    `;
    this.canvas = this.container.querySelector('#spectrumCanvas');
    this.ctx = this.canvas.getContext('2d');
    this.drawIdleBars();
  }

  drawIdleBars() {
    const ctx = this.ctx;
    ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
    const bars = 32;
    const width = this.canvas.width / bars;
    for (let i = 0; i < bars; i++) {
      const h = Math.random() * 6 + 2;
      ctx.fillStyle = 'rgba(64, 243, 255, 0.25)';
      ctx.fillRect(i * width, this.canvas.height - h, width - 2, h);
    }
  }
}
