import copy
import functools
import os.path
import random
from collections import defaultdict

import numpy as np
import networkx as nx
import csv

from mascoord.definitions import ROOT_DIR
from mascoord.src import messaging
from mascoord.src.envs import SimulationEnvironment
from mascoord.src.messaging import ANNOUNCE, AGENT_REGISTRATION, VALUE_SELECTED_MSG, ADD_GRAPH_EDGE, REMOVE_GRAPH_EDGE


class GridCell:
    """
    Models a cell in the GridWorld environment.

    The cell and its neighbors:
    .-----------.------.------------.
    | left_up   | up   | right_up   |
    :-----------+------+------------:
    | left      | cell | right      |
    :-----------+------+------------:
    | left_down | down | right_down |
    '-----------'------'------------'
    """

    def __init__(self, i, j):
        self.i = i
        self.j = j
        self.cell_id = f'{i}-{j}'
        self.contents = []

    def add(self, o):
        self.contents.append(o)

    def get_num_active_targets(self):
        num = 0
        for c in self.contents:
            if isinstance(c, Target) and c.is_active:
                num += 1
        return num

    def get_num_agents(self):
        num = 0
        for c in self.contents:
            if isinstance(c, MobileSensingAgent):
                num += 1
        return num

    def remove_detected_targets(self):
        ...

    def up(self):
        return str(self.i - 1) + '-' + str(self.j)

    def down(self):
        return str(self.i + 1) + '-' + str(self.j)

    def left(self):
        return str(self.i) + '-' + str(self.j - 1)

    def right(self):
        return str(self.i) + '-' + str(self.j + 1)

    def left_up(self):
        return str(self.i - 1) + '-' + str(self.j - 1)

    def left_down(self):
        return str(self.i + 1) + '-' + str(self.j - 1)

    def right_up(self):
        return str(self.i - 1) + '-' + str(self.j + 1)

    def right_down(self):
        return str(self.i + 1) + '-' + str(self.j + 1)

    def __str__(self):
        contents = []
        for c in self.contents:
            if isinstance(c, Target) and c.is_active or isinstance(c, MobileSensingAgent):
                contents.append(str(c))
        return f'{self.cell_id}: {str(contents)}'

    def __hash__(self):
        return hash(self.cell_id)


class MobileSensingAgent:

    def __init__(self, agent_id, cell):
        super().__init__()
        self.agent_id = agent_id
        self.current_cell = cell
        self.credibility = 5
        self.sensing_range = 1
        self.mobility_range = 2
        self.communication_range = 3

    def __str__(self):
        # return f'Agent(id={self.player_id}, cred={self.credibility})'
        return self.agent_id

    def __hash__(self):
        return hash(self.agent_id)


class Target:

    def __init__(self, target_id, cell, cov_req):
        self.target_id = target_id
        self.current_cell = cell
        self.coverage_requirement = cov_req
        self.is_active = True
        self.is_detected = False

    def __str__(self):
        # return f'Target(target_id={self.target_id}, cov_req={self.coverage_requirement}, is_active={self.is_active})'
        return 't' + str(self.target_id)

    def __hash__(self):
        return hash(self.target_id)


class GridWorld(SimulationEnvironment):
    name = 'GridWorld'
    grid = {}

    def __init__(self, size, num_targets, scenario=None):
        super(GridWorld, self).__init__(self.name, time_step_delay=10, scenario=scenario)
        self.log.info(f'Number of scenarios: {len(scenario)}')
        self._delayed_actions = {}
        self.grid_size = size
        # self.grid = {}
        self._current_time_step = -1
        self.num_targets = num_targets
        self._targets = {}
        self._events = ['add-agent', 'remove-agent', 'target_disabled', 'target_enabled', 'no-op']
        self._y = self._events.index('no-op')
        s = len(self._events)
        # v = np.random.rand(s)
        # self._initial_distribution = v / v.sum()
        m = np.random.rand(s, s)
        self._transition_function = m / m.sum(axis=1).reshape(-1, 1)
        self.scores = defaultdict(float)

        self._registered_agents = []

        # metrics-related
        self._metrics = {}
        self._metrics_file_headers = []
        self._metrics_file_name = 'metrics.csv'

        self._handlers = {
            AGENT_REGISTRATION: self._receive_agent_registration,
            ANNOUNCE: self._receive_announce_msg,
            VALUE_SELECTED_MSG: self._receive_value_selection,
            ADD_GRAPH_EDGE: self._receive_add_graph_edge,
            REMOVE_GRAPH_EDGE: self._receive_remove_graph_edge,
        }

    def __call__(self, *args, **kwargs):
        self.log.info('Started GridWorld simulation environment')
        self._create_cells()
        self._initialize_targets()

        # start processing events in scenario object
        self.step()

        self._listen_for_messages()

    def _initialize_targets(self):
        # get all possible positions
        cell_ids = list(self.grid.keys())

        for i in range(self.num_targets):
            # uniformly sample a position for this target
            selected_cell_id = random.choice(cell_ids)
            selected_cell = self.grid[selected_cell_id]

            # create the target
            target = Target(
                target_id=i,
                cell=selected_cell,
                cov_req=5,
            )

            # add target to cell
            self._targets[target.target_id] = target
            selected_cell.add(target)

    def _on_message(self, ch, method, properties, body):
        msg = eval(body.decode('utf-8'))
        func = self._handlers.get(msg['type'], None)

        if func:
            func(msg['payload'])
        else:
            self.log.warning(f'Message type {msg["type"]} has no handler')

    def _receive_agent_registration(self, msg):
        self.log.info(f'Received agent registration: {msg}')
        agent_id = msg['agent_id']
        self._registered_agents.append(agent_id)

        # send current time step info to the just registered agent
        self._send_time_step_info(agent_id)

    def _send_time_step_info(self, agent_id):
        self.log.info(f'Sending time step info to agent {agent_id}')
        self.channel.basic_publish(
            exchange=messaging.COMM_EXCHANGE,
            routing_key=f'{messaging.AGENTS_CHANNEL}.{agent_id}',
            body=messaging.create_sim_env_current_time_step_message(
                self.get_time_step_data(agent_id),
            )
        )

    def _receive_announce_msg(self, msg):
        self.log.info(f'Received announce message: {msg}')
        self._broadcast_announce(msg)
        self.client.call_later(0, functools.partial(self._broadcast_announce, msg))

    def _broadcast_announce(self, msg):
        for agent in self.get_agents_in_communication_range(msg['agent_id']):
            self.channel.basic_publish(
                exchange=messaging.COMM_EXCHANGE,
                routing_key=f'{messaging.AGENTS_CHANNEL}.{agent}',
                body=messaging.create_announce_message(msg)
            )

    def on_stop(self):
        self.log.debug('Stopped GridWorld simulation environment')

    def step(self):
        try:
            evt = next(self._events_iterator)
            while evt.is_delay:
                self.log.info('Skipping delay event')
                evt = next(self._events_iterator)

            for a in evt.actions:
                if a.type == 'add-agent':
                    self.log.info('Event action: Adding agent %s ', a)
                    self.run_stabilization_computation(a.args['agent'])

                    # send message to factory
                    self.channel.basic_publish(
                        exchange=messaging.COMM_EXCHANGE,
                        routing_key=f'{messaging.FACTORY_COMMAND_CHANNEL}',
                        body=messaging.create_agent_added_message({
                            'agent': a.args['agent'],
                        })
                    )

                elif a.type == 'remove-agent':
                    self.log.info('Event action: Remove agent %s ', a)
                    self.remove_agent(a.args['agent'])

                    # send message to factory
                    self.channel.basic_publish(
                        exchange=messaging.COMM_EXCHANGE,
                        routing_key=f'{messaging.FACTORY_COMMAND_CHANNEL}',
                        body=messaging.create_agent_removed_message({
                            'agent': a.args['agent'],
                        })
                    )

            self.next_time_step()
            self.log.debug(self.history)

        except StopIteration:
            self.on_simulation_ended()

    def run_stabilization_computation(self, agent):
        # get all possible positions
        cell_ids = list(self.grid.keys())

        # uniformly sample a position for this target
        selected_cell_id = random.choice(cell_ids)
        selected_cell = self.grid[selected_cell_id]

        # create agent in the environment
        msa = MobileSensingAgent(agent, selected_cell)
        self.agents[msa.agent_id] = msa

        # add sensor to cell
        selected_cell.add(msa)

        # add node to current graph
        self._current_graph.add_node(agent)

    def remove_agent(self, agent):
        # remove agent from agents list
        msa = self.agents.pop(agent)

        # remove agent from currently occupied cell
        cell: GridCell = msa.current_cell
        cell.contents.pop(cell.contents.index(msa))

        # remove node from current graph
        self._current_graph.remove_node(agent)

        # remove from registered agents
        self._registered_agents.remove(agent)

    def next_time_step(self):
        self._disable_detected_targets()
        self._current_time_step += 1
        grid = [str(v) for v in self.grid.values()]
        self._state_history.append((f't={str(self._current_time_step)}', grid))
        self.log.info(f'Current time step: {self._current_time_step}')

        # send time step information to already registered agents
        for agent in self._registered_agents:
            self._send_time_step_info(agent)

        # when next-time-step is called but there are no agents
        if len(self.agents) == 0:
            self._receive_value_selection({}, is_forced=True)

    def _create_cells(self):
        for i in range(1, self.grid_size + 1):
            for j in range(1, self.grid_size + 1):
                cell = GridCell(i, j)
                self.grid[cell.cell_id] = cell

    def get_time_step_data(self, agent_id):
        sensor = self.agents.get(agent_id, None)
        return {
            'current_position': sensor.current_cell.cell_id,
            # 'score': self.calc_agent_score(self.agents[agent_id]),  # score in the just ended time step
            'agents_in_comm_range': [] if sensor is None else self.get_agents_in_communication_range(agent_id),
            'agent_domain': self._get_legit_actions(self.agents[agent_id].current_cell),
            'neighbor_domains': {
                agt: self._get_legit_actions(self.agents[agt].current_cell)
                for agt in self.get_agents_in_communication_range(agent_id)
            },
        }

    def get_agents_in_communication_range(self, agent_id) -> list:
        nearby_agents = []
        cells_to_inspect = []
        agent: MobileSensingAgent = self.agents[agent_id]
        cell: GridCell = agent.current_cell

        # compile list of cells to inspect
        cells_to_inspect.append(cell)
        if agent.communication_range > 1:
            up = self.grid.get(cell.up(), None)
            down = self.grid.get(cell.down(), None)
            left = self.grid.get(cell.left(), None)
            right = self.grid.get(cell.right(), None)
            left_up = self.grid.get(cell.left_up(), None)
            right_up = self.grid.get(cell.right_up(), None)
            left_down = self.grid.get(cell.left_down(), None)
            right_down = self.grid.get(cell.right_down(), None)
            cells_to_inspect += [up, down, left, right, left_up, right_up, left_down, right_down]

        # inspect cells for agents
        for cell in cells_to_inspect:
            if cell:
                for obj in cell.contents:
                    if isinstance(obj, MobileSensingAgent) and obj.agent_id != agent_id:
                        nearby_agents.append(obj.agent_id)

        return nearby_agents

    def _get_legit_actions(self, cell):
        actions = []
        if cell:
            if self.grid.get(cell.up(), None):
                actions.append('up')
            if self.grid.get(cell.down(), None):
                actions.append('down')
            if self.grid.get(cell.left(), None):
                actions.append('left')
            if self.grid.get(cell.right(), None):
                actions.append('right')
            if self.grid.get(cell.left_up(), None):
                actions.append('left_up')
            if self.grid.get(cell.right_up(), None):
                actions.append('right_up')
            if self.grid.get(cell.left_down(), None):
                actions.append('left_down')
            if self.grid.get(cell.right_down(), None):
                actions.append('right_down')
        return actions

    @classmethod
    def constraint_evaluation(cls, sender: str, agent_values: dict):
        selected_cells = {}
        score = 0.

        for k, val in agent_values.items():
            try:
                current_cell = cls.agents[k].current_cell
                action = getattr(current_cell, val)
                cell = cls.grid.get(action(), None)
                if cell:
                    selected_cells[k] = cell
            except KeyError as e:
                cls.log.error(f'constraint_evaluation: {str(e)} - sender={sender}, msg = {agent_values}')

        if len(selected_cells) > 1:
            unique_cells = list(set(selected_cells.values()))

            if len(unique_cells) == 1:
                # self.log.debug('unique cells')
                score = unique_cells[0].get_num_active_targets() * 2

            elif len(unique_cells) > 1:
                # self.log.debug('multiple cells')
                score = 0
                for cell in selected_cells.values():
                    score += cell.get_num_active_targets() * 0.5

        elif len(selected_cells) == 1:
            # self.log.debug('single cell')
            score = list(selected_cells.values())[0].get_num_active_targets() * 0.5

        return score

    def _receive_value_selection(self, msg, is_forced=False):
        self.log.info(f'Received action selection: {msg}')

        if not is_forced:
            self._delayed_actions[msg['agent_id']] = msg

        if len(self._delayed_actions) == len(self.agents) or is_forced:
            self.log.info('Collecting simulation metrics...')
            # apply selected actions
            self._apply_all_actions()

            # gather simulation metrics
            self._record_simulation_metrics()

            # clear time step registers
            self._delayed_actions.clear()

            # move environment to new time step
            self.step()
        else:
            self.log.debug(f'delayed actions: {self._delayed_actions}, agents = {self.agents}')

    def _apply_selected_action(self, agent, value):
        # apply action
        agt = self.agents[agent]
        current_agt_cell = agt.current_cell
        action = getattr(current_agt_cell, value)
        if action is not None:
            new_cell = self.grid.get(action(), None)
            if new_cell:
                current_agt_cell.contents.remove(agt)
                agt.current_cell = new_cell
                new_cell.contents.append(agt)
                self.log.debug(f'Agent {agent} changed from {current_agt_cell.cell_id} to {new_cell.cell_id}')

    def calculate_global_score(self) -> float:  # number of violations, score
        self.log.debug('Calculating global score')
        score = 0.
        for agt in self.agents:
            score += self.calc_agent_score(self.agents[agt])
        self._mark_detected_targets()
        return score

    def _apply_all_actions(self):
        # apply all actions
        self.log.info(f'Applying actions: num of actions = {len(self._delayed_actions)}, num_agents: {len(self.agents)}')
        for msg in self._delayed_actions.values():
            self._apply_selected_action(agent=msg['agent_id'], value=msg['value'])

    def calc_agent_score(self, agent: MobileSensingAgent):
        score = 0.
        num_agents_in_cell = agent.current_cell.get_num_agents()
        num_targets_in_cell = agent.current_cell.get_num_active_targets()

        if num_agents_in_cell > 1:
            score = num_targets_in_cell * 2.
        elif num_agents_in_cell == 1:
            score = num_targets_in_cell * 0.5

        return score

    def _disable_detected_targets(self):
        for agt in self.agents:
            for c in self.agents[agt].current_cell.contents:
                if isinstance(c, Target) and c.is_detected:
                    c.is_active = False

    def _mark_detected_targets(self):
        """
        To be called after computing scores of all agents.
        """
        for agt in self.agents:
            for c in self.agents[agt].current_cell.contents:
                if isinstance(c, Target):
                    c.is_detected = True

    def on_simulation_ended(self):
        for agent in self.agents:
            self.channel.basic_publish(
                exchange=messaging.COMM_EXCHANGE,
                routing_key=f'{messaging.AGENTS_CHANNEL}.{agent}',
                body=messaging.create_stop_agent_message({})
            )
        self._terminate = True

    def _receive_add_graph_edge(self, msg):
        self.log.debug(f'Received add-graph edge msg: {msg}')
        self._current_graph.add_edge(u_of_edge=msg['from'], v_of_edge=msg['to'])

    def _receive_remove_graph_edge(self, msg):
        self.log.debug(f'Received remove-graph edge msg: {msg}')
        if self._current_graph.has_edge(msg['from'], msg['to']):
            self._current_graph.remove_edge(msg['from'], msg['to'])

    def _copy_current_graph(self):
        self._previous_graph = copy.deepcopy(self._current_graph)

    def _write_metrics_file_header(self, headers):
        os.makedirs(os.path.join(ROOT_DIR, 'simulation_metrics'), exist_ok=True)
        file = os.path.join(ROOT_DIR, 'simulation_metrics', self._metrics_file_name)
        with open(file, mode='w', encoding='utf-8', newline='') as f:
            csvwriter = csv.writer(f)
            csvwriter.writerow(headers)
        self._metrics_file_headers = headers

    def _add_metrics_csv_line(self, ts_metrics: dict):
        data = [ts_metrics[c] for c in self._metrics_file_headers]
        file = os.path.join(ROOT_DIR, 'simulation_metrics', self._metrics_file_name)
        with open(file, mode='a', encoding='utf-8', newline='\n') as f:
            csvwriter = csv.writer(f)
            csvwriter.writerow(data)

    def _record_simulation_metrics(self):
        self._metrics[self._current_time_step] = defaultdict(int)
        ts_metrics = self._metrics[self._current_time_step]
        ts_metrics['timestep'] = self._current_time_step
        ts_metrics['score'] = self.calculate_global_score()

        # update all metrics
        for record in self._delayed_actions.values():
            for metric, val in record['metrics'].items():
                ts_metrics[metric] += val

        # graph metrics
        if self._previous_graph is None:
            ts_metrics['edit distance'] = 0
        else:
            ts_metrics['edit distance'] = nx.graph_edit_distance(self._previous_graph, self._current_graph)
        self._copy_current_graph()
        ts_metrics['num components'] = nx.number_connected_components(self._current_graph)
        ts_metrics['num nodes'] = nx.number_of_nodes(self._current_graph)

        # save metrics to file
        if not self._metrics_file_headers:
            self._write_metrics_file_header(list(ts_metrics.keys()))
        self._add_metrics_csv_line(ts_metrics)

        # save grid info to file
        os.makedirs(os.path.join(ROOT_DIR, 'simulation_metrics', 'grids'), exist_ok=True)
        grid_info = self._state_history[-1]
        with open(os.path.join(
                ROOT_DIR,
                'simulation_metrics/grids',
                f'grid-{self._current_time_step}.txt'
        ), 'w') as f:
            f.write(str(grid_info))

        # save graph info to file
        os.makedirs(os.path.join(ROOT_DIR, 'simulation_metrics', 'graphs'), exist_ok=True)
        nx.write_adjlist(
            self._current_graph,
            os.path.join(ROOT_DIR, f'simulation_metrics/graphs/{self._current_time_step}.adjlist')
        )
