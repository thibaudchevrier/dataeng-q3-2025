"""
Kafka streaming consumer for transaction processing.

This module implements a Kafka consumer that continuously consumes
transaction messages from Kafka topics, processes them (validation,
ML predictions, database persistence), and handles failures.
"""

import logging
import os
import json
from contextlib import contextmanager
from confluent_kafka import Consumer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@contextmanager
def get_kafka_consumer(bootstrap_servers: str, group_id: str, topic: str):
    """
    Context manager for Kafka Consumer.
    
    Parameters
    ----------
    bootstrap_servers : str
        Kafka bootstrap servers (e.g., "localhost:9092").
    group_id : str
        Consumer group ID for coordinated consumption.
    topic : str
        Kafka topic to subscribe to.
        
    Yields
    ------
    Consumer
        Kafka consumer instance for message consumption.
        
    Notes
    -----
    Consumer automatically closes on context exit.
    Configured with 'auto.offset.reset' set to 'earliest' 
    to consume from beginning if no offset exists.
    """
    c = Consumer({
        'bootstrap.servers': bootstrap_servers,
        'group.id': group_id,
        'auto.offset.reset': 'earliest'
    })
    
    c.subscribe([topic])
    
    try:
        yield c
    finally:
        c.close()



def main():
    """
    Execute Kafka consumer workflow.
    
    This function orchestrates the consumer lifecycle:
    - Loads configuration from environment variables
    - Creates Kafka consumer with group coordination
    - Continuously polls for messages
    - Processes transactions (TODO: validation, ML, database)
    
    Environment Variables
    ---------------------
    KAFKA_BOOTSTRAP_SERVERS : str
        Kafka bootstrap servers (default: 'localhost:9092').
    KAFKA_CONSUMER_GROUP : str
        Consumer group ID (default: 'transaction-consumer-group').
    KAFKA_TOPIC : str
        Source Kafka topic (default: 'transactions').
        
    Notes
    -----
    Polls with 1 second timeout for responsive shutdown.
    Logs progress every 100 messages for monitoring.
    Gracefully handles KeyboardInterrupt for clean shutdown.
    
    TODO
    ----
    Implement full transaction processing:
    1. Validate transactions with Pydantic models
    2. Call ML API for fraud predictions
    3. Store results in PostgreSQL database
    4. Produce failed transactions to error topic
    """
    # Configuration
    bootstrap_servers = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092')
    group_id = os.getenv('KAFKA_CONSUMER_GROUP', 'transaction-consumer-group')
    topic = os.getenv('KAFKA_TOPIC', 'transactions')
    
    logger.info(f"Consumer started - Server: {bootstrap_servers}, Group: {group_id}, Topic: {topic}")
    
    message_count = 0

    with get_kafka_consumer(bootstrap_servers, group_id, topic) as c:
        try:
            while True:
                msg = c.poll(1.0)

                if msg is None:
                    continue
                if msg.error():
                    logger.error(f"Consumer error: {msg.error()}")
                    continue

                message_count += 1
                transaction = json.loads(msg.value().decode('utf-8'))
                
                logger.debug(f"Received message #{message_count}: {transaction.get('id', 'unknown')}")
                
                # TODO: Process transaction
                # 1. Validate
                # 2. Call ML API
                # 3. Store in database
                
                if message_count % 100 == 0:
                    logger.info(f"Processed {message_count} messages")

        except KeyboardInterrupt:
            logger.info(f"Consumer stopped. Total messages: {message_count}")


if __name__ == "__main__":
    main()




