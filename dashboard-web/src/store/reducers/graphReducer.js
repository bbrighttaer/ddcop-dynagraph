import {ADD_EDGE, ADD_NODE, REMOVE_EDGE, REMOVE_NODE} from "../actionTypes";

const init_state = {
    nodes: [],
    edges: [],
}

export function graphReducer(state = init_state, action) {
    switch (action.type) {
        case ADD_NODE:
            if (!state.nodes.some(node => node.id === action.node.id)) {
                return {
                    ...state,
                    nodes: [...state.nodes, action.node],
                };
            }
            return state;
        case REMOVE_NODE:
            let nodes_arr = [];
            for (let i = 0; i < state.nodes.length; i++) {
                if (state.nodes[i].id !== action.node.id){
                    nodes_arr.push(state.nodes[i]);
                }
            }
            return {
                ...state,
                nodes: nodes_arr,
            };
        case ADD_EDGE:
            if (!state.edges.some(edge => edge.id === action.edge.id)) {
                return {
                    ...state,
                    edges: [...state.edges, action.edge],
                };
            }
            return state;
        case REMOVE_EDGE:
            let edge_arr = [];
            for (let i=0; i < state.edges.length; i++){
                if (state.edges[i].id !== action.edge.id){
                    edge_arr.push(state.edges[i]);
                }
            }
            return {
                ...state,
                edges: edge_arr,
            };
        default:
            return state;
    }
}