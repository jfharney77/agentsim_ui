import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { LandingPage } from "./pages/LandingPage";
import { SetupPage } from "./pages/SetupPage";
import { RunView } from "./pages/RunView";
import { ParallelPage } from "./pages/ParallelPage";

export function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/setup" element={<SetupPage />} />
        <Route path="/run/:runGroupId" element={<RunView />} />
        <Route path="/parallel" element={<ParallelPage />} />
        <Route path="/parallel/:runGroupId" element={<ParallelPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
