import random

from mascoord.src import messaging


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
        self.agent.channel.basic_publish(exchange=messaging.COMM_EXCHANGE,
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
            self.select_value()

    def select_random_value(self):
        self.log.info('Selecting random value...')
        self.value = random.choice(self.domain)
        self.value_selection(self.value)

    def value_selection(self, val):
        self.agent.channel.basic_publish(
            exchange=messaging.COMM_EXCHANGE,
            routing_key=f'{messaging.SIM_ENV_CHANNEL}',
            body=messaging.create_value_selected_message({
                'agent_id': self.agent.agent_id,
                'cpa': self.cpa,
                'value': val,
                'metrics': {

                }
            })
        )

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

    def select_value(self):
        """
        Implement this method to determine the agent's value.
        """
        pass

    def on_time_step_changed(self):
        ...

    def __str__(self):
        return 'dcop'
