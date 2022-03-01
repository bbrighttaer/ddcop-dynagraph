import {setSavedSimulations} from "../store/actions/actions";

export const EVT_DASHBOARD_COMMAND_CHANNEL = 'dashboard-command';
export const EVT_BROKER_TO_DASHBOARD = 'publish-event';

// monitor channel message types
export const MESSAGE = {
    TEST: 'TEST',
    ADD_AGENT: 'ADD_AGENT',
    REMOVE_AGENT: 'REMOVE_AGENT',
    CHANGE_CONSTRAINT: 'CHANGE_CONSTRAINT',
    AGENT_CONNECTION_MSG: 'AGENT_CONNECTION_MSG',
    AGENT_REGISTRATION: 'AGENT_REGISTRATION',
    AGENT_RESET: 'AGENT_RESET',
    AGENT_STATE_CHANGED: 'AGENT_STATE_CHANGED',
    AGENT_CPA_REPORT: 'AGENT_CPA_REPORT',
    AGENT_DISCONNECTION: 'AGENT_DISCONNECTION',
    AGENT_SHUTDOWN: 'AGENT_SHUTDOWN',
    REQUEST_AGENT_REPORT: 'REQUEST_AGENT_REPORT',
    SAVE_SIMULATION: 'SAVE_SIMULATION',
    SAVED_SIMULATIONS_REPORT: 'SAVED_SIMULATIONS_REPORT',
    PLAY_SIMULATION: 'PLAY_SIMULATION',
    SAVE_METRICS: 'SAVE_METRICS',
};

export function messageHandler(message, dispatch, addNode, removeNode, addEdge,
                               removeEdge, setSavedSimulations, addMessage) {
    //Called each time a message is received
    console.log('Received message:', message, typeof message);
    dispatch(
        addMessage(message)
    );


    const {type, payload} = message;

    if (type === MESSAGE.AGENT_REGISTRATION) {
        dispatch(
            addNode({
                id: payload['agent_id'],
                label: `Agent ${payload['agent_id']}`,
                title: '',
            }));
    } else if (type === MESSAGE.AGENT_CONNECTION_MSG) {
        const {parent, child, constraint} = payload;
        dispatch(
            addEdge({
                id: `${parent}-${child}`,
                from: parent,
                to: child,
                constraint,
            }));
    } else if (type === MESSAGE.AGENT_SHUTDOWN) {
        dispatch(removeNode({
            id: payload['agent_id'],
        }));
    } else if (type === MESSAGE.AGENT_DISCONNECTION) {
        const {node1, node2} = payload;
        dispatch(
            removeEdge({
                id: `${node1}-${node2}`,
            })
        );
        dispatch(
            removeEdge({
                id: `${node2}-${node1}`,
            })
        );
    } else if (type === MESSAGE.SAVED_SIMULATIONS_REPORT) {
        dispatch(setSavedSimulations(payload.simulations));
    }
}