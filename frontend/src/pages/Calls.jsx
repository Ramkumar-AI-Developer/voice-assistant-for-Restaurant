import { useState, useEffect } from 'react';
import { HiOutlineEye, HiOutlineX } from 'react-icons/hi';
import toast from 'react-hot-toast';
import { callsAPI } from '../services/api';

export default function Calls() {
  const [data, setData] = useState({ calls: [], total: 0, page: 1, pages: 0 });
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [selectedCall, setSelectedCall] = useState(null);

  useEffect(() => { loadCalls(); }, [page]);

  const loadCalls = async () => {
    setLoading(true);
    try {
      const res = await callsAPI.list(page);
      setData(res.data);
    } catch (err) {
      toast.error('Failed to load call history');
    } finally { setLoading(false); }
  };

  const viewCall = async (id) => {
    try {
      const res = await callsAPI.get(id);
      setSelectedCall(res.data);
    } catch (err) {
      toast.error('Failed to load call details');
    }
  };

  const statusColor = (s) => ({
    in_progress: 'info', completed: 'success', failed: 'danger', abandoned: 'warning'
  }[s] || 'muted');

  const formatDuration = (seconds) => {
    if (!seconds) return '—';
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${m}m ${s}s`;
  };

  return (
    <div>
      <div className="page-header">
        <h1>Call History</h1>
        <p>View all AI voice call details and conversation transcripts</p>
      </div>

      <div className="card">
        {loading ? (
          <div className="loading"><div className="spinner" /></div>
        ) : data.calls.length === 0 ? (
          <div className="empty-state">
            <h3>No call history yet</h3>
            <p>Call logs will appear here when customers call your AI assistant</p>
          </div>
        ) : (
          <>
            <div className="table-container">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>#</th>
                    <th>Phone</th>
                    <th>Customer</th>
                    <th>Status</th>
                    <th>Duration</th>
                    <th>Order</th>
                    <th>Time</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {data.calls.map((c) => (
                    <tr key={c.id}>
                      <td>{c.id}</td>
                      <td style={{ fontFamily: 'monospace', fontSize: 12 }}>{c.phone_number}</td>
                      <td>{c.customer_name || '—'}</td>
                      <td><span className={`badge badge-${statusColor(c.status)}`}>{c.status?.replace('_', ' ')}</span></td>
                      <td>{formatDuration(c.duration_seconds)}</td>
                      <td>{c.order_id ? <span className="badge badge-success">#{c.order_id}</span> : <span style={{ color: 'var(--text-muted)' }}>—</span>}</td>
                      <td style={{ color: 'var(--text-muted)', fontSize: 12 }}>{c.started_at ? new Date(c.started_at).toLocaleString() : '-'}</td>
                      <td>
                        <button className="btn btn-sm btn-secondary btn-icon" onClick={() => viewCall(c.id)} title="View Transcript"><HiOutlineEye /></button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="pagination">
              <button disabled={page <= 1} onClick={() => setPage(page - 1)}>Previous</button>
              <span>Page {data.page} of {data.pages}</span>
              <button disabled={page >= data.pages} onClick={() => setPage(page + 1)}>Next</button>
            </div>
          </>
        )}
      </div>

      {/* ── Call Transcript Modal ─────────────────────────────────────────── */}
      {selectedCall && (
        <div className="modal-overlay" onClick={() => setSelectedCall(null)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 600 }}>
            <div className="modal-header">
              <h2>Call Transcript</h2>
              <button className="modal-close" onClick={() => setSelectedCall(null)}><HiOutlineX /></button>
            </div>

            <div style={{ display: 'grid', gap: 8, fontSize: 13, marginBottom: 16 }}>
              <div><strong>Phone:</strong> {selectedCall.phone_number}</div>
              <div><strong>Customer:</strong> {selectedCall.customer_name || 'Unknown'}</div>
              <div><strong>Status:</strong> <span className={`badge badge-${statusColor(selectedCall.status)}`}>{selectedCall.status?.replace('_', ' ')}</span></div>
              <div><strong>Duration:</strong> {formatDuration(selectedCall.duration_seconds)}</div>
              {selectedCall.order_id && <div><strong>Order:</strong> <span className="badge badge-success">#{selectedCall.order_id}</span></div>}
            </div>

            <div className="card-title" style={{ marginBottom: 12 }}>Conversation</div>

            {(selectedCall.messages || []).length === 0 ? (
              <div className="empty-state" style={{ padding: 24 }}>
                <p>No transcript available</p>
              </div>
            ) : (
              <div className="transcript">
                {selectedCall.messages.map((msg, i) => (
                  <div key={i} className={`msg-bubble ${msg.role === 'user' ? 'msg-user' : 'msg-assistant'}`}>
                    <div className="msg-label">{msg.role === 'user' ? '👤 Customer' : '🤖 AI Assistant'}</div>
                    {msg.content}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
