import styled from 'styled-components';
import Sidebar from './components/Sidebar';
import MainContent from './components/MainContent';
import Modal from "./components/Modal";
import {useSelector} from "react-redux";
import {HOME, METRICS} from "./util";
import Metrics from "./components/Metrics";

function DashboardApp() {
    const showModal = useSelector(state => state.app.showModal);

    return (
        <Content>
            <Sidebar/>
            <MainContent/>
            {showModal && <Modal/>}
        </Content>
    );
}

export default DashboardApp;


const Content = styled.div`
  display: grid;
  grid-template-columns: 20% 80%;
  //grid-column-gap: .2em;

  //> * {
  // border: 1px solid black; 
  //}
`;