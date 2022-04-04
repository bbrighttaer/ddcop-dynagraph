import collections
import random
import string

from mascoord import messaging
from mascoord.config import MAX_PING_COUNT

import enum


class State(enum.Enum):
    ACTIVE = enum.auto()
    INACTIVE = enum.auto()


class DynaGraph:
    """
    Implementation of the Dynamic Interaction Graph Construction algorithm
    """

    def __init__(self, agent):
        self.agent = agent
        self.channel = self.agent.channel
        self.parent = None
        self.children = []
        self.children_history = {}
        self.log = self.agent.log
        self.client = agent.client
        self.pinged_list_dict = {}
        self.state = State.INACTIVE
        self.announceResponseList = []

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

    def _start_dcop(self):
        self.log.debug(f'Starting DCOP...')

    def _send_to_agent(self, body, to):
        self.channel.basic_publish(exchange=messaging.COMM_EXCHANGE,
                                   routing_key=f'{messaging.AGENTS_CHANNEL}.{to}',
                                   body=body)

    def _report_connection(self, parent, child, constraint):
        self.channel.basic_publish(exchange=messaging.COMM_EXCHANGE,
                                   routing_key=f'{messaging.MONITORING_CHANNEL}',
                                   body=messaging.create_agent_connection_message({
                                       'agent_id': self.agent.agent_id,
                                       'child': child,
                                       'parent': parent,
                                       'constraint': str(constraint),
                                   }))

    def connect(self):
        if self.state == State.INACTIVE and not self.parent:
            self.log.debug(f'Publishing Announce message...')

            # publish Announce message
            self.channel.basic_publish(exchange=messaging.COMM_EXCHANGE,
                                       routing_key=f'{messaging.AGENTS_CHANNEL}.public',
                                       body=messaging.create_announce_message({
                                           'agent_id': self.agent.agent_id,
                                       }))

            # wait to receive responses
            self.agent.listen_to_network()

            self.log.debug(f'AnnounceResponse list in connect: {self.announceResponseList}')

            # select agent to connect to
            selected_agent = None
            for agent in self.announceResponseList:
                if agent < int(self.agent.agent_id):
                    selected_agent = agent
                    break
            if selected_agent is not None:
                self.log.debug(f'Selected agent for AddMe: {selected_agent}')
                self._send_to_agent(
                    body=messaging.create_add_me_message({'agent_id': self.agent.agent_id}),
                    to=selected_agent,
                )
                self.state = State.ACTIVE

            self.announceResponseList.clear()

    def receive_announce(self, message):
        self.log.debug(f'Received announce: {message}')
        sender = message['payload']['agent_id']

        if self.state == State.INACTIVE and int(self.agent.agent_id) < int(sender):
            self._send_to_agent(
                body=messaging.create_announce_response_message({'agent_id': self.agent.agent_id}),
                to=sender,
            )

    def receive_announce_response(self, message):
        self.log.debug(f'Received announce response: {message}')
        sender = message['payload']['agent_id']

        if self.state == State.INACTIVE:
            self.announceResponseList.append(int(sender))
            self.log.debug(f'AnnounceResponse list: {self.announceResponseList}')

    def receive_add_me(self, message):
        self.log.debug(f'Received AddMe: {message}')
        sender = message['payload']['agent_id']

        if self.state == State.INACTIVE:
            constraint = self.agent.get_constraint(sender)
            self.children.append(sender)
            self.children_history[sender] = constraint
            self._send_to_agent(
                body=messaging.create_child_added_message({
                    'agent_id': self.agent.agent_id,
                    'extra_args': self.agent.connection_extra_args,
                }),
                to=sender,
            )

            # inform dashboard about the connection
            self._report_connection(parent=self.agent.agent_id, child=sender, constraint=constraint)
        else:
            self.log.debug(f'Rejected AddMe from agent: {sender}, sending AlreadyActive message')
            self._send_to_agent(
                body=messaging.create_already_active_message({'agent_id': self.agent.agent_id}),
                to=sender,
            )

    def receive_child_added(self, message):
        self.log.debug(f'Received ChildAdded: {message}')
        sender = message['payload']['agent_id']

        if self.state == State.ACTIVE and not self.parent:
            self.state = State.INACTIVE
            self.parent = sender
            self.agent.connection_extra_args_callback(sender, message['payload']['extra_args'])
            self._send_to_agent(
                body=messaging.create_parent_assigned_message({
                    'agent_id': self.agent.agent_id,
                    'extra_args': self.agent.connection_extra_args,
                }),
                to=sender,
            )

            if self.agent.graph_traversing_order == 'bottom-up':
                self._start_dcop()

    def receive_parent_assigned(self, message):
        self.log.debug(f'Received ParentAssigned: {message}')

        sender = message['payload']['agent_id']
        self.agent.connection_extra_args_callback(sender, message['payload']['extra_args'])

        if self.agent.graph_traversing_order == 'top-down':
            self._start_dcop()

    def receive_already_active(self, message):
        self.log.debug(f'Received AlreadyActive: {message}')
        self.state = State.INACTIVE
