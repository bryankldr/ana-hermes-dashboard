#!/usr/bin/env python3
"""
Map Bridge for ANA HUD Dashboard.
Pushes MapLibre commands to the `map_store` via HTTP POST to localhost:9000.
"""
import os
import json
import time
import urllib.request
import urllib.error

API_BASE = os.getenv("API_BASE_URL", "http://127.0.0.1:9000")
API_TOKEN = os.getenv("ANA_TOKEN", "")

HEADERS = {"Content-Type": "application/json"}


def post(path, data):
    """POST to map store API."""
    url = f"{API_BASE}{path}"
    req = urllib.request.Request(url, data=json.dumps(data).encode(), headers=HEADERS, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        return {"error": str(e)}


def add_layer(table="petak", tahun=2025, layer_id=None):
    """Queue add_layer command for RTT petak geometry."""
    layer_id = layer_id or f"{table}_{tahun}"
    return {
        "type": "add_layer",
        "layer_id": layer_id,
        "source": f"{API_BASE}/api/simoge/query",
        "query": {
            "template": "petak_with_geometry",
            "params": {"tahun": tahun, "limit": 500}
        },
        "paint": {
            "fill-color": "#22c55e",
            "fill-opacity": 0.4,
            "fill-outline-color": "#16a34a"
        },
        "layout": {"visibility": "visible"}
    }


def add_layer_from_geojson(geojson, layer_id="custom"):
    """Queue add_layer for raw GeoJSON (from query results)."""
    return {
        "type": "add_layer",
        "layer_id": layer_id,
        "geojson": geojson,
        "paint": {"fill-color": "#22c55e", "fill-opacity": 0.5, "fill-outline-color": "#16a34a"}
    }


def filter_layer(layer_id, filter_expr):
    """Queue filter command."""
    return {"type": "filter_layer", "layer_id": layer_id, "filter": filter_expr}


def fit_bounds(layer_id, padding=50):
    """Queue fit_bounds command."""
    return {"type": "fit_bounds", "layer_id": layer_id, "padding": padding}


def highlight(layer_id, feature_ids, color="#fbbf24"):
    """Queue highlight command."""
    return {"type": "highlight", "layer_id": layer_id, "feature_ids": feature_ids, "paint": {"fill-color": color}}


def set_paint(layer_id, property, value):
    """Queue set_paint property command."""
    return {"type": "set_paint", "layer_id": layer_id, "property": property, "value": value}


def queue(commands):
    """Queue one or more map commands."""
    if isinstance(commands, dict):
        commands = [commands]
    return post("/api/map/queue", {"commands": commands})


def result(cmd_id):
    """Get result for command ID."""
    return post(f"/api/map/result?id={cmd_id}", {})


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: map_bridge.py <command> [args...]")
        print("Commands: add_layer, filter, fit_bounds, highlight, queue, result")
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "add_layer":
        layer = add_layer(
            tahun=int(sys.argv[2]) if len(sys.argv) > 2 else 2025,
            layer_id=sys.argv[3] if len(sys.argv) > 3 else None
        )
        print(json.dumps(queue(layer), indent=2))
    elif cmd == "fit_bounds":
        resp = queue(fit_bounds(sys.argv[2] if len(sys.argv) > 2 else "rtt_2025"))
        print(json.dumps(resp, indent=2))
    elif cmd == "result":
        if len(sys.argv) > 2:
            print(json.dumps(result(sys.argv[2]), indent=2))
        else:
            print("Need cmd_id")
    else:
        print(f"Unknown: {cmd}")