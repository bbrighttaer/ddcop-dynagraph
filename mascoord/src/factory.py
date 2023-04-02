import argparse
import functools
import os
import random
import signal
import time

import numpy as np

import config
import logger
from mascoord.src.config import DYNAMIC_SIM_ENV
from mascoord.src.runner import Runner
from mascoord.src.utils import time_since

log = logger.get_logger('Factory')

start_time = time.time()


def _on_force_exit(sub_exit_func, sig, frame):
    sub_exit_func(sig, frame)


def _on_timeout(on_timeout_func):
    on_timeout_func()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Dynamic DCOP Algorithms')
    parser.add_argument(
        '-a',
        '--algorithms',
        dest='algs',
        type=str,
        nargs='+',
        choices=['cocoa', 'c-cocoa', 'dpop', 'c-dpop', 'no-dcop'],
        default=['no-dcop'],
        help='The DCOP algorithm to be used with the Dynamic Graph algorithm',
    )
    parser.add_argument(
        '-g',
        '--graph_alg',
        type=str,
        choices=['ddfs', 'digca'],
        default='digca',
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
    parser.add_argument(
        '-p',
        '--opt_op',
        choices=['min', 'max'],
        default='min',
        dest='opt_op',
    )
    parser.add_argument(
        '-s',
        '--seed',
        default=0,
        type=int,
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
    sim_parser = subparsers.add_parser('simulation', help='Run the simulation from a given sim file')
    sim_parser.add_argument(
        '--num_runs',
        type=int,
        required=True,
    )

    # mst simulation
    sim_parser = subparsers.add_parser('mst-simulation', help='Run the MST simulation')
    sim_parser.add_argument(
        '--num_agents',
        type=int,
        help='The set the number of agents to add to the environment',
        required=True,
    )
    sim_parser.add_argument(
        '--num_remove',
        type=int,
        help='The set the number of agents to remove from the environment',
        default=0,
    )
    sim_parser.add_argument(
        "--grid_size",
        "-g",
        default=3,
        dest="grid_size",
        type=int,
        help="Size of the GridWorld",
    )
    sim_parser.add_argument(
        "--num_targets",
        "-k",
        default=2,
        dest="num_targets",
        type=int,
        help="Number of targets in the GridWorld",
    )

    args = parser.parse_args()

    from mascoord.src import logger, handlers

    seed = args.seed
    np.random.seed(seed)
    random.seed(seed)

    handlers.set_domain_size(args.domain_size)

    command = args.command
    config.shared_config.execution_mode = command
    config.shared_config.logger_level = args.logger_level.upper()
    config.shared_config.optimization_op = args.opt_op

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

    elif command == 'simulation':
        config.shared_config.use_predefined_graph = True
        simulations = os.listdir('../simulations')
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

    elif command == 'mst-simulation':
        config.shared_config.execution_mode = DYNAMIC_SIM_ENV
        handlers.set_dcop_algorithm(args.algs[0])
        handlers.set_graph_algorithm(args.graph_alg)
        runner = Runner(args)
        signal.signal(signal.SIGINT, functools.partial(_on_force_exit, runner.on_force_exit))
        runner.start_simulation_environment(args)
        runner.wait()
    else:
        handlers.set_dcop_algorithm(args.algs[0])
        runner = Runner(args)
        runner.execute_sim_with_dashboard()

    sim_time = time_since(start_time)
    log.info(f'Elapsed time: {sim_time}')
