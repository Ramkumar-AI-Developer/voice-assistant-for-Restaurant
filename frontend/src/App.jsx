import { useEffect } from 'react';
import { Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { useSelector, useDispatch } from 'react-redux';
import { Toaster } from 'react-hot-toast';
import Sidebar from './components/Sidebar';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import Menu from './pages/Menu';
import Orders from './pages/Orders';
import Calls from './pages/Calls';
import Users from './pages/Users';
import { logout } from './store/authSlice';

function ProtectedRoute({ children }) {
  const token = useSelector((state) => state.auth.token);
  if (!token) return <Navigate to="/login" replace />;
  return children;
}

export default function App() {
  const user = useSelector((state) => state.auth.user);
  const location = useLocation();
  const isLogin = location.pathname === '/login';

  return (
    <>
      <Toaster position="top-right" toastOptions={{
        style: { background: '#ffffff', color: '#0f172a', border: '1px solid #e2e8f0', boxShadow: '0 4px 20px rgba(0,0,0,0.08)' },
      }} />
      <div className="app-layout">
        {!isLogin && user && <Sidebar />}
        <main className={isLogin ? 'main-full' : 'main-content'}>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route path="/" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
            <Route path="/menu" element={<ProtectedRoute><Menu /></ProtectedRoute>} />
            <Route path="/orders" element={<ProtectedRoute><Orders /></ProtectedRoute>} />
            <Route path="/calls" element={<ProtectedRoute><Calls /></ProtectedRoute>} />
            <Route path="/users" element={<ProtectedRoute><Users /></ProtectedRoute>} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>
      </div>
    </>
  );
}
