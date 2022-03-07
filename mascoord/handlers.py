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

count = 0

commands = []

ADD_AGENT = 'add_agent'
REMOVE_AGENT = 'remove_agent'
CHANGE_CONSTRAINT = 'change_constraint'
last_event = None
last_event_date_time = None
dcop_algorithm = None
metrics_agent = None


def create_and_start_agent(agent_id):
    if dcop_algorithm:
        dcop_agent = agent.Agent(agent_id, dcop_algorithm, coefficients_dict=utils.coefficients_dict)
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


def check_inter_event_delay():
    if last_event_date_time:
        return last_event_date_time + datetime.timedelta(seconds=config.EVENT_DELAY) < datetime.datetime.now()
    else:
        return True


def event_delay():
    pass
    # while not check_inter_event_delay():
    #     pass


def add_agent_handler(msg):
    event_delay()

    global count

    num_agents = msg['num_agents']
    if config.USE_PREDEFINED_NETWORK:
        nodes = utils.nodes_list
        for _ in range(num_agents):
            if nodes:
                _spawn_agent(nodes.pop(0))
    else:
        for _ in range(num_agents):
            evt = f'{ADD_AGENT}:{count}'
            commands.append(evt)
            on_environment_event(evt)

            _spawn_agent(agent_id=count)

            count += 1

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
    event_delay()

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
                on_environment_event(evt)

                selected_agent.shutdown()
                # agents.pop(selected_id)
                log.info(f'Removed agent {selected_agent}')


def change_constraint_handler(msg):
    event_delay()
    commands.append(CHANGE_CONSTRAINT)
    coefficients = random.sample(range(1, 10), 3)

    if agents:
        selected_id = random.choice(list(agents.keys()))
        selected_agent = agents[selected_id]
        selected_neighbor = selected_agent.select_random_neighbor()

        evt = f'{CHANGE_CONSTRAINT}:{selected_id}-{selected_neighbor}:' + '-'.join([str(v) for v in coefficients])
        commands.append(evt)
        on_environment_event(evt)

        selected_agent.change_constraint(coefficients, selected_neighbor)


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
    if metrics_agent:
        metrics_agent.to_csv(metrics_file)
        log.info(f'Metrics saved at {metrics_file}')


def date_to_string():
    return datetime.datetime.now().strftime('%m-%d-%Y-%H-%M-%S')


def on_environment_event(evt):
    global last_event, last_event_date_time
    last_event = evt
    last_event_date_time = datetime.datetime.now()

    if metrics_agent:
        metrics_agent.set_event(last_event)

    for node in agents.values():
        node.clear_messages_count()


directory = {
    messaging.TEST: test_msg_handler,
    messaging.ADD_AGENT: add_agent_handler,
    messaging.REMOVE_AGENT: remove_agent_handler,
    messaging.CHANGE_CONSTRAINT: change_constraint_handler,
    messaging.REQUEST_AGENT_REPORT: agent_report_handler,
    messaging.SAVE_SIMULATION: save_simulation_handler,
    messaging.PLAY_SIMULATION: play_simulation_handler,
    messaging.SAVE_METRICS: save_simulation_metrics_handler,
}
