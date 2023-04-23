import os
import pickle
import random
import sys
import threading
import time
from argparse import ArgumentParser

import pika

import config
import logger
import messaging
from mascoord.definitions import ROOT_DIR
from mascoord.src import handlers
from mascoord.src.envs.mobile_sensing import GridWorld
from mascoord.src.envs.scenario import MSTScenario
from mascoord.src.utils import notify_wrap

log = logger.get_logger('Runner')


def on_message(ch, method, properties, body):
    msg = eval(body.decode('utf-8'))
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
        self.channel.queue_bind(
            exchange=messaging.COMM_EXCHANGE,
            queue=self.queue_name,
            routing_key=f'{messaging.DASHBOARD_COMMAND_CHANNEL}.#'
        )
        self.channel.queue_bind(
            exchange=messaging.COMM_EXCHANGE,
            queue=self.queue_name,
            routing_key=f'{messaging.FACTORY_COMMAND_CHANNEL}.#'
        )

        # subscribe to dashboard commands
        self.channel.basic_consume(queue=self.queue_name, on_message_callback=on_message, auto_ack=True)

        # send available simulations to dashboard
        simulations = os.listdir(os.path.join(ROOT_DIR, 'simulations'))
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

        # for simulation environment
        self.sim_env = None
        self._sim_env_stop_sig = threading.Event()

    @property
    def terminate(self):
        return self._terminate

    @terminate.setter
    def terminate(self, flag):
        self._terminate = flag

    def execute_sim_with_dashboard(self):
        log.info('Executing sim with dashboard (start dashboard to execute commands)')
        self._listen_for_messages()
        self.release_resources()

    def _listen_for_messages(self):
        while not self.terminate:
            self.client.sleep(0)

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
        log.info('Runner is closing')

        # remove rabbitmq resources
        self.channel.queue_unbind(exchange=messaging.COMM_EXCHANGE,
                                  queue=self.queue_name,
                                  routing_key=f'{messaging.DASHBOARD_COMMAND_CHANNEL}.#')
        self.channel.queue_unbind(exchange=messaging.COMM_EXCHANGE,
                                  queue=self.queue_name,
                                  routing_key=f'{messaging.FACTORY_COMMAND_CHANNEL}.#')
        self.channel.queue_delete(self.queue_name)
        self.client.close()

        log.info('Runner was closed successfully')

    def start_simulation_environment(self, args):
        self.sim_env = GridWorld(
            size=args.grid_size,
            num_targets=args.num_targets,
            scenario=MSTScenario(
                num_add_agents=args.num_agents,
                num_remove_agents=args.num_remove
            ).load(args.scenarios_file),
            dcop_alg=args.algs[0],
            graph_alg=args.graph_alg,
            seed=args.seed,
        )

        # override sim-ended func to call stop signal
        self.sim_env.on_simulation_ended = notify_wrap(
            self.sim_env.on_simulation_ended,
            self._on_dynamic_sim_env_ended,
        )

        # start sim environment
        threading.Thread(target=self.sim_env, daemon=True).start()

    def _on_dynamic_sim_env_ended(self):
        self._terminate = True

    def wait(self):
        self._listen_for_messages()
        self.release_resources()
        log.info('Simulation ended')

    def on_force_exit(self, sig, frame):
        log.info('Simulation terminated')
        self.terminate = True


if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument(
        '--num_agents',
        type=int,
        help='The set the number of agents to add to the environment',
        required=True,
    )
    parser.add_argument(
        '--num_remove',
        type=int,
        help='The set the number of agents to remove from the environment',
        default=0,
    )
    parser.add_argument(
        '-s',
        '--seed',
        default=0,
        type=int,
    )

    args = parser.parse_args()

    random.seed(args.seed)

    scenarios = MSTScenario(
                num_add_agents=args.num_agents,
                num_remove_agents=args.num_remove
            ).scenario()

    with open('scenarios.pkl', 'wb') as f:
        pickle.dump(scenarios, f)

    print('Scenarios generation completed successfully')



