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

shared_metrics_dict = {}
metrics_registry = []


def create_and_start_agent(agent_id):
    if dcop_algorithm:
        dcop_agent = agent.Agent(agent_id, dcop_algorithm,
                                 coefficients_dict=utils.coefficients_dict,
                                 metrics_dict=shared_metrics_dict,
                                 metrics_registry=metrics_registry)
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
    }.get(alg)


def test_msg_handler(msg):
    print('This is a test message handler: ', msg)


def add_agent_handler(msg):
    num_agents = msg['num_agents']
    log.info(f'Number of agents to add = {num_agents}')
    if config.USE_PREDEFINED_NETWORK:
        nodes = utils.nodes_list
        for _ in range(num_agents):
            agent_id = nodes.pop(0)
            evt = f'{ADD_AGENT}:{agent_id}'
            commands.append(evt)

            if nodes:
                _spawn_agent(agent_id)
                on_environment_event(evt)
    else:
        for i in range(num_agents):
            agent_id = len(agents)
            evt = f'{ADD_AGENT}:{agent_id}'
            commands.append(evt)

            _spawn_agent(agent_id=agent_id)
            log.info(f'agent {agent_id} added')
            on_environment_event(evt)

    # time.sleep(2)
    # client.publish(f'{messaging.FACTORY_COMMAND_CHANNEL}/',
    #                messaging.create_test_message({
    #                    'msg': 'this is a test message from factory',
    #                }))


def _spawn_agent(agent_id):
    t = threading.Thread(target=create_and_start_agent, args=(str(agent_id),))
    agent_id_to_thread[agent_id] = t
    t.start()


def create_and_start_metrics_agent():
    global metrics_agent
    metrics_agent = agent.MetricsAgent()
    metrics_agent()


def start_metrics_agent():
    t = threading.Thread(target=create_and_start_metrics_agent)
    t.start()


def remove_agent_handler(msg):
    if agents:
        for i in range(msg['num_agents']):
            selected_id = None
            selected_agent = None
            found = False

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

                selected_agent.shutdown()

                on_environment_event(evt)

                # agents.pop(selected_id)
                log.info(f'Removed agent {selected_agent}')


def change_constraint_handler(msg):
    if agents:
        for i in range(msg['num_agents']):
            coefficients = random.sample(range(1, 10), 3)
            selected_id = random.choice(list(agents.keys()))
            selected_agent = agents[selected_id]
            selected_neighbor = selected_agent.select_random_neighbor()

            evt = f'{CHANGE_CONSTRAINT}:{selected_id}-{selected_neighbor}:' + '-'.join([str(v) for v in coefficients])
            commands.append(evt)

            selected_agent.change_constraint(coefficients, selected_neighbor)

            on_environment_event(evt)


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
        handler = command_to_function.get(com.split(':')[0], None)
        if handler:
            log.info(f'Running command: {com}')
            handler({
                'num_agents': 1,
            })
            time.sleep(3)
    log.info('End of simulation')


def save_simulation_metrics_handler(msg):
    os.makedirs('metrics', exist_ok=True)
    label = dcop_algorithm.name + '-' + date_to_string()
    metrics_file = os.path.join('metrics/', f'{label}.csv')
    to_csv(metrics_file)
    log.info(f'Metrics saved at {metrics_file}')


def dcop_done_handler(msg):
    data = msg['payload']
    agent_id = data.pop('agent_id')
    shared_metrics_dict[agent_id] = data
    log.info(f'Done dict: {shared_metrics_dict}')


def date_to_string():
    return datetime.datetime.now().strftime('%m-%d-%Y-%H-%M-%S')


def on_environment_event(evt):
    time.sleep(1)
    while len(agents) > 1 and ((len(shared_metrics_dict) != len(set(metrics_registry))) or not metrics_registry):
        time.sleep(1)
        # print(shared_metrics_dict)
        # print(metrics_registry)

    global last_event, last_event_date_time
    last_event = evt
    last_event_date_time = datetime.datetime.now()

    agents_cost = {}
    agents_num_msgs = {}
    agents_time = {}

    for node in shared_metrics_dict:
        metrics = shared_metrics_dict[node]
        agents_time[node] = metrics['time']
        agents_cost[node] = metrics['cost']
        agents_num_msgs[node] = metrics['num_messages']

    costs_per_event[evt] = sum(agents_cost.values())
    num_mgs_per_event[evt] = sum(agents_num_msgs.values())
    time_per_event[evt] = sum(agents_time.values())

    log.info(f'Shared metrics dict: {shared_metrics_dict}')
    shared_metrics_dict.clear()
    metrics_registry.clear()
    log.info('Shared metrics dict cleared')


def to_csv(path):
    df = pd.DataFrame({
        'event': list(costs_per_event.keys()),
        'type': [evt.split(':')[0] for evt in costs_per_event.keys()],
        'cost': list(costs_per_event.values()),
        'message_count': list(num_mgs_per_event.values()),
        'time': list(time_per_event.values()),
    })
    df.to_csv(path, index=False)


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
