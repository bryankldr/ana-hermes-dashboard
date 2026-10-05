"""Metric host untuk dial dashboard ANA.

Semua dari stdlib (/proc, subprocess nvidia-smi) — tanpa psutil, karena itu
dependency baru hanya untuk 6 angka. Semua fungsi jalan di thread HTTP jadi
hasil di-cache: baca /proc murah tapi tidak gratis, dan dial poll tiap
2 detik dari semua tab yang terbuka.

Yang berat: GPU, net, dan disk punya cache TTL lebih panjang karena
pengambilan mahal (subprocess, socket, statvfs) atau,layar tidak perlu freshness
setinggi CPU/RAM.
"""

import os
import socket
import subprocess
import threading
import time

# Cache TTL per kelompok metrik (detik).
_TTL_CPU = 1.5      # poll dial 2s; di bawah ini cukup supaya tidak terbaca 2x
_TTL_HEAVY = 5.0    # nvidia-smi / socket / statvfs: mahal, dan 5s tak terasa
_TTL_NET_DELTA = 2.0  # throughput butuh dua_sample, jadi TTL harus > interval

_lock = threading.RLock()
_cache = {}

_PROC_STAT = "/proc/stat"
_PROC_MEMINFO = "/proc/meminfo"
_PROC_NET_DEV = "/proc/net/dev"


# ── CPU ───────────────────────────────────────────────────────────────
def _cpu_times():
    with open(_PROC_STAT, "r") as f:
        for line in f:
            if line.startswith("cpu "):
                # user nice system idle iowait irq softirq steal ...
                parts = [int(x) for x in line.split()[1:] if x.isdigit()]
                # idle = idle + iowait
                idle = parts[3] + (parts[4] if len(parts) > 4 else 0)
                busy = sum(parts) - idle
                return busy, idle
    raise OSError("no cpu line in /proc/stat")


def cpu_percent():
    """Pakai delta dua sample — loadavg bukan persentase."""
    now = time.time()
    with _lock:
        hit = _cache.get("cpu")
        if hit and now - hit[0] < _TTL_CPU:
            return hit[1]
    try:
        busy, idle = _cpu_times()
    except OSError:
        return None
    with _lock:
        prev = _cache.get("cpu_prev")
        _cache["cpu_prev"] = (busy, idle)
        if prev is None:
            return None  # sample pertama tak punya pembanding
        pct = 100.0 * (busy - prev[0]) / max(1, (busy - prev[0]) + (idle - prev[1]))
    with _lock:
        _cache["cpu"] = (time.time(), pct)
    return pct


# ── RAM ───────────────────────────────────────────────────────────────
def mem_percent():
    """Persentase RAM terpakai. More-accurate available vs total, bukan
    free-vs-total (free bukan 'tersedia' di Linux)."""
    try:
        with open(_PROC_MEMINFO, "r") as f:
            info = {}
            for line in f:
                key, _, rest = line.partition(":")
                info[key] = int(rest.split()[0])  # kB
    except (OSError, IndexError, ValueError):
        return None
    total = info.get("MemTotal")
    avail = info.get("MemAvailable")  # sejak 3.14; fallback di bawah
    if total is None:
        return None
    if avail is None:
        # fallback: free + buffers + cached, persis seperti free(1) lama
        avail = (info.get("MemFree", 0) + info.get("Buffers", 0)
                 + info.get("Cached", 0))
    return 100.0 * (total - avail) / total


# ── GPU ───────────────────────────────────────────────────────────────
def _nvidia():
    try:
        out = subprocess.run(
            ["nvidia-smi",
             "--query-gpu=utilization.gpu,memory.used,memory.total",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=3).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None
    for line in out.splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 3:
            continue
        try:
            util, used, total = float(parts[0]), float(parts[1]), float(parts[2])
        except ValueError:
            continue
        return {"util": util, "mem_used": used, "mem_total": total,
                "mem_percent": (100.0 * used / total) if total else 0.0}
    return None


def gpu():
    now = time.time()
    with _lock:
        hit = _cache.get("gpu")
        if hit and now - hit[0] < _TTL_HEAVY:
            return hit[1]
    data = _nvidia()
    with _lock:
        _cache["gpu"] = (time.time(), data)
    return data


# ── NET ───────────────────────────────────────────────────────────────
def _rx_bytes():
    total = 0
    try:
        with open(_PROC_NET_DEV, "r") as f:
            next(f)  # header 1
            next(f)  # header 2
            for line in f:
                _, _, rest = line.partition(":")
                cols = rest.split()
                if len(cols) < 9:
                    continue
                # loopback dihitung: dashboard lokal, jadinxrx host sendiri
                total += int(cols[0])
    except (OSError, ValueError):
        return None
    return total


def net_percent():
    """Persentase bandwidth uplink, dinormalkan terhadap link rate. Bukan
    'kecepatan' absolut — yang bisa ditampilkan adalah utilisasi link."""
    now = time.time()
    with _lock:
        hit = _cache.get("net")
        if hit and now - hit[0] < _TTL_NET_DELTA:
            return hit[1]
    rx = _rx_bytes()
    if rx is None:
        return None
    with _lock:
        prev = _cache.get("net_prev")
        prev_t = _cache.get("net_prev_t", 0.0)
        _cache["net_prev"] = rx
        _cache["net_prev_t"] = now
        if prev is None or rx <= prev or now - prev_t <= 0:
            # sample pertama (atau counter nyasar turun) tak punya throughput
            _cache["net"] = (time.time(), 0.0)
            return 0.0
        dt = now - prev_t
        mbps = (rx - prev) * 8 / dt / 1e6
        # kapasitas link: baca dari sysfs, fallback ke angka konservatif
        caps = _cache.get("net_cap") or _link_mbps()
        with _lock:
            _cache["net_cap"] = caps
        pct = min(100.0, 100.0 * mbps / caps) if caps else None
    with _lock:
        _cache["net"] = (time.time(), pct)
    return pct


def _link_mbps():
    """Mbps dari interface default, 1000 Mbit = 1_000_000 (bukan 1024)."""
    try:
        with open("/proc/net/route") as f:
            next(f)
            best = None
            for line in f:
                cols = line.split()
                if len(cols) > 2 and cols[1] == "00000000":  # default route
                    best = cols[0]
                    break
        if not best:
            return 1000.0
        # sysfs: kabel up = 1000, noload = 1000000000 (MHz)
        path = "/sys/class/net/%s/speed" % best
        mbps = float(open(path).read().strip())
        if mbps <= 0 or mbps >= 1_000_000_000:  # '-1' atau unknown
            return 1000.0
        return mbps
    except (OSError, ValueError):
        return 1000.0


# ── SUHU ──────────────────────────────────────────────────────────────
def _hwmon_temp():
    """CPU temperature in Celsius. Scan /sys/class/hwmon for the CPU package
    sensor, not acpitz: acpitz tracks the ACPI limit and often reads high or
    stale. Prefer k10temp/coretemp/cpu_thermal/cpu-thermal Tctl/Tdie/Package,
    because those are the real die sensors. Value is millidegrees."""
    import glob
    for hw in sorted(glob.glob("/sys/class/hwmon/hwmon*")):
        try:
            name = open(os.path.join(hw, "name")).read().strip()
        except OSError:
            continue
        if name not in ("k10temp", "coretemp", "cpu_thermal", "cpu-thermal",
                        "zenpower", "soc_thermal"):
            continue
        best = None
        for inp in sorted(glob.glob(os.path.join(hw, "temp*_input"))):
            try:
                raw = int(open(inp).read().strip())
            except (OSError, ValueError):
                continue
            lbl = ""
            lp = inp.replace("_input", "_label")
            try:
                lbl = open(lp).read().strip()
            except OSError:
                pass
            # Tctl/Tdie = package die; "Package id 0" on Intel
            if lbl in ("Tctl", "Tdie", "Package id 0", "Package", "CPU"):
                return raw / 1000.0
            if best is None:
                best = raw
        if best is not None:
            return best / 1000.0
    return None


def cpu_temp():
    """Cached wrapper around _hwmon_temp(). Reading hwmon is cheap but not free,
    and every open tab polls every 2s."""
    now = time.time()
    with _lock:
        hit = _cache.get("cpu_temp")
        if hit and now - hit[0] < _TTL_HEAVY:
            return hit[1]
    val = _hwmon_temp()
    with _lock:
        _cache["cpu_temp"] = (time.time(), val)
    return val


def gpu_temp():
    """GPU temperature in Celsius via nvidia-smi, same TTL as other GPU data."""
    now = time.time()
    with _lock:
        hit = _cache.get("gpu_temp")
        if hit and now - hit[0] < _TTL_HEAVY:
            return hit[1]
    val = None
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=temperature.gpu",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=3).stdout.strip()
        if out:
            val = float(out.splitlines()[0].strip())
    except (OSError, ValueError, subprocess.SubprocessError):
        val = None
    with _lock:
        _cache["gpu_temp"] = (time.time(), val)
    return val


# ── DISK ──────────────────────────────────────────────────────────────
def disk_percent(path="/"):
    try:
        st = os.statvfs(path)
    except OSError:
        return None
    total = st.f_blocks * st.f_frsize
    used = (st.f_blocks - st.f_bfree) * st.f_frsize
    return 100.0 * used / total if total else None


# ── AI ────────────────────────────────────────────────────────────────
def ai_percent(context_tokens=0, limit=200000):
    """Context window terpakai, 0..100. Sumbernya SESSION ctx, bukan tebakan."""
    if limit <= 0:
        return None
    return max(0.0, min(100.0, 100.0 * context_tokens / limit))


def snapshot(ctx_tokens=0):
    """Semua metrik dalam satu dict, untuk satu round-trip HTTP."""
    g = gpu() or {}
    return {
        "cpu": cpu_percent(),
        "ram": mem_percent(),
        "gpu": g.get("util"),
        "gpu_mem": g.get("mem_percent"),
        "net": net_percent(),
        "disk": disk_percent(),
        "ai": ai_percent(ctx_tokens),
        "cpu_temp": cpu_temp(),
        "gpu_temp": gpu_temp(),
        "ts": time.time(),
    }
