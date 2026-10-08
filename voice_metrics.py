"""
Phase 1: Voice Pipeline Latency Instrumentation
Minimal, non-invasive metrics collection for STT/TTS/LLM/e2e latency.
"""

import time
import threading
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional
from contextlib import contextmanager
import json


@dataclass
class VoiceMetrics:
    """Single voice interaction metrics."""
    session_id: str
    created_at: float = field(default_factory=time.time)
    
    # STT (browser Web Speech API) - client-reported
    stt_start_ms: float = 0.0
    stt_end_ms: float = 0.0
    stt_confidence: float = 0.0
    stt_is_final: bool = False
    
    # TTS (edge-tts server-side)
    tts_start_ms: float = 0.0
    tts_first_chunk_ms: float = 0.0
    tts_end_ms: float = 0.0
    tts_chars: int = 0
    
    # LLM (Hermes Agent)
    llm_ttft_ms: float = 0.0      # time to first token
    llm_end_ms: float = 0.0
    llm_tokens: int = 0
    
    # Tool calls
    tool_calls: List[Dict] = field(default_factory=list)
    
    # End-to-end (client speech end -> audio playback start)
    e2e_start_ms: float = 0.0
    e2e_end_ms: float = 0.0
    
    # Errors
    error: str = ""
    
    @property
    def stt_latency_ms(self) -> float:
        return self.stt_end_ms - self.stt_start_ms if self.stt_end_ms > 0 else 0.0
    
    @property
    def tts_latency_ms(self) -> float:
        return self.tts_end_ms - self.tts_start_ms if self.tts_end_ms > 0 else 0.0
    
    @property
    def tts_first_chunk_latency_ms(self) -> float:
        return self.tts_first_chunk_ms - self.tts_start_ms if self.tts_first_chunk_ms > 0 else 0.0
    
    @property
    def llm_latency_ms(self) -> float:
        return self.llm_end_ms - self.llm_ttft_ms if self.llm_end_ms > 0 else 0.0
    
    @property
    def e2e_latency_ms(self) -> float:
        return self.e2e_end_ms - self.e2e_start_ms if self.e2e_end_ms > 0 else 0.0
    
    def to_dict(self) -> dict:
        d = asdict(self)
        d.update({
            "stt_latency_ms": round(self.stt_latency_ms, 1),
            "tts_latency_ms": round(self.tts_latency_ms, 1),
            "tts_first_chunk_latency_ms": round(self.tts_first_chunk_latency_ms, 1),
            "llm_latency_ms": round(self.llm_latency_ms, 1),
            "e2e_latency_ms": round(self.e2e_latency_ms, 1),
        })
        return d


class MetricsCollector:
    """Thread-safe metrics collector with bounded history."""
    
    def __init__(self, max_history: int = 500):
        self._lock = threading.RLock()
        self._active: Dict[str, VoiceMetrics] = {}
        self._history: List[VoiceMetrics] = []
        self._max_history = max_history
    
    def start_session(self, session_id: str) -> VoiceMetrics:
        """Create new metrics session (called at user speech end)."""
        with self._lock:
            m = VoiceMetrics(session_id=session_id)
            m.e2e_start_ms = time.time() * 1000
            self._active[session_id] = m
            return m
    
    def ensure_session(self, session_id: str) -> VoiceMetrics:
        """Get or create session without wiping existing data (STT-safe)."""
        with self._lock:
            m = self._active.get(session_id)
            if not m:
                m = VoiceMetrics(session_id=session_id)
                m.e2e_start_ms = time.time() * 1000
                self._active[session_id] = m
            return m

    def get(self, session_id: str) -> Optional[VoiceMetrics]:
        with self._lock:
            return self._active.get(session_id)
    
    def complete(self, session_id: str) -> Optional[VoiceMetrics]:
        """Mark session complete (called at audio playback start)."""
        with self._lock:
            m = self._active.pop(session_id, None)
            if m:
                m.e2e_end_ms = time.time() * 1000
                self._history.append(m)
                if len(self._history) > self._max_history:
                    self._history.pop(0)
            return m
    
    def record_stt(self, session_id: str, start_ms: float, end_ms: float, 
                   confidence: float = 0.0, is_final: bool = False) -> bool:
        """Record STT timing from client (auto-create session if missing)."""
        with self._lock:
            m = self._active.get(session_id)
            if not m:
                m = VoiceMetrics(session_id=session_id)
                m.e2e_start_ms = time.time() * 1000
                self._active[session_id] = m
            m.stt_start_ms = start_ms
            m.stt_end_ms = end_ms
            m.stt_confidence = confidence
            m.stt_is_final = is_final
            return True
    
    def record_tts_start(self, session_id: str, chars: int) -> bool:
        with self._lock:
            m = self._active.get(session_id)
            if not m:
                return False
            m.tts_start_ms = time.time() * 1000
            m.tts_chars = chars
            return True
    
    def record_tts_first_chunk(self, session_id: str) -> bool:
        with self._lock:
            m = self._active.get(session_id)
            if not m or m.tts_first_chunk_ms > 0:
                return False
            m.tts_first_chunk_ms = time.time() * 1000
            return True
    
    def record_tts_end(self, session_id: str) -> bool:
        with self._lock:
            m = self._active.get(session_id)
            if not m:
                return False
            m.tts_end_ms = time.time() * 1000
            return True
    
    def record_llm_ttft(self, session_id: str) -> bool:
        with self._lock:
            m = self._active.get(session_id)
            if not m or m.llm_ttft_ms > 0:
                return False
            m.llm_ttft_ms = time.time() * 1000
            return True
    
    def record_llm_end(self, session_id: str, tokens: int = 0) -> bool:
        with self._lock:
            m = self._active.get(session_id)
            if not m:
                return False
            m.llm_end_ms = time.time() * 1000
            m.llm_tokens = tokens
            return True
    
    def record_tool_call(self, session_id: str, tool: str, duration_ms: float, 
                         success: bool = True) -> bool:
        with self._lock:
            m = self._active.get(session_id)
            if not m:
                return False
            m.tool_calls.append({
                "tool": tool,
                "duration_ms": round(duration_ms, 1),
                "success": success,
                "timestamp": time.time() * 1000,
            })
            return True
    
    def record_error(self, session_id: str, error: str) -> bool:
        with self._lock:
            m = self._active.get(session_id)
            if not m:
                return False
            m.error = error[:200]
            return True
    
    def summary(self) -> dict:
        """Aggregated statistics."""
        with self._lock:
            if not self._history:
                return {"samples": 0, "active": len(self._active)}
            
            def pct(values, p):
                if not values:
                    return 0
                values = sorted(values)
                return values[int(len(values) * p)]
            
            stt = [m.stt_latency_ms for m in self._history if m.stt_latency_ms > 0]
            tts = [m.tts_latency_ms for m in self._history if m.tts_latency_ms > 0]
            tts_fc = [m.tts_first_chunk_latency_ms for m in self._history if m.tts_first_chunk_latency_ms > 0]
            llm = [m.llm_latency_ms for m in self._history if m.llm_latency_ms > 0]
            e2e = [m.e2e_latency_ms for m in self._history if m.e2e_latency_ms > 0]
            
            return {
                "samples": len(self._history),
                "active_sessions": len(self._active),
                "stt": {
                    "count": len(stt),
                    "mean_ms": round(sum(stt) / len(stt), 1) if stt else 0,
                    "p50_ms": round(pct(stt, 0.5), 1) if stt else 0,
                    "p95_ms": round(pct(stt, 0.95), 1) if stt else 0,
                },
                "tts": {
                    "count": len(tts),
                    "mean_ms": round(sum(tts) / len(tts), 1) if tts else 0,
                    "p50_ms": round(pct(tts, 0.5), 1) if tts else 0,
                    "p95_ms": round(pct(tts, 0.95), 1) if tts else 0,
                    "first_chunk_mean_ms": round(sum(tts_fc) / len(tts_fc), 1) if tts_fc else 0,
                },
                "llm": {
                    "count": len(llm),
                    "mean_ms": round(sum(llm) / len(llm), 1) if llm else 0,
                    "p50_ms": round(pct(llm, 0.5), 1) if llm else 0,
                    "p95_ms": round(pct(llm, 0.95), 1) if llm else 0,
                },
                "e2e": {
                    "count": len(e2e),
                    "mean_ms": round(sum(e2e) / len(e2e), 1) if e2e else 0,
                    "p50_ms": round(pct(e2e, 0.5), 1) if e2e else 0,
                    "p95_ms": round(pct(e2e, 0.95), 1) if e2e else 0,
                },
                "errors": sum(1 for m in self._history if m.error),
            }
    
    def recent(self, n: int = 20) -> List[dict]:
        """Recent sessions as dicts."""
        with self._lock:
            return [m.to_dict() for m in self._history[-n:]]
    
    def clear(self) -> None:
        with self._lock:
            self._active.clear()
            self._history.clear()


# Global singleton
metrics = MetricsCollector()


@contextmanager
def measure(metrics_obj: VoiceMetrics, attr_ms: str):
    """Context manager to time a block and store ms in metric attr."""
    start = time.time() * 1000
    try:
        yield
    finally:
        setattr(metrics_obj, attr_ms, time.time() * 1000 - start)


@contextmanager
def measure_ttft(metrics_obj: VoiceMetrics):
    """Time to first token - records on first yield."""
    start = time.time() * 1000
    recorded = False
    try:
        yield lambda: None if recorded else (setattr(metrics_obj, 'llm_ttft_ms', time.time() * 1000 - start) or setattr(metrics_obj, 'llm_ttft_ms', time.time() * 1000 - start))
    finally:
        if not recorded:
            pass  # handled by lambda