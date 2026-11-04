from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict, Set
import redis
import ujson as json
import logging
import time
import asyncio
from collections import defaultdict
from threading import Thread
import queue

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    Manages WebSocket connections and Redis pub/sub for real-time status updates.

    This class handles:
    - WebSocket connections for each job ID
    - Redis pub/sub subscription for status updates
    - Broadcasting messages to connected clients
    - Connection cleanup and resource management

    Attributes:
        active_connections (Dict[str, Set[WebSocket]]): Maps job IDs to sets of active WebSocket connections
        pubsub: Redis pub/sub connection
        message_queue (Queue): Thread-safe queue for message processing
        redis_thread (Thread): Background thread for Redis subscription
        should_stop (bool): Flag to control background thread termination
        redis_client (redis.Redis): Redis client instance
    """

    def __init__(self, redis_client: redis.Redis):
        """
        Initialize the connection manager.

        Args:
            redis_client (redis.Redis): Redis client for pub/sub functionality
        """
        self.active_connections: Dict[str, Set[WebSocket]] = defaultdict(set)
        self.pubsub = None
        self.message_queue = queue.Queue()
        self.redis_thread = None
        self.should_stop = False
        self.redis_client = redis_client

    async def connect(self, websocket: WebSocket, job_id: str):
        """
        Accept a new WebSocket connection for a job.

        Args:
            websocket (WebSocket): The WebSocket connection to accept
            job_id (str): ID of the job this connection is monitoring
        """
        await websocket.accept()
        self.active_connections[job_id].add(websocket)
        logger.info(
            f"New WebSocket connection for job {job_id}. Total connections: {len(self.active_connections[job_id])}"
        )

        # Start Redis listener if not already running
        if self.redis_thread is None:
            self.redis_thread = Thread(target=self._redis_listener)
            self.redis_thread.daemon = True
            self.redis_thread.start()
            # Start the async message processor
            asyncio.create_task(self._process_messages())

    def disconnect(self, websocket: WebSocket, job_id: str):
        """
        Remove a WebSocket connection for a job.

        Args:
            websocket (WebSocket): The WebSocket connection to remove
            job_id (str): ID of the job the connection was monitoring
        """
        if job_id in self.active_connections:
            self.active_connections[job_id].remove(websocket)
            if not self.active_connections[job_id]:
                del self.active_connections[job_id]
            logger.info(
                f"WebSocket disconnected for job {job_id}. Remaining connections: {len(self.active_connections[job_id]) if job_id in self.active_connections else 0}"
            )

    def _redis_listener(self):
        """
        Background thread that listens for Redis pub/sub messages.

        Subscribes to the status_updates:all channel and queues received messages
        for processing by the async message processor.
        """
        try:
            self.pubsub = self.redis_client.pubsub(ignore_subscribe_messages=True)
            self.pubsub.subscribe("status_updates:all")
            logger.info("Successfully subscribed to Redis status_updates:all channel")

            while not self.should_stop:
                message = self.pubsub.get_message()
                if message and message["type"] == "message" and "data" in message:
                    data = message["data"].decode("utf-8")
                    try:
                        job_update = json.loads(data)
                        logger.info(
                            f"Received message for job {job_update.get('job_id')}"
                        )
                    except json.JSONDecodeError:
                        logger.error("Invalid JSON in Redis message")
                    # Put message in queue for processing regardless of logging logic error
                    finally:
                        self.message_queue.put(data)
                time.sleep(0.01)  # Prevent tight loop

        except Exception as e:
            logger.error(f"Redis subscription error: {e}")
        finally:
            if self.pubsub:
                self.pubsub.unsubscribe()
                self.pubsub.close()

    async def _process_messages(self):
        """
        Async task that processes queued messages and broadcasts them to clients.

        Continuously checks the message queue and broadcasts valid messages
        to all connected WebSocket clients for the relevant job ID.
        """
        while True:
            try:
                # Check queue in a non-blocking way
                while not self.message_queue.empty():
                    message: str = self.message_queue.get_nowait()
                    try:
                        update = json.loads(message)
                        job_id = update.get("job_id")
                        logger.info(f"Processing message for job {job_id}")

                        if job_id and job_id in self.active_connections:
                            logger.info(
                                f"Broadcasting update for job {job_id} to {len(self.active_connections[job_id])} connections"
                            )
                            await self.broadcast_to_job(
                                job_id,
                                {
                                    "service": update.get("service"),
                                    "status": update.get("status"),
                                    "message": update.get("message", ""),
                                },
                            )
                            logger.info(
                                f"Broadcasted update for job {job_id}: {update.get('service')} - {update.get('status')}"
                            )
                    except json.JSONDecodeError:
                        logger.error(f"Invalid JSON in Redis message: {message}")
                    except Exception as e:
                        logger.error(f"Error processing Redis message: {e}")

                # Small delay before next check
                await asyncio.sleep(0.01)

            except Exception as e:
                logger.error(f"Message processing error: {e}")
                await asyncio.sleep(1)

    async def broadcast_to_job(self, job_id: str, message: dict):
        """
        Send a message to all WebSocket connections for a specific job.

        Args:
            job_id (str): ID of the job to broadcast to
            message (dict): Message to broadcast to all connections
        """
        if job_id in self.active_connections:
            disconnected = set()
            for connection in self.active_connections[job_id]:
                try:
                    await connection.send_json(message)
                except WebSocketDisconnect:
                    disconnected.add(connection)
                except Exception as e:
                    logger.error(f"Error sending message to WebSocket: {e}")
                    disconnected.add(connection)

            # Clean up disconnected clients
            for connection in disconnected:
                self.disconnect(connection, job_id)

    def cleanup(self):
        """
        Clean up resources used by the connection manager.

        Stops the Redis listener thread and closes the pub/sub connection.
        """
        self.should_stop = True
        if self.redis_thread:
            self.redis_thread.join(timeout=1.0)
        if self.pubsub:
            self.pubsub.close()
