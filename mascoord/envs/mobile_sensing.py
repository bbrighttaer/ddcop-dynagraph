import random
import threading
from collections import defaultdict
from typing import Tuple

import numpy as np

from mascoord import messaging, logger
from mascoord.envs import SimulationEnvironment


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
        return f'{self.cell_id}: {str([str(c) for c in self.contents])}'

    def __hash__(self):
        return hash(self.cell_id)


class MobileSensingAgent:

    def __init__(self, player_id, cell):
        super().__init__()
        self.player_id = player_id
        self.current_cell = cell
        self.credibility = 5
        self.sensing_range = 1
        self.mobility_range = 2
        self.communication_range = 3

    def __str__(self):
        return f'Agent(id={self.player_id}, cred={self.credibility})'

    def __hash__(self):
        return hash(self.player_id)


class Target:

    def __init__(self, target_id, cell, cov_req):
        self.target_id = target_id
        self.current_cell = cell
        self.coverage_requirement = cov_req
        self.is_active = True
        self.is_detected = False

    def __str__(self):
        return f'Target(target_id={self.target_id}, cov_req={self.coverage_requirement}, is_active={self.is_active})'

    def __hash__(self):
        return hash(self.target_id)


class GridWorld(SimulationEnvironment):
    name = 'GridWorld'

    def __init__(self, size, num_targets, scenario=None):
        super(GridWorld, self).__init__(self.name, time_step_delay=10, scenario=scenario)
        self._delayed_actions = {}
        self.grid_size = size
        self.grid = {}
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

    def __call__(self, *args, **kwargs):
        self.log.info('Started GridWorld simulation environment')
        self._create_cells()
        self._initialize_targets()

        # start processing events in scenario object
        threading.Thread(target=self.step, daemon=True).start()

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

    def on_stop(self):
        self.log.debug('Stopped GridWorld simulation environment')

    def step(self):
        self.log.info(f'Processing scenarios for {self.name}')
        while True:
            try:
                evt = next(self._events_iterator)
                while evt.is_delay:
                    self.log.info('Skipping delay event')
                    evt = next(self._events_iterator)

                for a in evt.actions:
                    if a.type == 'add-agent':
                        self.log.info('Event action: Adding agent %s ', a)
                        self.run_stabilization_computation(a.args['agent'])

                        # self.post_msg(
                        #     ORCHESTRATOR_MGT,
                        #     GraphConnectionMessage(
                        #         action='add-node',
                        #         node1=a.args['agent'],
                        #         node2=None,
                        #     ),
                        #     MSG_MGT,
                        # )

                        # send message to factory
                        self.channel.basic_publish(
                            exchange=messaging.COMM_EXCHANGE,
                            routing_key=f'{messaging.FACTORY_COMMAND_CHANNEL}',
                            body=messaging.create_agent_added_message({
                                'added-agent': a.args['agent'],
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
                                'removed-agent': a.args['agent'],
                            })
                        )

                        # self.post_msg(
                        #     ORCHESTRATOR_MGT,
                        #     GraphConnectionMessage(
                        #         action='remove_node',
                        #         node1=a.args['agent'],
                        #         node2=None,
                        #     ),
                        #     MSG_MGT,
                        # )

                self.next_time_step()
                self.log.debug(self.history)

            except StopIteration:
                break

        self.on_simulation_ended()

    def run_stabilization_computation(self, agent):
        # get all possible positions
        cell_ids = list(self.grid.keys())

        # uniformly sample a position for this target
        selected_cell_id = random.choice(cell_ids)
        selected_cell = self.grid[selected_cell_id]

        # create agent in the environment
        msa = MobileSensingAgent(agent, selected_cell)
        self.agents[msa.player_id] = msa

        # add sensor to cell
        selected_cell.add(msa)

    def remove_agent(self, agent):
        # remove agent from agents list
        msa = self.agents.pop(agent)

        # remove agent from currently occupied cell
        cell: GridCell = msa.current_cell
        cell.contents.pop(cell.contents.index(msa))

    def next_time_step(self):
        self._disable_detected_targets()
        self._current_time_step += 1
        grid = [str(v) for v in self.grid.values()]
        self._state_history.append((f't={str(self._current_time_step)}', grid))
        self.log.info(f'Current time step: {self._current_time_step}')

    def _create_cells(self):
        for i in range(1, self.grid_size + 1):
            for j in range(1, self.grid_size + 1):
                cell = GridCell(i, j)
                self.grid[cell.cell_id] = cell

    def get_time_step_end_data(self, agent_id):
        sensor = self.agents.get(agent_id, None)
        return {
            'current_position': sensor.current_cell.cell_id,
            'score': self.calc_agent_score(self.agents[agent_id]),  # score in the just ended time step
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
                    if isinstance(obj, MobileSensingAgent) and obj.player_id != agent_id:
                        nearby_agents.append(obj.player_id)

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

    def _on_constraint_evaluation_msg(self, sender: str, msg, t: float):
        # self.log.debug(f'Received constraint evaluation msg: {msg} from {sender}')

        selected_cells = {}
        score = 0.

        for k, val in msg.var_assignments.items():
            try:
                if k.startswith('var'):
                    k = k.replace('var', 'a')
                    current_cell = self.agents[k].current_cell
                    action = getattr(current_cell, val)
                    cell = self.grid.get(action(), None)
                    if cell:
                        selected_cells[k] = cell
            except KeyError as e:
                self.log.error(f'_on_constraint_evaluation_msg: {str(e)} - sender={sender}, msg = {msg}')

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
        # self.log.debug(f'score = {score}')
        # send constraint evaluation result to computation (sender)
        self.send_constraint_evaluation_response(
            target=sender,
            constraint_name=msg.constraint_name,
            value=score,
        )

    def on_action_selection(self, on_action_cb, sender: str, msg, t: float):
        self.log.info(f'Received action selection from {sender}: {msg}')
        self._delayed_actions[sender] = (sender, msg.agent, msg.value, on_action_cb)

        if len(self._delayed_actions) == len(self.agents):
            self.log.info('Collecting simulation metrics...')
            self._record_simulation_metrics()
        else:
            self.log.debug(f'delayed actions: {self._delayed_actions}, agents = {self.agents}')

    def _apply_selected_action(self, sender, agent, value, on_action_cb):
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

                if callable(on_action_cb):
                    on_action_cb(
                        target=sender,
                        prev_position=current_agt_cell.cell_id,
                        new_position=new_cell.cell_id,
                        updated_domain=self._get_legit_actions(new_cell),
                        current_position=new_cell.cell_id,
                    )

    def calculate_global_score(self) -> Tuple[int, float]:  # number of violations, score
        self.log.debug('Calculating global score')
        self._apply_all_actions()
        score = 0.
        for agt in self.agents:
            score += self.calc_agent_score(self.agents[agt])
        self._mark_detected_targets()
        return 0, score

    def _apply_all_actions(self):
        # apply all actions
        self.log.info(f'Applying actions: num of actions = {len(self._delayed_actions)}, num_agents: {len(self.agents)}')
        for sender, agent, value, on_action_cb in self._delayed_actions.values():
            self._apply_selected_action(sender, agent, value, on_action_cb)
        self._delayed_actions.clear()

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
