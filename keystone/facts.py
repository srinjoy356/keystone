"""Facts shown on the Trust section, computed from artefacts so the UI never hard-codes numbers: python -m keystone.facts"""
import glob, json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def build():
    kept = rejected = prs = 0
    for f in glob.glob(str(ROOT / "data" / "decisions" / "*.json")):
        d = json.loads(Path(f).read_text(encoding="utf8"))
        kept += sum(len(v["decisions"]) for v in d.values())
        rejected += sum(v["rejected"] for v in d.values())
        prs += len(d)
    out = {"decisions": {"proposed": kept + rejected, "rejected": rejected, "kept": kept, "threads": prs}}
    (ROOT / "data" / "facts.json").write_text(json.dumps(out, indent=1))
    return out


if __name__ == "__main__":
    print(build())
