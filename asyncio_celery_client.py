from asyncio import Transport
from contextlib import asynccontextmanager
from typing import Optional, List
from urllib.parse import urlparse

import aioamqp
from aioamqp import AmqpProtocol
from aioamqp.channel import Channel
from aioamqp.protocol import OPEN
from aioredis import ConnectionsPool, Redis
from aioredis.util import parse_url
from celery import Celery, states
from celery.app.amqp import task_message
from celery.app.utils import Settings
from celery.backends.base import BaseKeyValueStoreBackend
from kombu import uuid, serialization


class AsyncResult:

    def __init__(self, client, task_id):
        self.client: AsyncCeleryClient = client
        self.task_id = task_id

    async def get(self):
        return await self.client.result_backend.wait_for_result(self.task_id)


class AmqpBackend:

    def __init__(self, conf):
        self.conf: Settings = conf
        self.transport: Optional[Transport] = None
        self.protocol: Optional[AmqpProtocol] = None
        self.channels: List[Channel] = []

    @asynccontextmanager
    async def get_channel(self):
        # TODO fix race to create connection
        # TODO be more persistent at creating the connection. Mimic
        #  what celery does perhaps.
        if self.protocol is None or self.protocol.state != OPEN:
            url = self.conf.broker_url
            parts = urlparse(url)
            self.channels = []
            # TODO more connection parameters, ssl, login details
            self.transport, self.protocol = await aioamqp.connect(
                host=parts.hostname,
                port=parts.port,
            )
        if self.channels:
            channel = self.channels.pop()
        else:
            channel = await self.protocol.channel()
        try:
            yield channel
        finally:
            self.channels.append(channel)


class RedisResultBackend:
    task_keyprefix = BaseKeyValueStoreBackend.task_keyprefix

    def __init__(self, celery):
        self.celery: Celery = celery
        address, options = parse_url(celery.conf.result_backend)
        self.redis_pool: Optional[ConnectionsPool] = ConnectionsPool(
            address,
            minsize=0,
            maxsize=10,
            **options
        )

    async def wait_for_result(self, task_id):
        key = (self.task_keyprefix + task_id).encode()
        # TODO share a single connection for all waiting results
        #  connections effectively get a task to process messages
        #  coming in. The built-in Connection then wants to put that
        #  on a queue. Do we then need another task processing those
        #  queues? The case of two concurrent waits on the same
        #  celery task is the tricky one. We can't just have the call
        #  to wait_for_result own that queue. Maybe the first call
        #  could own that queue and setup a future for any other calls
        #  to wait on.
        async with self.redis_pool.get() as conn:
            conn = Redis(conn)
            chan, = await conn.subscribe(key)
            try:
                while True:
                    encodedmeta = await Redis(self.redis_pool).get(key)
                    if not encodedmeta:
                        meta = {'status': states.PENDING, 'result': None}
                    else:
                        meta = self.celery.backend.decode_result(encodedmeta)
                    if meta['status'] in states.READY_STATES:
                        if meta['status'] in states.PROPAGATE_STATES:
                            raise meta['result']
                        return meta['result']
                    await chan.get()
            finally:
                await conn.unsubscribe(key)


class AsyncCeleryClient:

    def __init__(self, celery):
        self.celery: Celery = celery
        self.broker = AmqpBackend(celery.conf)
        self.result_backend = RedisResultBackend(celery)

    async def queue_task(self, task, args, kwargs):
        # TODO implement more options from apply_async. I need at least the
        #  queue option. I don't know what the other commonly used ones are.
        async with self.broker.get_channel() as channel:
            queue = self.celery.conf.task_default_queue
            # TODO who's responsible in celery for creating the queue
            #  I hoped that the consumer would create it so there'd
            #  never be any need to here. But I've seen errors that suggest
            #  other wise.
            await channel.queue_declare(queue, passive=True)
            task_id = uuid()
            message: task_message = self.celery.amqp.create_task_message(
                task_id, task.name, args, kwargs
            )
            content_type, content_encoding, body = serialization.dumps(
                message.body, 'json',
            )
            properties = {
                "content_type": content_type,
                "content_encoding": content_encoding,
                "headers": message.headers,
                **message.properties
            }
            body = body.encode(content_encoding)
            await channel.publish(
                body,
                '',
                queue,
                properties=properties
            )
            return AsyncResult(self, task_id)

    async def wait_task(self, task, args, kwargs):
        r = await self.queue_task(task, args, kwargs)
        return await r.get()
