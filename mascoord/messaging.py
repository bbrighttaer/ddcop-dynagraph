import datetime
import json

import config

COMM_EXCHANGE = f'{config.DOMAIN}.ddcop'

# communication channels
AGENTS_CHANNEL = f'{config.DOMAIN}.agent'  # for agent-to-agent communication
MONITORING_CHANNEL = f'{config.DOMAIN}.monitoring'  # for agent-to-dashboard monitoring communication
DASHBOARD_COMMAND_CHANNEL = f'{config.DOMAIN}.command.dashboard'  # for dashboard-to-factory command msgs
FACTORY_COMMAND_CHANNEL = f'{config.DOMAIN}.command.factory'  # for factory-agent msgs
METRICS_CHANNEL = f'{config.DOMAIN}.metrics'

# dashboard command message types
TEST = 'TEST'
ADD_AGENT = 'ADD_AGENT'
REMOVE_AGENT = 'REMOVE_AGENT'
CHANGE_CONSTRAINT = 'CHANGE_CONSTRAINT'
REQUEST_AGENT_REPORT = 'REQUEST_AGENT_REPORT'
SAVE_SIMULATION = 'SAVE_SIMULATION'
SAVED_SIMULATIONS_REPORT = 'SAVED_SIMULATIONS_REPORT'
PLAY_SIMULATION = 'PLAY_SIMULATION'
SAVE_METRICS = 'SAVE_METRICS'
DCOP_ALGORITHM = 'DCOP_ALGORITHM'
DISCONNECTION_MESSAGE = 'DISCONNECTION_MESSAGE'

# factory-agent command message types
DCOP_DONE = 'DCOP_DONE'

# agent channel message types
ANNOUNCE = 'ANNOUNCE_MSG'
ANNOUNCE_RESPONSE = 'ANNOUNCE_RESPONSE_MSG'
ADD_ME = 'ADD_ME'
CHILD_ADDED = 'CHILD_ADDED'
PARENT_ASSIGNED = 'PARENT_ASSIGNED'
ALREADY_ACTIVE = 'ALREADY_ACTIVE'
PING = 'PING'
PING_RESPONSE = 'PING_RESPONSE'
CONSTRAINT_CHANGED = 'CONSTRAINT_CHANGED'

# monitor channel message types
AGENT_CONNECTION_MSG = 'AGENT_CONNECTION_MSG'
AGENT_REGISTRATION = 'AGENT_REGISTRATION'
AGENT_CPA_REPORT = 'AGENT_CPA_REPORT'
AGENT_DISCONNECTION = 'AGENT_DISCONNECTION'
AGENT_RESET = 'AGENT_RESET'
AGENT_STATE_CHANGED = 'AGENT_STATE_CHANGED'
AGENT_SHUTDOWN = 'AGENT_SHUTDOWN'
AGENT_REPORT = 'AGENT_REPORT'

METRICS_REPORT = 'METRICS_REPORT'

# C-CoCoA message types
UPDATE_STATE_MESSAGE = 'UpdateStateMsg'
INQUIRY_MESSAGE = 'InquiryMessage'
COST_MESSAGE = 'CostMessage'

# SDPOP message types
VALUE_MESSAGE = 'ValueMessage'
UTIL_MESSAGE = 'UtilMessage'
REQUEST_UTIL_MESSAGE = 'RequestUtilMessage'


def _create_msg(msg_type, data):
    return json.dumps({
        'type': msg_type,
        'payload': data,
        'timestamp': datetime.datetime.now().timestamp()
    })


def create_test_message(data):
    return _create_msg(TEST, data)


def create_announce_message(data):
    return _create_msg(ANNOUNCE, data)


def create_add_me_message(data):
    return _create_msg(ADD_ME, data)


def create_child_added_message(data):
    return _create_msg(CHILD_ADDED, data)


def create_parent_assigned_message(data):
    return _create_msg(PARENT_ASSIGNED, data)


def create_announce_response_message(data):
    return _create_msg(ANNOUNCE_RESPONSE, data)


def create_already_active_message(data):
    return _create_msg(ALREADY_ACTIVE, data)


def create_agent_connection_message(data):
    return _create_msg(AGENT_CONNECTION_MSG, data)


def create_update_state_message(data):
    return _create_msg(UPDATE_STATE_MESSAGE, data)


def create_inquiry_message(data):
    return _create_msg(INQUIRY_MESSAGE, data)


def create_cost_message(data):
    return _create_msg(COST_MESSAGE, data)


def create_cpa_report_message(data):
    return _create_msg(AGENT_CPA_REPORT, data)


def create_ping_message(data):
    return _create_msg(PING, data)


def create_ping_response_message(data):
    return _create_msg(PING_RESPONSE, data)


def create_agent_disconnection_message(data):
    return _create_msg(AGENT_DISCONNECTION, data)


def create_agent_reset_message(data):
    return _create_msg(AGENT_RESET, data)


def create_agent_state_changed_message(data):
    return _create_msg(AGENT_STATE_CHANGED, data)


def create_agent_shutdown_message(data):
    return _create_msg(AGENT_SHUTDOWN, data)


def create_agent_report(data):
    return _create_msg(AGENT_REPORT, data)


def create_saved_simulations_report(data):
    return _create_msg(SAVED_SIMULATIONS_REPORT, data)


def create_constraint_changed_message(data):
    return _create_msg(CONSTRAINT_CHANGED, data)


def create_value_message(data):
    return _create_msg(VALUE_MESSAGE, data)


def create_util_message(data):
    return _create_msg(UTIL_MESSAGE, data)


def create_metrics_report(data):
    return _create_msg(METRICS_REPORT, data)


def create_dcop_algorithm_report(data):
    return _create_msg(DCOP_ALGORITHM, data)


def create_request_util_message(data):
    return _create_msg(REQUEST_UTIL_MESSAGE, data)


def create_dcop_done_message(data):
    return _create_msg(DCOP_DONE, data)


def create_disconnection_message(data):
    return _create_msg(DISCONNECTION_MESSAGE, data)
