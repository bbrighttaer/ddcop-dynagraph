import styled from 'styled-components';
import calendar from '../assets/calendar-icon.svg';
import online from '../assets/online.svg';
import offline from '../assets/offline.svg';
import poweron from '../assets/poweron-icon.svg';
import poweroff from '../assets/poweroff-icon.svg';
import moment from 'moment';
import {useSelector} from "react-redux";

function DashboardBar({isConnected, handleConnect, handleDisconnect}) {
    const dateStr = moment().format('ll');
    const dcop_alg = useSelector(state => state.app.dcop);

    return (
        <Content>
            {dcop_alg && <h3>{`DCOP algorithm in use: ${dcop_alg}`}</h3>}
            <DateArea>
                <img src={calendar} alt=""/>
                <span>{dateStr}</span>
            </DateArea>
            <Separator/>
            <Toggle>
                {isConnected ?
                    <img src={poweron} onClick={handleDisconnect} alt=""/> :
                    <img src={poweroff} onClick={handleConnect} alt=""/>}
            </Toggle>
            <Separator/>
            {isConnected ? <img src={online} alt=""/> : <img src={offline} alt=""/>}
        </Content>
    );
}

export default DashboardBar;

const Content = styled.div`
  display: flex;
  justify-content: flex-end;
  align-items: center;
  height: 10vh;
  width: 100%;
  box-shadow: 0 .2em .2em 0 rgba(221, 221, 221, 0.7);
  background-color: #FFFFFF;

  > * {
    margin-right: 1em;
  }
`;

const DateArea = styled.div`
  display: flex;
  background: #F0F0F0;
  border-radius: 10px;
  width: 146px;
  height: 42px;
  align-items: center;
  gap: .3em;
  padding: .3em;
`;

const Separator = styled.div`
  height: 1.7em;
  border: 1px solid #B6B6B6;
`;

const Toggle = styled.div`
  :hover {
    cursor: pointer;
  }
`;