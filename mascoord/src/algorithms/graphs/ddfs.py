from mascoord.src import messaging
from mascoord.src.algorithms.graphs.base import DynaGraph, get_agent_order


class DDFS(DynaGraph):
    """
    Implementation of the Distributed Depth-First Search algorithm
    """

    def __init__(self, agent):
        super(DDFS, self).__init__(agent)
        self._parents_levels = {}
        self._paused_value_msgs = []
        self._children_temp = []
        self._parents = []
        self.pseudo_children = []
        self.pseudo_parents = []
        self._neighbor_data = {}

        self._value_msgs = {}

        self._max = 0

    def on_time_step_changed(self):
        self.log.info('Time step changed')

        # base class props
        self.parent = None
        self.children.clear()
        self.pseudo_parents.clear()
        self.pseudo_children.clear()
        self._parents.clear()
        self._children_temp.clear()
        self._parents_levels.clear()
        self._value_msgs.clear()
        self._paused_value_msgs.clear()
        self._max = 0

        # send neighbor data to sim env
        self.channel.basic_publish(
            exchange=messaging.COMM_EXCHANGE,
            routing_key=f'{messaging.SIM_ENV_CHANNEL}',
            body=messaging.create_neighbor_data_message({
                'agent_id': self.agent.agent_id,
                'num_agents_in_comm_range': len(self.agent.agents_in_comm_range),
            })
        )

    def connect(self):
        ...

    def receive_neighbor_data(self, message):
        self.log.debug(f'Received neighbor data: {message}')
        message = message['payload']
        self._neighbor_data[message['agent_id']] = message['num_agents_in_comm_range']
        if len(set(self.agent.agents_in_comm_range) - set(self._neighbor_data.keys())) == 0:
            self._split_neighbors()

    def _split_neighbors(self):
        """
        split neighbors into children and parents
        """

        self.log.debug('Splitting neighbors')

        self.log.debug(f'Neighbor data for splitting: {self._neighbor_data}')

        for agt, num_neighbors in self._neighbor_data.items():
            if num_neighbors < len(self.agent.agents_in_comm_range) \
                    or (num_neighbors == len(self.agent.agents_in_comm_range)
                        and get_agent_order(self.agent.agent_id) < get_agent_order(agt)):
                self._children_temp.append(agt)
            else:
                self._parents.append(agt)

        self.log.debug(f'After splitting: children_temp={self._children_temp}, parents_temp={self._parents}')

        # if this agent is a leaf, begin level calculation for ordering parents
        if len(self._children_temp) == 0 and self._parents:
            self._max = 1

            for p in self._parents:
                self.log.debug(f'Sending value-msg to {p}')
                self.send_to_agent(
                    body=messaging.create_ddfs_value_message({
                        'agent_id': self.agent.agent_id,
                        'value': self._max,
                    }),
                    to=p,
                )

        self.log.debug(f'Splitting completed')

        self._neighbor_data.clear()

        # process any delayed value message
        if self._paused_value_msgs:
            self.log.debug(f'Found {len(self._paused_value_msgs)} paused value messages')
            self.receive_value_message()

    def remove_agent(self, agent):
        if self.parent == agent:
            self.parent = None
            self.agent.cpa.clear()
            self.agent.initialize_announce_call_exp_decay()  # so that Announce msgs can be published faster
        else:
            self.children.remove(agent)

        self.agent.agent_disconnection_callback(agent)
        self.report_agent_disconnection(agent)

    def receive_value_message(self, message=None):
        if message:
            self.log.debug(f'Received DDFS value message: {message}')
            msg = message['payload']
            self._value_msgs[msg['agent_id']] = msg['value']

            if self._max < msg['value']:
                self._max = msg['value']
        else:
            self.log.debug('Value message call triggered with an empty message')

        split_executed = bool(self._children_temp or self._parents)
        has_received_all_value_msgs = len(set(self._children_temp) - set(self._value_msgs.keys())) == 0
        if split_executed and has_received_all_value_msgs:
            self._max += 1

            # send max value info to ancestors
            for p in self._parents:
                self.send_to_agent(
                    body=messaging.create_ddfs_value_message({
                        'agent_id': self.agent.agent_id,
                        'value': self._max,
                    }),
                    to=p,
                )

            # send position to descendants
            for agt in self._children_temp:
                self.send_to_agent(
                    body=messaging.create_ddfs_position_message({
                        'agent_id': self.agent.agent_id,
                        'position': self._max,
                    }),
                    to=agt,
                )
        else:
            self._paused_value_msgs.append(message)

    def receive_position_msg(self, message):
        self.log.debug(f'Received position message: {message}')
        msg = message['payload']

        self._parents_levels[msg['agent_id']] = msg['position']

        if len(self._parents_levels) == len(self._parents):
            parents = sorted(self._parents, key=lambda p: self._parents_levels[p])
            self.parent = parents.pop(0)
            self.pseudo_parents = parents

            # send child msg to parent
            self.send_to_agent(
                body=messaging.create_ddfs_child_message({
                    'agent_id': self.agent.agent_id,
                }),
                to=self.parent,
            )
            self.log.debug(f'Added {self.parent} as parent')

            # send pseudo-child messages
            for p in parents:
                self.log.debug(f'Added {p} as pseudo-parent')
                self.send_to_agent(
                    body=messaging.create_ddfs_pseudo_child_message({
                        'agent_id': self.agent.agent_id,
                    }),
                    to=p,
                )

            # is_leaf_node = len(self._children_temp) == 0
            # if is_leaf_node:
            if self.agent.graph_traversing_order == 'bottom-up':
                self.start_dcop()

    def receive_pseudo_child_msg(self, msg):
        self.log.debug(f'Received pseudo-child msg: {msg}')
        msg = msg['payload']
        self.pseudo_children.append(msg['agent_id'])
        self.log.debug(f'Added {msg["agent_id"]} as pseudo-child')

        if self.agent.graph_traversing_order == 'top-down' \
                and len(self.children + self.pseudo_children) == len(self.agent.agents_in_comm_range):
            self.log.debug('Starting DCOP - pseudo-child')
            self.start_dcop()

    def receive_child_msg(self, msg):
        self.log.debug(f'Received child msg: {msg}')
        msg = msg['payload']
        self.children.append(msg['agent_id'])
        self.log.debug(f'Added {msg["agent_id"]} as child')

        # update current graph
        self.channel.basic_publish(
            exchange=messaging.COMM_EXCHANGE,
            routing_key=f'{messaging.SIM_ENV_CHANNEL}',
            body=messaging.create_add_graph_edge_message({
                'agent_id': self.agent.agent_id,
                'from': self.agent.agent_id,
                'to': msg['agent_id'],
            })
        )

        if self.agent.graph_traversing_order == 'top-down' \
                and len(self.children + self.pseudo_children) == len(self.agent.agents_in_comm_range):
            self.log.debug('Starting DCOP - child')
            self.start_dcop()

    def has_potential_neighbor(self):
        return bool(self.agent.agents_in_comm_range)


