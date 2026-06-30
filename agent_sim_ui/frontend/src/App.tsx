import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { MainPage } from "./pages/MainPage";
import { RunView } from "./pages/RunView";
import { ParallelPage } from "./pages/ParallelPage";

export function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<MainPage />} />
        <Route path="/run/:runGroupId" element={<RunView />} />
        <Route path="/parallel" element={<ParallelPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
