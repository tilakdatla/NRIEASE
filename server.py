import json
import os
import ssl
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


RAJASTHAN_RERA_API = "https://reraapi.rajasthan.gov.in/api/web/Home/GetProjects"
RAJASTHAN_RERA_REFERER = "https://rera.rajasthan.gov.in/"
GUJARAT_RERA_API = "https://gujrera.gujarat.gov.in/project_reg/public/global-search"


class PrototypeHandler(SimpleHTTPRequestHandler):
    def _send_json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/api/health":
            self._send_json(200, {"ok": True})
            return
        requested = Path(self.path.split("?", 1)[0].lstrip("/"))
        if not requested.name or not requested.is_file():
            self.path = "/index.html"
        super().do_GET()

    def do_POST(self):
        if self.path == "/api/gujarat-rera":
            self._proxy_gujarat_rera()
            return
        if self.path != "/api/rajasthan-rera":
            self._send_json(404, {"ok": False, "error": "Not found."})
            return

        api_key = os.environ.get("RAJASTHAN_RERA_API_KEY", "").strip()
        if not api_key:
            self._send_json(503, {"ok": False, "error": "Rajasthan RERA API key is not configured on the local server."})
            return

        try:
            length = min(int(self.headers.get("Content-Length", "0")), 8192)
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            registration_number = str(payload.get("RegistrationNo", "")).strip()
        except (ValueError, UnicodeDecodeError, AttributeError):
            self._send_json(400, {"ok": False, "error": "Expected JSON with a RegistrationNo field."})
            return

        if not registration_number or len(registration_number) > 80:
            self._send_json(400, {"ok": False, "error": "A valid RegistrationNo is required."})
            return

        request_body = json.dumps({"RegistrationNo": registration_number}).encode("utf-8")
        request = Request(
            RAJASTHAN_RERA_API,
            data=request_body,
            method="POST",
            headers={
                "Accept": "application/json, text/plain, */*",
                "Content-Type": "application/json",
                "Referer": RAJASTHAN_RERA_REFERER,
                "x-api-key": api_key,
            },
        )
        try:
            with urlopen(request, timeout=20) as response:
                upstream_body = response.read(2_000_000)
                upstream_payload = json.loads(upstream_body.decode("utf-8-sig"))
                self._send_json(200, upstream_payload)
        except HTTPError as error:
            self._send_json(502, {"ok": False, "error": f"Rajasthan RERA returned HTTP {error.code}."})
        except (URLError, TimeoutError, OSError):
            self._send_json(502, {"ok": False, "error": "Could not reach the Rajasthan RERA service."})
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._send_json(502, {"ok": False, "error": "Rajasthan RERA returned an unreadable response."})

    def _proxy_gujarat_rera(self):
        try:
            length = min(int(self.headers.get("Content-Length", "0")), 8192)
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            registration_number = str(payload.get("RegistrationNo", "")).strip()
        except (ValueError, UnicodeDecodeError, AttributeError):
            self._send_json(400, {"ok": False, "error": "Expected JSON with a RegistrationNo field."})
            return

        if not registration_number or len(registration_number) > 180:
            self._send_json(400, {"ok": False, "error": "A valid RegistrationNo is required."})
            return

        request_body = json.dumps({"query": registration_number, "dataSize": 25, "startWith": 0}).encode("utf-8")
        request = Request(
            GUJARAT_RERA_API,
            data=request_body,
            method="POST",
            headers={"Accept": "application/json", "Content-Type": "application/json"},
        )
        try:
            tls_context = ssl.create_default_context()
            tls_context.options |= getattr(ssl, "OP_LEGACY_SERVER_CONNECT", 0)
            with urlopen(request, timeout=20, context=tls_context) as response:
                upstream_body = response.read(2_000_000)
                upstream_payload = json.loads(upstream_body.decode("utf-8-sig"))
                self._send_json(200, upstream_payload)
        except HTTPError as error:
            self._send_json(502, {"ok": False, "error": f"Gujarat RERA returned HTTP {error.code}."})
        except (URLError, TimeoutError, OSError):
            self._send_json(502, {"ok": False, "error": "Could not reach the Gujarat RERA service."})
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._send_json(502, {"ok": False, "error": "Gujarat RERA returned an unreadable response."})


if __name__ == "__main__":
    print("NRI Ease prototype running at http://localhost:3000")
    ThreadingHTTPServer(("0.0.0.0", 3000), PrototypeHandler).serve_forever()
