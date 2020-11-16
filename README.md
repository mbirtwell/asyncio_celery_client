Asyncio Celery client
=====================

A client for celery to allow you to submit tasks and get task results from an 
asyncio context. No support for implementing tasks using asyncio.

Still a bit unfinished. 

Has basic support for submitting tasks to the default queue and getting the 
result using AMQP and Redis. 

Reads the configuration from your Celery app and provides alternative asyncio
function for queuing tasks etc. e.g.:

```
import asyncio

from asyncio_celery_client import AsyncCeleryClient

from tasks import app, add

client = AsyncCeleryClient(app)


async def main():
    r = await client.queue_task(add, (4, 4), {})
    v = await r.get()
    print(f"Got result {v}")


asyncio.run(main()
```