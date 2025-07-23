# EmojiStream Project

A real-time emoji streaming platform created using Kafka, PySpark, and Flask.

---

## Overview

EmojiStream is a scalable, real-time emoji streaming application. It enables users to send emoji reactions via a web client, streams the data through Kafka, and processes/aggregates this data using PySpark. Built for both interactive usage and load testing, it is ideal for analytics dashboards and distributed event processing.

---

## Architecture

- **Frontend Client:** A Flask-based web UI for users to connect, send emojis, and view streaming logs.
- **API Server:** Accepts emoji events via REST API, batches, and streams them to Kafka.
- **Load Testing Module:** Simulates multiple users and bulk emoji sending for performance testing.
- **Streaming Analytics:** PySpark consumer aggregates emoji usage in real-time for dashboarding or analytics.

---

## Features

- Real-time emoji sending and streaming.
- Web-based client with interactive emoji buttons.
- Automated emoji sender for load testing.
- Kafka-backed event ingestion.
- PySpark streaming consumer for windowed aggregation.
- Scalable for thousands of events per second.

---

## Getting Started

### Prerequisites

- Python 3.8+
- Apache Kafka (running locally on `localhost:9092`)
- PySpark
- Flask

### Installation

```bash
# Clone the repository
git clone https://github.com/suree20/emostream_project.git
cd emostream_project

# Install Python dependencies
pip install flask kafka-python pyspark requests
```

### Kafka Setup

Start a local Kafka broker and create the topic `emoji_topic`:

```bash
# Start Zookeeper and Kafka
bin/zookeeper-server-start.sh config/zookeeper.properties
bin/kafka-server-start.sh config/server.properties

# Create topic
bin/kafka-topics.sh --create --topic emoji_topic --bootstrap-server localhost:9092 --partitions 1 --replication-factor 1
```

---

## Usage

### Start the API Server

```bash
python api_server.py
```

### Start the Web Client

```bash
python client.py
```

Visit `http://localhost:5000` in your browser to use the interface.

### Start Spark Consumer

```bash
python spark_consumer.py
```

---

## Components

### 1. Frontend Client

- HTML/JS interface (`templates/index.html`)
- Connect/disconnect, send emoji, start/stop automated sender
- Real-time log display

### 2. API Server (`api_server.py`)

- `/send_emoji`: Accepts emoji data, writes to Kafka topic
- Message batching and flushing for high throughput

### 3. Load Testing & Automation (`client.py`)

- `ScalableEmojiGenerator` for bulk and automated emoji sending
- `AutomatedSender` class for rapid emoji streaming

### 4. Streaming Analytics (`spark_consumer.py`)

- Consumes from Kafka topic
- Aggregates emoji counts by type and time window (1 minute)
- Scales counts for high-volume scenarios

---

## Load Testing

Run load tests using the `/load_test` endpoint. Example:

```bash
curl -X POST http://localhost:5000/load_test -H "Content-Type: application/json" -d '{"duration":60,"batches_per_second":10}'
```

Access locust dashboard at `http://localhost:8089` 

---

## Streaming Analytics

- Spark consumer aggregates emoji counts in 1-minute windows.
- Results printed to console for monitoring or further integration.

