import numpy as np

from mascoord.src import messaging
from mascoord.src.algorithms.dcop import DCOP


class SDPOP(DCOP):
    """
    Implements the SDPOP algorithm
    """
    traversing_order = 'bottom-up'
    name = 'sdpop'

    def __init__(self, *args, **kwargs):
        super(SDPOP, self).__init__(*args, **kwargs)
        self.neighbor_domains = {}
        self.util_messages = {}
        self.X_ij = None
        self.util_received = False

    def set_edge_costs(self):
        """
        Trick to get values of neighbors in before setting edge costs
        """
        for agent in self.graph.neighbors:
            self.params[agent] = self.agent.metrics.get_agent_value(agent)
        super(SDPOP, self).set_edge_costs()

    def connection_extra_args(self) -> dict:
        return {
            'domain': self.domain,
            'alg': self.name,
        }

    def receive_extra_args(self, sender, args):
        self.neighbor_domains[sender] = args['domain']

    def agent_disconnection_callback(self, agent):
        if agent in self.neighbor_domains:
            self.neighbor_domains.pop(agent)

        if agent in self.util_messages:
            self.util_messages.pop(agent)

    def _compute_util_and_value(self):
        # children
        c_util_sum = np.array([0.] * len(self.domain))
        for child in self.graph.children:
            c_util = self.util_messages[child]
            c_util_sum += np.array(c_util)

        # parent
        if self.graph.parent:
            p_domain = self.neighbor_domains[self.graph.parent]

            x = np.array(self.domain).reshape(-1, 1)
            y = np.array(p_domain).reshape(-1, 1)
            xx, yy = np.meshgrid(x, y, indexing='ij')

            constraint = self.agent.active_constraints[f'{self.agent.agent_id},{self.graph.parent}']
            self.X_ij = constraint.evaluate(xx, yy) + c_util_sum.reshape(-1, 1)
            x_j = self.X_ij.min(axis=0)
            x_j = x_j / np.linalg.norm(x_j)

            self.send_util_message(self.graph.parent, x_j.tolist())
        else:
            # parent-level projection
            x_i = np.min(c_util_sum, axis=0)

            self.cost = float(np.min(x_i))  # todo: wrong cost computation
            self.value = self.domain[int(np.argmin(x_i))]
            self.agent.value_changes_count += 1
            self.cpa[f'agent-{self.agent.agent_id}'] = self.value

            self.log.info(f'Cost is {self.cost}')

            # send value msgs to children
            self.log.info(f'children: {self.graph.children}')
            for child in self.graph.children:
                self.send_value_message(child, {'cpa': self.cpa})

            self.collect_metrics()
        self.util_received = False

    def execute_dcop(self):
        self.log.info('Initiating SDPOP...')
        self.X_ij = None

        # calculate UTIL messages and send to parent
        self._compute_util_and_value()

    def can_resolve_agent_value(self) -> bool:
        # agent should have received util msgs from all children
        can_resolve = self.graph.neighbors \
                      and self.util_messages \
                      and len(self.util_messages) == len(self.graph.children) \
                      and self.util_received

        return can_resolve

    def select_value(self):
        # calculate value and send VALUE messages and send to children
        self._compute_util_and_value()

    def receive_util_message(self, payload):
        self.log.info(f'Received util message: {payload}')
        data = payload['payload']
        sender = data['agent_id']
        util = data['util']

        if self.graph.is_child(sender):
            self.util_messages[sender] = util
            self.util_received = True

    def send_util_message(self, recipient, util):
        self.graph.channel.basic_publish(exchange=messaging.COMM_EXCHANGE,
                                         routing_key=f'{messaging.AGENTS_CHANNEL}.{recipient}',
                                         body=messaging.create_util_message({
                                             'agent_id': self.agent.agent_id,
                                             'util': util,
                                         }))

    def receive_value_message(self, payload):
        self.log.info(f'Received value message: {payload}')
        data = payload['payload']
        sender = data['agent_id']
        value = data['value']

        # determine own value from parent's value
        if self.graph.is_parent(sender) and self.X_ij is not None:
            parent_cpa = value['cpa']
            parent_value = parent_cpa[f'agent-{sender}']
            self.cpa = parent_cpa
            j = self.neighbor_domains[sender].index(parent_value)
            x_i = self.X_ij[:, j].reshape(-1, )
            self.cost = float(x_i.min())  # todo: wrong cost computation
            self.value = self.domain[int(x_i.argmin())]
            self.agent.value_changes_count += 1
            self.cpa[f'agent-{self.agent.agent_id}'] = self.value

            self.log.info(f'Cost is {self.cost}')

            # send value msgs to children
            for child in self.graph.children:
                self.send_value_message(child, {'cpa': self.cpa})

            self.collect_metrics()

    def send_value_message(self, recipient, value):
        self.graph.channel.basic_publish(exchange=messaging.COMM_EXCHANGE,
                                         routing_key=f'{messaging.AGENTS_CHANNEL}.{recipient}',
                                         body=messaging.create_value_message({
                                             'agent_id': self.agent.agent_id,
                                             'value': value,
                                         }))

    def request_util_message(self, child):
        self.graph.channel.basic_publish(exchange=messaging.COMM_EXCHANGE,
                                         routing_key=f'{messaging.AGENTS_CHANNEL}.{child}',
                                         body=messaging.create_request_util_message({
                                             'agent_id': self.agent.agent_id,
                                         }))

    def receive_util_message_request(self, payload):
        self.log.info(f'Received util request message: {payload}')
        data = payload['payload']
        sender = data['agent_id']

        if self.graph.is_neighbor(sender):
            self._compute_util_and_value()

    def __str__(self):
        return 'sdpop'
