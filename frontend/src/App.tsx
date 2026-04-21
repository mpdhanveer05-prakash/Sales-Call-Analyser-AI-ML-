import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { useAuthStore } from "@/store/authStore";
import ToastContainer from "@/components/ui/ToastContainer";
import LoginPage from "@/pages/LoginPage";
import UploadPage from "@/pages/UploadPage";
import CallsListPage from "@/pages/CallsListPage";
import CallDetailPage from "@/pages/CallDetailPage";
import SettingsPage from "@/pages/SettingsPage";
import SearchPage from "@/pages/SearchPage";
import AgentScorecardPage from "@/pages/AgentScorecardPage";
import AgentComparePage from "@/pages/AgentComparePage";
import TeamDashboardPage from "@/pages/TeamDashboardPage";
import Layout from "@/components/Layout";

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const token = useAuthStore((s) => s.token);
  return token ? <>{children}</> : <Navigate to="/login" replace />;
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <Layout />
            </ProtectedRoute>
          }
        >
          <Route index element={<Navigate to="/calls" replace />} />
          <Route path="calls" element={<CallsListPage />} />
          <Route path="calls/:id" element={<CallDetailPage />} />
          <Route path="upload" element={<UploadPage />} />
          <Route path="settings" element={<SettingsPage />} />
          <Route path="search" element={<SearchPage />} />
          <Route path="agents/:id" element={<AgentScorecardPage />} />
          <Route path="compare" element={<AgentComparePage />} />
          <Route path="dashboard" element={<TeamDashboardPage />} />
        </Route>
        <Route path="*" element={<Navigate to="/calls" replace />} />
      </Routes>
      <ToastContainer />
    </BrowserRouter>
  );
}
