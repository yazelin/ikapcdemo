"""Web UI: single-shot preview plus feature panel. Stdlib + ffmpeg only.

The camera stays open for the life of the server (exclusive access);
every request is serialized through one lock because IKapC handles are
not thread-safe and the camera is a one-shot photo device anyway.
"""

import json
import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from .camera import Camera, list_cameras

_camera = None
_serial = None
_lock = threading.Lock()


def _cam():
    global _camera
    if _camera is None:
        _camera = Camera(_serial)
    return _camera


class RequestHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    timeout = 120  # full-res capture + encode can take a few seconds

    def log_message(self, fmt, *args):
        if os.environ.get("IKAPCDEMO_DEBUG") == "1":
            sys.stderr.write(fmt % args + "\n")

    def _json(self, obj, status=200):
        body = json.dumps(obj).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        query = {k: v[0] for k, v in parse_qs(parsed.query).items()}
        try:
            if parsed.path == "/":
                self._index()
            elif parsed.path == "/api/cameras":
                self._json(list_cameras())
            elif parsed.path == "/api/features":
                with _lock:
                    self._json(_cam().list_features())
            elif parsed.path == "/snapshot.jpg":
                self._snapshot(query)
            else:
                self._json({"error": "not found"}, 404)
        except (BrokenPipeError, ConnectionResetError):
            self.close_connection = True
        except Exception as exc:
            self._json({"error": str(exc)}, 500)

    def do_POST(self):
        parsed = urlparse(self.path)
        try:
            length = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(length) or b"{}")
        except ValueError:
            self._json({"error": "invalid body"}, 400)
            return
        try:
            if parsed.path == "/api/feature":
                with _lock:
                    cam = _cam()
                    cam.set(body["name"], body["value"])
                    self._json({"ok": True, "features": cam.list_features()})
            else:
                self._json({"error": "not found"}, 404)
        except (BrokenPipeError, ConnectionResetError):
            self.close_connection = True
        except Exception as exc:
            self._json({"error": str(exc)}, 500)

    def _index(self):
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "static", "index.html")
        with open(path, "rb") as fh:
            body = fh.read()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _snapshot(self, query):
        kwargs = {}
        if query.get("exposure"):
            kwargs["exposure_us"] = float(query["exposure"])
        if query.get("gain"):
            kwargs["gain"] = float(query["gain"])
        with _lock:
            ppm = _cam().read_ppm(**kwargs)
        jpeg = subprocess.run(
            ["ffmpeg", "-loglevel", "error", "-i", "pipe:0",
             "-frames:v", "1", "-q:v", "3", "-f", "mjpeg", "pipe:1"],
            input=ppm, capture_output=True, check=True).stdout
        self.send_response(200)
        self.send_header("Content-Type", "image/jpeg")
        self.send_header("Content-Length", str(len(jpeg)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(jpeg)


def serve(serial=None, host="127.0.0.1", port=8601):
    global _serial
    _serial = serial
    httpd = ThreadingHTTPServer((host, port), RequestHandler)
    sys.stderr.write("ikapcdemo server on http://%s:%d\n" % (host, port))
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
        if _camera is not None:
            _camera.close()


if __name__ == "__main__":
    serve()
