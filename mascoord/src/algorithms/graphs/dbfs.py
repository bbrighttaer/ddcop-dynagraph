import time

from mascoord.src import messaging
from mascoord.src.algorithms.graphs.base import DynaGraph, get_agent_order


class DBFS(DynaGraph):
    """
    Implementation of the Distributed Breadth-First Search algorithm
    """

    def __init__(self, agent):
        super(DBFS, self).__init__(agent)

        # for tracking hierarchy level
        self.level = 0

        # connection management helpers
        self._potential_children_rec_msgs = []
        self._potential_children_count = 0

    def on_time_step_changed(self):
        self.log.info('Time step changed')

        # base class props
        self.parent = None
        self.children.clear()
        self.pseudo_parents.clear()
        self.pseudo_children.clear()
        self._potential_children_rec_msgs.clear()
        self.level = 0
        self._potential_children_count = 0

        # execute BDFS algorithm
        self.begin_dbfs()



    def connect(self):
        ...

    def begin_dbfs(self):
        """
        The starting point of the DBFS process.
        """
        # find the agent with the smallest ID and use that as parent
        smallest_id = float('inf')
        sm_agt = None
        for agt in self.agent.agents_in_comm_range + [self.agent.agent_id]:
            agt_id = get_agent_order(agt)
            if smallest_id > agt_id:
                smallest_id = agt_id
                sm_agt = agt

        # send layer messages if this agent has the smallest order
        if self.agent.agents_in_comm_range and sm_agt:
            time.sleep(.2)  # wait for other agents to be ready for messages
            if self.agent.agent_id == sm_agt:
                self.level = 0
                for a in self.agent.agents_in_comm_range:
                    self.log.debug(f'Sending root level msg to {a}')
                    self.send_to_agent(
                        body=messaging.create_dbfs_level_message({
                            'agent_id': self.agent.agent_id,
                            'level': self.level,
                            'extra_args': self.agent.connection_extra_args,
                        }),
                        to=a,
                    )
                    self._potential_children_count += 1

    def receive_dbfs_level_message(self, message):
        self.log.debug(f'Received DBFS level message: {message}')
        msg = message['payload']
        sender = msg['agent_id']
        level = msg['level']

        if not self.parent:
            # send ack message to sender and set as parent
            self.parent = sender
            self.agent.connection_extra_args_callback(sender, msg['extra_args'])
            self.send_to_agent(
                body=messaging.create_dbfs_ack_message({
                    'agent_id': self.agent.agent_id,
                    'extra_args': self.agent.connection_extra_args,
                }),
                to=sender,
            )

            # send layer messages to other agents
            self.level = level + 1
            for a in self.agent.agents_in_comm_range:
                if a != self.parent and get_agent_order(self.agent.agent_id) < get_agent_order(a):
                    self.log.debug(f'Sending level msg to {a}')
                    self.send_to_agent(
                        body=messaging.create_dbfs_level_message({
                            'agent_id': self.agent.agent_id,
                            'level': self.level,
                            'extra_args': self.agent.connection_extra_args
                        }),
                        to=a,
                    )
                    self._potential_children_count += 1

            # if no child is expected then start optimisation
            if self._potential_children_count == 0:
                self._check_and_start_dcop()
        else:
            self.send_level_ignored_msg(sender)

    def send_level_ignored_msg(self, sender):
        self.log.debug('sending DBFS level message call ignored')
        self.send_to_agent(
            body=messaging.create_dbfs_level_ignored_message({
                'agent_id': self.agent.agent_id,
            }),
            to=sender,
        )

    def receive_dbfs_ack_message(self, message):
        self.log.debug(f'Received DBFS ack message: {message}')
        msg = message['payload']
        sender = msg['agent_id']
        self.children.append(sender)
        self._potential_children_rec_msgs.append(sender)
        self.agent.connection_extra_args_callback(sender, msg['extra_args'])

        # update current sim graph
        self.channel.basic_publish(
            exchange=messaging.COMM_EXCHANGE,
            routing_key=f'{messaging.SIM_ENV_CHANNEL}',
            body=messaging.create_add_graph_edge_message({
                'agent_id': self.agent.agent_id,
                'from': self.agent.agent_id,
                'to': sender,
            })
        )

        # start optimisation if all expected incoming messages have been received
        if self._potential_children_count == len(self._potential_children_rec_msgs):
            self._check_and_start_dcop()
        else:
            self.log.info(f"ack_msg: {self._potential_children_count}, {len(self._potential_children_rec_msgs)}")

    def receive_dbfs_level_ignored_message(self, message):
        self.log.debug(f'Received DBFS level ignored message: {message}')
        msg = message['payload']
        sender = msg['agent_id']
        self._potential_children_rec_msgs.append(sender)

        # start optimisation if all expected incoming messages have been received
        if self._potential_children_count == len(self._potential_children_rec_msgs):
            self._check_and_start_dcop()
        else:
            self.log.info(f"level_ignored: {self._potential_children_count}, {len(self._potential_children_rec_msgs)}")

    def _check_and_start_dcop(self):
        # order = self.agent.graph_traversing_order
        # if (
        #         order == 'top-down'
        #         and len(self.children + self.pseudo_children) == len(self.agent.agents_in_comm_range)
        # ) or (
        #         order == 'bottom-up'
        #         and set(self.get_connected_agents()) == set(self.agent.agents_in_comm_range)
        # ):
        self.start_dcop()

    def has_potential_neighbor(self):
        return bool(self.agent.agents_in_comm_range)


    def remove_agent(self, agent):
        if self.parent == agent:
            self.parent = None
            self.agent.cpa.clear()
            self.agent.initialize_announce_call_exp_decay()  # so that Announce msgs can be published faster
        else:
            self.children.remove(agent)

        self.agent.agent_disconnection_callback(agent)
        self.report_agent_disconnection(agent)