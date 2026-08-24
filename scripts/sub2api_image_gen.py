#!/usr/bin/env python3
"""Generate or edit images through a Codex custom provider without the OpenAI SDK."""

from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
from pathlib import Path
import re
import struct
import sys
import tempfile
import tomllib
from typing import Any
import urllib.error
import urllib.request
import uuid

USER_AGENT = "codex-sub2api-imagegen/1.0"
DEFAULT_MODEL = "gpt-image-2"
DEFAULT_SIZE = "3840x2160"
DEFAULT_OUT = "output/imagegen/output.png"
MAX_INPUT_BYTES = 50 * 1024 * 1024


def fail(message: str) -> None:
    raise SystemExit(f"Error: {message}")


def default_config_path() -> Path:
    codex_home = os.environ.get("CODEX_HOME")
    return Path(codex_home).expanduser() / "config.toml" if codex_home else Path.home() / ".codex/config.toml"


def load_route(config_path: Path, provider_name: str | None) -> tuple[str, dict[str, str], str]:
    env_url = os.environ.get("OPENAI_BASE_URL")
    env_key = os.environ.get("OPENAI_API_KEY")
    config: dict[str, Any] = {}
    if config_path.exists():
        config = tomllib.loads(config_path.read_text(encoding="utf-8"))
    elif not (env_url and env_key):
        fail(f"Codex config not found: {config_path}")

    name = provider_name or str(config.get("model_provider", ""))
    provider = config.get("model_providers", {}).get(name, {}) if name else {}
    base_url = env_url or provider.get("base_url")
    token = env_key or provider.get("experimental_bearer_token")
    if not isinstance(base_url, str) or not base_url.startswith(("https://", "http://")):
        fail("No valid provider base URL. Set OPENAI_BASE_URL or configure model_providers.<name>.base_url.")
    if not isinstance(token, str) or not token:
        fail("No provider token. Set OPENAI_API_KEY or configure experimental_bearer_token locally.")

    custom = provider.get("http_headers", {})
    headers = {
        str(k): str(v)
        for k, v in custom.items()
        if str(k).lower() not in {"authorization", "user-agent"}
    } if isinstance(custom, dict) else {}
    headers.update({"Authorization": f"Bearer {token}", "User-Agent": USER_AGENT, "Accept": "application/json"})
    source = "environment" if env_url or env_key else f"Codex provider {name}"
    return base_url.rstrip("/"), headers, source


def request_json(url: str, headers: dict[str, str], data: bytes | None = None, content_type: str | None = None) -> dict[str, Any]:
    request_headers = dict(headers)
    if content_type:
        request_headers["Content-Type"] = content_type
    request = urllib.request.Request(url, data=data, headers=request_headers, method="POST" if data is not None else "GET")
    try:
        with urllib.request.urlopen(request, timeout=300 if data is not None else 20) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        detail = exc.read(4000).decode("utf-8", "replace").strip()
        fail(f"HTTP {exc.code} from {url}: {detail or exc.reason}")
    except urllib.error.URLError as exc:
        fail(f"Could not reach {url}: {exc.reason}")
    return {}  # unreachable


def output_paths(raw: str, count: int, output_format: str, force: bool) -> list[Path]:
    path = Path(raw)
    if not path.suffix:
        path = path.with_suffix("." + output_format)
    expected = {".jpg", ".jpeg"} if output_format == "jpeg" else {"." + output_format}
    if path.suffix.lower() not in expected:
        fail(f"Output extension {path.suffix} does not match --output-format {output_format}.")
    paths = [path] if count == 1 else [path.with_name(f"{path.stem}-{index}{path.suffix}") for index in range(1, count + 1)]
    existing = [str(item) for item in paths if item.exists()]
    if existing and not force:
        fail(f"Output already exists: {', '.join(existing)} (choose another path or pass --force)")
    return paths


def atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_name = ""
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=f".{path.name}.", delete=False) as temp:
            temp.write(content)
            temp_name = temp.name
        Path(temp_name).replace(path)
    finally:
        if temp_name:
            Path(temp_name).unlink(missing_ok=True)


def download_image(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return response.read()
    except urllib.error.URLError as exc:
        fail(f"Could not download generated image: {exc.reason}")
    return b""  # unreachable


def detect_png_size(content: bytes) -> str | None:
    if len(content) >= 24 and content.startswith(b"\x89PNG\r\n\x1a\n"):
        width, height = struct.unpack(">II", content[16:24])
        if width > 0 and height > 0:
            return f"{width}x{height}"
    return None


def save_response(result: dict[str, Any], paths: list[Path], requested_size: str) -> None:
    items = result.get("data")
    if not isinstance(items, list) or len(items) < len(paths):
        fail("Image API response did not contain the expected data array.")
    for item, path in zip(items, paths):
        if not isinstance(item, dict):
            fail("Image API returned an invalid data item.")
        if item.get("b64_json"):
            try:
                content = base64.b64decode(item["b64_json"], validate=True)
            except (ValueError, TypeError) as exc:
                fail(f"Image API returned invalid base64 data: {exc}")
        elif item.get("url"):
            content = download_image(str(item["url"]))
        else:
            fail("Image API response contained neither b64_json nor url.")
        atomic_write(path, content)
        actual_size = str(item.get("size") or "").strip() or detect_png_size(content)
        if actual_size and requested_size != "auto" and actual_size.lower() != requested_size.lower():
            print(
                f"Warning: provider returned {actual_size} for requested {requested_size}; "
                "saved original bytes without local upscaling.",
                file=sys.stderr,
            )
        print(path.resolve())


def multipart(fields: dict[str, str], files: list[tuple[str, Path]]) -> tuple[bytes, str]:
    boundary = "----codex-sub2api-" + uuid.uuid4().hex
    body = bytearray()
    for name, value in fields.items():
        body.extend(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n".encode())
    for name, path in files:
        media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        safe_name = path.name.replace('"', "")
        body.extend(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"; filename=\"{safe_name}\"\r\nContent-Type: {media_type}\r\n\r\n".encode())
        body.extend(path.read_bytes())
        body.extend(b"\r\n")
    body.extend(f"--{boundary}--\r\n".encode())
    return bytes(body), f"multipart/form-data; boundary={boundary}"


def common_payload(args: argparse.Namespace) -> dict[str, Any]:
    if not args.prompt.strip():
        fail("--prompt must not be blank.")
    if not 1 <= args.n <= 10:
        fail("--n must be between 1 and 10.")
    if args.model == "gpt-image-2" and args.size != "auto":
        match = re.fullmatch(r"([1-9][0-9]*)x([1-9][0-9]*)", args.size)
        if not match:
            fail("gpt-image-2 --size must be auto or WIDTHxHEIGHT.")
        width, height = map(int, match.groups())
        long_edge, short_edge = max(width, height), min(width, height)
        if (
            long_edge > 3840
            or width % 16
            or height % 16
            or long_edge / short_edge > 3
            or not 655_360 <= width * height <= 8_294_400
        ):
            fail("gpt-image-2 size exceeds its edge, alignment, ratio, or pixel-count limits.")
    return {key: value for key, value in {
        "model": args.model,
        "prompt": args.prompt.strip(),
        "n": args.n,
        "size": args.size,
        "quality": args.quality,
        "background": args.background,
        "output_format": args.output_format,
    }.items() if value is not None}


def route(args: argparse.Namespace) -> tuple[str, dict[str, str], str]:
    base_url, headers, source = load_route(Path(args.config).expanduser(), args.provider)
    return base_url, headers, source


def doctor(args: argparse.Namespace) -> None:
    base_url, headers, source = route(args)
    result = request_json(base_url + "/models", headers)
    models = [item.get("id") for item in result.get("data", []) if isinstance(item, dict)]
    print(f"route: {source}")
    print(f"base_url: {base_url}")
    print(f"user_agent: {USER_AGENT}")
    print(f"model: {args.model} ({'available' if args.model in models else 'not listed'})")
    if args.model not in models:
        raise SystemExit(2)


def generate(args: argparse.Namespace) -> None:
    payload = common_payload(args)
    paths = output_paths(args.out, args.n, args.output_format, args.force)
    base_url, headers, source = route(args)
    if args.dry_run:
        print(json.dumps({"route": source, "endpoint": base_url + "/images/generations", "payload": payload, "outputs": [str(path) for path in paths]}, ensure_ascii=False, indent=2))
        return
    result = request_json(base_url + "/images/generations", headers, json.dumps(payload).encode(), "application/json")
    save_response(result, paths, args.size)


def edit(args: argparse.Namespace) -> None:
    image = Path(args.image)
    mask = Path(args.mask) if args.mask else None
    for path in [item for item in (image, mask) if item is not None]:
        if not path.is_file():
            fail(f"Input file not found: {path}")
        if path.stat().st_size > MAX_INPUT_BYTES:
            fail(f"Input exceeds 50 MB: {path}")
    payload = common_payload(args)
    paths = output_paths(args.out, args.n, args.output_format, args.force)
    base_url, headers, source = route(args)
    if args.dry_run:
        print(json.dumps({"route": source, "endpoint": base_url + "/images/edits", "fields": payload, "image": str(image), "mask": str(mask) if mask else None, "outputs": [str(path) for path in paths]}, ensure_ascii=False, indent=2))
        return
    fields = {key: str(value) for key, value in payload.items()}
    body, content_type = multipart(fields, [("image", image)] + ([("mask", mask)] if mask else []))
    result = request_json(base_url + "/images/edits", headers, body, content_type)
    save_response(result, paths, args.size)


def parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--config", default=str(default_config_path()))
    common.add_argument("--provider")
    common.add_argument("--model", default=DEFAULT_MODEL)

    image = argparse.ArgumentParser(description=__doc__)
    commands = image.add_subparsers(dest="command", required=True)
    check = commands.add_parser("doctor", parents=[common])
    check.set_defaults(run=doctor)

    for name, handler in (("generate", generate), ("edit", edit)):
        command = commands.add_parser(name, parents=[common])
        command.add_argument("--prompt", required=True)
        command.add_argument("--size", default=DEFAULT_SIZE)
        command.add_argument("--quality", choices=("low", "medium", "high", "auto"), default="medium")
        command.add_argument("--n", type=int, default=1)
        command.add_argument("--background", choices=("transparent", "opaque", "auto"))
        command.add_argument("--output-format", choices=("png", "jpeg", "webp"), default="png")
        command.add_argument("--out", default=DEFAULT_OUT)
        command.add_argument("--force", action="store_true")
        command.add_argument("--dry-run", action="store_true")
        command.set_defaults(run=handler)
    commands.choices["edit"].add_argument("--image", required=True)
    commands.choices["edit"].add_argument("--mask")
    return image


def main() -> None:
    args = parser().parse_args()
    args.run(args)


if __name__ == "__main__":
    main()
