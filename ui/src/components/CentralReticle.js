// Central Reactor Reticle & Targeting Visor
export class CentralReticle {
  constructor(container) {
    this.container = container;
    this.render();
  }

  render() {
    this.container.innerHTML = `
      <div class="reticle-core" style="position:relative; width:280px; height:280px; display:grid; place-items:center;">
        <svg viewBox="0 0 400 400" style="width:100%; height:100%; overflow:visible;">
          <defs>
            <filter id="cyanGlow" x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur stdDeviation="4" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>
          <!-- Outer Compass Dial -->
          <circle cx="200" cy="200" r="180" fill="none" stroke="rgba(64,243,255,0.15)" stroke-width="1.5" />
          <circle cx="200" cy="200" r="160" fill="none" stroke="rgba(64,243,255,0.3)" stroke-width="2" stroke-dasharray="4 8" style="animation: spin 30s linear infinite;" />
          
          <!-- Targeting Arcs -->
          <circle cx="200" cy="200" r="130" fill="none" stroke="var(--cyan-bright)" stroke-width="3" stroke-dasharray="100 300" stroke-linecap="round" filter="url(#cyanGlow)" style="animation: spinRev 12s linear infinite;" />
          <circle cx="200" cy="200" r="95" fill="none" stroke="var(--amber-bright)" stroke-width="2" stroke-dasharray="60 200" stroke-linecap="round" style="animation: spin 8s linear infinite;" />
          
          <!-- Crosshair Brackets -->
          <line x1="200" y1="10" x2="200" y2="40" stroke="var(--cyan-bright)" stroke-width="2" />
          <line x1="200" y1="360" x2="200" y2="390" stroke="var(--cyan-bright)" stroke-width="2" />
          <line x1="10" y1="200" x2="40" y2="200" stroke="var(--cyan-bright)" stroke-width="2" />
          <line x1="360" y1="200" x2="390" y2="200" stroke="var(--cyan-bright)" stroke-width="2" />

          <!-- Center Glowing Orb -->
          <circle cx="200" cy="200" r="45" fill="rgba(64,243,255,0.15)" stroke="var(--cyan-bright)" stroke-width="2" filter="url(#cyanGlow)" />
        </svg>
        <div style="position:absolute; text-align:center; pointer-events:none;">
          <div style="font-family:var(--font-mono); font-size:10px; color:var(--text-dim); letter-spacing:0.2em;">ANA AI</div>
          <div id="reactorStatus" style="font-family:var(--font-disp); font-size:16px; font-weight:700; color:var(--cyan-bright); text-shadow:0 0 10px var(--cyan-bright);">STANDBY</div>
        </div>
      </div>
      <style>
        @keyframes spin { 100% { transform: rotate(360deg); transform-origin: 200px 200px; } }
        @keyframes spinRev { 100% { transform: rotate(-360deg); transform-origin: 200px 200px; } }
      </style>
    `;
  }

  setStatus(status) {
    const el = document.getElementById('reactorStatus');
    if (el) el.textContent = status;
  }
}
