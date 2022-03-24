import os

import dotenv

dotenv.load_dotenv()

DOMAIN = os.environ['DOMAIN']
BROKER_URL = os.environ['BROKER_URL']
BROKER_PORT = os.environ['BROKER_PORT']
LEARNING_RATE = float(os.environ['LEARNING_RATE'])
HANDLER_COMM_EXEC_DELAY_IN_SECONDS = int(os.environ['HANDLER_COMM_EXEC_DELAY_IN_SECONDS'])
AGENT_COMM_TIMEOUT_IN_SECONDS = int(os.environ['AGENT_COMM_TIMEOUT_IN_SECONDS'])
PING_PROC_CALL_DELAY_IN_SECONDS = int(os.environ['PING_PROC_CALL_DELAY_IN_SECONDS'])
MAX_PING_COUNT = int(os.environ['MAX_PING_COUNT'])
PIKA_USERNAME = os.environ['PIKA_USERNAME']
PIKA_PASSWORD = os.environ['PIKA_PASSWORD']
CONNECT_CALL_DELAY_COUNT = int(os.environ['CONNECT_CALL_DELAY_COUNT'])


class SharedConfig:

    def __init__(self):
        self.use_predefined_graph = False
        self.max_out_degree = float('inf')
        self.execution_mode = None


shared_config = SharedConfig()
