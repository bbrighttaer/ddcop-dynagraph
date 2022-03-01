import {io} from "socket.io-client";
import {
    ADD_EDGE,
    ADD_NODE,
    CONNECT,
    DISCONNECT, RECEIVED_MESSAGE,
    REMOVE_EDGE,
    REMOVE_NODE, SET_ACTIVE_APP,
    SET_SAVED_SIMULATIONS, SET_SELECTED_MESSAGE_INDEX,
    SET_SHOW_MODAL
} from "../actionTypes";
import {EVT_BROKER_TO_DASHBOARD, EVT_DASHBOARD_COMMAND_CHANNEL, MESSAGE, messageHandler} from "../../logic/messaging";
import {BROKER_PORT, BROKER_URL} from "../../env";

export function connect() {
    return (dispatch) => {
        const client = io(`ws://${BROKER_URL}:${BROKER_PORT}`, {transports: ['websocket']});
        client.on('connect', () => {
            dispatch({
                type: CONNECT,
                client,
            });
            console.log('Connected');

            client.on('disconnect', () => {
                console.log('Disconnected from middleware');
            });

            client.on(EVT_BROKER_TO_DASHBOARD, data => {
                messageHandler(data, dispatch, addNode, removeNode, addEdge, removeEdge,
                    setSavedSimulations, addMessage);
            })
        });

        client.on('connect_error', (err) => {
            console.log('Error connecting to middleware', err);
            dispatch({
                type: DISCONNECT,
            });
        })
    };
}

export function disconnect() {
    return (dispatch, getstate) => {
        const client = getstate().app.client;
        if (client) {
            client.disconnect();
            dispatch({
                type: DISCONNECT,
            });
        }
    };
}

export function testCommand() {
    return (dispatch, getstate) => {
        const state = getstate();
        const client = state.app.client;
        client?.emit(`${EVT_DASHBOARD_COMMAND_CHANNEL}`, {
                type: MESSAGE.TEST,
                message: 'this is a test command'
            }
        );
    };
}

export function addNode(node) {
    return (dispatch) => {
        dispatch({
            type: ADD_NODE,
            node,
        });
    }
}

export function removeNode(node) {
    return (dispatch) => {
        dispatch({
            type: REMOVE_NODE,
            node,
        });
    }
}

export function addEdge(edge) {
    return (dispatch) => {
        dispatch({
            type: ADD_EDGE,
            edge,
        });
    }
}

export function removeEdge(edge) {
    return (dispatch) => {
        dispatch({
            type: REMOVE_EDGE,
            edge,
        });
    }
}

export function addAgent() {
    return (dispatch, getstate) => {
        const state = getstate();
        if (state.app.client) {
            const client = state.app.client;
            client?.emit(EVT_DASHBOARD_COMMAND_CHANNEL, {
                    type: MESSAGE.ADD_AGENT,
                    num_agents: 1
                }
            );
        }
    }
}

export function removeAgent() {
    return (dispatch, getstate) => {
        const state = getstate();
        if (state.app.client) {
            const client = state.app.client;
            client?.emit(EVT_DASHBOARD_COMMAND_CHANNEL, {
                    type: MESSAGE.REMOVE_AGENT,
                    num_agents: 1
                }
            );
        }
    }
}

export function changeConstraint() {
    return (dispatch, getstate) => {
        const state = getstate();
        if (state.app.client) {
            const client = state.app.client;
            client?.emit(EVT_DASHBOARD_COMMAND_CHANNEL, {
                    type: MESSAGE.CHANGE_CONSTRAINT,
                    num_agents: 1
                }
            );
        }
    }
}

export function requestAgentReport(agent_id) {
    return (dispatch, getstate) => {
        const state = getstate();
        if (state.app.client) {
            const client = state.app.client;
            client?.emit(EVT_DASHBOARD_COMMAND_CHANNEL, {
                    type: MESSAGE.REQUEST_AGENT_REPORT,
                    agent_id,
                }
            );
        }
    }
}

export function saveSimulation() {
    return (dispatch, getstate) => {
        const state = getstate();
        if (state.app.client) {
            const client = state.app.client;
            client?.emit(EVT_DASHBOARD_COMMAND_CHANNEL, {
                    type: MESSAGE.SAVE_SIMULATION,
                }
            );
        }
    }
}

export function setSavedSimulations(simulations) {
    return (dispatch) => {
        dispatch({
            type: SET_SAVED_SIMULATIONS,
            simulations,
        });
    }
}

export function playSelectedSimulation(simulation) {
    return (dispatch, getstate) => {
        const state = getstate();
        if (state.app.client && simulation) {
            const client = state.app.client;
            client?.emit(EVT_DASHBOARD_COMMAND_CHANNEL, {
                    type: MESSAGE.PLAY_SIMULATION,
                    simulation,
                }
            );
        } else {
            console.log('Simulation could not be played');
        }
    }
}

export function setShowModal(status) {
    return (dispatch) => {
        dispatch({
           type: SET_SHOW_MODAL,
           showModal: status,
        });
    }
}

export function addMessage(message) {
    return (dispatch) => {
        dispatch({
            type: RECEIVED_MESSAGE,
            message,
        });
    }
}

export function setSelectedMessageIndex(index) {
    return (dispatch) => {
        dispatch({
            type: SET_SELECTED_MESSAGE_INDEX,
            index,
        })
    }
}

export function setActiveApp(activeApp) {
    return (dispatch) => {
        dispatch({
            type: SET_ACTIVE_APP,
            activeApp,
        });
    }
}

export function saveMetrics() {
    return (dispatch, getstate) => {
        const state = getstate();

        if (state.app.client) {
            const client = state.app.client;
            client?.emit(EVT_DASHBOARD_COMMAND_CHANNEL, {
                    type: MESSAGE.SAVE_METRICS,
                }
            );
        } else {
            console.log('Metrics could not be saved');
        }
    }
}