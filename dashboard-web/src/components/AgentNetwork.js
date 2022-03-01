import React from "react";
import Graph from "react-graph-vis";
import {useDispatch} from "react-redux";
import {requestAgentReport} from "../store/actions/actions";

function AgentNetwork({nodes, edges}) {
    const dispatch = useDispatch();

    const graph = {
        nodes,
        edges
    };

    const options = {
        layout: {
            hierarchical: true
        },
        edges: {
            color: "#000000"
        },
        height: "500px"
    };

    const events = {
        select: function (event) {
            const {nodes, edges} = event;
            dispatch(requestAgentReport(nodes[0]));
        }
    };

    return (
        <Graph
            graph={graph}
            options={options}
            events={events}
            getNetwork={network => {
                //  if you want access to vis.js network api you can set the state in a parent component using this property
            }}
        />
    );
}

export default AgentNetwork;