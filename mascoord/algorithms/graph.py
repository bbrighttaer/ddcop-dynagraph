import collections
import random
import string

from mascoord import config
from mascoord import messaging
from mascoord import utils
from mascoord.config import MAX_PING_ALLOWANCE


class DynaGraph:
    """
    Implementation of the Dynamic Interaction Graph Construction algorithm
    """

    def __init__(self, agent):
        self.agent = agent
        self.channel = self.agent.channel
        self.parent = None
        self.children = []
        self.children_history = []
        self.log = self.agent.log
        self.client = agent.client
        self.responses = collections.deque()
        self.network = ''.join([random.choice(string.ascii_lowercase) for _ in range(5)])
        self.pinged_list_dict = {}
        self.busy = False

    def has_no_neighbors(self):
        return not self.parent and not self.children

    def is_neighbor(self, agent_id):
        return self.parent == agent_id or agent_id in self.children

    def is_child(self, agent_id):
        return agent_id in self.children

    def is_parent(self, agent_id):
        return self.parent == agent_id

    @property
    def neighbors(self):
        neighbors = []
        if self.children:
            neighbors.extend(self.children)
        if self.parent:
            neighbors.append(self.parent)
        return neighbors

    def on_network_changed(self):
        for child in self.children:
            self.channel.basic_publish(exchange=messaging.COMM_EXCHANGE,
                                       routing_key=f'{messaging.AGENTS_CHANNEL}.{child}',
                                       body=messaging.create_set_network_message({
                                           'agent_id': self.agent.agent_id,
                                           'network': self.network,
                                       }))
        self.channel.basic_publish(exchange=messaging.COMM_EXCHANGE,
                                   routing_key=f'{messaging.MONITORING_CHANNEL}',
                                   body=messaging.create_set_network_message({
                                       'agent_id': self.agent.agent_id,
                                       'network': self.network,
                                   }))

    def remove_inactive_connections(self):
        """remove agents that are still in the pinged list"""
        disconnected = False

        temp_list = list(self.pinged_list_dict.keys())

        for agent in temp_list:
            if self.pinged_list_dict[agent] >= MAX_PING_ALLOWANCE:
                # remove constraint
                self.agent.active_constraints.pop(f'{self.agent.agent_id},{agent}')

                # remove from responses
                if agent in self.responses:
                    self.responses.remove(agent)

                # remove from neighbor list
                if self.parent == agent:
                    self.busy = True
                    self.parent = None
                    self.network = ''.join([random.choice(string.ascii_lowercase) for _ in range(5)])
                    self.agent.cpa.clear()
                    self.on_network_changed()
                else:
                    self.children.remove(agent)

                disconnected = True
                self.agent.agent_disconnection_callback(agent)
                self.report_agent_disconnection(agent)
                self.pinged_list_dict.pop(agent)

        if disconnected:
            self.reset()

    def report_agent_disconnection(self, agent):
        # inform dashboard of disconnection
        self.channel.basic_publish(exchange=messaging.COMM_EXCHANGE,
                                   routing_key=f'{messaging.MONITORING_CHANNEL}',
                                   body=messaging.create_agent_disconnection_message({
                                       'agent_id': self.agent.agent_id,
                                       'node1': self.agent.agent_id,
                                       'node2': agent,
                                       'network': self.network,
                                   }))

    def reset(self):
        # Run DCOP algorithm
        self.agent.execute_dcop()

        if not self.children:
            self.busy = False
            # self.channel.basic_publish(exchange=messaging.COMM_EXCHANGE,
            #                            routing_key=f'{messaging.AGENTS_CHANNEL}.public',
            #                            body=messaging.create_network_update_completion({
            #                                'agent_id': self.agent.agent_id,
            #                                'network': self.network,
            #                            }))

    def connect(self):
        if not self.parent:
            self.channel.basic_publish(exchange=messaging.COMM_EXCHANGE,
                                       routing_key=f'{messaging.AGENTS_CHANNEL}.public',
                                       body=messaging.create_announce_message({
                                           'agent_id': self.agent.agent_id,
                                           'network': self.network,
                                       }))

    def receive_announce_message(self, payload):
        self.log.debug(f'received {payload}')

        data = payload['payload']
        sender = data['agent_id']
        sender_network = data['network']

        if self.network != sender_network and not self.busy:
            self.busy = True
            if config.USE_PREDEFINED_NETWORK:
                key = f'{self.agent.agent_id},{sender}'
                if key in self.agent.coefficients_dict:
                    self.channel.basic_publish(exchange=messaging.COMM_EXCHANGE,
                                               routing_key=f'{messaging.AGENTS_CHANNEL}.{sender}',
                                               body=messaging.create_announce_response_message({
                                                   'agent_id': self.agent.agent_id,
                                                   'network': self.network,
                                                   'extra_args': self.agent.connection_extra_args,
                                               }))
                else:
                    self.busy = False
            else:
                self.responses.append(sender)
                self.channel.basic_publish(exchange=messaging.COMM_EXCHANGE,
                                           routing_key=f'{messaging.AGENTS_CHANNEL}.{sender}',
                                           body=messaging.create_announce_response_message({
                                               'agent_id': self.agent.agent_id,
                                               'network': self.network,
                                               'extra_args': self.agent.connection_extra_args,
                                           }))

    def receive_announce_response_message(self, payload):
        self.log.debug(f'received {payload}')

        data = payload['payload']
        sender = data['agent_id']
        network = data['network']
        extra_args = data['extra_args']

        key = f'{sender},{self.agent.agent_id}'
        saved_sim = config.USE_PREDEFINED_NETWORK

        if not self.busy and not self.parent \
                and not self.is_neighbor(sender) \
                and sender not in self.responses \
                and self.network != network \
                and ((saved_sim and key in self.agent.coefficients_dict) or not saved_sim):
            self.busy = True

            self.log.debug('receive_announce_response_message' + str(self.responses))

            constraint = self.agent.get_constraint(sender)
            self.agent.active_constraints[f'{self.agent.agent_id},{sender}'] = constraint
            self.parent = sender
            previous_network = self.network
            self.network = network
            self.on_network_changed()
            self.agent.connection_extra_args_callback(sender, extra_args)

            # send acknowledgement to sender
            self.channel.basic_publish(exchange=messaging.COMM_EXCHANGE,
                                       routing_key=f'{messaging.AGENTS_CHANNEL}.{sender}',
                                       body=messaging.create_announce_response_message_ack({
                                           'agent_id': self.agent.agent_id,
                                           'connected': True,
                                           'extra_args': self.agent.connection_extra_args,
                                       }))

            # inform dashboard about connection
            self.channel.basic_publish(exchange=messaging.COMM_EXCHANGE,
                                       routing_key=f'{messaging.MONITORING_CHANNEL}',
                                       body=messaging.create_agent_connection_message({
                                           'agent_id': self.agent.agent_id,
                                           'child': self.agent.agent_id,
                                           'parent': sender,
                                           'constraint': str(constraint.equation),
                                           'route': messaging.ANNOUNCE_RESPONSE_MSG,
                                           'network': self.network,
                                           'previous': previous_network,
                                       }))

            self.log.info(f'parent = {self.parent}, children = {self.children}')

            if not self.children:
                self.busy = False

            if self.agent.graph_traversing_order == 'bottom-up':
                self.reset()

        else:
            # respond if connection is not possible
            self.channel.basic_publish(exchange=messaging.COMM_EXCHANGE,
                                       routing_key=f'{messaging.AGENTS_CHANNEL}.{sender}',
                                       body=messaging.create_announce_response_message_ack({
                                           'agent_id': self.agent.agent_id,
                                           'connected': False,
                                       }))

    def receive_announce_response_message_ack(self, payload):
        self.log.debug(f'received {payload}')

        data = payload['payload']
        sender = data['agent_id']
        connected = data['connected']

        if connected and not self.is_neighbor(sender):
            constraint = self.agent.get_constraint(sender)
            self.agent.active_constraints[f'{self.agent.agent_id},{sender}'] = constraint
            self.children.append(sender)
            self.children_history.append(sender)
            extra_args = data['extra_args']
            self.agent.connection_extra_args_callback(sender, extra_args)

            # inform dashboard about connection
            self.channel.basic_publish(exchange=messaging.COMM_EXCHANGE,
                                       routing_key=f'{messaging.MONITORING_CHANNEL}',
                                       body=messaging.create_agent_connection_message({
                                           'agent_id': self.agent.agent_id,
                                           'parent': self.agent.agent_id,
                                           'child': sender,
                                           'constraint': str(constraint.equation),
                                           'route': messaging.ANNOUNCE_RESPONSE_MSG_ACK,
                                           'network': self.network,
                                       }))

            self.log.info(f'parent = {self.parent}, children = {self.children}')

            if self.agent.graph_traversing_order == 'top-down':
                self.reset()

        # announce cycle is complete so remove this sender to allow future connections
        if not config.USE_PREDEFINED_NETWORK:
            self.responses.remove(sender)
        self.busy = False

    def receive_set_network_message(self, payload):
        data = payload['payload']
        network = data['network']
        self.network = network
        self.on_network_changed()

        if not self.children:
            self.channel.basic_publish(exchange=messaging.COMM_EXCHANGE,
                                       routing_key=f'{messaging.AGENTS_CHANNEL}.public',
                                       body=messaging.create_network_update_completion({
                                           'agent_id': self.agent.agent_id,
                                           'network': self.network,
                                       }))

    def ping_neighbors(self):
        for agent in self.neighbors:
            if agent not in self.pinged_list_dict:
                self.channel.basic_publish(exchange=messaging.COMM_EXCHANGE,
                                           routing_key=f'{messaging.AGENTS_CHANNEL}.{agent}',
                                           body=messaging.create_ping_message({
                                               'agent_id': self.agent.agent_id,
                                           }))
                self.pinged_list_dict[agent] = 1
            else:
                self.pinged_list_dict[agent] += 1

        # wait to hear from neighbors
        # self.client.sleep(config.PING_TIMEOUT)

        # remove agents that are no longer connected (we didn't hear from them)
        if self.pinged_list_dict:
            self.remove_inactive_connections()

    def receive_ping_message(self, payload):
        data = payload['payload']
        sender = data['agent_id']
        self.channel.basic_publish(exchange=messaging.COMM_EXCHANGE,
                                   routing_key=f'{messaging.AGENTS_CHANNEL}.{sender}',
                                   body=messaging.create_ping_response_message({
                                       'agent_id': self.agent.agent_id,
                                   }))

    def receive_ping_response_message(self, payload):
        data = payload['payload']
        sender = data['agent_id']

        if sender in self.pinged_list_dict:
            self.pinged_list_dict.pop(sender)
            self.log.debug(f'received ping response from agent {sender}')
            self.log.debug(f'after: {self.pinged_list_dict}')

    def receive_network_update_completion_message(self, payload):
        network = payload['payload']['network']
        self.log.debug(self.busy)
        self.log.debug(payload)
        if self.network == network:
            self.busy = False

    def receive_constraint_changed_message(self, payload):
        self.log.info(payload)
        data = payload['payload']
        sender = data['agent_id']

        # update the constraint
        coefficients = data['coefficients']
        constraint = self.agent.get_constraint(sender, coefficients)
        self.agent.active_constraints[f'{self.agent.agent_id},{sender}'] = constraint

        # check for DCOP initiation
        if self.agent.graph_traversing_order == 'top-down' and self.is_child(sender):
            self.reset()
        elif self.agent.graph_traversing_order == 'bottom-up' and self.is_parent(sender):
            self.reset()

        self.log.info('constraint changed')

    def change_constraint(self, coefficients, neighbor_id):
        # update constraint's coefficients (event injection)
        self.log.info(f'constraint change requested: agent-{neighbor_id}')
        constraint = self.agent.get_constraint(neighbor_id, coefficients)
        self.agent.active_constraints[f'{self.agent.agent_id},{neighbor_id}'] = constraint

        # inform neighbor of constraint update
        self.channel.basic_publish(exchange=messaging.COMM_EXCHANGE,
                                   routing_key=f'{messaging.AGENTS_CHANNEL}.{neighbor_id}',
                                   body=messaging.create_constraint_changed_message({
                                       'agent_id': self.agent.agent_id,
                                       'coefficients': coefficients,
                                   }))

        # check for DCOP initiation
        if self.agent.graph_traversing_order == 'top-down' and self.is_child(neighbor_id):  # parent node
            self.reset()
        elif self.agent.graph_traversing_order == 'bottom-up' and self.is_parent(neighbor_id):  # then it is a leaf node
            self.reset()
