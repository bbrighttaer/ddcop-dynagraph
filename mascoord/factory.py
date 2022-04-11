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
        while not self.terminate:
            self.client.sleep(0)
        self.release_resources()

    def execute_graph_gen(self):
        log.info('Executing graph gen')

        handlers.add_agent_handler({'num_agents': self.exec_args.num_agents})

        time.sleep(60)

        handlers.change_constraint_handler({'num_agents': self.exec_args.num_const_change})

        handlers.remove_agent_handler({'num_agents': self.exec_args.num_remove})

        time.sleep(30)

    def execute_sim_from_files(self, sim_file):
        log.info(f'Executing from sim files, using predefined network: {config.shared_config.use_predefined_graph}')
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
    parser.add_argument(
        '-l',
        '--logger_level',
        choices=['debug', 'info', 'warning', 'error', 'critical'],
        default='debug',
        dest='logger_level',
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
        '--num_diff_graphs',
        type=int,
        help='The number of graphs to generate for each specified out degree',
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
        default=0,
    )
    parser_graph_gen.add_argument(
        '--num_const_change',
        type=int,
        help='The set the number of agents that change their constraints in the environment',
        default=0,
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
    config.shared_config.execution_mode = command
    config.shared_config.logger_level = args.logger_level.upper()

    if command == 'graph-gen':
        handlers.set_dcop_algorithm('no-dcop')
        config.shared_config.use_predefined_graph = False

        for degree in args.degrees:
            random.seed(degree)
            config.shared_config.max_out_degree = degree
            for k in range(args.num_diff_graphs):
                log.info(f'------------- Degree: {degree}, run: {k + 1} ----------------')
                handlers.metrics.can_save = False
                runner = Runner(args)
                runner.execute_graph_gen()
                handlers.save_simulation_handler({
                    'prefix': f'max-deg-{degree}-graph-{k + 1}-'
                })
                handlers.reset_buffers()
                runner.release_resources()
        sim_time = time_since(start_time)
        log.info(f'Simulation elapsed time: {sim_time}')
    elif command == 'simulation':
        config.shared_config.use_predefined_graph = True
        simulations = os.listdir('simulations')
        sim_files = [file for file in simulations if '.sim' in file]

        for algorithm in args.algs:
            handlers.set_dcop_algorithm(algorithm)
            for i in range(args.num_runs):
                random.seed(i)
                for filename in sim_files:
                    log.info(f'---------- Executing: {algorithm}, run: {i + 1}, filename: {filename} -------------')
                    handlers.set_metrics_file_prefix(f'{filename}-run-{i + 1}-')
                    runner = Runner(args)
                    runner.execute_sim_from_files(filename)
                    handlers.reset_buffers()
                    runner.release_resources()

        sim_time = time_since(start_time)
        log.info(f'Simulation elapsed time: {sim_time}')
    else:
        handlers.set_dcop_algorithm(args.algs[0])
        runner = Runner(args)
        runner.execute_sim_with_dashboard()
