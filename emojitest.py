import unittest
import json
from api_server import app


class EmojiAPITestCase(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    def test_send_emoji_local(self):
        payload = {
            "user_id": "test_user",
            "emoji_type": "👍",
            "timestamp": "2024-11-19T12:34:56.789Z"
        }
        response = self.app.post('/send_emoji', json=payload)
        self.assertEqual(response.status_code, 200)
        self.assertIn("status", response.json)
if __name__ == "__main__":
    unittest.main()
