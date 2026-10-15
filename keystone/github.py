"""Fetch PR history from GitHub GraphQL into a resumable on-disk cache (public data only)."""
import json, sys, time
from pathlib import Path
import httpx
from .config import env

RAW = Path(__file__).resolve().parent.parent / "data" / "raw"
QUERY = """
query($owner:String!,$name:String!,$after:String){
 rateLimit{cost remaining resetAt}
 repository(owner:$owner,name:$name){
  pullRequests(first:30,after:$after,orderBy:{field:CREATED_AT,direction:DESC}){
   pageInfo{hasNextPage endCursor}
   nodes{number title url state isDraft createdAt mergedAt closedAt additions deletions changedFiles
    author{login __typename} bodyText mergedBy{login}
    labels(first:5){nodes{name}}
    files(first:50){nodes{path additions deletions}}
    reviews(first:20){nodes{author{login __typename} state submittedAt bodyText}}
    comments(first:20){nodes{author{login __typename} createdAt bodyText}}
    closingIssuesReferences(first:3){nodes{number title}}
 }}}}"""


ISSUE_QUERY = """
query($owner:String!,$name:String!,$after:String){
 rateLimit{cost remaining resetAt}
 repository(owner:$owner,name:$name){
  issues(first:30,after:$after,orderBy:{field:CREATED_AT,direction:DESC}){
   pageInfo{hasNextPage endCursor}
   nodes{number title url state createdAt closedAt author{login __typename} bodyText
    labels(first:5){nodes{name}}
    comments(first:20){nodes{author{login __typename} createdAt bodyText}}
 }}}}"""


def _post(client, variables, query=None):
    for attempt in range(6):
        try:
            r = client.post("https://api.github.com/graphql", json={"query": query or QUERY, "variables": variables})
            if r.status_code in (502, 503, 504) or "RESOURCE_LIMITS" in r.text[:300]:
                raise httpx.HTTPError(f"retryable {r.status_code}")
            r.raise_for_status()
            d = r.json()
            if "errors" in d and not d.get("data"):
                raise RuntimeError(d["errors"])
            return d["data"]
        except (httpx.HTTPError, httpx.TimeoutException, ValueError):
            time.sleep(2 ** attempt)
    raise RuntimeError("github fetch failed after retries")


def fetch_repo(full_name: str, since: str = "2023-01-01", kind: str = "pullRequests") -> int:
    """Page newest-to-oldest until PRs predate `since`. Returns PR count cached. Resumable via cursor file."""
    owner, name = full_name.split("/")
    out = (RAW if kind == "pullRequests" else RAW.parent / "raw_issues") / owner / name
    out.mkdir(parents=True, exist_ok=True)
    cur_f = out / "_cursor.json"
    state = json.loads(cur_f.read_text()) if cur_f.exists() else {"after": None, "page": 0, "done": False}
    headers = {"Authorization": f"Bearer {env('GITHUB_TOKEN')}"}
    n = 0
    with httpx.Client(headers=headers, timeout=60) as client:
        while not state["done"]:
            data = _post(client, {"owner": owner, "name": name, "after": state["after"]}, QUERY if kind == "pullRequests" else ISSUE_QUERY)
            rl, prs = data["rateLimit"], data["repository"][kind]
            nodes = prs["nodes"]
            (out / f"p{state['page']:04d}.json").write_text(json.dumps(nodes), encoding="utf8")
            n += len(nodes)
            oldest = nodes[-1]["createdAt"] if nodes else since
            state = {"after": prs["pageInfo"]["endCursor"], "page": state["page"] + 1,
                     "done": not prs["pageInfo"]["hasNextPage"] or oldest[:10] < since}
            cur_f.write_text(json.dumps(state))
            print(f"{full_name} page={state['page']} prs={n} oldest={oldest[:10]} rate_left={rl['remaining']}", flush=True)
            if rl["remaining"] < 150:  # wait for the hourly window instead of failing
                wait = max(5, (time.mktime(time.strptime(rl["resetAt"], "%Y-%m-%dT%H:%M:%SZ")) - time.mktime(time.gmtime())))
                print(f"rate limit low, sleeping {int(wait)}s", flush=True)
                time.sleep(wait + 5)
    return n


def iter_prs(full_name: str, kind: str = "prs"):
    owner, name = full_name.split("/")
    base = RAW if kind == "prs" else RAW.parent / "raw_issues"
    for p in sorted((base / owner / name).glob("p*.json")):
        yield from json.loads(p.read_text(encoding="utf8"))


if __name__ == "__main__":
    kind = "issues" if sys.argv[1] == "--issues" else "pullRequests"
    for repo in sys.argv[2 if kind == "issues" else 1:]:
        fetch_repo(repo, "2024-01-01" if kind == "issues" else "2023-01-01", kind)
