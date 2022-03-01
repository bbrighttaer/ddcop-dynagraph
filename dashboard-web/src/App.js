import './App.css';
import {useDispatch, useSelector} from "react-redux";
import {
    addAgent,
    changeConstraint,
    connect,
    disconnect, playSelectedSimulation,
    removeAgent,
    saveSimulation,
    testCommand
} from "./store/actions/actions";
import {useEffect, useState} from "react";
import AgentNetwork from "./components/AgentNetwork";

function App() {
    const dispatch = useDispatch();

    const [selectedSimulation, setSelectedSimulation] = useState('');

    const nodes = useSelector(state => state.graph.nodes);
    const edges = useSelector(state => state.graph.edges);
    const client = useSelector(state => state.app.client);
    const saved_simulations = useSelector(state => state.app.simulations);

    // event handlers
    const handleConnect = () => dispatch(connect());
    const handleDisconnect = () => dispatch(disconnect());
    const sendTestCommand = () => dispatch(testCommand());
    const handleAddAgent = () => dispatch(addAgent());
    const handleRemoveAgent = () => dispatch(removeAgent());
    const handleChangeConstraint = () => dispatch(changeConstraint());
    const handleSaveSimulation = () => dispatch(saveSimulation());
    const handleSavedSimulationChange = (e) => setSelectedSimulation(e.target.value);
    const handlePlaySimulation = () => dispatch(playSelectedSimulation(selectedSimulation));

    // connect on startup
    useEffect(() => {
        dispatch(connect());
    }, [dispatch]);

    // client ops
    useEffect(() => {
        if (client) {
            client.on('message', (data) => {
                console.log(data);
            });
        }
    }, [client, dispatch]);

    return (
        <div>
            <button onClick={handleConnect}>Connect</button>
            <button onClick={handleDisconnect}>Disconnect</button>
            <button onClick={sendTestCommand}>Test Command</button>
            <button onClick={handleAddAgent}>Add Agent</button>
            <button onClick={handleRemoveAgent}>Remove Agent</button>
            <button onClick={handleChangeConstraint}>Change Constraint</button>
            <button onClick={handleSaveSimulation}>Save Simulation</button>
            <br/>
            <select onChange={handleSavedSimulationChange} value={selectedSimulation}>
                <option key={-1} value=''>--- Select Simulation ---</option>
                {
                    saved_simulations?.map((sim, key) => {
                        return (<option key={key} value={sim.filename}>{sim.date}</option>)
                    })
                }
            </select>
            <button onClick={handlePlaySimulation}>Play Simulation</button>
            <p>Number of agents {nodes.length}</p>
            <AgentNetwork nodes={nodes} edges={edges}/>
        </div>
    );
}

export default App;