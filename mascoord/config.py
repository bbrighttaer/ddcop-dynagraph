import os

import dotenv

dotenv.load_dotenv()

USE_PREDEFINED_NETWORK = True

DOMAIN = os.environ['DOMAIN']
BROKER_URL = os.environ['BROKER_URL']
BROKER_PORT = os.environ['BROKER_PORT']
LEARNING_RATE = float(os.environ['LEARNING_RATE'])
COMM_EXEC_DELAY_IN_SECONDS = int(os.environ['COMM_EXEC_DELAY_IN_SECONDS'])
COMM_TIMEOUT_IN_SECONDS = int(os.environ['COMM_TIMEOUT_IN_SECONDS'])
PING_PROC_CALL_DELAY_IN_SECONDS = int(os.environ['PING_PROC_CALL_DELAY_IN_SECONDS'])
MAX_PING_COUNT = int(os.environ['MAX_PING_COUNT'])
PIKA_USERNAME = os.environ['PIKA_USERNAME']
PIKA_PASSWORD = os.environ['PIKA_PASSWORD']
