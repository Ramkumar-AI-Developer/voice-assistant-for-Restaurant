import { createSlice } from '@reduxjs/toolkit';

// Default users for the demo
const DEFAULT_USERS = [
  { username: 'admin', password: 'admin123', email: 'admin@vasanthavilas.com', is_admin: true },
  { username: 'staff', password: 'staff123', email: 'staff@vasanthavilas.com', is_admin: false },
];

const getStoredUsers = () => {
  const users = localStorage.getItem('demo_users');
  if (users) return JSON.parse(users);
  localStorage.setItem('demo_users', JSON.stringify(DEFAULT_USERS));
  return DEFAULT_USERS;
};

const getStoredUser = () => {
  const user = localStorage.getItem('user');
  return user ? JSON.parse(user) : null;
};

const getStoredToken = () => {
  return localStorage.getItem('token') || null;
};

const initialState = {
  user: getStoredUser(),
  token: getStoredToken(),
  users: getStoredUsers(),
  loading: false,
  error: null,
};

const authSlice = createSlice({
  name: 'auth',
  initialState,
  reducers: {
    loginStart: (state) => {
      state.loading = true;
      state.error = null;
    },
    loginSuccess: (state, action) => {
      state.loading = false;
      state.user = { username: action.payload.username, is_admin: action.payload.is_admin };
      state.token = 'dummy-jwt-token-for-demo';
      localStorage.setItem('user', JSON.stringify(state.user));
      localStorage.setItem('token', state.token);
    },
    loginFailure: (state, action) => {
      state.loading = false;
      state.error = action.payload;
    },
    logout: (state) => {
      state.user = null;
      state.token = null;
      localStorage.removeItem('user');
      localStorage.removeItem('token');
    },
    registerStart: (state) => {
      state.loading = true;
      state.error = null;
    },
    registerSuccess: (state, action) => {
      state.loading = false;
      state.users.push(action.payload);
      localStorage.setItem('demo_users', JSON.stringify(state.users));
    },
    registerFailure: (state, action) => {
      state.loading = false;
      state.error = action.payload;
    },
    clearError: (state) => {
      state.error = null;
    },
  },
});

export const {
  loginStart,
  loginSuccess,
  loginFailure,
  logout,
  registerStart,
  registerSuccess,
  registerFailure,
  clearError,
} = authSlice.actions;

// Async simulated actions
export const loginUser = (username, password) => (dispatch, getState) => {
  dispatch(loginStart());
  return new Promise((resolve, reject) => {
    setTimeout(() => {
      const state = getState().auth;
      const user = state.users.find(
        (u) => u.username.toLowerCase() === username.toLowerCase() && u.password === password
      );

      if (user) {
        dispatch(loginSuccess(user));
        resolve(user);
      } else {
        const errorMsg = 'Invalid username or password.';
        dispatch(loginFailure(errorMsg));
        reject(new Error(errorMsg));
      }
    }, 400);
  });
};

export const registerUser = (userData) => (dispatch, getState) => {
  dispatch(registerStart());
  return new Promise((resolve, reject) => {
    setTimeout(() => {
      const state = getState().auth;
      const exists = state.users.some(
        (u) => u.username.toLowerCase() === userData.username.toLowerCase()
      );

      if (exists) {
        const errorMsg = 'Username already exists.';
        dispatch(registerFailure(errorMsg));
        reject(new Error(errorMsg));
      } else {
        const newUser = {
          username: userData.username,
          password: userData.password,
          email: userData.email || '',
          is_admin: !!userData.is_admin,
        };
        dispatch(registerSuccess(newUser));
        resolve(newUser);
      }
    }, 400);
  });
};

export default authSlice.reducer;
