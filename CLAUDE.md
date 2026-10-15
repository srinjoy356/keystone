# Graph Hacks (FalkorDB) - Keystone

Hackathon Oct 15 12:01 AM IST to Oct 18 11:59 PM IST 2026. Write no app code before kickoff.

## Secrets
- OpenAI key and model are in `important_.txt` (gpt-4o-mini; embeddings text-embedding-3-small). Load via env. Never print, log or commit. Repo is public.

## Token discipline (always)
- Use rtk-condensed output, jcodemunch (route/menu/order) and ast-grep before reading files. Filter at the source. Batch commands.
- Ponytail: smallest complete change, reuse before writing. One test or assert per non-trivial logic.
- Terse replies, no filler, no emojis, no em dashes.

## Project rules
- FalkorDB must be essential. Public/synthetic data only, no emails or personal data.
- README must have: setup, graph data model, key Cypher, AI-usage disclosure, declared tracks.
- Agent DB access is read-only, parameterized, with timeout and LIMIT. Imports idempotent (MERGE).
