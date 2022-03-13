import styled from 'styled-components';
import addIcon from "../assets/add-icon.svg";
import removeIcon from "../assets/remove-icon.svg";
import changeIcon from "../assets/changeicon.svg";
import saveIcon from "../assets/save-icon.svg";
import playIcon from "../assets/play-icon.svg";
import AgentNetwork from "./AgentNetwork";
import Console from "./Console";
import {useDispatch, useSelector} from "react-redux";
import {
    addAgent,
    changeConstraint,
    playSelectedSimulation,
    removeAgent,
    saveSimulation
} from "../store/actions/actions";
import {useState} from "react";


function SimulationPanel() {
    const dispatch = useDispatch();

    const [numAgents, setNumAgents] = useState(1);
    const handleNumAgentsChange = (e) => setNumAgents(e.target.value)

    const nodes = useSelector(state => state.graph.nodes);
    const edges = useSelector(state => state.graph.edges);
    const saved_simulations = useSelector(state => state.app.simulations);

    const [selectedSimulation, setSelectedSimulation] = useState('');

    const handleAddAgent = () => dispatch(addAgent(numAgents));
    const handleRemoveAgent = () => dispatch(removeAgent(numAgents));
    const handleChangeConstraint = () => dispatch(changeConstraint(numAgents));
    const handleSaveSimulation = () => dispatch(saveSimulation());
    const handleSavedSimulationChange = (e) => setSelectedSimulation(e.target.value);
    const handlePlaySimulation = () => dispatch(playSelectedSimulation(selectedSimulation));

    return (
        <>
            <Controls>
                <div>
                    <Button onClick={handleAddAgent}>
                        <img src={addIcon} alt=""/>
                        <span>Add Agents</span>
                    </Button>
                    <label htmlFor="numAgentsSelect">Num. of agents: </label>
                    <input type="Number" min="0"
                           value={numAgents}
                           onChange={handleNumAgentsChange}
                           style={{width:'50px'}}
                    />
                </div>

                <Button onClick={handleRemoveAgent}>
                    <img src={removeIcon} alt=""/>
                    <span>Remove Agents</span>
                </Button>

                <Button onClick={handleChangeConstraint}>
                    <img src={changeIcon} alt=""/>
                    <span>Change Constraint</span>
                </Button>

                <Button onClick={handleSaveSimulation}>
                    <img src={saveIcon} alt=""/>
                    <span>Save Simulation</span>
                </Button>

                <Button onClick={handlePlaySimulation}>
                    <img src={playIcon} alt=""/>
                    <span>Play Simulation</span>
                </Button>

            </Controls>
            <DisplayArea>
                <GraphArea>
                    <NorthPanel>
                        <span>Number of agents - {nodes.length}</span>
                        <select onChange={handleSavedSimulationChange} value={selectedSimulation}>
                            <option key={-1} value=''>--- Select Simulation ---</option>
                            {
                                saved_simulations?.map((sim, key) => {
                                    return (<option key={key} value={sim.filename}>{sim.date}</option>)
                                })
                            }
                        </select>
                    </NorthPanel>
                    <Graph>
                        <AgentNetwork nodes={nodes} edges={edges}/>
                    </Graph>
                </GraphArea>
                <SimConsole>
                    <Console/>
                </SimConsole>
            </DisplayArea>
        </>
    );
}

export default SimulationPanel;


const Controls = styled.div`
  grid-column: 1/3;
  //border: 1px solid black;
  width: 100%;
  display: flex;
  gap: 1em;
  justify-content: center;
`;

const GraphArea = styled.div`
  display: flex;
  flex-direction: column;
  gap: 1em;
  width: 70%;
`;

const NorthPanel = styled.div`
  display: flex;
  justify-content: space-between;

  :first-child {
    color: #00199B;
    font-style: normal;
    font-weight: 600;
    font-size: 19px;
    line-height: 28px;
  }

  select {
    color: #01199B;
    font-style: normal;
    font-weight: 500;
    font-size: 17px;
    line-height: 25px;

    border: 1.5px solid #0400CF;
    box-sizing: border-box;
    border-radius: 15px;
    min-width: 30%;
  }
`;

const SimConsole = styled.div`
  width: 30%;
  justify-self: end;
`;

const DisplayArea = styled.div`
  display: flex;
  flex-direction: row;
  gap: 1em;
`;

const Button = styled.button`
  display: flex;
  color: #FFFFFF;
  width: 216px;
  height: 58px;
  background: #212121;
  border: 2px solid #212121;
  box-sizing: border-box;
  border-radius: 18px;
  align-items: center;
  justify-content: center;
  gap: 1em;
  cursor: pointer;

  font-style: normal;
  font-weight: 400;
  font-size: 14px;
  line-height: 25px;
  text-align: center;

  :active {
    background-color: grey;
  }
`;

const Graph = styled.div`
  border: 1px solid rgba(180, 180, 180, 0.8);
  border-radius: 1em;
  height: 80vh;
`;

const Select = styled.select`
  border-radius: 15px;
  min-width: 30%;
`;