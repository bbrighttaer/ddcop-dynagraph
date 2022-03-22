import styled from 'styled-components';
import {useDispatch, useSelector} from "react-redux";
import {setSelectedMessageIndex, setShowModal} from "../store/actions/actions";

function Console() {
    const dispatch = useDispatch();

    const messages = useSelector(state => state.app.receivedMessages);
    messages.sort((m1, m2) => {
        if (m1.timestamp > m2.timestamp) {
            return -1;
        } else {
            return 1;
        }
    });

    const handleOnClick = (index) => {
        dispatch(setSelectedMessageIndex(index));
        dispatch(setShowModal(true));
    }

    return (
        <Content>
            <Header/>
            <Separator/>
            <div>
                {
                    messages?.map((message, key) => {
                        return (
                            <div key={key}>
                                <Record onClick={() => handleOnClick(key)}>
                                    <span>Received message:</span>
                                    <Message>
                                        <MessageTime>{new Date().toLocaleTimeString()}:</MessageTime>
                                        <MessageType>{message.type}</MessageType>
                                    </Message>
                                </Record>
                                <Separator/>
                            </div>
                        );
                    })
                }
            </div>
        </Content>
    );
}

export default Console;

const Content = styled.div`
  background: #000000;
  height: 80vh;
  box-shadow: inset 0px 4px 4px rgba(0, 0, 0, 0.25);
  border-radius: 20px;
  //overflow-y: scroll;
  scroll-behavior: smooth;
  box-sizing: content-box;
`;

const Record = styled.div`
  color: rgba(255, 255, 255, 0.9);
  cursor: pointer;

  > * {
    margin: 0 1em;
  }

  :active {
    background-color: grey;
  }
`;

const Message = styled.div`
  display: flex;
  justify-content: space-between;
`;

const MessageTime = styled.span`
    font-size: 12px;
`;

const MessageType = styled.span`
  color: rgba(2, 188, 10);
  font-size: 14px;
  //font-weight: bold;
`;

const Separator = styled.div`
  width: 100%;
  background-color: #C7C7C7;
  border: 1px solid #C7C7C7;
  box-shadow: 0px 4px 4px rgba(0, 0, 0, 0.25);
`;

const Header = styled.div`
  height: 2em;
`;