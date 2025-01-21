from locust import HttpUser, task, between
import random
from datetime import datetime

class EmojiLoadTester(HttpUser):
    wait_time = between(0.1, 0.5) 

    @task
    def send_emoji(self):
        emoji_types = ["👍", "❤️", "😂", "🎉", "😢", "🔥", "👏", "🏆", "😮", "💔"]
        emoji_data = {
            "user_id": f"user_{random.randint(1, 1000)}",
            "emoji_type": random.choice(emoji_types),
            "timestamp": datetime.now().isoformat()
        }
        self.client.post("/send_emoji", json=emoji_data)

