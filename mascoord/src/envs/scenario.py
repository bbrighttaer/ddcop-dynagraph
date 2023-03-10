# BSD-3-Clause License
#
# Copyright 2017 Orange
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice,
#    this list of conditions and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# 3. Neither the name of the copyright holder nor the names of its contributors
#    may be used to endorse or promote products derived from this software
#    without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
import random
from typing import List

from mascoord.src.envs.simple_repr import SimpleRepr


class EventAction(SimpleRepr):

    def __init__(self, type: str, **kwargs):
        self._type = type
        self._args = kwargs

    @property
    def type(self):
        return self._type

    @property
    def args(self):
        return self._args

    def __repr__(self):
        return 'EventAction({}, {})'.format(self.type, self._args)


class DcopEvent(SimpleRepr):
    """
    A Dcop Event is used to represent an event happening in the system.

    An event can contains several actions that are happening at the same time.
    This is for example useful when several agents disappear simultaneously.

    """

    type = None

    def __init__(self, id: str, delay: float = None,
                 actions: List[EventAction] = None):
        """
        :param actions: a list of EventAction objects
        """
        self._actions = actions
        self._delay = delay
        self._id = id

    @property
    def id(self):
        return self._id

    @property
    def delay(self):
        return self._delay

    @property
    def actions(self):
        return self._actions

    @property
    def is_delay(self):
        return self.delay is not None

    def __repr__(self):
        return 'Event({}, {})'.format(self.id, self.actions)


class Scenario(SimpleRepr):
    """
    A scenario is a list of events that happens in the system.

    """

    def __init__(self, events: List[DcopEvent] = None):
        self._events = events if events else []

    def __iter__(self):
        return iter(self._events)

    def __len__(self):
        return len(self._events)

    @property
    def events(self):
        return list(self._events)

    def add_event(self, evt: DcopEvent):
        self._events.append(evt)


class MSTScenario:
    """
    Generates events for a dynamic mobile sensor team environment
    """

    def __init__(self, num_add_agents, num_remove_agents):
        self._num_add_agents = num_add_agents
        self._num_remove_agents = num_remove_agents

    def scenario(self) -> Scenario:
        scenario = Scenario()

        add_agents = []
        remove_agents = []

        # construct events
        i = 0
        while len(scenario) < self._num_add_agents + self._num_remove_agents:
            available = list(set(add_agents) - set(remove_agents))
            if available and len(remove_agents) < self._num_remove_agents and random.random() < 0.5:
                agent = random.choice(available)
                scenario.add_event(
                    evt=DcopEvent(
                        id=str(len(scenario)),
                        actions=[EventAction(type='remove-agent', agent=agent)]
                    )
                )
                remove_agents.append(agent)
            elif len(add_agents) < self._num_add_agents:
                agent = f'a{i}'
                scenario.add_event(
                    evt=DcopEvent(
                        id=str(len(scenario)),
                        actions=[EventAction(type='add-agent', agent=agent)]
                    )
                )
                add_agents.append(agent)
                i += 1

        return scenario
