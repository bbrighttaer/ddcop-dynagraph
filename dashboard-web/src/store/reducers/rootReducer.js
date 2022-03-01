import appReducer from "./appReducer";
import {combineReducers} from "redux";
import {graphReducer} from "./graphReducer";

const rootReducer = combineReducers({
    app: appReducer,
    graph: graphReducer,
});

export default rootReducer;