import datetime
import math
import os
import time

import yaml
from paho.mqtt import client as mqtt


def connect_client(client, sync=True):
    # enable TLS
    client.tls_set(tls_version=mqtt.ssl.PROTOCOL_TLS)

    # set username and password
    client.username_pw_set(os.environ['HIVEMQ_USERNAME'], os.environ['HIVEMQ_PASSWORD'])

    # connect to HiveMQ Cloud
    if sync:
        client.connect(os.environ['HIVEMQ_CLOUD_ADDRESS'], int(os.environ['HIVEMQ_CLOUD_PORT']))
    else:
        client.connect_async(os.environ['HIVEMQ_CLOUD_ADDRESS'], int(os.environ['HIVEMQ_CLOUD_PORT']))


def get_agent_config(agent_id):
    with open('agent-config.yml') as f:
        data = yaml.load(f, Loader=yaml.FullLoader)
        for config in data:
            if config['agent']['id'] == agent_id:
                return config['agent']


def read_coefficients(file, prefix='cons='):
    def clean(s):
        return s.replace('(', '').replace(')', '').replace(' ', '')

    coeff_dict = {}
    if file:
        with open(file) as f:
            while True:
                line = f.readline()
                if line and line.startswith(prefix):
                    line = line.removeprefix(prefix)
                    cons = line.split('>')
                    if not cons[-1]:
                        cons = cons[:-1]
                    for con in cons:
                        parts = con.split(':')
                        key = clean(parts[0])
                        coefficients = [eval(v.strip()) for v in clean(parts[1]).split(',')]
                        coeff_dict[key] = coefficients
                    break
    return coeff_dict


def read_edges(file, prefix='edges='):
    nodes = []
    if file:
        with open(file) as f:
            while True:
                line = f.readline()
                if line and line.startswith(prefix):
                    line = line.removeprefix(prefix).replace(' ', ';').removesuffix('-')
                    for pair in line.split(';'):
                        nodes += [eval(n) for n in pair.split(',')]
                    break
        seen = set()
        set_add = seen.add
        nodes = [n for n in nodes if not (n in seen or set_add(n))]
    return nodes


def read_simulation_commands(filename):
    with open(f'simulations/{filename}') as f:
        while True:
            line = f.readline()
            if line and line.startswith('commands'):
                commands = line.removeprefix('commands=').removesuffix('\n').split(' ')
                break
    return commands


def set_timeout(timeout, callback, args):
    timeout = datetime.datetime.now() + datetime.timedelta(seconds=timeout)
    while timeout > datetime.datetime.now():
        callback(*args)


coefficients_dict = read_coefficients(None)
nodes_list = read_edges(None)


def reset_coefficients_dict_and_nodes_list(filename):
    global coefficients_dict
    global nodes_list

    coefficients_dict = read_coefficients(f'simulations/{filename}')
    nodes_list = read_edges(f'simulations/{filename}')

    print(f'coefficients_dict (len={len(coefficients_dict)}) '
          f'and nodes_list (len={len(nodes_list)}) have been successfully reset')


def time_since(since):
    s = time.time() - since
    m = math.floor(s / 60)
    s -= m * 60
    return '%dm %ds' % (m, s)


def time_diff(start_time):
    return (time.time() - start_time) * 1000
