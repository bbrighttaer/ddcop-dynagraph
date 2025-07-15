import threading
from typing import Tuple

import pika
import networkx as nx

from mascoord.src import logger, messaging, config


class SimulationEnvironment(object):
    """
    Base class for all simulation environments used for D-DCOP
    """
    agents = {}
    log = None

    def __init__(self, name, time_step_delay, scenario):
        self._terminate = False
        self.log = logger.get_logger(name)
        self.name = name
        self.scenario = scenario
        self._events_iterator = iter(scenario) if scenario else None
        self._state_history = []
        self.time_step_delay = time_step_delay
        # self.agents = {}

        # graphs
        self._current_graph = nx.Graph()
        self._previous_graph = None

        # communication props
        self.queue_name = 'sim-env-queue'
        self.client = pika.BlockingConnection(pika.ConnectionParameters(
            host=config.BROKER_URL,
            port=config.BROKER_PORT,
            heartbeat=0,  # only for experiment purposes - not recommended (https://www.rabbitmq.com/heartbeats.html)
            credentials=pika.credentials.PlainCredentials(config.PIKA_USERNAME, config.PIKA_PASSWORD))
        )
        self.channel = self.client.channel()
        self.channel.exchange_declare(exchange=messaging.COMM_EXCHANGE, exchange_type='topic')
        self.channel.queue_declare(queue=self.queue_name, exclusive=True)

        # register topics (aka routing keys) associated to the factory queue
        self.channel.queue_bind(
            exchange=messaging.COMM_EXCHANGE,
            queue=self.queue_name,
            routing_key=f'{messaging.SIM_ENV_CHANNEL}.#'
        )

        # subscribe to in-coming msgs
        self.channel.basic_consume(queue=self.queue_name, on_message_callback=self._on_message, auto_ack=True)

    def _on_message(self, ch, method, properties, body):
        msg = eval(body.decode('utf-8'))
        print(msg, ch, method, properties, body)

    def _listen_for_messages(self):
        while not self._terminate:
            self.client.sleep(0)

    def step(self):
        ...

    def set_scenario(self, scenario):
        self._events_iterator = iter(scenario) if scenario else None

    def display(self):
        self.log.info(str(self))

    @property
    def history(self):
        return self._state_history

    def __str__(self):
        return str(self.history)

    def on_simulation_ended(self):
        ...

    def run_stabilization_computation(self, agent):
        ...

    def remove_agent(self, agent):
        ...

    def next_time_step(self):
        ...

    def get_time_step_data(self, agent_id):
        ...

    def get_agents_in_communication_range(self, agent_id):
        ...

    def send_constraint_evaluation_response(self, target, constraint_name, value):
        ...

    def calculate_global_score(self) -> Tuple[int, float]:
        """
        Calculates the global cost or utility of the DCOP problem at a particular snapshot of the simulation.
        Returns
        -------
        Returns a tuple: (number of constraints violated, cost/utility)
        """
        raise NotImplementedError('Global score logic is missing')

    def _receive_value_selection(self, msg):
        """
        Applies selected value in the environment.
        """
        ...

    def _record_simulation_metrics(self):
        val = self.calculate_global_score()


class TimeStep:
    """
    Models a single time step of a simulation
    """

    def __init__(self, step_i, state):
        self._i = step_i
        self._state = state

    def __str__(self):
        return f't-{self._i}, state: {self._state}'


