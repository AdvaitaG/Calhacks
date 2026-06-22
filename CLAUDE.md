# Baymax — Claude Code Instructions

## Git hygiene
- Always `git fetch && git pull --rebase` before committing or pushing
- When teammates are actively pushing, stash local changes first: `git stash && git pull --rebase && git stash pop`
- Commit in logical batches (one concern per commit), then push

## Secrets
- Never copy API keys, Band API keys, or any credentials into any file (md, yaml, py, txt, etc.)
- All credentials live in `.env` only — never committed
- Use placeholders (`...`) in `.env.example`
- Never push `.env`

## Band handles
- All agent handles are read from `.env` as `<Name>Handle` vars (e.g. `ConductorHandle`, `SafetyHandle`)
- Never hardcode handles in source code
- Defaults use the `@your-workspace/<name>` format

## Agent code patterns
- All agents use `AGENT_CONFIGS[name]` from `agents/shared/config.py` for credentials
- All agents use `WS_URL` / `REST_URL` from `agents/shared/config.py`
- INSTRUCTIONS that are f-strings must double all JSON braces: `{{` and `}}`
- All `LangGraphAdapter` calls must include `recursion_limit=200`
