import datetime
import os
import random
import threading
import time

import pandas as pd

import agent
import config
import logger
import messaging
import utils
from mascoord.algorithms.dcop import DCOP, CSDPOP

agents = {}
agent_id_to_thread = {}

log = logger.get_logger('factory-handler')

commands = []

ADD_AGENT = 'add_agent'
REMOVE_AGENT = 'remove_agent'
CHANGE_CONSTRAINT = 'change_constraint'
last_event = None
last_event_date_time = None
dcop_algorithm = None
metrics_agent = None

costs_per_event = {}
num_mgs_per_event = {}
time_per_event = {}

domain_size = 2


def create_and_start_agent(agent_id):
    if dcop_algorithm:
        dcop_agent = agent.Agent(agent_id, dcop_algorithm,
                                 coefficients_dict=utils.coefficients_dict,
                                 domain_size=domain_size,
                                 metrics=metrics)
        agents[agent_id] = dcop_agent
        dcop_agent()
    else:
        log.error('DCOP algorithm must be provided before creating an agent')


def set_dcop_algorithm(alg):
    from mascoord.algorithms.dcop import CCoCoA, SDPOP
    global dcop_algorithm

    dcop_algorithm = {
        'c-cocoa': CCoCoA,
        'sdpop': SDPOP,
        'c-sdpop': CSDPOP,
    }.get(alg, DCOP)


def set_domain_size(size):
    global domain_size
    domain_size = size


def test_msg_handler(msg):
    print('This is a test message handler: ', msg)


def add_agent_handler(msg):
    num_agents = msg['num_agents']
    log.info(f'Number of agents to add = {num_agents}')
    if config.USE_PREDEFINED_NETWORK:
        nodes = utils.nodes_list
        for _ in range(num_agents):
            agent_id = nodes[len(agents)]
            evt = f'{ADD_AGENT}:{agent_id}'
            commands.append(evt)

            metrics.last_event = evt
            metrics.last_event_date_time = datetime.datetime.now()

            _spawn_agent(agent_id)

            time.sleep(config.COMM_EXEC_DELAY_IN_SECONDS)
    else:
        for i in range(num_agents):
            agent_id = len(agents)
            evt = f'{ADD_AGENT}:{agent_id}'
            commands.append(evt)

            metrics.last_event = evt
            metrics.last_event_date_time = datetime.datetime.now()

            _spawn_agent(agent_id=agent_id)

            time.sleep(config.COMM_EXEC_DELAY_IN_SECONDS)

    # time.sleep(2)
    # client.publish(f'{messaging.FACTORY_COMMAND_CHANNEL}/',
    #                messaging.create_test_message({
    #                    'msg': 'this is a test message from factory',
    #                }))


def _spawn_agent(agent_id):
    t = threading.Thread(target=create_and_start_agent, args=(str(agent_id),))
    agent_id_to_thread[agent_id] = t
    t.start()


def remove_agent_handler(msg):
    if agents:
        for i in range(msg['num_agents']):
            selected_id = None
            selected_agent = None
            found = False

            if config.USE_PREDEFINED_NETWORK:
                selected_id = msg['agent_id']
                selected_agent = agents[selected_id]
            else:
                timeout = 0
                while not found and timeout <= len(agents):
                    selected_id = random.choice(list(agents.keys()))
                    selected_agent = agents[selected_id]
                    found = not selected_agent.terminate
                    timeout += 1

            if selected_id and selected_agent:
                log.info(f'Removing agent {selected_agent}')

                evt = f'{REMOVE_AGENT}:{selected_id}'
                commands.append(evt)

                metrics.last_event = evt
                metrics.last_event_date_time = datetime.datetime.now()

                selected_agent.shutdown()

                time.sleep(config.COMM_EXEC_DELAY_IN_SECONDS)

                # agents.pop(selected_id)
                log.info(f'Removed agent {selected_agent}')


def change_constraint_handler(msg):
    if agents:
        for i in range(msg['num_agents']):
            coefficients = [round(random.uniform(0, 1), 3) for _ in range(3)]
            selected_id = random.choice(list(agents.keys()))
            selected_agent = agents[selected_id]
            selected_neighbor = selected_agent.select_random_neighbor()

            evt = f'{CHANGE_CONSTRAINT}:{selected_id}-{selected_neighbor}:' + '-'.join([str(v) for v in coefficients])
            commands.append(evt)

            metrics.last_event = evt
            metrics.last_event_date_time = datetime.datetime.now()

            selected_agent.change_constraint(coefficients, selected_neighbor)

            time.sleep(config.COMM_EXEC_DELAY_IN_SECONDS)


def agent_report_handler(msg):
    if agents and 'agent_id' in msg and msg['agent_id'] in agents:
        selected_agent = agents[msg['agent_id']]
        selected_agent.send_report()


def save_simulation_handler(msg):
    label = datetime.datetime.now().timestamp()
    base_path = f'simulations/'
    os.makedirs(base_path, exist_ok=True)

    lines = [f'nodes={len(agents)}\n', f'commands={" ".join(commands)}\n']

    edges = []
    cons = []
    domains = []
    for node in agents.values():
        # edges
        e = node.get_child_edges_history()
        if e:
            edges.extend(e)

        # cons
        c = node.get_child_connections_history()
        if c:
            cons.extend(c)

        # agent domain
        domain = [str(v) for v in node.domain]
        domains.append(str(node.agent_id) + ':' + ','.join(domain))

    lines.append(f'edges={" ".join(edges)}\n')
    lines.append(f'cons={">".join(cons)}\n')
    lines.append(f'domains={" ".join(domains)}\n')

    sim_file = os.path.join(base_path, f'{label}.sim')
    with open(sim_file, 'w') as file:
        file.writelines(lines)

    log.info(f'Simulation saved at {sim_file}')


def play_simulation_handler(msg):
    filename = msg['simulation']
    utils.reset_coefficients_dict_and_nodes_list(filename)
    sim_commands = utils.read_simulation_commands(filename)

    command_to_function = {
        ADD_AGENT: add_agent_handler,
        REMOVE_AGENT: remove_agent_handler,
        CHANGE_CONSTRAINT: change_constraint_handler,
    }

    for com in sim_commands:
        split = com.split(':')
        handler = command_to_function.get(split[0], None)
        if handler:
            log.info(f'Running command: {com}')
            handler({
                'num_agents': 1,
                'agent_id': split[1],
            })
    log.info('End of simulation')


def save_simulation_metrics_handler(msg=None):
    os.makedirs('metrics', exist_ok=True)
    label = f'{dcop_algorithm.name}-d{domain_size}Lr{config.LEARNING_RATE}'
    metrics_file = os.path.join('metrics/', f'{label}.csv')
    metrics.to_csv(metrics_file)
    log.info(f'Metrics saved at {metrics_file}')


def dcop_done_handler(msg):
    pass
    # record_metrics()
    # data = msg['payload']
    # agent_id = data.pop('agent_id')
    # shared_metrics_dict[agent_id] = data
    # log.info(f'Done dict: {shared_metrics_dict}')


def current_datetime():
    return datetime.datetime.now().strftime('%m-%d-%Y-%H-%M-%S')


class MetricsTable:

    def __init__(self):
        self.cost = {}
        self.edge_cost_per_event = {}
        self.edge_cost_per_agent = {}
        self.message_count = {}
        self.num_changes_per_event = {}
        self.num_agents_per_event = {}

        self.announce_msg_count = {}
        self.announce_res_msg_count = {}
        self.announce_resp_msg_ack_count = {}
        self.set_network_count = {}
        self.ping_msg_count = {}
        self.ping_msg_resp_count = {}
        self.network_update_comp_count = {}
        self.constraint_changed_count = {}

        self.last_event = None
        self.last_event_date_time = None

    def update_metrics(self):
        messages_count = 0
        total_cost = 0
        num_changes = 0
        num_active_agents = 0
        announce_msg_count = 0
        announce_res_msg_count = 0
        announce_resp_msg_ack_count = 0
        set_network_count = 0
        ping_msg_count = 0
        ping_msg_resp_count = 0
        network_update_comp_count = 0
        constraint_changed_count = 0

        for node in agents.values():
            if not node.terminate:
                num_active_agents += 1
                messages_count += node.messages_count
                total_cost += node.cost
                num_changes += node.value_changes_count

                announce_msg_count += node.announce_msg_count
                announce_res_msg_count += node.announce_res_msg_count
                announce_resp_msg_ack_count += node.announce_resp_msg_ack_count
                set_network_count += node.set_network_count
                ping_msg_count += node.ping_msg_count
                ping_msg_resp_count += node.ping_msg_resp_count
                network_update_comp_count += node.network_update_comp_count
                constraint_changed_count += node.constraint_changed_count

                node.set_edge_costs()

        self.cost[self.last_event] = total_cost
        self.edge_cost_per_event[self.last_event] = sum(self.edge_cost_per_agent.values())
        self.message_count[self.last_event] = messages_count
        self.num_changes_per_event[self.last_event] = num_changes
        self.num_agents_per_event[self.last_event] = num_active_agents

        self.announce_msg_count[self.last_event] = announce_msg_count
        self.announce_res_msg_count[self.last_event] = announce_res_msg_count
        self.announce_resp_msg_ack_count[self.last_event] = announce_resp_msg_ack_count
        self.set_network_count[self.last_event] = set_network_count
        self.ping_msg_count[self.last_event] = ping_msg_count
        self.ping_msg_resp_count[self.last_event] = ping_msg_resp_count
        self.network_update_comp_count[self.last_event] = network_update_comp_count
        self.constraint_changed_count[self.last_event] = constraint_changed_count

        save_simulation_metrics_handler()

    def update_edge_cost(self, agent1, agent2, cost):
        k1 = agent1
        k2 = agent2
        if agent2 < k1:
            k1 = agent2
            k2 = agent1
        self.edge_cost_per_agent[f'{k1}-{k2}'] = cost

    def to_csv(self, path):
        df = pd.DataFrame({
            'event': list(self.cost.keys()),
            'type': [evt.split(':')[0] for evt in self.cost.keys()],
            'num_agents': list(self.num_agents_per_event.values()),
            'node_cost': list(self.cost.values()),
            'edge_cost': list(self.edge_cost_per_event.values()),
            'message_count': list(self.message_count.values()),
            'num_changes': list(self.num_changes_per_event.values()),

            # dynamic graph stats
            'announce_msg_count': list(self.announce_msg_count.values()),
            'announce_res_msg_count': list(self.announce_res_msg_count.values()),
            'announce_resp_msg_ack_count': list(self.announce_resp_msg_ack_count.values()),
            'set_network_count': list(self.set_network_count.values()),
            'ping_msg_count': list(self.ping_msg_count.values()),
            'ping_msg_resp_count': list(self.ping_msg_resp_count.values()),
            'network_update_comp_count': list(self.network_update_comp_count.values()),
            'constraint_changed_count': list(self.constraint_changed_count.values()),
        })
        df.to_csv(path, index=False)

    def get_agent_value(self, agent_id):
        if agent_id in agents:
            return agents[agent_id].value
        else:
            return None


directory = {
    messaging.TEST: test_msg_handler,
    messaging.ADD_AGENT: add_agent_handler,
    messaging.REMOVE_AGENT: remove_agent_handler,
    messaging.CHANGE_CONSTRAINT: change_constraint_handler,
    messaging.REQUEST_AGENT_REPORT: agent_report_handler,
    messaging.SAVE_SIMULATION: save_simulation_handler,
    messaging.PLAY_SIMULATION: play_simulation_handler,
    messaging.SAVE_METRICS: save_simulation_metrics_handler,
    messaging.DCOP_DONE: dcop_done_handler,
}

metrics = MetricsTable()
