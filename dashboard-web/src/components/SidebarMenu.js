import styled from 'styled-components';

function SidebarMenu({name, isActive, icon, clickFunc}) {
    return (
        <Menu onClick={clickFunc}>
            <VerticalBar isActive={isActive}/>
            <MenuSection isActive={isActive}>
                <img src={icon} alt=""/>
                <span>{name}</span>
            </MenuSection>
        </Menu>
    );
}

export default SidebarMenu;

const Menu = styled.div`
  display: flex;
  height: 3em;
  margin-left: .3em;
  padding-bottom: .16em;

  :hover {
    cursor: pointer;
  }
`;

const VerticalBar = styled.div`
  width: 0;
  border: 3px solid rgba(0, 13, 126, ${({isActive}) => isActive ? 0.8 : 0.});
`;

const MenuSection = styled.div`
  display: flex;
  //border: 1px solid black;
  width: 100%;
  margin-left: .3em;
  align-items: center;
  gap: 3em;

  background: rgba(0, 13, 126, ${({isActive}) => isActive ? 0.2 : 0.});
  border-radius: 8px;
  padding-left: 1.5em;
  margin-right: .3em;
  
  ${({isActive}) => !isActive && `
    :hover {
        background-color: whitesmoke;
    }
  `}
`;