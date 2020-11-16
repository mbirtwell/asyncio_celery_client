import asyncio
import logging

from asyncio_celery_client import AsyncCeleryClient

from tasks import app, add

logging.basicConfig(level=logging.DEBUG)

client = AsyncCeleryClient(app)


async def main():
    logging.debug("Starting add")
    r = await client.queue_task(add, (4, 4), {})
    print("Queued task")
    v = await r.get()
    print(f"Got result {v}")


asyncio.run(main())
