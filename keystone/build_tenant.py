"""One command: any public repos -> a tenant graph.   python -m keystone.build_tenant <tenant> owner/repo [owner/repo ...]
fetch (cached, resumable) -> MERGE load -> derive algorithms -> embed PRs -> extract + verify decisions -> load decisions."""
import sys
from . import decisions, embed_prs, github, load, load_decisions
from .derive import derive


def build(tenant: str, repos: list[str], decide: bool = True):
    for r in repos:
        github.fetch_repo(r, "2023-01-01", "pullRequests")
        github.fetch_repo(r, "2024-01-01", "issues")
        print(r, "prs", load.load_repo(tenant, r), "issues", load.load_issues(tenant, r), flush=True)
    print("derived", derive(tenant), "embedded", embed_prs.embed_prs(tenant), flush=True)
    if decide:
        for r in repos:
            for kind in ("prs", "issues"):
                decisions.run(r, kind=kind)
                print(r, kind, "decisions loaded", load_decisions.load(tenant, r, kind), flush=True)
    print(load.stats(tenant))


if __name__ == "__main__":
    build(sys.argv[1], sys.argv[2:])
