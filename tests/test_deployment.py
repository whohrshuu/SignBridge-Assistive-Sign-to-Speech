import unittest
from fastapi.testclient import TestClient
import api
class DeploymentTests(unittest.TestCase):
    def setUp(self): self.client=TestClient(api.app)
    def test_same_origin_ui(self):
        self.assertEqual(self.client.get('/').status_code,200)
        self.assertIn('authGate',self.client.get('/').text)
        self.assertEqual(self.client.get('/gestures.js').status_code,200)
        self.assertIn('"apiUrl": ""',self.client.get('/config.js').text)
    def test_private_routes_require_login(self):
        for p in ['/api/me','/api/samples','/api/history','/api/export.json']:
            self.assertEqual(self.client.get(p).status_code,401,p)
    def test_secret_key_not_exposed(self):
        old=api.KEY
        try:
            api.KEY='sb_secret_test'
            self.assertNotIn(api.KEY,self.client.get('/config.js').text)
        finally: api.KEY=old
    def test_source_not_served(self):
        self.assertEqual(self.client.get('/api.py').status_code,404)
        self.assertEqual(self.client.get('/supabase/migrations/001_private_data.sql').status_code,404)
