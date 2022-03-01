import os

import dotenv

dotenv.load_dotenv()

DOMAIN = os.environ['DOMAIN']
BROKER_URL = os.environ['BROKER_URL']
BROKER_PORT = os.environ['BROKER_PORT']
USE_PREDEFINED_NETWORK = False
MQTT_USERNAME = os.environ['MQTT_USERNAME']
MQTT_PASSWORD = os.environ['MQTT_PASSWORD']
COMM_TIMEOUT = int(os.environ['COMM_TIMEOUT'])
# PING_TIMEOUT = int(os.environ['PING_TIMEOUT'])
PING_CALL_DELAY = int(os.environ['PING_CALL_DELAY'])
# AGENT_PING_DELAY = int(os.environ['AGENT_PING_DELAY_IN_SECONDS'])
EVENT_DELAY = int(os.environ['EVENT_DELAY_IN_SECONDS'])
LEARNING_RATE = float(os.environ['LEARNING_RATE'])
MAX_PING_ALLOWANCE = int(os.environ['MAX_PING_ALLOWANCE'])

