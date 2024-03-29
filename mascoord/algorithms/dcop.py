import random

import numpy as np

from mascoord import config
from mascoord import messaging


class DCOP:
    """
    Parent class for DCOP algorithms
    """
    traversing_order = None
    name = 'dcop-base'

    def __init__(self, agent, num_discrete_points, domain_lb=-50, domain_ub=50):
        self.log = agent.log
        self.agent = agent
        self.graph = self.agent.graph
        self.domain = random.sample(range(domain_lb, domain_ub), num_discrete_points)
        # self.domain = [-10.0, 5.0, 12.0] # random.sample(range(domain_lb, domain_ub), num_discrete_points)
        # self.domain = [-43, 21, 49, 8, 19, -24, 24, -2, -32, 33, -42, -3, 10, -31, -40, -16, 40, 25, 4, -8, -38,
        #                -21, -33, 34, 46, -5, 13, 45, -39, -49, -12, -35, -44, 2, -30, -9, 1, -15, -25, 16]
        self.domain_lb = domain_lb
        self.domain_ub = domain_ub
        self.state = None
        self.value = None
        self.cpa = {}
        self.cost = 0
        self.params = {}

    def calculate_and_report_cost(self, best_params):
        """
        compute final cost
        """
        self.cost = 0
        for neighbor in self.graph.neighbors:
            constraint = self.agent.active_constraints[f'{self.agent.agent_id},{neighbor}']
            n_value = best_params[neighbor]
            self.cost += constraint.evaluate(self.value, n_value)
        self.log.info(f'Cost is {self.cost}')

        self.collect_metrics()

    def set_edge_costs(self):
        try:
            if self.params:
                for neighbor in self.graph.neighbors:
                    constraint = self.agent.active_constraints[f'{self.agent.agent_id},{neighbor}']
                    n_value = self.params[neighbor]
                    if n_value:
                        cost = constraint.evaluate(self.value, n_value)
                        self.agent.metrics.update_edge_cost(self.agent.agent_id, neighbor, cost)
        except:
            pass

    def collect_metrics(self):
        self.log.info('DCOP done')
        # if this agent is a leaf node then it should report the cpa to dashboard
        if not self.agent.graph.children:
            self.send_cpa_to_dashboard()
        self.agent.metrics.update_metrics()

    def send_cpa_to_dashboard(self):
        self.graph.channel.basic_publish(exchange=messaging.COMM_EXCHANGE,
                                         routing_key=f'{messaging.MONITORING_CHANNEL}',
                                         body=messaging.create_cpa_report_message({
                                             'agent_id': self.agent.agent_id,
                                             'cpa': self.cpa
                                         }))

    def resolve_value(self):
        """
        Resolves an agent's value.
        """
        if self.can_resolve_agent_value():
            self.calculate_value()

    # ---------------- Algorithm specific methods ----------------------- #

    def connection_extra_args(self) -> dict:
        """
        Provides any custom arguments to be sent when the agent connects to another agent
        """
        return {'alg': self.name}

    def receive_extra_args(self, sender, args):
        """
        Callback for handling extra args received from a new connection
        """
        pass

    def agent_disconnection_callback(self, agent):
        """
        Handles agent disconnection side-effects
        """
        pass

    def execute_dcop(self):
        """
        This is the entry method for executing the DCOP algorithm.
        Operations that should happen before the agent calls `resolve_value` should be placed here.
        """
        pass

    def can_resolve_agent_value(self) -> bool:
        """
        Checks if the DCOP algorithm is ready to resolve an agent's value.
        If True, the dcop algorithm will execute the `calculate_value` method.
        """
        return False

    def calculate_value(self):
        """
        Implement this method to determine the agent's value.
        """
        pass

    def __str__(self):
        return 'dcop'


class CCoCoA(DCOP):
    """
    Implementation of the C-CoCoA algorithm to work with dynamic interaction graph
    """
    traversing_order = 'top-down'
    name = 'c-cocoa'

    IDLE = 'IDLE'
    DONE = 'DONE'
    ACTIVE = 'ACTIVE'
    HOLD = 'HOLD'

    def __init__(self, *args, **kwargs):
        super(CCoCoA, self).__init__(*args, **kwargs)
        self.state = self.IDLE
        self.alpha = config.LEARNING_RATE
        self.max_iter = 100
        self.neighbor_states = {}
        self.cost_map = {}

    def execute_dcop(self):
        self.log.info('Initiating C-CoCoA')

        self.value = None

        self.state = self.ACTIVE
        self.report_state_change_to_dashboard()

        for agent in self.graph.neighbors:
            # if agent in self.graph.children:
            #     self.send_update_state_message(agent, {
            #         'agent_id': self.agent.agent_id,
            #         'state': self.state,
            #     })
            self.send_inquiry_message(agent, {
                'agent_id': self.agent.agent_id,
                'domain': self.domain,
            })

    def calculate_value(self):
        """
        when value is set, send an UpdateStateMessage({agent_id, state=DONE, value})
        :return:
        """
        total_cost_dict = {}

        # perform dcop computations
        self.log.info(f'Cost map: {self.cost_map}')
        for sender in self.cost_map:
            for val_self, val_sender, cost in self.cost_map[sender]:
                if val_self in total_cost_dict:
                    total_cost_dict[val_self]['cost'] += cost
                    total_cost_dict[val_self]['params'][sender] = val_sender
                else:
                    total_cost_dict[val_self] = {
                        'cost': cost,
                        'params': {
                            sender: val_sender,
                        }
                    }
        self.log.info(f'Total cost dict: {total_cost_dict}')
        self.value = min(total_cost_dict, key=lambda d: total_cost_dict[d]['cost'])
        best_params = total_cost_dict[self.value]['params']
        self.log.info(f'Best params: {best_params}, {self.value}')

        # perform non-linear optimization
        for i in range(self.max_iter):
            grad_sum = 0
            for neighbor in self.graph.neighbors:
                if neighbor in best_params:  # needed due to async nature of execution
                    constraint = self.agent.active_constraints[f'{self.agent.agent_id},{neighbor}']
                    n_value = best_params[neighbor]
                    grad_sum += constraint.ddx(self.value, n_value)

                    # neighbor value optimization
                    n_grad = constraint.ddy(self.value, n_value)
                    n_value = n_value - self.alpha * n_grad
                    best_params[neighbor] = min(max(self.domain_lb, n_value), self.domain_ub)

            self.value = self.value - self.alpha * grad_sum

            # clip to be in domain
            self.value = min(max(self.domain_lb, self.value), self.domain_ub)

        # update agent
        self.agent.value_changes_count += 1
        self.cpa[f'agent-{self.agent.agent_id}'] = self.value
        self.state = self.DONE
        self.report_state_change_to_dashboard()

        # update children
        for child in self.graph.children:
            self.send_update_state_message(child, {
                'agent_id': self.agent.agent_id,
                'state': self.state,
                'cpa': self.cpa,
            })

        self.cost_map.clear()
        self.params = best_params
        self.calculate_and_report_cost(best_params)

    def can_resolve_agent_value(self) -> bool:
        return self.state == self.ACTIVE \
               and self.graph.neighbors \
               and len(self.cost_map) == len(self.graph.neighbors)

    def send_update_state_message(self, recipient, data):
        self.graph.channel.basic_publish(exchange=messaging.COMM_EXCHANGE,
                                         routing_key=f'{messaging.AGENTS_CHANNEL}.{recipient}',
                                         body=messaging.create_update_state_message(data))

    def send_inquiry_message(self, recipient, data):
        self.graph.channel.basic_publish(exchange=messaging.COMM_EXCHANGE,
                                         routing_key=f'{messaging.AGENTS_CHANNEL}.{recipient}',
                                         body=messaging.create_inquiry_message(data))

    def send_cost_message(self, recipient, data):
        self.graph.channel.basic_publish(exchange=messaging.COMM_EXCHANGE,
                                         routing_key=f'{messaging.AGENTS_CHANNEL}.{recipient}',
                                         body=messaging.create_cost_message(data))

    def report_state_change_to_dashboard(self):
        self.graph.channel.basic_publish(exchange=messaging.COMM_EXCHANGE,
                                         routing_key=f'{messaging.MONITORING_CHANNEL}',
                                         body=messaging.create_agent_state_changed_message({
                                             'agent_id': self.agent.agent_id,
                                             'state': self.state,
                                         }))

    def receive_cost_message(self, payload):
        self.log.info(f'Received cost message: {payload}')
        data = payload['payload']
        sender = data['agent_id']
        cost_map = data['cost_map']
        self.cost_map[sender] = cost_map

    def receive_inquiry_message(self, payload):
        self.log.info(f'Received inquiry message: {payload}')
        data = payload['payload']
        sender = data['agent_id']
        sender_domain = data['domain']

        key = f'{self.agent.agent_id},{sender}'
        if key in self.agent.active_constraints:
            constraint = self.agent.active_constraints[f'{self.agent.agent_id},{sender}']
            cost_map = []
            for value1 in sender_domain:
                min_cost = float('inf')
                entry = None

                # if this agent has already set its value then keep it fixed
                # iter_list = [self.value] if self.value and sender in self.graph.children else self.domain

                for value2 in self.domain:
                    cost = constraint.evaluate(value2, value1)
                    if cost < min_cost:
                        entry = (value1, value2, cost)
                        min_cost = cost

                cost_map.append(entry)

            # send cost map (via cost message) to requesting agent
            self.send_cost_message(sender, {'agent_id': self.agent.agent_id, 'cost_map': cost_map})

    def receive_update_state_message(self, payload):
        self.log.info(f'Received update state message: {payload}')
        data = payload['payload']
        sender = data['agent_id']
        if sender in self.graph.neighbors:
            self.neighbor_states[str(sender)] = data['state']

        if data['state'] == self.DONE:
            self.cpa = data['cpa']
            self.execute_dcop()

    def __str__(self):
        return 'c-cocoa'


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

    def calculate_value(self):
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


class CSDPOP(SDPOP):
    """
    A continuous domain analogue of the SDPOP algorithm
    """
    name = 'c-sdpop'

    def __init__(self, *args, **kwargs):
        super(CSDPOP, self).__init__(*args, **kwargs)
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
