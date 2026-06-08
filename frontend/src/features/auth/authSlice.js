import { createSlice } from "@reduxjs/toolkit";


const initialState = {
  isLoggedIn: false,
  email: null,
  displayName: null,
};

const authSlice = createSlice({
  name: "auth",
  initialState,
  reducers: {
    loginUser: (state, action) => {
      const email = action.payload.email.trim();
      state.isLoggedIn = true;
      state.email = email;
      state.displayName = email.split("@")[0] || "Turkcell User";
    },
    logout: (state) => {
      state.isLoggedIn = false;
      state.email = null;
      state.displayName = null;
    },
  },
});

export const { loginUser, logout } = authSlice.actions;
export default authSlice.reducer;
