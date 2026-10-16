"""Small helpers for recording time and memory, saved next to every run."""
from __future__ import annotations

import json
import resource
import sys
from pathlib import Path
from typing import Dict, List

import numpy as np


def peak_rss_mb() -> float:
    """Peak resident memory of this process so far (MB)."""
    r = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return r / 1024.0 if sys.platform != "darwin" else r / (1024.0 * 1024.0)


def latency_summary(lat: List[float]) -> Dict[str, float]:
    a = np.asarray(lat) * 1000.0
    if a.size == 0:
        return {"mean_ms": float("nan"), "median_ms": float("nan"), "p95_ms": float("nan")}
    return {"mean_ms": float(a.mean()), "median_ms": float(np.median(a)), "p95_ms": float(np.percentile(a, 95))}


def save_efficiency(path: str | Path, record: Dict) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    record = dict(record)
    record.setdefault("peak_rss_mb", round(peak_rss_mb(), 1))
    Path(path).write_text(json.dumps(record, indent=2))


def load_efficiency(paths) -> Dict[str, Dict]:
    out = {}
    for p in paths:
        d = json.loads(Path(p).read_text())
        out[d["system"]] = d
    return out
