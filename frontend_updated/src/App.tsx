import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import { ProtectedRoute } from './components/ProtectedRoute';
import { Layout } from './components/Layout';
import { LoginPage } from './pages/LoginPage';
import { DashboardPage } from './pages/DashboardPage';
import { UploadPage } from './pages/UploadPage';
import { PreprocessingPage } from './pages/PreprocessingPage';
import { AspectDiscoveryPage } from './pages/AspectDiscoveryPage';
import { SentimentPage } from './pages/SentimentPage';
import { RootCausePage } from './pages/RootCausePage';
import { RecommendationPage } from './pages/RecommendationPage';
import { ReportPage } from './pages/ReportPage';
import { SettingsPage } from './pages/SettingsPage';

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route
            element={
              <ProtectedRoute>
                <Layout />
              </ProtectedRoute>
            }
          >
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/upload" element={<UploadPage />} />
            <Route path="/preprocessing" element={<PreprocessingPage />} />
            <Route path="/aspect-discovery" element={<AspectDiscoveryPage />} />
            <Route path="/sentiment" element={<SentimentPage />} />
            <Route path="/root-cause" element={<RootCausePage />} />
            <Route path="/recommendations" element={<RecommendationPage />} />
            <Route path="/report" element={<ReportPage />} />
            <Route path="/settings" element={<SettingsPage />} />
          </Route>
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
