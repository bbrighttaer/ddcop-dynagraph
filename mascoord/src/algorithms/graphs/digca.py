import random
import time

from mascoord.src import messaging
from mascoord.src.algorithms.graphs.base import DynaGraph, get_agent_order
from mascoord.src.config import MAX_PING_COUNT

import enum


class State(enum.Enum):
    ACTIVE = enum.auto()
    INACTIVE = enum.auto()


class DIGCA(DynaGraph):
    """
    Implementation of the Dynamic Interaction Graph Construction algorithm
    """

    def __init__(self, agent):
        super(DIGCA, self).__init__(agent)
        self._has_sent_parent_available = False
        self.pinged_list_dict = {}
        self.state = State.INACTIVE
        self.announceResponseList = []
        self._ignored_ann_msgs = {}
        self._parent_already_assigned_msgs = {}
        self._timeout_delay_in_seconds = .5
        self._timeout_delay_start = None

    def on_time_step_changed(self):
        self._ignored_ann_msgs.clear()
        self._parent_already_assigned_msgs.clear()
        self._has_sent_parent_available = False
        self._timeout_delay_start = time.time()
        self.exec_started = False

    def connect(self):
        if not self.parent and self.has_potential_parent() and self.state == State.INACTIVE:
            self.log.debug(f'Publishing Announce message...')

            # publish Announce message
            self.channel.basic_publish(
                exchange=messaging.COMM_EXCHANGE,
                routing_key=f'{messaging.SIM_ENV_CHANNEL}',
                body=messaging.create_announce_message({
                    'agent_id': self.agent.agent_id,
                })
            )

            # wait to receive responses
            self.agent.listen_to_network()

            self.log.debug(f'AnnounceResponse list in connect: {self.announceResponseList}')

            # select agent to connect to
            selected_agent = None
            if self.announceResponseList:
                selected_agent = random.choice(self.announceResponseList)

            if selected_agent is not None:
                self.log.debug(f'Selected agent for AddMe: {selected_agent}')
                self.send_to_agent(
                    body=messaging.create_add_me_message({'agent_id': self.agent.agent_id}),
                    to=selected_agent,
                )
                self.state = State.ACTIVE

            # send announce response ignored messages
            for a in set(self.announceResponseList):
                if a != selected_agent:
                    self.channel.basic_publish(
                        exchange=messaging.COMM_EXCHANGE,
                        routing_key=f'{messaging.AGENTS_CHANNEL}.{a}',
                        body=messaging.create_announce_response_ignored_message({
                            'agent_id': self.agent.agent_id,
                        })
                    )

            self.announceResponseList.clear()

        elif not self.exec_started \
                and self._timeout_delay_start \
                and time.time() - self._timeout_delay_start > self._timeout_delay_in_seconds:
            self.start_dcop()
            self._timeout_delay_start = None

            # all_potential_children = set(self._get_potential_children())
            # exclusion_set = set(self._parent_already_assigned_msgs.keys()) ^ set(self.neighbors)
            # potential_children = all_potential_children - exclusion_set
            #
            # self.log.debug(f'Sending parent available message to {potential_children}')
            #
            # for a in potential_children:
            #     self.channel.basic_publish(
            #         exchange=messaging.COMM_EXCHANGE,
            #         routing_key=f'{messaging.AGENTS_CHANNEL}.{a}',
            #         body=messaging.create_parent_available_message({
            #             'agent_id': self.agent.agent_id,
            #         })
            #     )

        # else:
        #     self.log.debug(f'Not announcing, state={self.state}')

    def receive_announce(self, message):
        self.log.debug(f'Received announce: {message}')
        sender = message['payload']['agent_id']

        if self.state == State.INACTIVE and get_agent_order(self.agent.agent_id) < get_agent_order(sender):
            self.send_to_agent(
                body=messaging.create_announce_response_message({'agent_id': self.agent.agent_id}),
                to=sender,
            )

    def receive_announce_response(self, message):
        self.log.debug(f'Received announce response: {message}')
        sender = message['payload']['agent_id']

        if self.state == State.INACTIVE:
            self.announceResponseList.append(sender)
            self.log.debug(f'AnnounceResponse list: {self.announceResponseList}')

    def receive_add_me(self, message):
        self.log.debug(f'Received AddMe: {message}')
        sender = message['payload']['agent_id']

        key = f'{self.agent.agent_id},{sender}'
        using_saved_sim = self.agent.shared_config.use_predefined_graph

        if self.state == State.INACTIVE \
                and len(self.children) < self.agent.shared_config.max_out_degree \
                and ((using_saved_sim and key in self.agent.coefficients_dict) or not using_saved_sim):
            constraint = self.agent.get_constraint(sender)
            self.agent.active_constraints[key] = constraint
            self.children.append(sender)
            self.children_history[sender] = constraint
            self.send_to_agent(
                body=messaging.create_child_added_message({
                    'agent_id': self.agent.agent_id,
                    'extra_args': self.agent.connection_extra_args,
                }),
                to=sender,
            )
            self.log.info(f'Added agent {sender} to children: {self.children}')

            # update current graph
            self.channel.basic_publish(
                exchange=messaging.COMM_EXCHANGE,
                routing_key=f'{messaging.SIM_ENV_CHANNEL}',
                body=messaging.create_add_graph_edge_message({
                    'agent_id': self.agent.agent_id,
                    'from': self.agent.agent_id,
                    'to': sender,
                })
            )

            # inform dashboard about the connection
            self.report_connection(parent=self.agent.agent_id, child=sender, constraint=constraint)
        else:
            self.log.debug(f'Rejected AddMe from agent: {sender}, sending AlreadyActive message')
            self.send_to_agent(
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
            self.send_to_agent(
                body=messaging.create_parent_assigned_message({
                    'agent_id': self.agent.agent_id,
                    'extra_args': self.agent.connection_extra_args,
                }),
                to=sender,
            )
            self.log.info(f'Set parent node to agent {sender}')

            # update current graph
            self.channel.basic_publish(
                exchange=messaging.COMM_EXCHANGE,
                routing_key=f'{messaging.SIM_ENV_CHANNEL}',
                body=messaging.create_add_graph_edge_message({
                    'agent_id': self.agent.agent_id,
                    'from': sender,
                    'to': self.agent.agent_id,
                })
            )

            if self.agent.graph_traversing_order == 'bottom-up':
                self.start_dcop()

    def receive_parent_assigned(self, message):
        self.log.debug(f'Received ParentAssigned: {message}')

        sender = message['payload']['agent_id']
        self.agent.connection_extra_args_callback(sender, message['payload']['extra_args'])

        if self.agent.graph_traversing_order == 'top-down':
            self.start_dcop()

    def receive_already_active(self, message):
        self.log.debug(f'Received AlreadyActive: {message}')
        self.state = State.INACTIVE

    def ping_neighbors(self):
        for agent in self.neighbors:
            if agent not in self.pinged_list_dict:
                # self._send_to_agent(
                #     body=messaging.create_ping_message({'agent_id': self.agent.agent_id}),
                #     to=agent,
                # )
                self.channel.basic_publish(
                    exchange=messaging.COMM_EXCHANGE,
                    routing_key=f'{messaging.SIM_ENV_CHANNEL}',
                    body=messaging.create_ping_message({'agent_id': self.agent.agent_id, 'recipient': agent})
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
            self.send_to_agent(
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
                key = f'{self.agent.agent_id},{agent}'
                if key in self.agent.active_constraints:
                    self.agent.active_constraints.pop(key)

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
                self.report_agent_disconnection(agent)
                self.pinged_list_dict.pop(agent)

        if disconnected:
            self.start_dcop()

    def change_constraint(self, coefficients, neighbor_id):
        # update constraint's coefficients (event injection)
        self.log.info(f'Constraint change requested: agent-{neighbor_id}')
        constraint = self.agent.get_constraint(neighbor_id, coefficients)
        self.agent.active_constraints[f'{self.agent.agent_id},{neighbor_id}'] = constraint

        # inform neighbor of constraint update
        self.send_to_agent(
            body=messaging.create_constraint_changed_message({
                'agent_id': self.agent.agent_id,
                'coefficients': coefficients,
            }),
            to=neighbor_id,
        )

        # check for DCOP initiation
        if self.agent.graph_traversing_order == 'top-down' and self.is_child(neighbor_id):  # parent node case
            self.start_dcop()
        elif self.agent.graph_traversing_order == 'bottom-up' and self.is_parent(neighbor_id):  # child node case
            self.start_dcop()

        self.agent.metrics.update_metrics()

    def receive_constraint_changed_message(self, message):
        self.log.info(f'Received constraint changed: {message}')
        data = message['payload']
        sender = data['agent_id']

        # update the constraint
        coefficients = data['coefficients']
        constraint = self.agent.get_constraint(sender, coefficients)
        self.agent.active_constraints[f'{self.agent.agent_id},{sender}'] = constraint

        # check for DCOP initiation
        if self.agent.graph_traversing_order == 'top-down' and self.is_child(sender):
            self.start_dcop()
        elif self.agent.graph_traversing_order == 'bottom-up' and self.is_parent(sender):
            self.start_dcop()

        self.log.debug('Constraint changed')

    def remove_agent(self, agent):
        if self.parent == agent:
            self.state = State.INACTIVE
            self.parent = None
            self.agent.cpa.clear()
            self.agent.initialize_announce_call_exp_decay()  # so that Announce msgs can be published faster
        else:
            self.children.remove(agent)

        self.agent.agent_disconnection_callback(agent)
        self.report_agent_disconnection(agent)

    def receive_announce_response_ignored(self, message):
        sender = message['payload']['agent_id']
        self._ignored_ann_msgs[sender] = message
        self.log.info(f'Received announce ignored message from {sender}')

        if len(set(self._ignored_ann_msgs)) == len(self._get_potential_children()) and not self.agent.value:
            self.agent.execute_dcop()

    def receive_parent_available_message(self, message):
        # self.log.info(f'Received parent available message: {message}')
        if self.parent:
            sender = message['payload']['agent_id']
            self.channel.basic_publish(
                exchange=messaging.COMM_EXCHANGE,
                routing_key=f'{messaging.AGENTS_CHANNEL}.{sender}',
                body=messaging.create_parent_already_assigned_message({
                    'agent_id': self.agent.agent_id,
                })
            )

    def receive_parent_already_assigned(self, message):
        sender = message['payload']['agent_id']
        self._parent_already_assigned_msgs[sender] = message
        self.log.debug(f'Received parent already assigned message from {sender}')

        if len(self._parent_already_assigned_msgs.keys()) == len(self._get_potential_children()) \
                and not self.agent.value:
            self._has_sent_parent_available = True
            self.agent.execute_dcop()

    def _get_potential_children(self):
        agents = []
        for _agt in set(self.agent.new_agents) - set(self.neighbors):
            if int(_agt.replace('a', '')) > int(self.agent.agent_id.replace('a', '')):
                agents.append(_agt)

        return agents

    def has_potential_parent(self):
        for _agt in set(self.agent.new_agents) - set(self.neighbors):
            if int(_agt.replace('a', '')) < int(self.agent.agent_id.replace('a', '')):
                return True

        return False

    def has_potential_child(self):
        return bool(self._get_potential_children())

    def has_potential_neighbor(self):
        return self.has_potential_child() or (not self.parent and self.has_potential_parent())
