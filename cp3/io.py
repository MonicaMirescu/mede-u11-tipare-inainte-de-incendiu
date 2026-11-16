"""I/O fără rotunjirea predictorilor și protejarea explicită a CP2."""
import hashlib
import json
from pathlib import Path

import pandas as pd


def sha256(path, text=False):
    data = Path(path).read_bytes()
    if text:
        data = data.replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()


def read_csv(path, **kwargs):
    return pd.read_csv(path, float_precision="round_trip", **kwargs)


def save_csv(frame, path, na_rep=""):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, float_format="%.17g", na_rep=na_rep, lineterminator="\n")


def save_json(value, path):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def cp2_fingerprints(project):
    root = Path(project) / "outputs/CP2"
    return {p.relative_to(project).as_posix(): sha256(p) for p in sorted(root.rglob("*")) if p.is_file()}


def require(condition, message):
    if not condition:
        raise ValueError(message)
