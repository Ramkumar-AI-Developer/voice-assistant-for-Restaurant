import { useState, useEffect, useRef } from 'react';
import { HiOutlineShoppingCart, HiOutlineCurrencyDollar, HiOutlinePhone, HiOutlineClock } from 'react-icons/hi';
import { dashboardAPI } from '../services/api';

export default function Dashboard() {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [wsConnected, setWsConnected] = useState(false);
  const [recentEvents, setRecentEvents] = useState([]);
  const wsRef = useRef(null);

  useEffect(() => {
    loadStats();
    connectWebSocket();
    return () => {
      if (wsRef.current) wsRef.current.close();
    };
  }, []);

  const loadStats = async () => {
    try {
      const res = await dashboardAPI.stats();
      setStats(res.data);
    } catch (err) {
      console.error('Failed to load stats:', err);
    } finally {
      setLoading(false);
    }
  };

  const connectWebSocket = () => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const apiBase = import.meta.env.VITE_API_URL || window.location.origin;
    const wsHost = apiBase.replace(/^https?:\/\//, '');
    const wsUrl = `${protocol}//${wsHost}/ws/dashboard`;

    try {
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        setWsConnected(true);
        console.log('Dashboard WebSocket connected');
      };

      ws.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        if (msg.type === 'heartbeat' || msg.type === 'pong') return;

        // Add event to recent events feed
        setRecentEvents(prev => [{
          type: msg.type,
          data: msg.data,
          time: new Date().toLocaleTimeString(),
        }, ...prev].slice(0, 10));

        // Refresh stats on important events
        if (['new_order', 'call_ended', 'order_update'].includes(msg.type)) {
          loadStats();
        }
      };

      ws.onclose = () => {
        setWsConnected(false);
        // Auto-reconnect after 3 seconds
        setTimeout(connectWebSocket, 3000);
      };

      ws.onerror = () => setWsConnected(false);

      // Ping every 25 seconds to keep alive
      const pingInterval = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) ws.send('ping');
      }, 25000);

      ws.addEventListener('close', () => clearInterval(pingInterval));
    } catch (err) {
      console.error('WebSocket connection failed:', err);
    }
  };

  if (loading) return <div className="loading"><div className="spinner" /></div>;

  const today = stats?.today || {};
  const totals = stats?.totals || {};

  const getGreeting = () => {
    const hour = new Date().getHours();
    if (hour < 12) return 'Good Morning';
    if (hour < 17) return 'Good Afternoon';
    return 'Good Evening';
  };

  return (
    <div>
      {/* ── Welcome Banner ───────────────────────────────────────────────── */}
      <div className="welcome-banner">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div>
            <h1>{getGreeting()}, Vasantha Vilas 🍃</h1>
            <p>Here's how your AI voice assistant is performing today</p>
          </div>
          <div className="live-indicator">
            <div className="live-dot" />
            {wsConnected ? 'Live' : 'Reconnecting...'}
          </div>
        </div>
      </div>

      {/* ── Today's Stats ─────────────────────────────────────────────────── */}
      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-icon blue"><HiOutlineShoppingCart /></div>
          <div className="stat-value">{today.orders || 0}</div>
          <div className="stat-label">Orders Today</div>
        </div>
        <div className="stat-card">
          <div className="stat-icon green"><HiOutlineCurrencyDollar /></div>
          <div className="stat-value">£{(today.revenue || 0).toFixed(2)}</div>
          <div className="stat-label">Revenue Today</div>
        </div>
        <div className="stat-card">
          <div className="stat-icon purple"><HiOutlinePhone /></div>
          <div className="stat-value">{today.calls || 0}</div>
          <div className="stat-label">Calls Today</div>
        </div>
        <div className="stat-card">
          <div className="stat-icon yellow"><HiOutlineClock /></div>
          <div className="stat-value">{today.avg_call_duration || 0}s</div>
          <div className="stat-label">Avg. Call Duration</div>
        </div>
      </div>

      {/* ── Weekly Trend + Totals ─────────────────────────────────────────── */}
      <div className="grid-2">
        <div className="card">
          <div className="card-header">
            <span className="card-title">Weekly Order Trend</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'flex-end', gap: 8, height: 120, padding: '0 8px' }}>
            {(stats?.weekly_trend || []).map((day, i) => {
              const maxOrders = Math.max(...(stats?.weekly_trend || []).map(d => d.orders), 1);
              const height = Math.max(8, (day.orders / maxOrders) * 100);
              return (
                <div key={i} style={{ flex: 1, textAlign: 'center' }}>
                  <div style={{
                    height: `${height}px`,
                    background: 'var(--gradient-gold)',
                    borderRadius: '4px 4px 0 0',
                    transition: 'height 0.5s ease',
                    marginBottom: 6,
                  }} />
                  <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>{day.day}</div>
                  <div style={{ fontSize: 11, color: 'var(--text-secondary)', fontWeight: 600 }}>{day.orders}</div>
                </div>
              );
            })}
          </div>
        </div>

        <div className="card">
          <div className="card-header">
            <span className="card-title">All-Time Totals</span>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ color: 'var(--text-secondary)', fontSize: 14 }}>Total Orders</span>
              <span style={{ fontSize: 18, fontWeight: 700 }}>{totals.orders || 0}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ color: 'var(--text-secondary)', fontSize: 14 }}>Total Revenue</span>
              <span style={{ fontSize: 18, fontWeight: 700, color: 'var(--success)' }}>£{(totals.revenue || 0).toFixed(2)}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ color: 'var(--text-secondary)', fontSize: 14 }}>Total Calls</span>
              <span style={{ fontSize: 18, fontWeight: 700 }}>{totals.calls || 0}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ color: 'var(--text-secondary)', fontSize: 14 }}>Pending Orders</span>
              <span className="badge badge-warning">{stats?.pending_orders || 0}</span>
            </div>
          </div>
        </div>
      </div>

      {/* ── Live Activity Feed ────────────────────────────────────────────── */}
      {recentEvents.length > 0 && (
        <div className="card" style={{ marginTop: 20 }}>
          <div className="card-header">
            <span className="card-title">Live Activity</span>
            <div className="live-indicator"><div className="live-dot" />Real-time</div>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {recentEvents.map((evt, i) => (
              <div key={i} style={{
                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                padding: '10px 14px', background: 'var(--bg-warm)', borderRadius: 'var(--radius-sm)',
                fontSize: 13, animation: i === 0 ? 'fadeIn 0.3s' : 'none',
                borderLeft: '3px solid var(--accent-gold)',
              }}>
                <span>
                  {evt.type === 'new_order' && `🛒 New order from ${evt.data?.customer_name || 'customer'} — £${evt.data?.total?.toFixed(2) || '0.00'}`}
                  {evt.type === 'call_started' && `📞 Call started`}
                  {evt.type === 'call_ended' && `📴 Call ended (${evt.data?.duration || 0}s)`}
                  {evt.type === 'order_update' && `➕ ${evt.data?.item || 'Item'} added to order`}
                </span>
                <span style={{ color: 'var(--text-muted)', fontSize: 11 }}>{evt.time}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Recent Orders ─────────────────────────────────────────────────── */}
      <div className="card" style={{ marginTop: 20 }}>
        <div className="card-header">
          <span className="card-title">Recent Orders</span>
        </div>
        <div className="table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th>Order #</th>
                <th>Customer</th>
                <th>Total</th>
                <th>Status</th>
                <th>Time</th>
              </tr>
            </thead>
            <tbody>
              {(stats?.recent_orders || []).length === 0 ? (
                <tr><td colSpan={5} style={{ textAlign: 'center', padding: 32, color: 'var(--text-muted)' }}>No orders yet</td></tr>
              ) : (
                (stats?.recent_orders || []).map((o) => (
                  <tr key={o.id}>
                    <td style={{ fontWeight: 600 }}>#{o.id}</td>
                    <td>{o.customer_name}</td>
                    <td style={{ fontWeight: 600, color: 'var(--success)' }}>£{o.total?.toFixed(2)}</td>
                    <td><span className={`badge badge-${getStatusColor(o.status)}`}>{o.status}</span></td>
                    <td style={{ color: 'var(--text-muted)' }}>{o.created_at ? new Date(o.created_at).toLocaleTimeString() : '-'}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function getStatusColor(status) {
  const map = { pending: 'warning', confirmed: 'info', preparing: 'primary', ready: 'success', completed: 'success', cancelled: 'danger' };
  return map[status] || 'muted';
}
