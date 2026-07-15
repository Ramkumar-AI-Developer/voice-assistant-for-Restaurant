import { useState, useEffect, useRef } from 'react';
import { HiOutlineShoppingCart, HiOutlineCurrencyDollar, HiOutlinePhone, HiOutlineClock } from 'react-icons/hi';
import { useSelector, useDispatch } from 'react-redux';
import { createOrder } from '../store/orderSlice';
import { addCall } from '../store/callSlice';
import toast from 'react-hot-toast';

export default function Dashboard() {
  const orders = useSelector(state => state.orders.orders);
  const calls = useSelector(state => state.calls.calls);
  const menuItems = useSelector(state => state.menu.items);
  const dispatch = useDispatch();

  const [wsConnected, setWsConnected] = useState(true);
  const [recentEvents, setRecentEvents] = useState([]);
  const activityTimerRef = useRef(null);

  // Seed initial events on load
  useEffect(() => {
    setRecentEvents([
      { type: 'call_ended', data: { duration: 125 }, time: new Date(Date.now() - 30 * 60000).toLocaleTimeString() },
      { type: 'new_order', data: { customer_name: 'Rajesh Patel', total: 23.96 }, time: new Date(Date.now() - 25 * 60000).toLocaleTimeString() },
      { type: 'call_ended', data: { duration: 98 }, time: new Date(Date.now() - 15 * 60000).toLocaleTimeString() },
      { type: 'new_order', data: { customer_name: 'Priya Sharma', total: 15.00 }, time: new Date(Date.now() - 12 * 60000).toLocaleTimeString() },
    ]);

    // Setup simulated activity generator (every 45 seconds)
    activityTimerRef.current = setInterval(generateMockActivity, 45000);

    return () => {
      if (activityTimerRef.current) clearInterval(activityTimerRef.current);
    };
  }, []);

  // Names pool for mock orders
  const mockNames = ['Amit Verma', 'Sanjay Kumar', 'Neha Gupta', 'Rohan Das', 'Komal Mehta', 'Vikram Singh', 'Deepa Rao'];
  const mockPhones = ['+44 7911 223344', '+44 7911 554433', '+44 7911 778899', '+44 7911 990011', '+44 7911 112233'];

  const generateMockActivity = () => {
    const eventType = Math.random() > 0.5 ? 'call_started' : 'new_order';
    const randomName = mockNames[Math.floor(Math.random() * mockNames.length)];
    const randomPhone = mockPhones[Math.floor(Math.random() * mockPhones.length)];
    const timeStr = new Date().toLocaleTimeString();

    if (eventType === 'call_started') {
      // 1. Simulates a call starting
      setRecentEvents(prev => [{
        type: 'call_started',
        data: {},
        time: timeStr,
      }, ...prev].slice(0, 10));

      // After 6 seconds, simulate it completing with an order
      setTimeout(() => {
        const duration = Math.floor(Math.random() * 90) + 40;
        const availableDishes = menuItems.filter(item => item.available);
        const orderItemsCount = Math.floor(Math.random() * 2) + 1;
        const selectedDishes = [];

        for (let i = 0; i < orderItemsCount; i++) {
          const dish = availableDishes[Math.floor(Math.random() * availableDishes.length)];
          if (dish && !selectedDishes.some(d => d.id === dish.id)) {
            selectedDishes.push({
              ...dish,
              quantity: Math.floor(Math.random() * 2) + 1,
              notes: Math.random() > 0.7 ? 'spicy' : '',
            });
          }
        }

        const totalValue = selectedDishes.reduce((sum, item) => sum + (item.price * item.quantity), 0);

        // Dispatch call completion
        const newCallId = Date.now();
        const newOrderId = 1000 + orders.length + 1;

        dispatch(addCall({
          phone_number: randomPhone,
          customer_name: randomName,
          status: 'completed',
          duration_seconds: duration,
          order_id: newOrderId,
          messages: [
            { role: 'assistant', content: 'Shiva Vilas AI Assistant, how can I help?' },
            { role: 'user', content: `Can I get some food? I'd like ${selectedDishes.map(d => `${d.quantity} ${d.name}`).join(' and ')}.` },
            { role: 'assistant', content: `Sure! That's placed for you.` }
          ]
        }));

        dispatch(createOrder({
          customer_name: randomName,
          customer_phone: randomPhone,
          items: selectedDishes,
          total: totalValue,
          order_type: 'call',
        }));

        setRecentEvents(prev => [
          {
            type: 'new_order',
            data: { customer_name: randomName, total: totalValue },
            time: new Date().toLocaleTimeString(),
          },
          {
            type: 'call_ended',
            data: { duration },
            time: new Date().toLocaleTimeString(),
          },
          ...prev
        ].slice(0, 10));

        toast.success(`📞 Call Completed: New order from ${randomName} (₹${totalValue.toFixed(2)})`);
      }, 6000);

    } else {
      // 2. Simulates a Walk-in or Takeaway order directly placed
      const availableDishes = menuItems.filter(item => item.available);
      const dish = availableDishes[Math.floor(Math.random() * availableDishes.length)];
      if (!dish) return;

      const qty = Math.floor(Math.random() * 2) + 1;
      const totalValue = dish.price * qty;

      dispatch(createOrder({
        customer_name: randomName,
        customer_phone: 'Walk-in',
        items: [{ ...dish, quantity: qty, notes: '' }],
        total: totalValue,
        order_type: Math.random() > 0.5 ? 'takeaway' : 'eat in',
      }));

      setRecentEvents(prev => [{
        type: 'new_order',
        data: { customer_name: randomName, total: totalValue },
        time: timeStr,
      }, ...prev].slice(0, 10));

      toast(`🛒 Direct Order from ${randomName} (₹${totalValue.toFixed(2)})`, { icon: '🛒' });
    }
  };

  // Compute stats dynamically from Redux store
  const getStats = () => {
    const todayStr = new Date().toDateString();

    // Filter for today
    const todayOrders = orders.filter(o => new Date(o.created_at).toDateString() === todayStr);
    const todayCalls = calls.filter(c => new Date(c.started_at).toDateString() === todayStr);

    const todayRevenue = todayOrders.reduce((sum, o) => sum + (o.total || 0), 0);
    const completedCalls = todayCalls.filter(c => c.status === 'completed');
    const avgCallDuration = completedCalls.length > 0
      ? Math.round(completedCalls.reduce((sum, c) => sum + (c.duration_seconds || 0), 0) / completedCalls.length)
      : 0;

    // Totals
    const totalOrders = orders.length;
    const totalRevenue = orders.reduce((sum, o) => sum + (o.total || 0), 0);
    const totalCalls = calls.length;

    // Pending count
    const pendingOrdersCount = orders.filter(o => ['pending', 'confirmed', 'preparing', 'ready'].includes(o.status)).length;

    // Weekly trend (last 7 days)
    const weeklyTrend = [];
    const now = new Date();
    for (let i = 6; i >= 0; i--) {
      const d = new Date(now);
      d.setDate(now.getDate() - i);
      const dayName = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'][d.getDay()];
      const dayOrdersCount = orders.filter(o => new Date(o.created_at).toDateString() === d.toDateString()).length;
      weeklyTrend.push({ day: dayName, orders: dayOrdersCount });
    }

    return {
      today: {
        orders: todayOrders.length,
        revenue: todayRevenue,
        calls: todayCalls.length,
        avg_call_duration: avgCallDuration,
      },
      totals: {
        orders: totalOrders,
        revenue: totalRevenue,
        calls: totalCalls,
      },
      pending_orders: pendingOrdersCount,
      weekly_trend: weeklyTrend,
      recent_orders: orders.slice(0, 5),
    };
  };

  const stats = getStats();
  const today = stats.today;
  const totals = stats.totals;

  const getGreeting = () => {
    const hour = new Date().getHours();
    if (hour < 12) return 'Good Morning';
    if (hour < 17) return 'Good Afternoon';
    return 'Good Evening';
  };

  const getStatusColor = (status) => {
    const map = { pending: 'warning', confirmed: 'info', preparing: 'primary', ready: 'success', completed: 'success', cancelled: 'danger' };
    return map[status] || 'muted';
  };

  return (
    <div>
      {/* ── Welcome Banner ───────────────────────────────────────────────── */}
      <div className="welcome-banner">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div>
            <h1>{getGreeting()}, Shiva Vilas 🍃</h1>
            <p>Here's how your static demo dashboard is performing</p>
          </div>
          <div className="live-indicator">
            <div className="live-dot" />
            {wsConnected ? 'Live Simulation' : 'Offline'}
          </div>
        </div>
      </div>

      {/* ── Today's Stats ─────────────────────────────────────────────────── */}
      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-icon blue"><HiOutlineShoppingCart /></div>
          <div className="stat-value">{today.orders}</div>
          <div className="stat-label">Orders Today</div>
        </div>
        <div className="stat-card">
          <div className="stat-icon green"><HiOutlineCurrencyDollar /></div>
          <div className="stat-value">₹{today.revenue.toFixed(2)}</div>
          <div className="stat-label">Revenue Today</div>
        </div>
        <div className="stat-card">
          <div className="stat-icon purple"><HiOutlinePhone /></div>
          <div className="stat-value">{today.calls}</div>
          <div className="stat-label">Calls Today</div>
        </div>
        <div className="stat-card">
          <div className="stat-icon yellow"><HiOutlineClock /></div>
          <div className="stat-value">{today.avg_call_duration}s</div>
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
            {stats.weekly_trend.map((day, i) => {
              const maxOrders = Math.max(...stats.weekly_trend.map(d => d.orders), 1);
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
              <span style={{ fontSize: 18, fontWeight: 700 }}>{totals.orders}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ color: 'var(--text-secondary)', fontSize: 14 }}>Total Revenue</span>
              <span style={{ fontSize: 18, fontWeight: 700, color: 'var(--success)' }}>₹{totals.revenue.toFixed(2)}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ color: 'var(--text-secondary)', fontSize: 14 }}>Total Calls</span>
              <span style={{ fontSize: 18, fontWeight: 700 }}>{totals.calls}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ color: 'var(--text-secondary)', fontSize: 14 }}>Pending Orders</span>
              <span className="badge badge-warning">{stats.pending_orders}</span>
            </div>
          </div>
        </div>
      </div>

      {/* ── Live Activity Feed ────────────────────────────────────────────── */}
      {recentEvents.length > 0 && (
        <div className="card" style={{ marginTop: 20 }}>
          <div className="card-header">
            <span className="card-title">Live Activity (Simulated)</span>
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
                  {evt.type === 'new_order' && `🛒 New order from ${evt.data?.customer_name || 'customer'} — ₹${evt.data?.total?.toFixed(2) || '0.00'}`}
                  {evt.type === 'call_started' && `📞 Incoming simulated call...`}
                  {evt.type === 'call_ended' && `📴 Simulated call ended (${evt.data?.duration || 0}s)`}
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
              {stats.recent_orders.length === 0 ? (
                <tr><td colSpan={5} style={{ textAlign: 'center', padding: 32, color: 'var(--text-muted)' }}>No orders yet</td></tr>
              ) : (
                stats.recent_orders.map((o) => (
                  <tr key={o.id}>
                    <td style={{ fontWeight: 600 }}>#{o.id}</td>
                    <td>{o.customer_name}</td>
                    <td style={{ fontWeight: 600, color: 'var(--success)' }}>₹{o.total?.toFixed(2)}</td>
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
