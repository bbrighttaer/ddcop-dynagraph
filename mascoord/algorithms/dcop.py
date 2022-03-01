import random

from mascoord import config
from mascoord import messaging


class CCoCoA:
    """
    Implementation of the C-CoCoA algorithm to work with dynamic interaction graph
    """

    IDLE = 'IDLE'
    DONE = 'DONE'
    ACTIVE = 'ACTIVE'
    HOLD = 'HOLD'

    def __init__(self, agent, num_discrete_points=3, domain_lb=-50, domain_ub=50):
        self.log = agent.log
        self.agent = agent

        self.graph = self.agent.graph
        self.neighbor_states = {}

        self.domain = random.sample(range(domain_lb, domain_ub), num_discrete_points)
        self.domain_lb = domain_lb
        self.domain_ub = domain_ub
        self.state = self.IDLE
        self.value = None
        self.alpha = config.LEARNING_RATE
        self.max_iter = 100
        self.cpa = {}
        self.cost_map = {}
        self.cost = 0

    def reset(self, *args, **kwargs):
        self.log.info('Resetting...')

        self.state = self.IDLE
        self.value = None

        # inform dashboard
        self.graph.channel.basic_publish(exchange=messaging.COMM_EXCHANGE,
                                         routing_key=f'{messaging.MONITORING_CHANNEL}',
                                         body=messaging.create_agent_reset_message({
                                             'agent_id': self.agent.agent_id,
                                             'state': self.state,
                                         }))

        # inform children
        # for child in self.graph.children:
        #     self.graph.channel.basic_publish(exchange=messaging.COMM_EXCHANGE,
        #                                      routing_key=f'{messaging.AGENTS_CHANNEL}.{child}',
        #                                      body=messaging.create_agent_reset_message({
        #                                          'agent_id': self.agent.agent_id,
        #                                      }))
        self.log.info('Reset completed.')

    def resolve_agent_value(self):
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
                constraint = self.agent.active_constraints[f'{self.agent.agent_id},{neighbor}']
                n_value = best_params[neighbor]
                grad_sum += constraint.ddx.evaluate({'x': self.value, 'y': n_value})

                # neighbor value optimization
                n_grad = constraint.ddy.evaluate({'x': self.value, 'y': n_value})
                n_value = n_value - self.alpha * n_grad
                best_params[neighbor] = min(max(self.domain_lb, n_value), self.domain_ub)

            self.value = self.value - self.alpha * grad_sum

            # clip to be in domain
            self.value = min(max(self.domain_lb, self.value), self.domain_ub)

        # compute final cost
        self.cost = 0
        for neighbor in self.graph.neighbors:
            constraint = self.agent.active_constraints[f'{self.agent.agent_id},{neighbor}']
            n_value = best_params[neighbor]
            self.cost += constraint.equation.evaluate({'x': self.value, 'y': n_value})
        self.log.info(f'Cost is {self.cost}')

        # update agent
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

        # if this agent is a leaf node then it should report the cpa to dashboard
        if not self.agent.graph.children:
            self.send_cpa_to_dashboard()
            from mascoord.handlers import MetricsTable
            MetricsTable.update_metrics()

        self.cost_map.clear()

    def run_algorithm(self):
        if self.state == self.ACTIVE \
                and self.graph.neighbors \
                and len(self.cost_map) == len(self.graph.neighbors):
            self.resolve_agent_value()

    # def change_constraints(self):
    #     """simulates constraint change at the agent level"""
    #     # reset agent on constraint change
    #     self.reset()
    #     # self.initiate_dcop_execution()

    def report_state_change_to_dashboard(self):
        self.graph.channel.basic_publish(exchange=messaging.COMM_EXCHANGE,
                                         routing_key=f'{messaging.MONITORING_CHANNEL}',
                                         body=messaging.create_agent_state_changed_message({
                                             'agent_id': self.agent.agent_id,
                                             'state': self.state,
                                         }))

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

    def receive_cost_message(self, payload):
        data = payload['payload']
        sender = data['agent_id']
        cost_map = data['cost_map']
        self.cost_map[sender] = cost_map

    def receive_inquiry_message(self, payload):
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
                iter_list = [self.value] if self.value and sender in self.graph.children else self.domain

                for value2 in iter_list:
                    cost = constraint.equation.evaluate({'x': value2, 'y': value1})
                    if cost < min_cost:
                        entry = (value1, value2, cost)
                        min_cost = cost

                cost_map.append(entry)

            # send cost map (via cost message) to requesting agent
            self.send_cost_message(sender, {'agent_id': self.agent.agent_id, 'cost_map': cost_map})

    def receive_update_state_message(self, payload):
        data = payload['payload']
        sender = data['agent_id']
        if sender in self.graph.neighbors:
            self.neighbor_states[str(sender)] = data['state']

        if data['state'] == self.DONE:
            self.cpa = data['cpa']
            self.initiate_dcop_execution()

    def initiate_dcop_execution(self):
        self.log.info('Initiating DCOP')

        self.state = self.ACTIVE
        self.report_state_change_to_dashboard()

        for agent in self.graph.neighbors:
            if agent in self.graph.children:
                self.send_update_state_message(agent, {
                    'agent_id': self.agent.agent_id,
                    'state': self.state,
                })
            self.send_inquiry_message(agent, {
                'agent_id': self.agent.agent_id,
                'domain': self.domain,
            })

    def send_cpa_to_dashboard(self):
        self.graph.channel.basic_publish(exchange=messaging.COMM_EXCHANGE,
                                         routing_key=f'{messaging.MONITORING_CHANNEL}',
                                         body=messaging.create_cpa_report_message({
                                             'agent_id': self.agent.agent_id,
                                             'cpa': self.cpa
                                         }))

    def request_states_of_neighbors(self):
        for agent in self.graph.neighbors:
            self.graph.channel.basic_publish(exchange=messaging.COMM_EXCHANGE,
                                             routing_key=f'{messaging.AGENTS_CHANNEL}.{agent}',
                                             body=messaging.create_state_request_message({
                                                 'agent_id': self.agent.agent_id,
                                             }))

    def receive_state_request(self, payload):
        data = payload['payload']
        sender = data['agent_id']

        self.graph.channel.basic_publish(exchange=messaging.COMM_EXCHANGE,
                                         routing_key=f'{messaging.AGENTS_CHANNEL}.{sender}',
                                         body=messaging.create_state_request_response_message({
                                             'agent_id': self.agent.agent_id,
                                             'state': self.state
                                         }))

    def receive_state_request_response(self, payload):
        data = payload['payload']
        sender = data['agent_id']
        if sender in self.graph.neighbors:
            self.neighbor_states[sender] = data['state']
