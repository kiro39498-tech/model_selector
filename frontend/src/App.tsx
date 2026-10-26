import { Routes, Route, Navigate } from "react-router-dom";
import ChatHome from "./screens/ChatHome";
import Welcome from "./screens/Welcome";
import ApiDocs from "./screens/ApiDocs";
import Discovery from "./screens/Discovery";
import RequirementsReview from "./screens/RequirementsReview";
import Architecture from "./screens/Architecture";
import ModelComparison from "./screens/ModelComparison";
import Evaluation from "./screens/Evaluation";
import Settings from "./screens/Settings";

export default function App() {
  return (
    <div className="min-h-screen bg-canvas text-ink">
      <Routes>
        <Route path="/" element={<ChatHome />} />
        <Route path="/new-project" element={<Welcome />} />
        <Route path="/api-docs" element={<ApiDocs />} />
        <Route path="/projects/:projectId/discovery" element={<Discovery />} />
        <Route path="/projects/:projectId/requirements" element={<RequirementsReview />} />
        <Route path="/projects/:projectId/architecture" element={<Architecture />} />
        <Route path="/projects/:projectId/models" element={<ModelComparison />} />
        <Route path="/projects/:projectId/evaluation" element={<Evaluation />} />
        <Route path="/projects/:projectId/settings" element={<Settings />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </div>
  );
}
