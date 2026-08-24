---
name: "sub2api-imagegen"
description: "Generate or edit raster images through the current Codex custom provider or sub2api when the built-in image_gen tool is unavailable, missing, or blocked. Use for image assets and visual variants; do not use for SVG, HTML/CSS, diagrams, or other deterministic code-native visuals."
---

# Sub2API Image Generation

Use the bundled dependency-free client instead of the system `imagegen` CLI. It reads the active provider's `base_url`, `experimental_bearer_token`, and `http_headers` from Codex config, then sends a non-SDK User-Agent to avoid the known sub2api/Cloudflare SDK-header block.

## Workflow

1. Resolve `<skill-dir>` as the directory containing this `SKILL.md`. Run the no-cost connectivity check:

   ```bash
   python3 "<skill-dir>/scripts/sub2api_image_gen.py" doctor
   ```

2. Normalize the user's request into a concise prompt. Preserve exact text and explicitly state edit invariants such as `change only the background; keep the subject unchanged`.
3. Generate or edit exactly once. A user request to create/edit an image authorizes that call; diagnostics alone do not authorize a billed smoke test.
4. Read the client's requested/actual-size warning, then inspect the untouched saved image with `view_image`. Retry only for a specific defect the user asked to fix.
5. Report the model, final prompt, and absolute saved path. For project assets, save under the project's `output/imagegen/` or the user-named path.

Generate:

```bash
python3 "<skill-dir>/scripts/sub2api_image_gen.py" generate \
  --prompt "A ceramic coffee mug in soft studio light; no logo, text, or watermark" \
  --quality medium \
  --out output/imagegen/mug.png
```

Edit:

```bash
python3 "<skill-dir>/scripts/sub2api_image_gen.py" edit \
  --image input.png \
  --prompt "Replace only the background with a warm sunset; keep the product and edges unchanged" \
  --out output/imagegen/sunset-edit.png
```

Use `--dry-run` to inspect a redacted request without network or cost. Use `--provider NAME` or `--config PATH` only when the active Codex provider is not the intended route. `OPENAI_BASE_URL` and `OPENAI_API_KEY` override config values when set.

## Resolution

- Default `gpt-image-2` request: `3840x2160`, the experimental maximum landscape request accepted by the current Image API constraints. Use `2160x3840` for maximum portrait output.
- Provider-returned bytes are authoritative. The client reports any requested/actual mismatch and never upscales, resamples, or pads locally.
- sub2api account routes differ. OpenAI OAuth can pass `3840x2160` upstream yet return `1672x941`; API-key routes or other compatible providers may return a larger image. Keep the maximum request as the portable default instead of hard-coding one OAuth result as every provider's ceiling.
- Evidence: [OpenAI `gpt-image-2` sizes](https://developers.openai.com/cookbook/examples/multimodal/image-gen-models-prompting-guide#popular-gpt-image-2-sizes) and [sub2api OAuth actual-size test](https://github.com/Wei-Shaw/sub2api/blob/d45135d87df16d48637f04ccd245727bc955ba54/backend/internal/service/openai_images_actual_size_test.go#L42-L54).

## Boundaries

- Never print, persist, or ask the user to paste a token. Do not copy credentials into project files.
- Never auto-retry a paid request. Surface the API error and change only the demonstrated cause.
- Never claim requested dimensions are actual dimensions; report the decoded/API-reported output size.
- Do not overwrite an existing file unless the user requested replacement; otherwise choose a versioned filename. `--force` is explicit overwrite authorization.
- `gpt-image-2` supports transparent output. For a transparent background, keep the default model and pass `--background transparent --output-format png` (or `webp`).
- Prefer the built-in `image_gen` tool when it is actually available and working. This skill exists for the custom-provider fallback path.
