import datetime
import functools
import json
import random
from traceback import print_exception

import pandas as pd
import pika

import config
import equations
import logger
import messaging
from algorithms import graph


def parse_amqp_body(body):
    return eval(body.decode('utf-8').replace('true', 'True').replace('false', 'False').replace('null', 'None'))


def create_on_message(log, agent_id, handle_message, agent_snapshot):
    def on_message(ch, method, properties, body):
        payload = parse_amqp_body(body)

        # avoid own messages (no local is not supported ATM, see https://www.rabbitmq.com/specification.html)
        if 'agent_id' in payload['payload'] and payload['payload']['agent_id'] == agent_id:
            return

        log.debug(f'from agent.on_message: received {payload}')

        # run agent ops on payload
        try:
            handle_message(payload)
        except Exception as e:
            log.info(f'Agent snapshot: {agent_snapshot()}\nPayload: {payload}')
            print_exception(e)

    return on_message


def send_report_callback(channel, agent_snapshot):
    channel.basic_publish(exchange=messaging.COMM_EXCHANGE,
                          routing_key=f'{messaging.MONITORING_CHANNEL}',
                          body=messaging.create_agent_report(agent_snapshot()))


def change_constraint_callback(dyna_graph, coefficients, neighbor_id):
    dyna_graph.change_constraint(coefficients, neighbor_id)


class Agent:
    class State:
        ANNOUNCING = 'announcing'
        BROADCASTING = 'broadcasting'
        IDLE = 'idle'

        # agent states and their corresponding mutually exclusive in-coming message types
        mutually_exclusive = {
            IDLE: [],
            ANNOUNCING: [messaging.ANNOUNCE_MSG],
            BROADCASTING: [messaging.BROADCAST_MSG]
        }

    def __init__(self, agent_id, dcop_algorithm, *args, **kwargs):
        # agent props
        self.agent_id = agent_id
        self.log = logger.get_logger(agent_id, prefix='Agent')
        self.terminate = False
        self.active_constraints = {}
        self.coefficients_dict = kwargs['coefficients_dict'] if 'coefficients_dict' in kwargs else {}
        self.metrics_dict = kwargs['metrics_dict']
        self.metrics_registry = kwargs['metrics_registry']

        self.is_client_asleep = False

        self.messages_count = 0

        self.client = pika.BlockingConnection(pika.ConnectionParameters(host=config.BROKER_URL,
                                                                        port=config.BROKER_PORT))
        self.channel = self.client.channel()
        # self.client.add_callback_threadsafe(callback=self.start)
        self.queue = f'queue-{self.agent_id}'
        self.channel.queue_declare(self.queue, exclusive=True)

        self.channel.queue_bind(exchange=messaging.COMM_EXCHANGE,
                                queue=self.queue,
                                routing_key=f'{messaging.AGENTS_CHANNEL}.{self.agent_id}.#')
        self.channel.queue_bind(exchange=messaging.COMM_EXCHANGE,
                                queue=self.queue,
                                routing_key=f'{messaging.AGENTS_CHANNEL}.public.#')
        self.channel.queue_bind(exchange=messaging.COMM_EXCHANGE,
                                queue=self.queue,
                                routing_key=f'{messaging.FACTORY_COMMAND_CHANNEL}.#')

        self.channel.basic_consume(queue=self.queue,
                                   on_message_callback=create_on_message(self.log,
                                                                         self.agent_id,
                                                                         self.handle_message,
                                                                         self.agent_snapshot),
                                   auto_ack=True)

        # algorithms
        self.graph = graph.DynaGraph(self)
        self.dcop = dcop_algorithm(self)

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
        self.dcop.cost = None

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
            coefficients = self.coefficients_dict.get(f'{self.agent_id},{sender_id}', [1, 1, 1])
        equation_class = equations.equations_directory['linear']
        constraint = equation_class(*coefficients)
        return constraint

    def execute_dcop(self):
        self.dcop.execute_dcop()

    def increment_messages_count(self):
        self.messages_count += 1

    def clear_messages_count(self):
        self.messages_count = 0

    def shutdown(self):
        self.terminate = True

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
        self.channel.basic_publish(exchange=messaging.COMM_EXCHANGE,
                                   routing_key=f'{messaging.METRICS_CHANNEL}',
                                   body=messaging.create_metrics_report({
                                       'agent_id': self.agent_id,
                                       'cost': float(self.cost),
                                       'num_messages': self.messages_count,
                                   }))

    def dcop_done(self):
        self.metrics_dict[self.agent_id] = {
            'cost': float(self.cost),
            'num_messages': self.messages_count,
        }
        self.log.info('DCOP done')
        self.clear_messages_count()
        self.clear_cost()

    def agent_snapshot(self):
        snapshot = {
            'agent_id': self.agent_id,
            'domain': self.domain,
            'network': self.graph.network,
            'constraints': {k: str(v) for k, v in self.active_constraints.items()},
            'cpa': self.cpa,
            'state': self.state,
            'cost': self.cost,
            'parent': self.parent,
            'pinged_list': self.graph.pinged_list_dict,
            'responses': list(self.graph.responses),
            'value': self.dcop.value,
            'busy': self.graph.busy,
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
            eqn = self.get_constraint(child)
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

    def handle_message(self, payload):
        message_type = payload['type']

        # connection message handling
        if message_type == messaging.ANNOUNCE_MSG:
            self.graph.receive_announce_message(payload)
            self.increment_messages_count()

        elif message_type == messaging.ANNOUNCE_RESPONSE_MSG:
            self.graph.receive_announce_response_message(payload)
            self.increment_messages_count()

        elif message_type == messaging.ANNOUNCE_RESPONSE_MSG_ACK:
            self.graph.receive_announce_response_message_ack(payload)
            self.increment_messages_count()

        elif message_type == messaging.SET_NETWORK:
            self.graph.receive_set_network_message(payload)
            self.increment_messages_count()

        elif message_type == messaging.PING_MESSAGE:
            self.graph.receive_ping_message(payload)
            self.increment_messages_count()

        elif message_type == messaging.PING_RESPONSE_MESSAGE:
            self.graph.receive_ping_response_message(payload)
            self.increment_messages_count()

        elif message_type == messaging.NETWORK_UPDATE_COMPLETION:
            self.graph.receive_network_update_completion_message(payload)
            self.increment_messages_count()

        elif message_type == messaging.CONSTRAINT_CHANGED:
            self.graph.receive_constraint_changed_message(payload)
            self.increment_messages_count()

        # C-CoCoA message handling
        elif message_type == messaging.UPDATE_STATE_MESSAGE:
            self.dcop.receive_update_state_message(payload)
            self.increment_messages_count()

        elif message_type == messaging.INQUIRY_MESSAGE:
            self.dcop.receive_inquiry_message(payload)
            self.increment_messages_count()

        elif message_type == messaging.COST_MESSAGE:
            self.dcop.receive_cost_message(payload)
            self.increment_messages_count()

        # SDPOP message handling
        elif message_type == messaging.VALUE_MESSAGE:
            self.dcop.receive_value_message(payload)
            self.increment_messages_count()
        elif message_type == messaging.UTIL_MESSAGE:
            self.dcop.receive_util_message(payload)
            self.increment_messages_count()
        elif message_type == messaging.REQUEST_UTIL_MESSAGE:
            self.dcop.receive_util_message_request(payload)
            self.increment_messages_count()

        # elif message_type == messaging.AGENT_RESET:
        #     self.dcop.reset(payload=payload)

        # elif message_type == messaging.NEIGHBOR_STATE_REQUEST:
        #     self.dcop.receive_state_request(payload)
        #
        # elif message_type == messaging.NEIGHBOR_STATE_REQUEST_RESPONSE:
        #     self.dcop.receive_state_request_response(payload)

    def __call__(self, *args, **kwargs):
        self.log.info('Initializing...')

        self.register_agent()

        last_ping_call_time = None

        while not self.terminate:
            self.graph.connect()

            # process network events
            self.client.sleep(config.COMM_TIMEOUT_IN_SECONDS)

            self.dcop.resolve_value()

            # check if neighbors should be pinged
            if not last_ping_call_time or datetime.datetime.now() > last_ping_call_time \
                    + datetime.timedelta(seconds=config.PING_PROC_CALL_DELAY_IN_SECONDS):
                self.graph.ping_neighbors()

                # process network (ping) events
                self.client.sleep(config.COMM_TIMEOUT_IN_SECONDS)

                last_ping_call_time = datetime.datetime.now()

        self.log.info('Shutting down...')

        self.release_resources()

    def release_resources(self):
        # inform dashboard
        self.channel.basic_publish(exchange=messaging.COMM_EXCHANGE,
                                   routing_key=f'{messaging.MONITORING_CHANNEL}',
                                   body=messaging.create_agent_shutdown_message({
                                       'agent_id': self.agent_id,
                                       'network': self.graph.network,
                                   }))
        # remove rabbitmq resources
        self.channel.queue_unbind(exchange=messaging.COMM_EXCHANGE,
                                  queue=self.queue,
                                  routing_key=f'{messaging.AGENTS_CHANNEL}.{self.agent_id}.#')
        self.channel.queue_unbind(exchange=messaging.COMM_EXCHANGE,
                                  queue=self.queue,
                                  routing_key=f'{messaging.AGENTS_CHANNEL}.public.#')
        self.channel.queue_unbind(exchange=messaging.COMM_EXCHANGE,
                                  queue=self.queue,
                                  routing_key=f'{messaging.FACTORY_COMMAND_CHANNEL}.#')
        self.channel.queue_delete(self.queue)

    def register_agent(self):
        # register with dashboard
        self.channel.basic_publish(
            exchange=messaging.COMM_EXCHANGE,
            routing_key=f'{messaging.MONITORING_CHANNEL}',
            body=bytes(
                json.dumps({
                    'type': messaging.AGENT_REGISTRATION,
                    'payload': {
                        'agent_id': self.agent_id,
                    },
                    'timestamp': datetime.datetime.now().timestamp(),
                }),
                'utf-8'
            )
        )

    def __str__(self) -> str:
        return self.agent_id


def create_metrics_on_message(metrics):
    def on_message(ch, method, properties, body):
        body = parse_amqp_body(body)
        metrics.log.info(body)
        metrics.record_agent_stats(body['payload'])

    return on_message


class MetricsAgent:
    log = logger.get_logger('metrics-agent')

    def __init__(self):
        self.agent_id = 'metrics-agent'
        self.terminate = False

        self.cost_per_agent = {}
        self.num_msgs_per_agent = {}

        self.costs_per_event = {}
        self.num_mgs_per_event = {}

        self.client = pika.BlockingConnection(pika.ConnectionParameters(host=config.BROKER_URL,
                                                                        port=config.BROKER_PORT))
        self.channel = self.client.channel()
        self.queue = 'metrics-queue'
        self.channel.queue_declare(self.queue, exclusive=True)
        self.channel.queue_bind(exchange=messaging.COMM_EXCHANGE,
                                queue=self.queue,
                                routing_key=f'{messaging.METRICS_CHANNEL}.#')
        self.channel.basic_consume(queue=self.queue,
                                   on_message_callback=create_metrics_on_message(self),
                                   auto_ack=True)

    def record_agent_stats(self, payload):
        agent = payload['agent_id']
        self.cost_per_agent[agent] = payload['cost']
        self.num_msgs_per_agent[agent] = payload['num_messages']

    def set_event(self, event):
        self.log.info(event)
        self.record_metrics(event)
        self.cost_per_agent.clear()
        self.num_msgs_per_agent.clear()

    def __call__(self, *args, **kwargs):
        log = MetricsAgent.log
        log.info('Metrics collection started')

        while not self.terminate:
            self.client.sleep(config.COMM_TIMEOUT_IN_SECONDS)

        log.info('Metrics collection stopped')
        self.release_resources()

    def release_resources(self):
        self.channel.queue_unbind(exchange=messaging.COMM_EXCHANGE,
                                  queue=self.queue,
                                  routing_key=f'{messaging.METRICS_CHANNEL}.#')

    def record_metrics(self, event):
        messages_count = 0
        total_cost = 0
        for cost, num_msgs in zip(self.cost_per_agent.values(), self.num_msgs_per_agent.values()):
            total_cost += cost
            messages_count += num_msgs
        self.costs_per_event[event] = total_cost
        self.num_mgs_per_event[event] = messages_count

    def to_csv(self, path):
        df = pd.DataFrame({
            'event': list(self.costs_per_event.keys()),
            'type': [evt.split(':')[0] for evt in self.costs_per_event.keys()],
            'cost': list(self.costs_per_event.values()),
            'message_count': list(self.num_mgs_per_event.values()),
        })
        df.to_csv(path, index=False)
