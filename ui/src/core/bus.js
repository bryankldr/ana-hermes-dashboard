// Event Bus & State Store
export class EventBus {
  constructor() {
    this.events = {};
  }
  on(event, listener) {
    if (!this.events[event]) this.events[event] = [];
    this.events[event].push(listener);
  }
  emit(event, data) {
    if (this.events[event]) {
      this.events[event].forEach(fn => fn(data));
    }
  }
}

export const bus = new EventBus();

export const state = {
  mode: 'coding',
  session: null,
  running: false,
  activeCode: '// Waiting for agent code execution...\n// Live terminal code stream will display here.',
  bgJobs: []
};
