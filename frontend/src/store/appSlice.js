import { createAsyncThunk, createSlice } from "@reduxjs/toolkit";

const gatewayUrl = import.meta.env.VITE_API_GATEWAY_URL || "http://localhost:8280";

export const fetchDashboard = createAsyncThunk("app/fetchDashboard", async (projectId) => {
  const response = await fetch(`${gatewayUrl}/dashboard/${projectId}`);
  if (!response.ok) {
    throw new Error(`Failed to fetch dashboard: ${response.status}`);
  }
  return response.json();
});

const initialState = {
  projectId: "PRJ-DEMO",
  theme: "light",
  status: "idle",
  board: { data: {} },
  forecast: {},
  risk: {},
  error: null,
};

const appSlice = createSlice({
  name: "app",
  initialState,
  reducers: {
    setProjectId(state, action) {
      state.projectId = action.payload;
    },
    toggleTheme(state) {
      state.theme = state.theme === "light" ? "dark" : "light";
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(fetchDashboard.pending, (state) => {
        state.status = "loading";
        state.error = null;
      })
      .addCase(fetchDashboard.fulfilled, (state, action) => {
        state.status = "succeeded";
        state.board = action.payload.board;
        state.forecast = action.payload.forecast;
        state.risk = action.payload.risk;
      })
      .addCase(fetchDashboard.rejected, (state, action) => {
        state.status = "failed";
        state.error = action.error.message;
      });
  },
});

export const { setProjectId, toggleTheme } = appSlice.actions;
export const appReducer = appSlice.reducer;
