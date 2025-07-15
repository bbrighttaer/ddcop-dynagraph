import datetime
import functools
import json
import math
import queue
import random
import time
from collections import defaultdict
from traceback import print_exception

import pika

import config
import logger
import mascoord.src.algorithms.graphs
import mascoord.src.algorithms.graphs.digca
import messaging
from mascoord.src.algorithms.graphs import DDFS, DIGCA, DBFS
from mascoord.src.equations import Quadratic
from mascoord.src.utils import time_diff, notify_wrap


def parse_amqp_body(body):
    return eval(body.decode('utf-8').replace('true', 'True').replace('false', 'False').replace('null', 'None'))


def create_on_message(log, agent_id, message_queue, handle_message, agent_snapshot):
    def on_message(ch, method, properties, body):
        message = parse_amqp_body(body)

        # avoid own messages (no local is not supported ATM, see https://www.rabbitmq.com/specification.html)
        if 'agent_id' in message['payload'] and message['payload']['agent_id'] == agent_id:
            return

        # message_queue.put(payload)

        # log.debug(f'from agent.on_message: received {message}')

        # run agent ops on payload
        # try:
        handle_message(message)
        # except Exception as e:
        #     log.info(f'Agent snapshot: {agent_snapshot()}\nPayload: {message}')
        #     log.exception(e)

    return on_message


def send_report_callback(channel, agent_snapshot):
    channel.basic_publish(exchange=messaging.COMM_EXCHANGE,
                          routing_key=f'{messaging.MONITORING_CHANNEL}',
                          body=messaging.create_agent_report(agent_snapshot()))


def change_constraint_callback(dyna_graph, coefficients, neighbor_id):
    dyna_graph.change_constraint(coefficients, neighbor_id)


class Agent:

    def __init__(self, agent_id, dcop_algorithm, *args, **kwargs):
        self.message_queue = queue.Queue()

        # agent props
        self.agent_id = agent_id
        self.log = logger.get_logger(agent_id, prefix='Agent')
        self.terminate = False
        self.active_constraints = {}
        self.coefficients_dict = kwargs['coefficients_dict'] if 'coefficients_dict' in kwargs else {}
        self.metrics = kwargs['metrics']
        self.shared_config = kwargs['shared_config']

        self.initialize_announce_call_exp_decay()

        self.is_client_asleep = False

        self.start_time = time.time()
        self.accum_time = 0
        self.agent_metrics = AgentMetrics(self.agent_id, self.log)
        self.latest_event_timestamp = None
        self.timestep = -1

        self.agents_in_comm_range = None
        self.new_agents = set()

        self.client = pika.BlockingConnection(
            pika.ConnectionParameters(
                host=config.BROKER_URL,
                port=config.BROKER_PORT,
                heartbeat=0,  # only for experiment purposes - see (https://www.rabbitmq.com/heartbeats.html)
                credentials=pika.credentials.PlainCredentials(config.PIKA_USERNAME, config.PIKA_PASSWORD)
            ))
        self.channel = self.client.channel()
        # self.client.add_callback_threadsafe(callback=self.start)
        self.queue = f'queue-{self.agent_id}'
        self.channel.queue_declare(self.queue, exclusive=False)

        self.channel.queue_bind(exchange=messaging.COMM_EXCHANGE,
                                queue=self.queue,
                                routing_key=f'{messaging.AGENTS_CHANNEL}.{self.agent_id}.#')
        self.channel.queue_bind(exchange=messaging.COMM_EXCHANGE,
                                queue=self.queue,
                                routing_key=f'{messaging.AGENTS_CHANNEL}.public.#')
        # self.channel.queue_bind(exchange=messaging.COMM_EXCHANGE,
        #                         queue=self.queue,
        #                         routing_key=f'{messaging.FACTORY_COMMAND_CHANNEL}.#')

        self.channel.basic_consume(queue=self.queue,
                                   on_message_callback=create_on_message(self.log,
                                                                         self.agent_id,
                                                                         self.message_queue,
                                                                         self.handle_message,
                                                                         self.agent_snapshot),
                                   auto_ack=True)

        # Overwrite basic publish of channel to gather communication metrics
        self.channel.basic_publish = notify_wrap(
            self.channel.basic_publish,
            self.agent_metrics.on_message_published,
        )

        # algorithms
        self.graph = {
            'ddfs': DDFS,
            'dbfs': DBFS,
        }.get(kwargs['graph_algorithm'], DIGCA)(self)
        self.dcop = dcop_algorithm(self, num_discrete_points=kwargs['domain_size'])

        self.report_shutdown = False

    def initialize_announce_call_exp_decay(self):
        # control announce calls with exponential decay
        self.initial_rate = .4
        self.num_connect_calls = 0
        self.decay_rate = 0.1

    @property
    def graph_traversing_order(self):
        return self.dcop.traversing_order

    @property
    def cpa(self):
        return self.dcop.cpa

    @property
    def state(self):
        return self.dcop.state

    @property
    def value(self):
        return self.dcop.value

    @property
    def cost(self):
        return self.dcop.cost

    def clear_cost(self):
        self.dcop.cost = 0

    @property
    def parent(self):
        return self.graph.parent

    @property
    def children(self):
        return self.graph.children

    @property
    def domain(self):
        return self.dcop.domain

    @property
    def connection_extra_args(self):
        return self.dcop.connection_extra_args()

    @property
    def has_neighbor(self):
        return bool(self.graph.neighbors)

    def agent_disconnection_callback(self, agent_id):
        self.dcop.agent_disconnection_callback(agent=agent_id)

    def connection_extra_args_callback(self, sender, args):
        self.dcop.receive_extra_args(sender, args)

    def get_constraint(self, sender_id, coefficients: list = None):
        if not coefficients:
            coefficients = self.coefficients_dict.get(f'{self.agent_id},{sender_id}',
                                                      [round(random.uniform(-5, 5), 3) for _ in range(3)])
        constraint = Quadratic(*coefficients)
        return constraint

    def execute_dcop(self):
        self.dcop.execute_dcop()

    def increment_messages_count(self):
        self.messages_count += 1

    def clear_messages_count(self):
        self.messages_count = 0

    def shutdown(self):
        self.terminate = True
        self.report_shutdown = True
        # self.metrics.update_metrics()

    def send_report(self):
        try:
            self.client.add_callback_threadsafe(functools.partial(
                send_report_callback,
                self.channel,
                self.agent_snapshot
            ))
        except Exception as e:
            self.log.info(f'Agent state report failed, retry: {str(e)}')

    def report_metrics(self):
        self.channel.basic_publish(
            exchange=messaging.COMM_EXCHANGE,
            routing_key=f'{messaging.METRICS_CHANNEL}',
            body=messaging.create_metrics_report({
                'agent_id': self.agent_id,
                'cost': float(self.cost),
                'num_messages': self.messages_count,
            }))

    def _start_time(self):
        self.start_time = time.time()

    def _time_lapse(self):
        self.accum_time = time_diff(self.start_time)

    def agent_snapshot(self):
        snapshot = {
            'agent_id': self.agent_id,
            'domain': self.domain,
            'constraints': {k: str(v) for k, v in self.active_constraints.items()},
            'cpa': self.cpa,
            'state': self.state,
            'cost': self.cost,
            'parent': self.parent,
            # 'pinged_list': self.graph.pinged_list_dict,
            'value': self.dcop.value,
        }
        if self.dcop.name == 'c-cocoa':
            snapshot.update({
                'neighbor_states': self.dcop.neighbor_states,
                'cost_map': self.dcop.cost_map,
            })
        elif self.dcop.name == 'sdpop':
            snapshot.update({
                'neighbor_domains': self.dcop.neighbor_domains,
                'util_messages': self.dcop.util_messages,
            })
        return snapshot

    def get_child_connections_history(self):
        cons = []
        for child in self.graph.children_history:
            eqn = self.graph.children_history[child]
            coefficients = [str(v) for v in eqn.coefficients.values()]
            c_str = ','.join(coefficients)
            cons.append(f'({self.agent_id},{child}):({c_str})')
        return cons

    def get_child_edges_history(self):
        parent_child_edges = []
        for child in self.graph.children_history:
            parent_child_edges.append(f'{self.agent_id},{child}')
        return parent_child_edges

    def change_constraint(self, coefficients, neighbor_id):
        try:
            self.client.add_callback_threadsafe(functools.partial(
                change_constraint_callback,
                self.graph,
                coefficients,
                neighbor_id
            ))
        except Exception as e:
            self.log.info(f'Agent state report failed, retry: {str(e)}')

    def select_random_neighbor(self):
        keys = list(self.active_constraints.keys())
        selected = keys[random.randrange(len(keys))]
        neighbor_id = selected.split(',')[1]
        return neighbor_id

    def set_edge_costs(self):
        self.dcop.set_edge_costs()

    def handle_message(self, message):
        # reject outdated messages (every message has a timestamp)
        if self.latest_event_timestamp and message['timestamp'] < self.latest_event_timestamp:
            return

        match message['type']:
            case messaging.ANNOUNCE:
                self.client.call_later(0, functools.partial(self.graph.receive_announce, message))

            case messaging.ANNOUNCE_RESPONSE:
                self.graph.receive_announce_response(message)

            case messaging.ANNOUNCE_RESPONSE_IGNORED:
                self.graph.receive_announce_response_ignored(message)

            case messaging.ADD_ME:
                self.graph.receive_add_me(message)

            case messaging.CHILD_ADDED:
                self.graph.receive_child_added(message)

            case messaging.PARENT_ASSIGNED:
                self.graph.receive_parent_assigned(message)

            case messaging.ALREADY_ACTIVE:
                self.graph.receive_already_active(message)

            case messaging.PING:
                self.graph.receive_ping_message(message)

            case messaging.PING_RESPONSE:
                self.graph.receive_ping_response_message(message)

            case messaging.CONSTRAINT_CHANGED:
                self.graph.receive_constraint_changed_message(message)

            # C-CoCoA message handling
            case messaging.UPDATE_STATE_MESSAGE:
                self.dcop.receive_update_state_message(message)

            case messaging.INQUIRY_MESSAGE:
                self.dcop.receive_inquiry_message(message)

            case messaging.COST_MESSAGE:
                self.dcop.receive_cost_message(message)

            case messaging.EXECUTION_REQUEST:
                self.dcop.receive_execution_request_message(message)

            # SDPOP/C-SDPOP message handling
            case messaging.VALUE_MESSAGE:
                self.dcop.receive_value_message(message)

            case messaging.UTIL_MESSAGE:
                self.dcop.receive_util_message(message)

            case messaging.REQUEST_UTIL_MESSAGE:
                self.dcop.receive_util_message_request(message)

            case messaging.SIM_ENV_CURRENT_TIME_STEP_MSG:
                self._receive_time_step_message(message)

            case messaging.STOP_AGENT:
                self.terminate = True

            case messaging.PARENT_AVAILABLE:
                self.graph.receive_parent_available_message(message)

            case messaging.PARENT_ALREADY_ASSIGNED:
                self.graph.receive_parent_already_assigned(message)

            case messaging.DDFS_NEIGHBOR_DATA:
                self.graph.receive_neighbor_data(message)

            case messaging.DDFS_VALUE_MSG:
                self.graph.receive_value_message(message)

            case messaging.DDFS_POSITION_MSG:
                self.graph.receive_position_msg(message)

            case messaging.DDFS_CHILD_MSG:
                self.graph.receive_child_msg(message)

            case messaging.DDFS_PSEUDO_CHILD_MSG:
                self.graph.receive_pseudo_child_msg(message)

            case messaging.DBFS_LEVEL_MESSAGE:
                self.graph.receive_dbfs_level_message(message)

            case messaging.DBFS_ACK_MESSAGE:
                self.graph.receive_dbfs_ack_message(message)

            case messaging.DBFS_LEVEL_IGNORED_MESSAGE:
                self.graph.receive_dbfs_level_ignored_message(message)

            case _:
                self.log.info(f'Could not handle received payload: {message}')

    def _receive_time_step_message(self, message):
        self.latest_event_timestamp = message['payload']['event_timestamp']
        self.log.info(f'Received time step message: {message}')
        self.timestep = message['payload']['timestep']
        self.dcop.domain = message['payload']['agent_domain']
        self.dcop.neighbor_domains = message['payload']['neighbor_domains']
        self.agents_in_comm_range = message['payload']['agents_in_comm_range']
        self.new_agents = set(self.agents_in_comm_range) - set(self.graph.neighbors)

        # remove agents that are out-of-range
        agents_to_remove = set(self.graph.neighbors) - set(self.agents_in_comm_range)
        if agents_to_remove:
            for _agent in agents_to_remove:
                self.graph.remove_agent(_agent)

        self.log.info(f'parent={self.parent}, children={self.children}, agents-in-range={self.agents_in_comm_range}')

        self.dcop.on_time_step_changed()
        self.graph.on_time_step_changed()

        # if no neighborhood change
        if not self.graph.has_potential_neighbor():
            self.graph.start_dcop()

    def select_random_value(self):
        self.dcop.select_random_value()

    def __call__(self, *args, **kwargs):
        self.log.info('Initializing...')
        # self.metrics.update_metrics()

        # register with graph-ui and sim env
        self.register_agent()

        last_ping_call_time = None

        while not self.terminate:
            self.listen_to_network()

            self.graph.connect()

            self.dcop.resolve_value()

            # check if neighbors should be pinged
            # if not last_ping_call_time or datetime.datetime.now() > last_ping_call_time \
            #         + datetime.timedelta(seconds=config.PING_PROC_CALL_DELAY_IN_SECONDS):
            #     self.graph.ping_neighbors()
            #     self.listen_to_network()
            #
            #     last_ping_call_time = datetime.datetime.now()

        self.log.info('Shutting down...')

        self.release_resources()

    def listen_to_network(self):
        self._time_lapse()
        # self.log.info('listening...')
        self.client.sleep(.1)
        self._start_time()

    def release_resources(self):
        if self.report_shutdown:
            # inform dashboard
            self.channel.basic_publish(
                exchange=messaging.COMM_EXCHANGE,
                routing_key=f'{messaging.MONITORING_CHANNEL}',
                body=messaging.create_agent_shutdown_message({
                    'agent_id': self.agent_id,
                })
            )
        # remove rabbitmq resources
        self.channel.queue_unbind(
            exchange=messaging.COMM_EXCHANGE,
            queue=self.queue,
            routing_key=f'{messaging.AGENTS_CHANNEL}.{self.agent_id}.#'
        )
        self.channel.queue_unbind(
            exchange=messaging.COMM_EXCHANGE,
            queue=self.queue,
            routing_key=f'{messaging.AGENTS_CHANNEL}.public.#'
        )
        # self.channel.queue_unbind(
        #     exchange=messaging.COMM_EXCHANGE,
        #     queue=self.queue,
        #     routing_key=f'{messaging.FACTORY_COMMAND_CHANNEL}.#'
        # )
        self.channel.queue_delete(self.queue)
        self.channel.close()
        self.client.close()
        self.log.info('Channel closed')

    def register_agent(self):
        # register with dashboard
        agent_reg_info = {
                'agent_id': self.agent_id,
            }
        self.channel.basic_publish(
            exchange=messaging.COMM_EXCHANGE,
            routing_key=f'{messaging.MONITORING_CHANNEL}',
            body=messaging.create_agent_registration_dashboard_message(agent_reg_info),
        )

        # register with sim environment
        self.channel.basic_publish(
            exchange=messaging.COMM_EXCHANGE,
            routing_key=f'{messaging.SIM_ENV_CHANNEL}',
            body=messaging.create_agent_registration_message(agent_reg_info),
        )

    def connect_exp_decay(self):
        rate = self.initial_rate * math.exp(-self.decay_rate * self.num_connect_calls)
        return rate

    def __str__(self) -> str:
        return self.agent_id


class AgentMetrics:

    def __init__(self, agent_id, log):
        self.agent_id = agent_id
        self.log = log
        self.messages_count = 0
        self._msg_type_count = defaultdict(int)

    def on_message_published(self, *args, **kwargs):
        # extract message
        if len(args) >= 3:
            message = args[2]
        else:
            message = kwargs['body']
        message = json.loads(message)

        ignored_messages = [
            messaging.AGENT_REGISTRATION_DASHBOARD,
            messaging.AGENT_REPORT,
            messaging.AGENT_CONNECTION_MSG,
            messaging.AGENT_DISCONNECTION,
            messaging.ADD_GRAPH_EDGE,
            messaging.REMOVE_GRAPH_EDGE,
            messaging.AGENT_STATE_CHANGED,
            messaging.VALUE_SELECTED_MSG,
        ]

        if message['type'] in ignored_messages:
            return

        # update total messages published
        self.messages_count += 1

        # shortcut to keep track of each message type's count
        self._msg_type_count[message['type']] += 1

    def get_metrics(self):
        metrics = {
            'messages_count': self.messages_count,
        }
        metrics.update(self._msg_type_count)
        return metrics

