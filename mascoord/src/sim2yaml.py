import argparse
import os.path

import oyaml as yaml


def parse_constraint(con_str):
    # sample: (0,1):(1,1,1)
    agents_str, coefficients_str = con_str.split(':')
    x, y = agents_str.replace('(', '').replace(')', '').split(',')
    a, b, c = coefficients_str.replace('(', '').replace(')', '').split(',')
    c1 = f'{a} * var{x}^2 + {b} * var{x} * var{y} + {c} * var{y}^2'
    c2 = f'{c} * var{y}^2 + {b} * var{y} * var{x} + {a} * var{x}^2'
    return c1, c2


def main(args):
    lines_4_config = {}
    with open(args.file, 'r') as f:
        line = f.readline()
        while line:
            kv = line.split('=')
            lines_4_config[kv[0]] = kv[1].strip()
            line = f.readline()

    yaml_dict = {
        'name': args.name,
        'objective': 'min',
    }

    # domains
    domains = {}
    domain_info = lines_4_config['domains'].split(' ')
    agent_ids = []
    for domain_str in domain_info:
        agent_id, dvals = domain_str.split(':')
        domains[f'd{agent_id}'] = {
            'values': [int(v) for v in dvals.split(',')],
        }
        agent_ids.append(agent_id)
    yaml_dict['domains'] = domains

    # variables
    variables = {}
    for agent in agent_ids:
        variables[f'var{agent}'] = {
            'domain': f'd{agent}',
        }
    yaml_dict['variables'] = variables

    # constraints
    constraints = {}
    for con in lines_4_config['cons'].split('>'):
        eq1, eq2 = parse_constraint(con)
        constraints[f'c{len(constraints)}'] = {
            'type': 'intention',
            'function': eq1,
        }
        constraints[f'c{len(constraints)}'] = {
            'type': 'intention',
            'function': eq2,
        }
    yaml_dict['constraints'] = constraints

    # agents
    agents = [f'a{agent_id}' for agent_id in agent_ids]
    yaml_dict['agents'] = agents

    # export to yaml
    exported_file = args.file.split('/')[-1] + '.yaml'
    yaml_file = os.path.join('./yaml-files', exported_file)
    with open(yaml_file, 'w') as f:
        yaml.dump(yaml_dict, f)
        print(f'Simulation config file saved: {yaml_file}')

    # create scenario file
    events = [{
        'id': 'w',
        'delay': 1,
    }]
    scenarios = {'events': events}
    for i, cmd in enumerate(lines_4_config['commands'].split(' ')):
        cmd, agent = cmd.split(':')
        if cmd == 'remove_agent':  # only agent removal is supported by pydcop
            events.append({
                'id': f'e{i}',
                'actions': {
                    'type': cmd,
                    'agent': f'a{agent}'
                }
            })
            events.append({
                'id': 'w',
                'delay': 1,
            })
    exported_file = args.file.split('/')[-1] + '-scenario.yaml'
    yaml_file = os.path.join('./yaml-files', exported_file)
    with open(yaml_file, 'w') as f:
        yaml.dump(scenarios, f)
        print(f'Simulation scenario file saved: {yaml_file}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Convert DynaGraph sim file to pyDCOP compatible yaml config')
    parser.add_argument('-f', '--file', type=str, required=True, help='sim file path')
    parser.add_argument('-n', '--name', type=str, required=True, help='DCOP name')

    args = parser.parse_args()

    main(args)
