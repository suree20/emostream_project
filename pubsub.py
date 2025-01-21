import json
import asyncio
import uuid
import websockets
from kafka import KafkaConsumer, KafkaProducer
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Set, List, Optional, Union

class ClusterNode:
    def __init__(self, cluster_id: str):
        self.id = cluster_id
        self.subscribers: Set[websockets.WebSocketServerProtocol] = set()
        self.client_registry: Dict[str, websockets.WebSocketServerProtocol] = {}

    async def broadcast(self, message: Dict):
        disconnected = set()
        for subscriber in self.subscribers:
            try:
                await asyncio.wait_for(
                    subscriber.send(json.dumps(message)), 
                    timeout=5.0
                )
            except (websockets.exceptions.ConnectionClosed, asyncio.TimeoutError):
                disconnected.add(subscriber)
        
        self.subscribers -= disconnected
        for client_id, socket in list(self.client_registry.items()):
            if socket in disconnected:
                del self.client_registry[client_id]

class ClusterManager:
    def __init__(self, 
                 num_clusters: int = 3, 
                 kafka_bootstrap_servers: str = 'localhost:9092', 
                 websocket_base_port: int = 8765):
        self.clusters: Dict[str, ClusterNode] = {
            f"cluster_{i}": ClusterNode(f"cluster_{i}") 
            for i in range(num_clusters)
        }
        self.kafka_bootstrap_servers = kafka_bootstrap_servers
        self.websocket_base_port = websocket_base_port
        self.running = True
        self.executor = ThreadPoolExecutor(max_workers=10)
        
    def setup_kafka_consumer(self, topic: str = 'emoji_topic') -> KafkaConsumer:
        return KafkaConsumer(
            topic,
            bootstrap_servers=self.kafka_bootstrap_servers,
            value_deserializer=lambda x: json.loads(x.decode('utf-8')),
            group_id=f'cluster_consumer_{uuid.uuid4()}',
            auto_offset_reset='latest',
            enable_auto_commit=True
        )

    async def handle_subscriber_connection(self, 
                                           websocket: websockets.WebSocketServerProtocol, 
                                           path: Union[str, None] = None):
        if not path:
            cluster_id = list(self.clusters.keys())[0]
        else:
            parts = path.strip('/').split('/')
            cluster_id = parts[0] if parts and 'cluster_' in parts[0] else \
                list(self.clusters.keys())[0]
        
        if cluster_id not in self.clusters:
            cluster_id = list(self.clusters.keys())[0]
        
        cluster = self.clusters[cluster_id]
        
        client_id = f"{cluster_id}_{uuid.uuid4().hex[:8]}"
        
        cluster.subscribers.add(websocket)
        cluster.client_registry[client_id] = websocket
        
        try:
            async for message in websocket:
                pass
        finally:
            cluster.subscribers.discard(websocket)
            cluster.client_registry.pop(client_id, None)

    def kafka_consumer_loop(self):
        consumer = self.setup_kafka_consumer()
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        while self.running:
            try:
                for message in consumer:
                    if message and message.value:
                        loop.run_until_complete(
                            self.distribute_to_clusters(message.value)
                        )
            except Exception as e:
                print(f"Error in Kafka consumer loop: {e}")
                loop.run_until_complete(asyncio.sleep(1))

    async def distribute_to_clusters(self, message: Dict):
        distribution_tasks = []
        for cluster in self.clusters.values():
            distribution_tasks.append(cluster.broadcast(message))
        
        await asyncio.gather(*distribution_tasks, return_exceptions=True)

    async def start_websocket_server(self):
        servers = []
        for i, cluster_id in enumerate(self.clusters.keys()):
            server = await websockets.serve(
                self.handle_subscriber_connection,
                "localhost",
                self.websocket_base_port + i,
                ping_timeout=None,
                ping_interval=None,
            )
            servers.append(server)
        
        return servers

    async def start(self):
        self.executor.submit(self.kafka_consumer_loop)
        
        servers = await self.start_websocket_server()
        
        await asyncio.gather(*(server.wait_closed() for server in servers))

    def stop(self):
        self.running = False
        self.executor.shutdown(wait=True)

async def run_cluster_manager():
    cluster_manager = ClusterManager()
    try:
        await cluster_manager.start()
    except KeyboardInterrupt:
        cluster_manager.stop()
    except Exception as e:
        print(f"Error in cluster manager: {e}")
        cluster_manager.stop()

if __name__ == "__main__":
    asyncio.run(run_cluster_manager())
