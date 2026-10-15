"""Cached snapshot of every read the page makes, so the first impression survives a slow or unavailable backend.
python -m keystone.snapshot   (writes public/snapshot.json; run before each deploy)"""
import json
from pathlib import Path
from . import api

OUT = Path(__file__).resolve().parent.parent / "public" / "snapshot.json"


def build():
    snap = {"tenants": api.tenants(), "eval": api.evaluation(), "t": {}}
    for t in snap["tenants"]:
        snap["t"][t] = {"overview": api.overview(t), "riskmap": api.riskmap(t), "risk": api.risk(t), "ticker": api.ticker(t)}
    OUT.write_text(json.dumps(snap, ensure_ascii=False, separators=(",", ":")), encoding="utf8")
    return {t: len(json.dumps(v)) // 1024 for t, v in snap["t"].items()}


if __name__ == "__main__":
    print(build(), "KB per tenant ->", OUT)
