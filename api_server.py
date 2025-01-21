from flask import Flask, request, jsonify
from kafka import KafkaProducer
import json
import threading
import time
import queue

app = Flask(__name__)

message_queue = queue.Queue(maxsize=10000)
producer = KafkaProducer(
    bootstrap_servers='localhost:9092',
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)

message_count = 0
message_count_lock = threading.Lock()

def flush_messages():
    global message_count
    batch = []
    while True:
        try:
            start_time = time.time()
            while len(batch) < 1000 and time.time() - start_time < 0.5:
                try:
                    message = message_queue.get(timeout=0.1)
                    batch.append(message)
                except queue.Empty:
                    break
            
            if batch:
                for message in batch:
                    producer.send('emoji_topic', message)
                    with message_count_lock:
                        message_count += 1
                producer.flush()
                print(f"Flushed {len(batch)} messages to Kafka")
                batch.clear()
            
            time.sleep(0.1)

            with message_count_lock:
                print(f"Total messages processed: {message_count}")

        except Exception as e:
            print(f"Error in flush_messages: {e}")

flush_thread = threading.Thread(target=flush_messages, daemon=True)
flush_thread.start()

@app.route('/send_emoji', methods=['POST'])
def send_emoji():
    data = request.json
    if not all(field in data for field in ['user_id', 'emoji_type', 'timestamp']):
        return jsonify({"error": "Missing fields in request data"}), 400
    
    try:
        message_queue.put(data, block=False)
        with message_count_lock:
            print(f"Message added to queue: {data}")
        return jsonify({"status": "Emoji data queued"}), 200
    except queue.Full:
        return jsonify({"error": "Message queue is full"}), 503
    except Exception as e:
        return jsonify({"error": f"Failed to queue data: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(port=5000, debug=True, threaded=True)
