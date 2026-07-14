import { configureStore } from '@reduxjs/toolkit';
import authReducer from './authSlice';
import menuReducer from './menuSlice';
import orderReducer from './orderSlice';
import callReducer from './callSlice';

export const store = configureStore({
  reducer: {
    auth: authReducer,
    menu: menuReducer,
    orders: orderReducer,
    calls: callReducer,
  },
});

export default store;
