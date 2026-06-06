import asyncio
import json
import logging
from typing import Any
import redis.asyncio as redis
from redis.exceptions import RedisError

logger = logging.getLogger('hotelos.broker')


class Broker:
    def __init__(self, url: str = "redis://localhost"):
        self._url = url
        self._redis = redis.from_url(url)

    async def ping(self) -> bool:
        try:
            return await self._redis.ping()
        except Exception as exc:
            # Catch all connection-related errors and log them.
            # Returning False signals caller to fall back to InMemoryBroker.
            logger.warning('Redis ping failed: %s', exc)
            return False

    async def publish(self, channel: str, payload: Any):
        data = json.dumps(payload)
        try:
            await self._redis.publish(channel, data)
        except Exception as exc:
            logger.warning('Failed to publish to Redis (%s): %s', channel, exc)

    async def subscribe_to_channels(self, channels: list[str], queue: asyncio.Queue):
        backoff = 1
        while True:
            try:
                pubsub = self._redis.pubsub()
                await pubsub.subscribe(*channels)
                logger.info('Subscribed to Redis channels: %s', channels)

                async for message in pubsub.listen():
                    if message is None:
                        continue
                    if message.get("type") != "message":
                        continue
                    channel = message.get("channel")
                    data = message.get("data")
                    try:
                        payload = json.loads(data)
                    except Exception:
                        payload = data.decode() if isinstance(data, bytes) else data
                    await queue.put({"channel": channel, "payload": payload})
            except Exception as exc:
                logger.warning('Redis subscribe loop terminated: %s', exc)
                await self._safe_close_pubsub()
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30)
                logger.info('Reconnecting to Redis in %s seconds...', backoff)
                self._redis = redis.from_url(self._url)
                continue

    async def _safe_close_pubsub(self):
        try:
            await self._redis.close()
        except Exception:
            pass

    async def close(self):
        try:
            await self._redis.close()
        except Exception:
            pass


class InMemoryBroker:
    """A lightweight in-memory broker for tests and demos without Redis."""
    def __init__(self):
        self.queue = asyncio.Queue()

    async def publish(self, channel: str, payload: Any):
        await self.queue.put({"channel": channel, "payload": payload})

    async def subscribe_to_channels(self, channels: list[str], queue: asyncio.Queue):
        # forward messages from internal queue to provided queue
        while True:
            msg = await self.queue.get()
            await queue.put(msg)

    async def close(self):
        return


# module-level broker singleton with factory
_BROKER: "Broker | InMemoryBroker | None" = None

def get_broker(url: str | None = None):
    global _BROKER
    if _BROKER is None:
        if url == "memory":
            _BROKER = InMemoryBroker()
        else:
            _BROKER = Broker(url or "redis://localhost")
    return _BROKER


def set_broker_instance(inst):
    global _BROKER
    _BROKER = inst
