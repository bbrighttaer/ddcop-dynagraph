import numpy as np

from mascoord.src import config
from mascoord.src.algorithms.dcop.dpop import DPOP


class CDPOP(DPOP):
    """
    A continuous domain analogue of the SDPOP algorithm
    """
    name = 'c-sdpop'

    def __init__(self, *args, **kwargs):
        super(CDPOP, self).__init__(*args, **kwargs)
        self.max_iter = 100
        self.alpha = config.LEARNING_RATE
        self.X_ij_prev_norm = None
        self.prev_initial_val = None

    def _compute_util_and_value(self):
        # children
        c_util_sum = np.zeros((len(self.domain), len(self.domain)))
        for child in self.graph.children:
            c_util = self.util_messages[child]
            c_util_sum += np.array(c_util)

        # parent-level projection
        x_i = np.min(c_util_sum, axis=0)

        # parent
        if self.graph.parent:
            p_domain = self.neighbor_domains[self.graph.parent]

            domain = [self.value] * len(self.domain) if self.value else self.domain
            x = np.array(domain).reshape(-1, 1)
            y = np.array(p_domain).reshape(-1, 1)
            xx, yy = np.meshgrid(x, y, indexing='ij')

            constraint = self.agent.active_constraints[f'{self.agent.agent_id},{self.graph.parent}']
            self.X_ij = constraint.evaluate(xx, yy) + c_util_sum.T

            if self.X_ij_prev_norm is None or np.linalg.norm(self.X_ij) != self.X_ij_prev_norm:
                self.send_util_message(self.graph.parent, self.X_ij.tolist())
            self.X_ij_prev_norm = np.linalg.norm(self.X_ij)
        else:
            # set this agent's initial value
            j = int(np.argmin(x_i))
            self.value = self.domain[j]

            # get initial agent values for optimization
            initial_val = self.value
            if self.prev_initial_val is None or self.prev_initial_val != initial_val:
                agent_values = {self.agent.agent_id: self.value}
                for child in self.graph.children:
                    c_util = np.array(self.util_messages[child])
                    agent_values[child] = self.neighbor_domains[child][np.argmin(c_util[:, j])]

                self.nonlinear_optimization(agent_values)

                self.cpa[f'agent-{self.agent.agent_id}'] = self.value

                self.log.info(f'Cost is {self.cost}')

                # send value msgs to children
                self.log.info(f'children: {self.graph.children}')
                for child in self.graph.children:
                    self.send_value_message(child, {'cpa': self.cpa, 'initial-value': initial_val})
            self.prev_initial_val = initial_val

        self.util_received = False

    def receive_value_message(self, payload):
        self.log.info(f'Received value message: {payload}')
        data = payload['payload']
        sender = data['agent_id']
        value = data['value']

        # determine own value from parent's value
        if self.graph.is_parent(sender) and self.X_ij is not None:
            parent_cpa = value['cpa']
            parent_value = parent_cpa[f'agent-{sender}']
            parent_initial_value = value['initial-value']
            self.cpa = parent_cpa

            j = self.neighbor_domains[sender].index(parent_initial_value)
            x_i = self.X_ij[:, j].reshape(-1, )

            self.value = self.domain[int(x_i.argmin())]
            initial_val = self.value

            if self.prev_initial_val is None or self.prev_initial_val != initial_val:
                agent_values = {
                    self.agent.agent_id: self.value,
                    sender: parent_value,
                }

                k = self.domain.index(self.value)
                for child in self.graph.children:
                    c_util = np.array(self.util_messages[child])
                    agent_values[child] = self.neighbor_domains[child][np.argmin(c_util[:, k])]

                self.nonlinear_optimization(agent_values)

                self.cpa[f'agent-{self.agent.agent_id}'] = self.value

                self.log.info(f'Cost is {self.cost}')

                # send value msgs to children
                for child in self.graph.children:
                    self.send_value_message(child, {'cpa': self.cpa, 'initial-value': initial_val})
            self.prev_initial_val = initial_val

    def nonlinear_optimization(self, agent_values):
        # non-linear optimization
        for i in range(self.max_iter):
            grad_sum = 0
            for neighbor in self.graph.neighbors:
                constraint = self.agent.active_constraints[f'{self.agent.agent_id},{neighbor}']
                n_value = agent_values[neighbor]
                grad_sum += constraint.ddx(self.value, n_value)

                # child value optimization (parent value is already set)
                if self.graph.is_child(neighbor):
                    n_grad = constraint.ddy(self.value, n_value)
                    n_value = n_value - self.alpha * n_grad
                    agent_values[neighbor] = min(max(self.domain_lb, n_value), self.domain_ub)

            self.value = self.value - self.alpha * grad_sum
            self.value = min(max(self.domain_lb, self.value), self.domain_ub)
        self.agent.value_changes_count += 1
        self.params = agent_values
        self.calculate_and_report_cost(agent_values)
