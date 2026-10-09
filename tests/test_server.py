"""End-to-end HTTP tests. Run: python -m unittest discover -s tests -v"""
import csv
import io
import json
import math
import os
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

TEMP = tempfile.TemporaryDirectory()
os.environ["SIGNBRIDGE_DB"] = str(Path(TEMP.name) / "test.sqlite3")
import server


def pose(shift=0, spread=1.0):
    # Controlled synthetic fixture for validating endpoints, NOT a sign-language dataset.
    return [{"x": 0.2 + shift + spread * (i % 5) * .06,
             "y": 0.35 + shift + spread * (i // 5) * .065,
             "z": spread * (i % 3) * .012} for i in range(21)]


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = server.serve("127.0.0.1", 0)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)
        TEMP.cleanup()

    def setUp(self):
        self.call("DELETE", "/api/history")
        self.call("DELETE", "/api/samples")

    def call(self, method, path, payload=None):
        body = json.dumps(payload).encode() if payload is not None else None
        req = urllib.request.Request(self.base + path, data=body, method=method,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=5) as res:
                content = res.read()
                return res.status, json.loads(content) if res.headers.get_content_type() == "application/json" else content, res.headers
        except urllib.error.HTTPError as err:
            return err.code, json.loads(err.read()), err.headers

    def test_page_assets_and_health(self):
        status, html, headers = self.call("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn(b"Dataset Studio", html)
        self.assertIn(b"app.js", html)
        code, js, _ = self.call("GET", "/app.js")
        self.assertEqual(code, 200)
        self.assertIn(b"captureSample", js)
        self.assertEqual(self.call("GET", "/api/health")[1]["status"], "ok")
        self.assertEqual(self.call("GET", "/secrets")[0], 404)

    def test_history_persistence_and_clear(self):
        code, out, _ = self.call("POST", "/api/history", {"event_type":"recognized", "phrase":"Water", "source":"gesture"})
        self.assertEqual(code, 201)
        self.assertEqual(out["item"]["phrase"], "Water")
        self.assertEqual(self.call("GET", "/api/history")[1]["items"][0]["phrase"], "Water")
        self.assertEqual(self.call("GET", "/api/stats")[1]["history_count"], 1)
        self.call("DELETE", "/api/history")
        self.assertEqual(self.call("GET", "/api/history")[1]["items"], [])

    def test_dataset_exports_delete_and_knn(self):
        # All inputs are synthetic software-testing fixtures, not real ASL samples.
        for _ in range(3):
            self.assertEqual(self.call("POST", "/api/samples", {"label":"Help", "landmarks":pose(), "handedness":"Right"})[0], 201)
        stats = self.call("GET", "/api/stats")[1]
        self.assertEqual(stats["sample_count"], 3)
        self.assertEqual(stats["trained_labels"], ["Help"])
        predicted = self.call("POST", "/api/predict", {"landmarks":pose(shift=.14, spread=.9), "handedness":"Right"})[1]
        self.assertEqual(predicted["label"], "Help")
        self.assertGreater(predicted["confidence"], 0.5)
        content = self.call("GET", "/api/export.json")[1]
        self.assertEqual(len(content["samples"]), 3)
        self.assertEqual(len(content["samples"][0]["landmarks"]), 21)
        _, csvdata, _ = self.call("GET", "/api/export.csv")
        parsed = list(csv.reader(io.StringIO(csvdata.decode())))
        self.assertEqual(len(parsed), 4)
        self.assertEqual(len(parsed[0]), 67)  # 4 metadata + 21*3 coords
        items = self.call("GET", "/api/samples")[1]["items"]
        self.assertEqual(self.call("DELETE", f"/api/samples/{items[0]['id']}")[0], 200)
        self.assertEqual(self.call("GET", "/api/stats")[1]["trained_labels"], [])
        self.assertIsNone(self.call("POST", "/api/predict", {"landmarks":pose()})[1]["label"])

    def test_validation_and_rejects(self):
        self.assertEqual(self.call("POST", "/api/samples", {"label":"Water", "landmarks":[]})[0], 400)
        self.assertEqual(self.call("POST", "/api/samples", {"label":"<script>", "landmarks":pose()})[0], 400)
        self.assertEqual(self.call("POST", "/api/samples", {"label":"Water", "landmarks":pose(), "handedness":"Middle"})[0], 400)
        self.assertEqual(self.call("POST", "/api/history", {"event_type":"invalid", "phrase":"Hello"})[0], 400)
        self.assertEqual(self.call("POST", "/api/predict", {"landmarks":pose()})[1]["label"], None)
        self.assertEqual(self.call("DELETE", "/api/samples/999999999")[0], 404)
        self.assertEqual(self.call("GET", "/api/history?limit=abc")[0], 400)

if __name__ == "__main__":
    unittest.main()
