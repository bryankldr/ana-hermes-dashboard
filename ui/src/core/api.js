// Core API Client for Hermes Backend
export class ApiClient {
  constructor() {
    this.token = document.querySelector('meta[name="ana-token"]')?.content || '';
  }

  headers(extra = {}) {
    return {
      'x-ana-token': this.token,
      'content-type': 'application/json',
      ...extra
    };
  }

  async getStatus() {
    const res = await fetch('/api/status', { headers: this.headers() });
    return res.json();
  }

  async getProjects() {
    const res = await fetch('/api/projects', { headers: this.headers() });
    return res.json();
  }

  async getBriefing() {
    const res = await fetch('/api/briefing', { headers: this.headers() });
    return res.json();
  }

  async getJobs() {
    const res = await fetch('/api/jobs', { headers: this.headers() });
    return res.json();
  }

  async getSessions() {
    const res = await fetch('/api/sessions', { headers: this.headers() });
    return res.json();
  }

  async getVault() {
    const res = await fetch('/api/vault', { headers: this.headers() });
    return res.json();
  }

  async getAvd() {
    const res = await fetch('/api/avd', { headers: this.headers() });
    return res.json();
  }

  async avdAction(action) {
    const res = await fetch('/api/avd', { method: 'POST', headers: this.headers(), body: JSON.stringify({ action }) });
    return res.json();
  }

  async getMissions() {
    const res = await fetch('/api/missions', { headers: this.headers() });
    return res.json();
  }

  async setSession(sessionId) {
    const res = await fetch('/api/session', {
      method: 'POST',
      headers: this.headers(),
      body: JSON.stringify({ session_id: sessionId })
    });
    return res.json();
  }

  async post(path, body = {}) {
    const res = await fetch(path, {
      method: 'POST',
      headers: this.headers({ 'content-type': 'application/json' }),
      body: JSON.stringify(body)
    });
    return res.json();
  }

  async setMode(mode) {
    const res = await fetch('/api/mode', {
      method: 'POST',
      headers: this.headers(),
      body: JSON.stringify({ mode })
    });
    return res.json();
  }

  async setVoice(voice_id) {
    const res = await fetch('/api/voice', {
      method: 'POST',
      headers: this.headers(),
      body: JSON.stringify({ voice_id })
    });
    return res.json();
  }

  async runStream(message, onEvent, onError) {
    try {
      const res = await fetch('/api/run', {
        method: 'POST',
        headers: this.headers(),
        body: JSON.stringify({ message })
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const reader = res.body.getReader();
      const dec = new TextDecoder();
      let buf = '';
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        let nl;
        while ((nl = buf.indexOf('\n')) >= 0) {
          const line = buf.slice(0, nl).trim();
          buf = buf.slice(nl + 1);
          if (line) {
            try { onEvent(JSON.parse(line)); } catch (e) {}
          }
        }
      }
    } catch (err) {
      if (onError) onError(err);
    }
  }
}

export const api = new ApiClient();
