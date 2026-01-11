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
    
    Args:
        bootstrap_servers: Kafka bootstrap servers
        group_id: Consumer group ID
        topic: Topic to subscribe to
        
    Yields:
        Consumer instance
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




