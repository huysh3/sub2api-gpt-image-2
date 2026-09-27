# Project conventions

- `scripts/sub2api_image_gen.py` is a Python 3.11+ standard-library Images API client. Keep runtime dependencies empty; its inline metadata supports `uv run` without preinstalled Python.
- Default model is `gpt-image-2.5-sunburst` with `size=auto`. Explicit `gpt-image-2` retains its 3840x2160 default and local size validation. Both official 2.5 variants and their 2026-09-08 snapshots use the documented size constraints; `xhigh`/`max` quality is supported. Bare `gpt-image-2.5` is an unverified provider alias, never auto-selected or silently mapped.
- Endpoint precedence: environment > selected Codex provider. Key precedence: environment > provider token > top-level `OPENAI_API_KEY` in `auth.json` beside the selected config. Never use OAuth tokens or silently change endpoints.
- Keep README.md and SKILL.md synchronized with CLI defaults, routing, and startup instructions.
- Verify with `uv run --python 3.11 tests/test_sub2api_image_gen.py` and `git diff --check`. Local tests use dummy credentials; do not run paid generation solely for verification.
