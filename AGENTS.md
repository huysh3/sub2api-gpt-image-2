# Project conventions

- `scripts/sub2api_image_gen.py` is a Python 3.11+ standard-library Images API client. Keep runtime dependencies empty; its inline metadata supports `uv run` without preinstalled Python.
- Default model is `gpt-image-2.6-sunburst` with `size=auto`. Official 2.6 and 2.5 variants, including the 2.5 snapshots, share size constraints and support `xhigh`/`max` quality. Bare `gpt-image-2.5` and `gpt-image-2.6` are unverified provider aliases and are never auto-selected or silently mapped.
- The 2.6 client supports optional complexity, GIF generation and editing, and SVG generation with one output. Preserve returned bytes and keep GIF frame settings exclusive to GIF output.
- Endpoint precedence: environment > selected Codex provider. Key precedence: environment > provider token > top-level `OPENAI_API_KEY` in `auth.json` beside the selected config. Never use OAuth tokens or silently change endpoints.
- Keep README.md and SKILL.md synchronized with CLI defaults, routing, and startup instructions.
- Verify with `uv run --python 3.11 tests/test_sub2api_image_gen.py` and `git diff --check`. Local tests use dummy credentials; do not run paid generation solely for verification.

- Public usage docs focus on GPT Image 2.6. Prompt routing lives in SKILL.md: explicit model wins; speed/drafts use Flare, precise edits/default use Sunburst. Always pass the selected full ID via --model; the CLI does not route prompt text.
