import { useState } from 'react';
import { HiOutlinePlus, HiOutlineX } from 'react-icons/hi';
import toast from 'react-hot-toast';
import { authAPI } from '../services/api';

export default function Users() {
  const [showModal, setShowModal] = useState(false);
  const [form, setForm] = useState({ username: '', password: '', email: '', is_admin: false });
  const [loading, setLoading] = useState(false);

  const handleCreate = async () => {
    if (!form.username || !form.password) {
      toast.error('Username and password are required');
      return;
    }
    setLoading(true);
    try {
      await authAPI.register(form);
      toast.success(`User "${form.username}" created successfully`);
      setShowModal(false);
      setForm({ username: '', password: '', email: '', is_admin: false });
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to create user');
    } finally { setLoading(false); }
  };

  return (
    <div>
      <div className="page-header">
        <h1>User Management</h1>
        <p>Create new dashboard users (admin access only)</p>
        <div className="page-actions">
          <button className="btn btn-primary" onClick={() => setShowModal(true)}>
            <HiOutlinePlus /> Create User
          </button>
        </div>
      </div>

      <div className="card">
        <div className="empty-state">
          <h3>User Management</h3>
          <p>Create new dashboard users by clicking the button above. Only admin accounts can access this page.</p>
        </div>
      </div>

      {/* ── Create User Modal ─────────────────────────────────────────────── */}
      {showModal && (
        <div className="modal-overlay" onClick={() => setShowModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>Create New User</h2>
              <button className="modal-close" onClick={() => setShowModal(false)}><HiOutlineX /></button>
            </div>

            <div className="form-group">
              <label className="form-label">Username *</label>
              <input className="form-input" value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} placeholder="e.g. john_staff" />
            </div>
            <div className="form-group">
              <label className="form-label">Password *</label>
              <input className="form-input" type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} placeholder="Minimum 6 characters" />
            </div>
            <div className="form-group">
              <label className="form-label">Email (optional)</label>
              <input className="form-input" type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} placeholder="user@restaurant.com" />
            </div>
            <div className="form-group">
              <label className="checkbox-label">
                <input type="checkbox" checked={form.is_admin} onChange={(e) => setForm({ ...form, is_admin: e.target.checked })} />
                Admin privileges (can create users and manage settings)
              </label>
            </div>

            <div className="modal-footer">
              <button className="btn btn-secondary" onClick={() => setShowModal(false)}>Cancel</button>
              <button className="btn btn-primary" onClick={handleCreate} disabled={loading}>
                {loading ? 'Creating…' : 'Create User'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
