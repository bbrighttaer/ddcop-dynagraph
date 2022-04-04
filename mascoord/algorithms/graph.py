import enum

from mascoord import messaging
from mascoord.config import MAX_PING_COUNT


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
        self.agent.execute_dcop()

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

        key = f'{self.agent.agent_id},{sender}'
        using_saved_sim = self.agent.shared_config.use_predefined_graph

        if self.state == State.INACTIVE \
                and ((using_saved_sim and key in self.agent.coefficients_dict) or not using_saved_sim):
            constraint = self.agent.get_constraint(sender)
            self.agent.active_constraints[key] = constraint
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
            constraint = self.agent.get_constraint(sender)
            self.agent.active_constraints[f'{self.agent.agent_id},{sender}'] = constraint
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

    def ping_neighbors(self):
        for agent in self.neighbors:
            if agent not in self.pinged_list_dict:
                self._send_to_agent(
                    body=messaging.create_ping_message({'agent_id': self.agent.agent_id}),
                    to=agent,
                )
                self.pinged_list_dict[agent] = 1
            else:
                self.pinged_list_dict[agent] += 1

        # remove agents that are no longer connected (we didn't hear from them)
        if self.pinged_list_dict:
            self._remove_dead_connections()

    def receive_ping_message(self, message):
        self.log.debug(f'Received Ping message: {message}')
        sender = message['payload']['agent_id']

        if self.is_neighbor(sender):
            self._send_to_agent(
                body=messaging.create_ping_response_message({'agent_id': self.agent.agent_id}),
                to=sender,
            )

    def receive_ping_response_message(self, message):
        data = message['payload']
        sender = data['agent_id']

        if sender in self.pinged_list_dict:
            self.log.debug(f'Received ping response from agent {sender}')
            self.pinged_list_dict.pop(sender)
            self.log.debug(f'Pinged list after removing {sender}: {self.pinged_list_dict}')

    def _remove_dead_connections(self):
        disconnected = False
        temp_list = list(self.pinged_list_dict.keys())
        self.log.debug(f'Temp list for removal: {temp_list}')

        for agent in temp_list:
            if self.pinged_list_dict[agent] >= MAX_PING_COUNT:

                # remove constraint
                self.agent.active_constraints.pop(f'{self.agent.agent_id},{agent}')

                # remove from neighbor list
                if self.parent == agent:
                    self.state = State.INACTIVE
                    self.parent = None
                    self.agent.cpa.clear()
                    self.agent.initialize_announce_call_exp_decay()  # so that Announce msgs can be published faster
                else:
                    self.children.remove(agent)

                disconnected = True
                self.agent.agent_disconnection_callback(agent)
                self._report_agent_disconnection(agent)
                self.pinged_list_dict.pop(agent)

        if disconnected:
            self._start_dcop()

    def _report_agent_disconnection(self, agent):
        # inform dashboard about disconnection
        self.channel.basic_publish(exchange=messaging.COMM_EXCHANGE,
                                   routing_key=f'{messaging.MONITORING_CHANNEL}',
                                   body=messaging.create_agent_disconnection_message({
                                       'agent_id': self.agent.agent_id,
                                       'node1': self.agent.agent_id,
                                       'node2': agent,
                                   }))

    def change_constraint(self, coefficients, neighbor_id):
        # update constraint's coefficients (event injection)
        self.log.debug(f'Constraint change requested: agent-{neighbor_id}')
        constraint = self.agent.get_constraint(neighbor_id, coefficients)
        self.agent.active_constraints[f'{self.agent.agent_id},{neighbor_id}'] = constraint

        # inform neighbor of constraint update
        self._send_to_agent(
            body=messaging.create_constraint_changed_message({
                'agent_id': self.agent.agent_id,
                'coefficients': coefficients,
            }),
            to=neighbor_id,
        )

        # check for DCOP initiation
        if self.agent.graph_traversing_order == 'top-down' and self.is_child(neighbor_id):  # parent node case
            self._start_dcop()
        elif self.agent.graph_traversing_order == 'bottom-up' and self.is_parent(neighbor_id):  # child node case
            self._start_dcop()

        self.agent.metrics.update_metrics()

    def receive_constraint_changed_message(self, message):
        self.log.debug(f'Received constraint changed: {message}')
        data = message['payload']
        sender = data['agent_id']

        # update the constraint
        coefficients = data['coefficients']
        constraint = self.agent.get_constraint(sender, coefficients)
        self.agent.active_constraints[f'{self.agent.agent_id},{sender}'] = constraint

        # check for DCOP initiation
        if self.agent.graph_traversing_order == 'top-down' and self.is_child(sender):
            self._start_dcop()
        elif self.agent.graph_traversing_order == 'bottom-up' and self.is_parent(sender):
            self._start_dcop()

        self.log.debug('Constraint changed')


