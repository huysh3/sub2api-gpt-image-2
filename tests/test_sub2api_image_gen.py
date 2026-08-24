#!/usr/bin/env python3
"""One local end-to-end check for the Sub2API image client."""

import base64
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import subprocess
import tempfile
import threading


PNG_1X1 = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M/wHwAF/gL+XxKjWQAAAABJRU5ErkJggg==")
SCRIPT = Path(__file__).parents[1] / "scripts/sub2api_image_gen.py"


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def do_GET(self):
        assert self.path == "/v1/models"
        assert self.headers["Authorization"] == "Bearer not-a-secret"
        assert self.headers["User-Agent"] == "codex-sub2api-imagegen/1.0"
        self.reply(b'{"data":[{"id":"gpt-image-2"}]}')

    def do_POST(self):
        assert self.path in {"/v1/images/generations", "/v1/images/edits"}
        assert self.headers["X-Test-Header"] == "kept"
        request = self.rfile.read(int(self.headers["Content-Length"]))
        assert b"test image" in request or b"transparent image" in request
        if b"transparent image" in request:
            assert b'"model": "gpt-image-2"' in request
            assert b'"background": "transparent"' in request
            assert b'"output_format": "png"' in request
        if self.path.endswith("/edits"):
            assert b'name="image"' in request
            assert PNG_1X1 in request
        else:
            assert b'"size": "3840x2160"' in request
        payload = b'{"data":[{"b64_json":"' + base64.b64encode(PNG_1X1) + b'"}]}'
        self.reply(payload)

    def reply(self, payload):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def main():
    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        config = root / "config.toml"
        output = root / "image.png"
        config.write_text(
            f'model_provider = "test"\n[model_providers.test]\nbase_url = "http://127.0.0.1:{server.server_port}/v1"\n'
            'experimental_bearer_token = "not-a-secret"\nhttp_headers = { "X-Test-Header" = "kept" }\n'
        )
        subprocess.run(["python3", str(SCRIPT), "doctor", "--config", str(config)], check=True)
        subprocess.run(["python3", str(SCRIPT), "generate", "--config", str(config), "--prompt", "test image", "--out", str(output)], check=True)
        assert output.read_bytes() == PNG_1X1
        transparent = root / "transparent.png"
        subprocess.run(["python3", str(SCRIPT), "generate", "--config", str(config), "--prompt", "transparent image", "--background", "transparent", "--output-format", "png", "--out", str(transparent)], check=True)
        assert transparent.read_bytes() == PNG_1X1
        edited = root / "edited.png"
        subprocess.run(["python3", str(SCRIPT), "edit", "--config", str(config), "--image", str(output), "--prompt", "test image", "--out", str(edited)], check=True)
        assert edited.read_bytes() == PNG_1X1
    server.shutdown()
    print("ok")


if __name__ == "__main__":
    main()
