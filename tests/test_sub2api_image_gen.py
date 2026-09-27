#!/usr/bin/env python3
"""Local end-to-end and credential-routing checks; no provider access required."""

import base64
from http.server import BaseHTTPRequestHandler, HTTPServer
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
from unittest.mock import patch


PNG_1X1 = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M/wHwAF/gL+XxKjWQAAAABJRU5ErkJggg==")
SCRIPT = Path(__file__).parents[1] / "scripts/sub2api_image_gen.py"
spec = importlib.util.spec_from_file_location("image_client", SCRIPT)
client = importlib.util.module_from_spec(spec)
spec.loader.exec_module(client)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def do_GET(self):
        assert self.path == "/v1/models"
        assert self.headers["Authorization"] == "Bearer not-a-secret"
        assert self.headers["User-Agent"] == "codex-sub2api-imagegen/1.0"
        self.reply(json.dumps({"data": [{"id": model} for model in
                              ("gpt-image-2.5-sunburst", "gpt-image-2.5-flare", "gpt-image-2")]}).encode())

    def do_POST(self):
        assert self.path in {"/v1/images/generations", "/v1/images/edits"}
        assert self.headers["Authorization"] == "Bearer not-a-secret"
        assert self.headers["X-Test-Header"] == "kept"
        request = self.rfile.read(int(self.headers["Content-Length"]))
        model, size, quality = self.server.expected
        if self.path.endswith("/edits"):
            assert b'name="image"' in request
            assert PNG_1X1 in request
            for key, value in (("model", model), ("size", size), ("quality", quality)):
                assert f'name="{key}"\r\n\r\n{value}\r\n'.encode() in request
        else:
            payload = json.loads(request)
            assert payload["model"] == model
            assert payload["size"] == size
            assert payload["quality"] == quality
            if payload["prompt"] == "transparent image":
                assert payload["background"] == "transparent"
                assert payload["output_format"] == "png"
        self.reply(json.dumps({"data": [{"b64_json": base64.b64encode(PNG_1X1).decode()}]}).encode())

    def reply(self, payload):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def check_routes(root, base_url):
    config = root / "routing" / "config.toml"
    config.parent.mkdir()
    auth = config.with_name("auth.json")
    provider_config = f'model_provider = "test"\n[model_providers.test]\nbase_url = "{base_url}"\n'
    config.write_text(provider_config)
    auth.write_text(json.dumps({"OPENAI_API_KEY": "auth-key"}))

    def expect_key(key, url=base_url):
        actual_url, headers, _ = client.load_route(config, None)
        assert actual_url == url
        assert headers["Authorization"] == f"Bearer {key}"

    def expect_failure():
        try:
            client.load_route(config, None)
        except SystemExit as exc:
            assert "Error:" in str(exc)
        else:
            raise AssertionError("Missing usable API key or URL must fail")

    with patch.dict(os.environ, {}, clear=True):
        expect_key("auth-key")
        config.write_text(provider_config + 'experimental_bearer_token = "provider-key"\n')
        expect_key("provider-key")
        with patch.dict(os.environ, {"OPENAI_API_KEY": "environment-key", "OPENAI_BASE_URL": base_url + "/override"}):
            expect_key("environment-key", base_url + "/override")
        auth.write_text("not json")
        expect_key("provider-key")  # A lower-priority malformed file is irrelevant.
        config.write_text(provider_config)
        expect_failure()
        for value in ({}, {"OPENAI_API_KEY": ""}, {"OPENAI_API_KEY": 123}, [],
                      {"tokens": {"access_token": "oauth-secret", "id_token": "oauth-id", "refresh_token": "oauth-refresh"}}):
            auth.write_text(json.dumps(value))
            expect_failure()
        auth.unlink()
        expect_failure()
        auth.write_text(json.dumps({"OPENAI_API_KEY": "auth-key"}))
        config.unlink()
        with patch.dict(os.environ, {"OPENAI_BASE_URL": base_url}):
            expect_key("auth-key")
        expect_failure()  # Credentials alone must not select a default endpoint.
        config.write_text(provider_config)
        elsewhere = root / "other-home"
        elsewhere.mkdir()
        (elsewhere / "auth.json").write_text(json.dumps({"OPENAI_API_KEY": "wrong-key"}))
        with patch.dict(os.environ, {"CODEX_HOME": str(elsewhere)}):
            expect_key("auth-key")  # Explicit config uses its own sibling auth.json.
        with patch.dict(os.environ, {"CODEX_HOME": str(config.parent)}):
            assert client.default_config_path() == config
            expect_key("auth-key")
    return config


def main():
    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base_url = f"http://127.0.0.1:{server.server_port}/v1"
            config = root / "config.toml"
            config.write_text(
                f'model_provider = "test"\n[model_providers.test]\nbase_url = "{base_url}"\n'
                'experimental_bearer_token = "not-a-secret"\nhttp_headers = { "X-Test-Header" = "kept" }\n'
            )
            env = {key: value for key, value in os.environ.items()
                   if key not in {"OPENAI_BASE_URL", "OPENAI_API_KEY", "CODEX_HOME"}
                   and not key.lower().endswith("_proxy")}
            env["CODEX_HOME"] = str(root)

            def run(*args, success=True):
                result = subprocess.run([sys.executable, str(SCRIPT), *args], env=env, capture_output=True, text=True)
                assert (result.returncode == 0) == success, result.stdout + result.stderr
                return result

            for model, size, quality in (("gpt-image-2.5-sunburst", "auto", "xhigh"),
                                         ("gpt-image-2.5-flare", "auto", "max"),
                                         ("gpt-image-2", "3840x2160", "medium")):
                options = [] if model == "gpt-image-2.5-sunburst" else ["--model", model]
                assert f"model: {model} (available)" in run("doctor", *options).stdout
                server.expected = model, size, quality
                output = root / f"{model}.png"
                run("generate", *options, "--quality", quality, "--prompt", "transparent image", "--background", "transparent", "--output-format", "png", "--out", str(output))
                assert output.read_bytes() == PNG_1X1
                edited = root / f"{model}-edit.png"
                run("edit", *options, "--quality", quality, "--image", str(output), "--prompt", "test image", "--out", str(edited))
                assert edited.read_bytes() == PNG_1X1
            for model in ("gpt-image-2", "gpt-image-2.5-sunburst", "gpt-image-2.5-flare",
                          "gpt-image-2.5-sunburst-2026-09-08", "gpt-image-2.5-flare-2026-09-08"):
                for size, success in (("1024x1024", True), ("3840x2160", True), ("auto", True),
                                      ("1000x1000", False), ("4096x4096", False),
                                      ("1024x256", False), ("256x256", False), ("bad", False)):
                    result = run("generate", "--model", model, "--size", size, "--prompt", "test image",
                                 "--out", str(root / "dry.png"), "--dry-run", success=success)
                    if success:
                        assert json.loads(result.stdout)["payload"]["size"] == size
            for model in ("future-model", "gpt-image-2.5"):
                result = run("generate", "--model", model, "--prompt", "test image",
                             "--out", str(root / "dry.png"), "--dry-run")
                assert json.loads(result.stdout)["payload"]["model"] == model
                if model == "gpt-image-2.5":
                    assert "warning" in result.stderr.lower() and model in result.stderr
            auth_config = check_routes(root, base_url)
            auth_config.with_name("auth.json").write_text(json.dumps({"OPENAI_API_KEY": "not-a-secret"}))
            env["CODEX_HOME"] = str(auth_config.parent)
            assert "gpt-image-2.5-sunburst (available)" in run("doctor").stdout
            env["CODEX_HOME"] = str(root)
            assert "gpt-image-2.5-sunburst (available)" in run("doctor", "--config", str(auth_config)).stdout
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
    print("ok")


if __name__ == "__main__":
    main()
