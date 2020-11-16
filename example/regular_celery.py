
import logging
from tasks import add

logging.basicConfig(level=logging.DEBUG)
logging.debug("Starting add")
r = add.delay(4, 4)
v = r.get()
if v == 8:
    print("regular_celery.py SUCCESS")
else:
    print("regular_celery.py WTF")
