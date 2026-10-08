/**
 * Voice Metrics Client - Phase 1 Instrumentation
 * Reports STT timing from browser Web Speech API to server for latency analysis.
 */

class VoiceMetricsClient {
    constructor() {
        this.sessionId = this._getOrCreateSessionId();
        this.sttStartTime = 0;
        this.sttEndTime = 0;
        this.e2eStartTime = 0;
        this.audioPlaybackStarted = false;
    }

    _getOrCreateSessionId() {
        let sid = localStorage.getItem('voice_session_id');
        if (!sid) {
            sid = 'voice-' + Date.now() + '-' + Math.random().toString(36).slice(2, 9);
            localStorage.setItem('voice_session_id', sid);
        }
        return sid;
    }

    newSession() {
        this.sessionId = 'voice-' + Date.now() + '-' + Math.random().toString(36).slice(2, 9);
        localStorage.setItem('voice_session_id', this.sessionId);
        this.sttStartTime = 0;
        this.sttEndTime = 0;
        this.e2eStartTime = 0;
        this.audioPlaybackStarted = false;
        return this.sessionId;
    }

    // Called when user starts speaking (speech recognition starts)
    onSpeechStart() {
        this.sttStartTime = performance.now();
        this.e2eStartTime = performance.now(); // Approximation: speech end ~ STT end
    }

    // Called when speech recognition returns final result
    onSpeechEnd(isFinal, confidence = 0) {
        this.sttEndTime = performance.now();
        if (isFinal) {
            this._reportSTT(confidence, true);
        }
    }

    // Called when interim result received
    onSpeechInterim(confidence = 0) {
        this.sttEndTime = performance.now();
        this._reportSTT(confidence, false);
    }

    _token() {
        return document.querySelector('meta[name="ana-token"]')?.content || '';
    }

    _reportSTT(confidence, isFinal) {
        if (this.sttStartTime === 0) return;
        
        fetch('/api/voice/metrics/stt', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'x-ana-token': this._token() },
            body: JSON.stringify({
                session_id: this.sessionId,
                start_ms: this.sttStartTime,
                end_ms: this.sttEndTime,
                confidence: confidence,
                is_final: isFinal
            })
        }).catch(e => console.warn('STT metrics report failed:', e));
    }

    // Called when TTS audio playback starts (in speak() function)
    onAudioPlaybackStart() {
        if (!this.audioPlaybackStarted) {
            this.audioPlaybackStarted = true;
            fetch('/api/voice/metrics/tts-chunk', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'x-ana-token': this._token() },
                body: JSON.stringify({ session_id: this.sessionId })
            }).catch(e => console.warn('TTS chunk metrics report failed:', e));
        }
    }

    // Called when conversation turn completes
    onTurnComplete() {
        this.newSession();
    }

    // Get current session ID for server correlation
    getSessionId() {
        return this.sessionId;
    }
}

// Global instance
window.voiceMetrics = new VoiceMetricsClient();