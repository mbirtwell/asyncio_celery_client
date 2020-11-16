from celery import Celery

app = Celery(
    'myapp',
    broker='amqp://guest@rabbitmq//',
    # ## add result backend here if needed.
    backend='redis://redis'
)


@app.task
def add(x, y):
    return x + y
