import random

from mascoord.src import config, messaging
from mascoord.src.algorithms.dcop import DCOP
from mascoord.src.envs.mobile_sensing import GridWorld


class CoCoA(DCOP):
    """
    Implementation of the CoCoA algorithm to work with dynamic interaction graph
    """
    traversing_order = 'top-down'
    name = 'cocoa'

    IDLE = 'IDLE'
    DONE = 'DONE'
    ACTIVE = 'ACTIVE'
    HOLD = 'HOLD'

    def __init__(self, *args, **kwargs):
        super(CoCoA, self).__init__(*args, **kwargs)
        self.state = self.IDLE
        self.neighbor_states = {}
        self.cost_map = {}

    def on_time_step_changed(self):
        self.state = self.IDLE
        self.cost_map.clear()
        self.value = None
        self.neighbor_states.clear()

    def execute_dcop(self):
        self.log.info('Initiating CoCoA')

        self.value = None

        self.state = self.ACTIVE
        self.report_state_change_to_dashboard()

        if len(self.graph.neighbors) == 0:
            self.select_random_value()
        else:
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

    def select_value(self):
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
        if config.shared_config.optimization_op == 'max':
            op = max
        else:
            op = min
        self.value = op(total_cost_dict, key=lambda d: total_cost_dict[d]['cost'])
        best_params = total_cost_dict[self.value]['params']
        self.log.info(f'Best params: {best_params}, {self.value}')

        # update agent
        self.cpa[f'agent-{self.agent.agent_id}'] = self.value
        self.state = self.DONE
        self.report_state_change_to_dashboard()

        # update children
        for child in self.graph.neighbors:
            self.send_update_state_message(child, {
                'agent_id': self.agent.agent_id,
                'state': self.state,
                'cpa': self.cpa,
            })

        self.cost_map.clear()
        self.params = best_params
        self.value_selection(self.value)
        # self.calculate_and_report_cost(best_params)

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

        cost_map = []
        for value1 in sender_domain:
            min_cost = float('inf')
            entry = None

            # if this agent has already set its value then keep it fixed
            iter_list = [self.value] if self.value and sender in self.graph.children else self.domain

            for value2 in iter_list:
                cost = GridWorld.constraint_evaluation(
                    sender=sender,
                    agent_values={
                        sender: value1,
                        self.agent.agent_id: value2,
                    }
                )
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

        if data['state'] == self.DONE and self.value is None:
            self.cpa = data['cpa']
            self.execute_dcop()

    def __str__(self):
        return 'c-cocoa'
