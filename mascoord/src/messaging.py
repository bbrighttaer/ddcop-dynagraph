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
SIM_ENV_CHANNEL = f'{config.DOMAIN}.sim_env'

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
ANNOUNCE_RESPONSE_IGNORED = 'ANNOUNCE_IGNORED_MSG'
ADD_ME = 'ADD_ME'
CHILD_ADDED = 'CHILD_ADDED'
PARENT_ASSIGNED = 'PARENT_ASSIGNED'
ALREADY_ACTIVE = 'ALREADY_ACTIVE'
PING = 'PING'
PING_RESPONSE = 'PING_RESPONSE'
CONSTRAINT_CHANGED = 'CONSTRAINT_CHANGED'
PARENT_AVAILABLE = 'PARENT_AVAILABLE'
PARENT_ALREADY_ASSIGNED = 'PARENT_ALREADY_ASSIGNED'
AGENT_REGISTRATION = 'AGENT_REGISTRATION'
DBFS_LEVEL_MESSAGE = 'LEVEL_MESSAGE'
DBFS_ACK_MESSAGE = 'ACK_MESSAGE'
DBFS_LEVEL_IGNORED_MESSAGE = 'LEVEL_IGNORED_MESSAGE'

# monitor channel message types
AGENT_CONNECTION_MSG = 'AGENT_CONNECTION_MSG'
AGENT_REGISTRATION_DASHBOARD = 'AGENT_REGISTRATION_DASHBOARD'
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
EXECUTION_REQUEST = 'ExecutionRequest'

# SDPOP message types
VALUE_MESSAGE = 'ValueMessage'
UTIL_MESSAGE = 'UtilMessage'
REQUEST_UTIL_MESSAGE = 'RequestUtilMessage'

# Sim environment message
AGENT_ADDED = 'AGENT_ADDED'
AGENT_REMOVED = 'AGENT_REMOVED'
SIM_ENV_CURRENT_TIME_STEP_MSG = 'SIM_ENV_CURRENT_TIME_STEP_MSG'
VALUE_SELECTED_MSG = 'VALUE_SELECTED_MSG'
STOP_AGENT = 'STOP_AGENT'
ADD_GRAPH_EDGE = 'ADD_GRAPH_EDGE'
REMOVE_GRAPH_EDGE = 'REMOVE_GRAPH_EDGE'
DDFS_NEIGHBOR_DATA = 'DDFS_NEIGHBOR_DATA'
DDFS_VALUE_MSG = 'DDFS_VALUE_MSG'
DDFS_POSITION_MSG = 'DDFS_POSITION_MSG'
DDFS_CHILD_MSG = 'DDFS_CHILD_MSG'
DDFS_PSEUDO_CHILD_MSG = 'DDFS_PSEUDO_CHILD_MSG'


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


def create_agent_added_message(data):
    return _create_msg(AGENT_ADDED, data)


def create_agent_removed_message(data):
    return _create_msg(AGENT_REMOVED, data)


def create_sim_env_current_time_step_message(data):
    return _create_msg(SIM_ENV_CURRENT_TIME_STEP_MSG, data)


def create_value_selected_message(data):
    return _create_msg(VALUE_SELECTED_MSG, data)


def create_stop_agent_message(data):
    return _create_msg(STOP_AGENT, data)


def create_announce_response_ignored_message(data):
    return _create_msg(ANNOUNCE_RESPONSE_IGNORED, data)


def create_agent_registration_message(data):
    return _create_msg(AGENT_REGISTRATION, data)


def create_agent_registration_dashboard_message(data):
    return _create_msg(AGENT_REGISTRATION_DASHBOARD, data)


def create_add_graph_edge_message(data):
    return _create_msg(ADD_GRAPH_EDGE, data)


def create_remove_graph_edge_message(data):
    return _create_msg(REMOVE_GRAPH_EDGE, data)


def create_parent_available_message(data):
    return _create_msg(PARENT_AVAILABLE, data)


def create_parent_already_assigned_message(data):
    return _create_msg(PARENT_ALREADY_ASSIGNED, data)


def create_neighbor_data_message(data):
    return _create_msg(DDFS_NEIGHBOR_DATA, data)


def create_ddfs_value_message(data):
    return _create_msg(DDFS_VALUE_MSG, data)


def create_ddfs_position_message(data):
    return _create_msg(DDFS_POSITION_MSG, data)


def create_ddfs_child_message(data):
    return _create_msg(DDFS_CHILD_MSG, data)


def create_ddfs_pseudo_child_message(data):
    return _create_msg(DDFS_PSEUDO_CHILD_MSG, data)


def create_execution_request_message(data):
    return _create_msg(EXECUTION_REQUEST, data)

def create_dbfs_level_message(data):
    return _create_msg(DBFS_LEVEL_MESSAGE, data)

def create_dbfs_ack_message(data):
    return _create_msg(DBFS_ACK_MESSAGE, data)

def create_dbfs_level_ignored_message(data):
    return _create_msg(DBFS_LEVEL_IGNORED_MESSAGE, data)
