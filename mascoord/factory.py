import argparse
import os
import random
import time

import pika

import config
import logger
import messaging
from mascoord.utils import time_since

log = logger.get_logger('Factory')

start_time = time.time()


def on_message(ch, method, properties, body):
    msg = eval(body.decode('utf-8'))
    from mascoord import handlers
    func = handlers.directory.get(msg['type'], None)

    if func:
        func(msg)
    else:
        log.warning(f'Message type {msg["type"]} has no handler')


class Runner:

    def __init__(self, exec_args):
        self.exec_args = exec_args

        self.client = pika.BlockingConnection(pika.ConnectionParameters(
            host=config.BROKER_URL,
            port=config.BROKER_PORT,
            heartbeat=0,  # only for experiment purposes - not recommended (https://www.rabbitmq.com/heartbeats.html)
            credentials=pika.credentials.PlainCredentials(config.PIKA_USERNAME, config.PIKA_PASSWORD))
        )
        self.channel = self.client.channel()
        self.channel.exchange_declare(exchange=messaging.COMM_EXCHANGE, exchange_type='topic')

        self._terminate = False

        # factory queue
        self.queue_name = 'factory-queue'
        self.channel.queue_declare(queue=self.queue_name, exclusive=True)

        # register topics (aka routing keys) associated to the factory queue
        self.channel.queue_bind(exchange=messaging.COMM_EXCHANGE,
                                queue=self.queue_name,
                                routing_key=f'{messaging.DASHBOARD_COMMAND_CHANNEL}.#')
        self.channel.queue_bind(exchange=messaging.COMM_EXCHANGE,
                                queue=self.queue_name,
                                routing_key=f'{messaging.FACTORY_COMMAND_CHANNEL}.#')

        # subscribe to dashboard commands
        self.channel.basic_consume(queue=self.queue_name, on_message_callback=on_message, auto_ack=True)

        # send available simulations to dashboard
        simulations = os.listdir('simulations')
        if simulations:
            parsed_sim = [{
                'date': sim.removesuffix('.sim'),
                'filename': sim,
            } for sim in simulations if '.sim' in sim]
            self.channel.basic_publish(exchange=messaging.COMM_EXCHANGE,
                                       routing_key=f'{messaging.MONITORING_CHANNEL}',
                                       body=messaging.create_saved_simulations_report({
                                           'simulations': parsed_sim,
                                       }))

        # report algorithm in use
        self.channel.basic_publish(exchange=messaging.COMM_EXCHANGE,
                                   routing_key=f'{messaging.MONITORING_CHANNEL}',
                                   body=messaging.create_dcop_algorithm_report({
                                       'dcop': handlers.dcop_algorithm.name,
                                   }))

    @property
    def terminate(self):
        return self._terminate

    @terminate.setter
    def terminate(self, flag):
        self._terminate = flag

    def execute_sim_with_dashboard(self):
        log.info('Executing sim with dashboard (start dashboard to execute commands)')
        random.seed(0)
        handlers.set_dcop_algorithm(self.exec_args.algs[0])
        while not self.terminate:
            self.client.sleep(0)
        self.release_resources()

    def execute_graph_gen(self):
        log.info('Executing graph gen')

        for _ in range(self.exec_args.num_agents):
            handlers.add_agent_handler({'num_agents': 1})

        for _ in range(self.exec_args.num_const_change):
            handlers.change_constraint_handler({'num_agents': 1})

        for _ in range(self.exec_args.num_remove):
            handlers.remove_agent_handler({'num_agents': 1})

    def execute_sim_from_files(self, sim_file):
        log.info(f'Executing from sim files, using predefined network: {config.USE_PREDEFINED_NETWORK}')
        handlers.play_simulation_handler({'simulation': sim_file})

    def release_resources(self):
        log.info('Factory runner is closing')

        # remove rabbitmq resources
        self.channel.queue_unbind(exchange=messaging.COMM_EXCHANGE,
                                  queue=self.queue_name,
                                  routing_key=f'{messaging.DASHBOARD_COMMAND_CHANNEL}.#')
        self.channel.queue_unbind(exchange=messaging.COMM_EXCHANGE,
                                  queue=self.queue_name,
                                  routing_key=f'{messaging.FACTORY_COMMAND_CHANNEL}.#')
        self.channel.queue_delete(self.queue_name)
        self.client.close()

        log.info('Factory runner was closed successfully')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Dynamic DCOP Algorithms')
    parser.add_argument(
        '-a',
        '--algorithms',
        dest='algs',
        type=str,
        nargs='+',
        choices=['c-cocoa', 'sdpop', 'c-sdpop', 'no-dcop'],
        default=['no-dcop'],
        help='The DCOP algorithm to be used with the Dynamic Graph algorithm',
    )
    parser.add_argument(
        '-d',
        '--domain_size',
        type=int,
        default=3,
        help='The number of discrete points in the domain of the agent',
    )

    subparsers = parser.add_subparsers(
        title='Execution modes',
        description='',
        dest='command',
        help='Select execution mode. Options are: with-ui, graph-gen, simulation'
    )

    # graph generation
    parser_graph_gen = subparsers.add_parser('graph-gen', help='sub command for sim graph generation')
    parser_graph_gen.add_argument(
        '--degrees',
        nargs='+',
        type=int,
        help='The set of maximum number of children/out-degree a node can have in the tree',
        required=True,
    )
    parser_graph_gen.add_argument(
        '--num_agents',
        type=int,
        help='The set the number of agents to add to the environment',
        required=True,
    )
    parser_graph_gen.add_argument(
        '--num_remove',
        type=int,
        help='The set the number of agents to remove from the environment',
        required=True,
    )
    parser_graph_gen.add_argument(
        '--num_const_change',
        type=int,
        help='The set the number of agents that change their constraints in the environment',
        required=True,
    )

    # simulation
    parser_sim = subparsers.add_parser('simulation', help='Run the simulation from a given sim file')
    parser_sim.add_argument(
        '--num_runs',
        type=int,
        required=True,
    )

    args = parser.parse_args()

    from mascoord import handlers

    handlers.set_domain_size(args.domain_size)

    command = args.command
    if command == 'graph-gen':
        handlers.set_dcop_algorithm('no-dcop')
        config.set_use_predefined_network(False)

        for degree in args.degrees:
            random.seed(degree)
            config.set_max_out_degree(degree)
            runner = Runner(args)
            runner.execute_graph_gen()
            handlers.save_simulation_handler({
                'prefix': f'max-deg-{degree}-'
            })
            handlers.reset_buffers()
            runner.release_resources()
    elif command == 'simulation':
        start_time = time.time()
        config.set_use_predefined_network(True)
        simulations = os.listdir('simulations')
        sim_files = [file for file in simulations if '.sim' in file]

        for algorithm in args.algs:
            handlers.set_dcop_algorithm(algorithm)
            for i in range(args.num_runs):
                random.seed(i)
                for filename in sim_files:
                    handlers.set_metrics_file_prefix(f'{filename}-run-{i + 1}-')
                    runner = Runner(args)
                    runner.execute_sim_from_files(filename)
                    time.sleep(5)
                    handlers.save_simulation_metrics_handler()
                    handlers.reset_buffers()
                    runner.release_resources()

        sim_time = time_since(start_time)
        log.info(f'Simulation elapsed time: {sim_time}')
    else:
        runner = Runner(args)
        runner.execute_sim_with_dashboard()
