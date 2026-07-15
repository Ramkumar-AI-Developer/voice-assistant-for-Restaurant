import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useDispatch, useSelector } from 'react-redux';
import { loginUser, clearError } from '../store/authSlice';

export default function Login() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const navigate = useNavigate();
  const dispatch = useDispatch();

  const { loading, error, token } = useSelector((state) => state.auth);

  useEffect(() => {
    dispatch(clearError());
  }, [dispatch]);

  useEffect(() => {
    if (token) {
      navigate('/');
    }
  }, [token, navigate]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      await dispatch(loginUser(username, password));
    } catch (err) {
      // Error handled by slice
    }
  };

  return (
    <div className="login-page">
      {/* ── Branded Left Panel ─────────────────────────────────────────── */}
      <div className="login-brand-panel">
        <div className="brand-logo-container">
          <div className="">
            <img src="/favicon.png" alt="Shiva Vilas" style={{ width: 100, height: 100, objectFit: 'contain' }} />
          </div>
          <h1 className="brand-title">Shiva Vilas</h1>
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
            Shiva Vilas · AI Voice Assistant Dashboard
          </p>
        </div>
      </div>
    </div>
  );
}
