import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { authAPI } from '../services/api';

export default function Login({ onLogin }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const res = await authAPI.login(username, password);
      localStorage.setItem('token', res.data.access_token);
      onLogin({ username: res.data.username, is_admin: res.data.is_admin });
      navigate('/');
    } catch (err) {
      setError(err.response?.data?.detail || 'Login failed. Check credentials.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-page">
      {/* ── Branded Left Panel ─────────────────────────────────────────── */}
      <div className="login-brand-panel">
        <div className="brand-logo-container">
          <div className="">
            <img src="/favicon.png" alt="Vasantha Vilas" style={{ width: 100, height: 100, objectFit: 'contain' }} />
          </div>
          <h1 className="brand-title">Vasantha Vilas</h1>
          <div className="brand-decorative-line" />
          <p className="brand-subtitle">Indian Vegetarian Restaurant</p>
          <p className="brand-tagline">Since 2005</p>
        </div>
      </div>

      {/* ── Login Form Panel ──────────────────────────────────────────── */}
      <div className="login-form-panel">
        <div className="login-card">
          <div className="login-header">
            <h1>Welcome Back</h1>
            <p>Sign in to your dashboard</p>
          </div>

          {error && <div className="login-error">{error}</div>}

          <form onSubmit={handleSubmit}>
            <div className="form-group">
              <label className="form-label" htmlFor="login-username">Username</label>
              <input
                id="login-username"
                className="form-input"
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="Enter your username"
                required
                autoFocus
              />
            </div>
            <div className="form-group">
              <label className="form-label" htmlFor="login-password">Password</label>
              <input
                id="login-password"
                className="form-input"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Enter your password"
                required
              />
            </div>
            <button
              type="submit"
              className="btn btn-primary"
              disabled={loading}
              style={{ width: '100%', justifyContent: 'center', marginTop: 8, padding: '12px 18px', fontSize: 14 }}
            >
              {loading ? 'Signing in…' : 'Sign In'}
            </button>
          </form>

          <p className="login-footer-text">
            Vasantha Vilas · AI Voice Assistant Dashboard
          </p>
        </div>
      </div>
    </div>
  );
}
