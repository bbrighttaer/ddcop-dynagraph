import saveIcon from "../assets/save-icon.svg";
import styled from "styled-components";
import {useDispatch} from "react-redux";
import {saveMetrics} from "../store/actions/actions";

function Metrics() {
    const dispatch = useDispatch();

    const handleSaveMetrics = () => dispatch(saveMetrics());


    return (
        <>
            <Controls>
                <Button onClick={handleSaveMetrics}>
                    <img src={saveIcon} alt=""/>
                    <span>Save Metrics</span>
                </Button>
            </Controls>
        </>
    );
}

export default Metrics;

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

const Controls = styled.div`
  grid-column: 1/3;
  width: 100%;
  display: flex;
  gap: 1em;
  justify-content: center;
`;