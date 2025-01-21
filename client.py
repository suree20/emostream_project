import os
import multiprocessing
import threading
import queue
import random
import requests
import time
import uuid
import json
import logging
import websockets
import asyncio
import concurrent.futures
from datetime import datetime
from flask import Flask, render_template, request, jsonify, Response, stream_with_context
from typing import Dict, List

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

class LoadTestConfig:
    MAX_WORKERS = multiprocessing.cpu_count() * 2
    MAX_EMOJIS_PER_SECOND_PER_CLIENT = 1000
    TOTAL_CLIENTS = 100
    API_ENDPOINT = "http://localhost:5000/send_emoji"
    WEBSOCKET_BASE_URI = "ws://localhost:"
    WEBSOCKET_BASE_PORT = 8765
    NUM_CLUSTERS = 3
    EMOJIS = ["👍", "❤️", "😂", "🎉", "😢", "🔥", "👏", "🏆", "😮", "💔"]

class ScalableEmojiGenerator:
    def __init__(self, config: LoadTestConfig):
        self.config = config
        self.message_queues: Dict[str, queue.Queue] = {}
        self.automated_senders: Dict[str, threading.Thread] = {}
        self.load_test_executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.config.MAX_WORKERS
        )

    def generate_unique_user_id(self) -> str:
        return str(uuid.uuid4())

    def send_emoji_bulk(self, batch_size: int) -> List[Dict]:
        user_id = self.generate_unique_user_id()
        emojis = []
        for _ in range(batch_size):
            emoji_data = {
                "user_id": user_id,
                "emoji_type": random.choice(self.config.EMOJIS),
                "timestamp": datetime.now().isoformat()
            }
            emojis.append(emoji_data)
        return emojis

    def send_bulk_emojis(self, batch_size: int = 1000):
        try:
            batch = self.send_emoji_bulk(batch_size)
            with concurrent.futures.ThreadPoolExecutor(max_workers=min(20, batch_size)) as executor:
                futures = [
                    executor.submit(requests.post, self.config.API_ENDPOINT, json=emoji)
                    for emoji in batch
                ]
                concurrent.futures.wait(futures)
            return len([f for f in futures if f.result().status_code == 200])
        except Exception as e:
            logger.error(f"Bulk emoji send error: {e}")
            return 0

    def load_test(self, duration: int = 60, batches_per_second: int = 1):
        start_time = time.time()
        total_emojis_sent = 0

        while time.time() - start_time < duration:
            batch_success_count = self.send_bulk_emojis(
                batch_size=batches_per_second * 1000
            )
            total_emojis_sent += batch_success_count
            time.sleep(1)

        logger.info(f"Load Test Results - Total Emojis Sent: {total_emojis_sent}")
        return total_emojis_sent

emoji_generator = ScalableEmojiGenerator(LoadTestConfig)

app = Flask(__name__)

message_queues = {}
automated_senders = {}

class AutomatedSender:
    def __init__(self, user_id, api_endpoint="http://localhost:5000/send_emoji", max_emojis_per_second=200):
        self.user_id = user_id
        self.api_endpoint = api_endpoint
        self.running = True
        self.max_emojis_per_second = max_emojis_per_second
        self.EMOJIS = ["👍", "❤️", "😂", "🎉", "😢", "🔥", "👏", "🏆", "😮", "💔"]
        
    def start(self):
        self.thread = threading.Thread(target=self._send_loop, daemon=True)
        self.thread.start()
        
    def stop(self):
        self.running = False
        
    def _send_loop(self):
        interval = 1.0 / self.max_emojis_per_second
        while self.running:
            emoji_data = {
                "user_id": self.user_id,
                "emoji_type": random.choice(self.EMOJIS),
                "timestamp": datetime.now().isoformat()
            }
            try:
                response = requests.post(self.api_endpoint, json=emoji_data)
                if response.status_code == 200:
                    _broadcast_message(f"Automated send: {emoji_data['emoji_type']} from {self.user_id}")
            except Exception as e:
                print(f"Error in automated sender: {e}")
            time.sleep(interval)

def _broadcast_message(message):
    for user_id, queue in message_queues.items():
        queue.put(message)

async def websocket_client(user_id, message_queue, cluster_id=None):
    if cluster_id is None:
        cluster_id = f"cluster_{random.randint(0, LoadTestConfig.NUM_CLUSTERS - 1)}"
    
    uri = f"{LoadTestConfig.WEBSOCKET_BASE_URI}{LoadTestConfig.WEBSOCKET_BASE_PORT + int(cluster_id.split('_')[1])}/{cluster_id}"
    
    while True:
        try:
            async with websockets.connect(uri) as websocket:
                message_queue.put(f"Connected to emoji stream in {cluster_id}")
                while True:
                    try:
                        message = await websocket.recv()
                        data = json.loads(message)
                        message_queue.put(f"Received: {data['emoji_type']} from {data['user_id']} in {cluster_id}")
                    except websockets.exceptions.ConnectionClosed:
                        message_queue.put(f"Connection closed in {cluster_id}. Reconnecting...")
                        break
        except Exception as e:
            message_queue.put(f"Connection error in {cluster_id}: {str(e)}")
            await asyncio.sleep(5)

def start_websocket_client(user_id, message_queue, cluster_id=None):
    asyncio.run(websocket_client(user_id, message_queue, cluster_id))

def _user_disconnected(user_id):
    if user_id in automated_senders:
        automated_senders[user_id].stop()
        del automated_senders[user_id]

    _broadcast_message(f"{user_id} has disconnected from the system.")

@app.route('/events')
def events():
    user_id = request.args.get('user_id', 'unknown_user')
    cluster_id = request.args.get('cluster', None)

    if user_id not in message_queues:
        message_queues[user_id] = queue.Queue()
        _broadcast_message(f"{user_id} has connected to the system.")
        
        threading.Thread(target=start_websocket_client, 
                         args=(user_id, message_queues[user_id], cluster_id), 
                         daemon=True).start()

    def generate():
        try:
            while True:
                message = message_queues[user_id].get(timeout=20)
                yield f"data: {message}\n\n"
        except queue.Empty:
            yield f"data: ping\n\n"
        finally:
            _user_disconnected(user_id)

    return Response(stream_with_context(generate()), 
                   mimetype='text/event-stream')

@app.route('/toggle_automated', methods=['POST'])
def toggle_automated():
    data = request.json
    user_id = data.get('user_id')
    should_start = data.get('start', False)
    
    if should_start:
        if user_id not in automated_senders:
            automated_senders[user_id] = AutomatedSender(user_id)
            automated_senders[user_id].start()
        return jsonify({"status": f"Automated sender started for {user_id}"}), 200
    else:
        if user_id in automated_senders:
            automated_senders[user_id].stop()
            del automated_senders[user_id]
        return jsonify({"status": f"Automated sender stopped for {user_id}"}), 200

@app.route('/load_test', methods=['POST'])
def perform_load_test():
    data = request.json
    duration = data.get('duration', 60)
    batches_per_second = data.get('batches_per_second', 1)
    
    total_emojis = emoji_generator.load_test(
        duration=duration,
        batches_per_second=batches_per_second
    )
    
    return jsonify({
        "status": "Load test completed",
        "total_emojis_sent": total_emojis
    })

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/send_emoji_local', methods=['POST'])
def send_emoji_local():
    data = request.json
    try:
        response = requests.post('http://localhost:5000/send_emoji', json=data)
        return jsonify(response.json()), response.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(port=5001, debug=True)
