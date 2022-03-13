import {
    CLEAR_MESSAGES,
    CONNECT,
    DISCONNECT,
    RECEIVED_MESSAGE, SET_ACTIVE_APP, SET_DCOP_ALGORITHM,
    SET_SAVED_SIMULATIONS,
    SET_SELECTED_MESSAGE_INDEX,
    SET_SHOW_MODAL
} from "../actionTypes";
import {HOME} from "../../util";

const init_state = {
    client: null,
    simulations: null,
    showModal: false,
    receivedMessages: [],
    selectedMessageIndex: null,
    activeApp: HOME,
    dcop: null,
};

const appReducer = (state = init_state, action) => {
    switch (action.type) {
        case CONNECT:
            return {
                ...state,
                client: action.client,
            };
        case DISCONNECT:
            return {
                ...state,
                client: null,
            };
        case SET_SAVED_SIMULATIONS:
            return {
                ...state,
                simulations: action.simulations,
            };
        case SET_SHOW_MODAL:
            return {
                ...state,
                showModal: action.showModal,
            }
        case RECEIVED_MESSAGE:
            return {
                ...state,
                receivedMessages: [...state.receivedMessages, action.message],
            }
        case SET_SELECTED_MESSAGE_INDEX:
            return {
                ...state,
                selectedMessageIndex: action.index,
            }
        case SET_ACTIVE_APP:
            return {
                ...state,
                activeApp: action.activeApp,
            }
        case SET_DCOP_ALGORITHM:
            return {
                ...state,
                dcop: action.dcop,
            }
        case CLEAR_MESSAGES:
            return {
                ...state,
                receivedMessages: [state.receivedMessages?.[0]],
            }
        default:
            return state;
    }
}

export default appReducer;