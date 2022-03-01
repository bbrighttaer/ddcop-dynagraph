import styled from 'styled-components';
import logo from '../assets/dynagraph-logo.svg';
import home from '../assets/home icon.svg';
import metric from '../assets/metrics-icon.svg';
import settings from '../assets/settings-icon.svg';
import SidebarMenu from "./SidebarMenu";
import {useDispatch, useSelector} from "react-redux";
import {setActiveApp} from "../store/actions/actions";
import {HOME, METRICS, SETTINGS} from "../util";

function Sidebar() {
    const dispatch = useDispatch();
    const selectedApp = useSelector(state => state.app.activeApp);

    return (
        <Content>
            <LogoSection>
                <img src={logo} alt=""/>
            </LogoSection>
            <MenuSection>
                <SidebarMenu
                    name={'Home'}
                    isActive={HOME === selectedApp}
                    icon={home}
                    clickFunc={() => dispatch(setActiveApp(HOME))}
                />
                <SidebarMenu
                    name={'Metrics'}
                    icon={metric}
                    isActive={METRICS === selectedApp}
                    clickFunc={() => dispatch(setActiveApp(METRICS))}
                />
                <SidebarMenu
                    name={'Settings'}
                    isActive={SETTINGS === selectedApp}
                    icon={settings}
                    clickFunc={() => dispatch(setActiveApp(SETTINGS))}
                />
            </MenuSection>
        </Content>
    );
}

export default Sidebar;

const Content = styled.div`
  background: rgba(220, 217, 255, 0.5);
  display: flex;
  flex-direction: column;

  //> * {
  //  border: 1px solid black;
  //}
`;

const LogoSection = styled.div`
  display: flex;
  height: 10vh;
  font-family: Podkova, serif;
  justify-content: center;
  box-shadow: 0 .2em .2em 0 rgba(221, 221, 221, 0.7);

  > img {
    max-width: 70%;
  }
`;

const MenuSection = styled.div`
  height: 100vh;
  margin-top: 5em;
`;