"""SignBridge: dependency-free Python HTTP API and SQLite storage.

Run: python server.py    (Python 3.9+)
Recognition landmarks remain client-side with MediaPipe; this backend stores
history, real labeled landmark samples, and performs optional KNN inference.
"""
import csv
import mimetypes
from contextlib import contextmanager
import io
import json
import math
import os
import re
import sqlite3
import threading
from collections import Counter
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, parse_qs

ROOT = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("SIGNBRIDGE_DB", str(ROOT / "data" / "signbridge.sqlite3")))
MAX_BODY = 1_000_000
MAX_SAMPLES = 50_000
SAMPLE_LABEL = re.compile(r"^[A-Za-z][A-Za-z0-9 _'-]{0,47}$")
ALLOWED_EVENTS = {"recognized", "quick", "spoken", "saved"}
_lock = threading.Lock()


@contextmanager
def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH), timeout=20)
    try:
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=20000")
        db.execute("PRAGMA journal_mode=WAL")
        with db:
            yield db
    finally:
        db.close()


def initialize():
    with connect() as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                phrase TEXT NOT NULL,
                source TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS samples (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                label TEXT NOT NULL,
                handedness TEXT NOT NULL,
                landmarks TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS sample_label_idx ON samples(label);
        """)


def iso_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def landmarks_valid(points):
    if not isinstance(points, list) or len(points) != 21:
        return False
    for point in points:
        if not isinstance(point, dict) or not all(k in point for k in ("x", "y", "z")):
            return False
        for k in ("x", "y", "z"):
            val = point[k]
            if isinstance(val, bool) or not isinstance(val, (int, float)) or not math.isfinite(val) or abs(val) > 10:
                return False
    return True


def normalized(points, handedness="Unknown"):
    """Center at wrist, mirror left to right, and normalize by max palm span."""
    origin = points[0]
    mirror = -1 if handedness == "Left" else 1
    coords = [[(p["x"]-origin["x"]) * mirror, p["y"]-origin["y"], (p["z"]-origin["z"])] for p in points]
    scale = max((math.hypot(x, y) for x, y, z in coords), default=0)
    if scale < 1e-5:
        raise ValueError("Landmarks must form a visible hand")
    return [v / scale for p in coords for v in p]


def classify(points, handedness="Unknown"):
    target = normalized(points, handedness)
    with connect() as db:
        samples = db.execute("SELECT label, handedness, landmarks FROM samples ORDER BY id DESC LIMIT ?", (MAX_SAMPLES,)).fetchall()
    counts = Counter(s["label"] for s in samples)
    eligible = {label for label, count in counts.items() if count >= 3}
    if not eligible:
        return {"label": None, "confidence": 0.0, "trained_labels": sorted(eligible), "reason": "Capture at least 3 examples per label"}
    candidates = []
    for sample in samples:
        if sample["label"] not in eligible:
            continue
        try:
            vector = normalized(json.loads(sample["landmarks"]), sample["handedness"])
        except (ValueError, KeyError, TypeError):
            continue
        dist = math.sqrt(sum((a-b)**2 for a, b in zip(vector, target)) / len(target))
        candidates.append((dist, sample["label"]))
    if not candidates:
        return {"label": None, "confidence": 0.0, "trained_labels": sorted(eligible), "reason": "No usable samples"}
    candidates.sort(key=lambda item: item[0])
    neighbors = candidates[:min(5, len(candidates))]
    votes = Counter(label for _, label in neighbors)
    winner = sorted(votes, key=lambda name: (-votes[name], min(d for d, label in neighbors if label == name), name))[0]
    winner_dist = min(dist for dist, label in neighbors if label == winner)
    # Reject unknown/poor matches instead of inventing a valid gesture.
    if winner_dist > 0.18:
        return {"label": None, "confidence": 0.0, "trained_labels": sorted(eligible), "reason": "No close match"}
    confidence = round(max(0.0, min(1.0, (votes[winner] / len(neighbors)) * (1 - winner_dist / 0.18))), 3)
    if confidence < 0.35:
        return {"label": None, "confidence": confidence, "trained_labels": sorted(eligible), "reason": "Low confidence"}
    return {"label": winner, "confidence": confidence, "trained_labels": sorted(eligible), "reason": None}


class Handler(BaseHTTPRequestHandler):
    server_version = "SignBridge/1.0"

    def send_json(self, code, payload):
        data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(data)

    def send_bytes(self, code, data, kind, filename=None):
        self.send_response(code)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-store")
        if filename:
            self.send_header("Content-Disposition", 'attachment; filename="%s"' % filename)
        self.end_headers()
        self.wfile.write(data)

    def read_json(self):
        raw_length = self.headers.get("Content-Length", "")
        if not raw_length.isdecimal() or int(raw_length) > MAX_BODY:
            raise ValueError("Missing or oversized request body")
        try:
            obj = json.loads(self.rfile.read(int(raw_length)))
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError("Malformed JSON") from exc
        if not isinstance(obj, dict):
            raise ValueError("Expected JSON object")
        return obj

    def do_GET(self):
        uri = urlsplit(self.path)
        path = uri.path
        q = parse_qs(uri.query)
        if path in ("/", "/index.html"):
            return self.send_bytes(200, (ROOT / "index.html").read_bytes(), "text/html; charset=utf-8")
        if path.startswith("/vendor/"):
            from urllib.parse import unquote
            target = (ROOT / unquote(path).lstrip("/")).resolve()
            if not target.is_relative_to(ROOT / "vendor") or not target.is_file():
                return self.send_json(404, {"error":"Asset not found"})
            kind = "application/wasm" if target.suffix == ".wasm" else (mimetypes.guess_type(str(target))[0] or "application/octet-stream")
            return self.send_bytes(200, target.read_bytes(), kind)
        if path == "/gestures.js":
            return self.send_bytes(200, (ROOT / "gestures.js").read_bytes(), "application/javascript; charset=utf-8")
        if path == "/app.js":
            return self.send_bytes(200, (ROOT / "app.js").read_bytes(), "application/javascript; charset=utf-8")
        if path == "/manifest.webmanifest":
            return self.send_bytes(200, (ROOT / "manifest.webmanifest").read_bytes(), "application/manifest+json")
        if path in ("/api/health", "/health"):
            return self.send_json(200, {"status": "ok", "service": "SignBridge API", "database": "sqlite"})
        if path == "/api/history":
            try:
                limit = min(100, max(1, int(q.get("limit", ["25"])[0])))
            except ValueError:
                return self.send_json(400, {"error": "Invalid limit"})
            with connect() as db:
                items = [dict(x) for x in db.execute("SELECT * FROM history ORDER BY id DESC LIMIT ?", (limit,))]
            return self.send_json(200, {"items": items})
        if path == "/api/samples":
            try:
                limit = min(500, max(1, int(q.get("limit", ["100"])[0])))
            except ValueError:
                return self.send_json(400, {"error": "Invalid limit"})
            with connect() as db:
                items = [dict(x) for x in db.execute("SELECT id,label,handedness,created_at FROM samples ORDER BY id DESC LIMIT ?", (limit,))]
            return self.send_json(200, {"items": items})
        if path == "/api/stats":
            with connect() as db:
                history_count = db.execute("SELECT COUNT(*) FROM history").fetchone()[0]
                rows = db.execute("SELECT label,COUNT(*) AS count FROM samples GROUP BY label ORDER BY label").fetchall()
            labels = {r["label"]: r["count"] for r in rows}
            return self.send_json(200, {"history_count": history_count, "sample_count": sum(labels.values()), "labels": labels, "trained_labels": [k for k,v in labels.items() if v >= 3]})
        if path in ("/api/export.csv", "/api/export.json"):
            with connect() as db:
                rows = [dict(x) for x in db.execute("SELECT * FROM samples ORDER BY id")]
            if path.endswith("json"):
                for r in rows:
                    r["landmarks"] = json.loads(r["landmarks"])
                return self.send_bytes(200, json.dumps({"format": "SignBridge landmarks v1", "samples": rows}, indent=2).encode(), "application/json", "signbridge-dataset.json")
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(["id", "label", "handedness", "created_at"] + [f"point_{i}_{a}" for i in range(21) for a in "xyz"])
            for r in rows:
                pts = json.loads(r["landmarks"])
                writer.writerow([r["id"], r["label"], r["handedness"], r["created_at"]] + [p[a] for p in pts for a in "xyz"])
            return self.send_bytes(200, output.getvalue().encode(), "text/csv; charset=utf-8", "signbridge-dataset.csv")
        if path == "/favicon.ico":
            return self.send_bytes(204, b"", "image/x-icon")
        return self.send_json(404, {"error": "Route not found"})

    def do_POST(self):
        path = urlsplit(self.path).path
        if path not in ("/api/history", "/api/samples", "/api/predict"):
            return self.send_json(404, {"error": "Route not found"})
        try:
            data = self.read_json()
            if path == "/api/history":
                phrase = data.get("phrase")
                source = data.get("source", "gesture")
                event = data.get("event_type", "recognized")
                if not isinstance(phrase, str) or not phrase.strip() or len(phrase) > 500:
                    raise ValueError("Phrase must contain 1 to 500 characters")
                if not isinstance(source, str) or len(source) > 32 or not source:
                    raise ValueError("Invalid source")
                if event not in ALLOWED_EVENTS:
                    raise ValueError("Invalid event type")
                with connect() as db:
                    cur = db.execute("INSERT INTO history(event_type,phrase,source,created_at) VALUES (?,?,?,?)", (event, phrase.strip(), source, iso_now()))
                    row = dict(db.execute("SELECT * FROM history WHERE id=?", (cur.lastrowid,)).fetchone())
                return self.send_json(201, {"item": row})
            points = data.get("landmarks")
            handed = data.get("handedness", "Unknown")
            if not landmarks_valid(points):
                raise ValueError("Exactly 21 valid x/y/z landmarks are required")
            if handed not in ("Left", "Right", "Unknown"):
                raise ValueError("Invalid handedness")
            normalized(points, handed)
            if path == "/api/predict":
                return self.send_json(200, classify(points, handed))
            label = data.get("label")
            if not isinstance(label, str) or not SAMPLE_LABEL.fullmatch(label.strip()):
                raise ValueError("Label must be 1-48 letters/numbers/spaces")
            label = label.strip()
            with _lock:
                with connect() as db:
                    if db.execute("SELECT COUNT(*) FROM samples").fetchone()[0] >= MAX_SAMPLES:
                        return self.send_json(409, {"error": "Dataset capacity reached"})
                    cur = db.execute("INSERT INTO samples(label,handedness,landmarks,created_at) VALUES(?,?,?,?)", (label, handed, json.dumps(points, separators=(",", ":")), iso_now()))
                    item_id = cur.lastrowid
            return self.send_json(201, {"id": item_id, "label": label})
        except ValueError as err:
            return self.send_json(400, {"error": str(err)})

    def do_DELETE(self):
        path = urlsplit(self.path).path
        if path == "/api/history":
            with connect() as db:
                db.execute("DELETE FROM history")
            return self.send_json(200, {"deleted": True})
        if path == "/api/samples":
            with connect() as db:
                db.execute("DELETE FROM samples")
            return self.send_json(200, {"deleted": True})
        match = re.fullmatch(r"/api/samples/(\d+)", path)
        if match:
            with connect() as db:
                res = db.execute("DELETE FROM samples WHERE id=?", (int(match.group(1)),))
            return self.send_json(200 if res.rowcount else 404, {"deleted": bool(res.rowcount)})
        return self.send_json(404, {"error": "Route not found"})


def serve(host="127.0.0.1", port=None):
    initialize()
    port = int(port if port is not None else os.environ.get("PORT", "8000"))
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"SignBridge available at http://localhost:{server.server_port}", flush=True)
    return server


if __name__ == "__main__":
    serve().serve_forever()
