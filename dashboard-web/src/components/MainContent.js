import styled from 'styled-components';
import DashboardBar from "./DashboardBar";
import {useDispatch, useSelector} from "react-redux";
import {useEffect} from "react";
import {connect, disconnect} from "../store/actions/actions";
import {HOME, METRICS, SETTINGS} from "../util";
import SimulationPanel from "./SimulationPanel";
import Metrics from "./Metrics";


function MainContent() {
    const activeApp = useSelector(state => state.app.activeApp);

    let app = null
    switch (activeApp) {
        case HOME:
            app = (<SimulationPanel/>);
            break;
        case METRICS:
            app = (<Metrics/>);
            break;
        case SETTINGS:
            app = (<p>settings.js</p>);
            break;
        default:
            app = (<p>404.js</p>);
    }

    const dispatch = useDispatch();

    const client = useSelector(state => state.app.client);

    // event handlers
    const handleConnect = () => dispatch(connect());
    const handleDisconnect = () => dispatch(disconnect());

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
        <ContentArea>
            <DashboardBar
                isConnected={client}
                handleConnect={handleConnect}
                handleDisconnect={handleDisconnect}/>
            <Content>
                {app}
            </Content>
        </ContentArea>
    );
}

export default MainContent;

const ContentArea = styled.div`
  background-color: whitesmoke;
`;

const Content = styled.div`
  display: flex;
  flex-direction: column;
  gap: 1em;
  grid-template-columns: 1fr 1fr;
  margin: 1em;
`;
