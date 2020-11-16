FROM python:3

WORKDIR /usr/src/app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY example/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY example .
COPY asyncio_celery_client.py .

CMD [ "celery", "-A", "tasks", "worker", "--loglevel", "INFO" ]