import styled from 'styled-components';
import closeIcon from '../assets/cancel icon.svg';
import robotIcon from '../assets/robot-agent.svg';
import {useDispatch, useSelector} from "react-redux";
import {setShowModal} from "../store/actions/actions";

function Modal() {
    const dispatch = useDispatch();

    const messages = useSelector(state => state.app.receivedMessages);
    const index = useSelector(state => state.app.selectedMessageIndex);
    const message = messages[index];

    const properties = []

    for(let key in message.payload){
        properties.push(
           <Property>
               <PropertyTitle>{`⦿ ${key}:`}</PropertyTitle>
               <PropertyValue>{JSON.stringify(message.payload[key])}</PropertyValue>
           </Property>
        );
    }

    const closeModal = () => dispatch(setShowModal(false));

    return (
        <ModalBackground>
            <Content>
                <ModalMain>
                    <IconSpace>
                        <img src={robotIcon} alt=""/>
                    </IconSpace>
                    <Title>{message.type.replace(/_/g, ' ')}</Title>
                    <Properties>
                        { properties }
                    </Properties>
                </ModalMain>
                <CloseModal onClick={closeModal}>
                    <img src={closeIcon} alt=""/>
                </CloseModal>
            </Content>
        </ModalBackground>
    );
}

export default Modal;

const ModalBackground = styled.div`
  z-index: 999;
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: rgba(0, 0, 0, 0.6);
`;

const Content = styled.div`
  display: flex;
  margin-top: 4%;
  margin-left: 30%;
`;

const ModalMain = styled.div`
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  background-color: #FFFFFF;
  width: 30em;
  height: 35em;
  border-radius: 1em;
  padding-top: 1em;
`;

const CloseModal = styled.div`
  display: flex;
  background-color: rebeccapurple;
  height: 2em;
  width: 2em;
  justify-content: center;
  align-items: center;
  border-radius: 3em;
  cursor: pointer;
`;

const IconSpace = styled.div`
  display: flex;
  justify-content: center;
  align-items: center;
  width: 5em;
  height: 5em;
  background: #D2F0EE;
  border-radius: 5em;
  overflow: hidden;
`;

const Title = styled.span`
  font-style: normal;
  font-weight: 300;
  font-size: 15px;
  line-height: 39px;

  display: flex;
  align-items: center;
  text-align: center;
  overflow: hidden;

  color: #000000;
`;

const Properties = styled.div`
    padding: 1em;
  width: 100%;
`;

const Property = styled.div`
`;

const PropertyTitle = styled.div`
    font-weight: 200;
`;

const PropertyValue = styled.div`
  padding-left: 1em;
    font-size: 13px;
`;