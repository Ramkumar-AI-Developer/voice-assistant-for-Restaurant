import { useState, useEffect } from 'react';
import { HiOutlineDownload, HiOutlineEye, HiOutlineX } from 'react-icons/hi';
import toast from 'react-hot-toast';
import { ordersAPI } from '../services/api';

export default function Orders() {
  const [data, setData] = useState({ orders: [], total: 0, page: 1, pages: 0 });
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState('');
  const [selectedOrder, setSelectedOrder] = useState(null);

  useEffect(() => { loadOrders(); }, [page, statusFilter]);

  const loadOrders = async () => {
    setLoading(true);
    try {
      const res = await ordersAPI.list(page, 20, statusFilter);
      setData(res.data);
    } catch (err) {
      toast.error('Failed to load orders');
    } finally { setLoading(false); }
  };

  const handleExport = async () => {
    try {
      const res = await ordersAPI.export();
      const url = URL.createObjectURL(new Blob([res.data]));
      const a = document.createElement('a');
      a.href = url; a.download = 'orders_export.xlsx'; a.click();
      URL.revokeObjectURL(url);
      toast.success('Orders exported');
    } catch (err) {
      toast.error('Export failed');
    }
  };

  const handleStatusUpdate = async (orderId, newStatus) => {
    try {
      await ordersAPI.updateStatus(orderId, newStatus);
      toast.success(`Order #${orderId} → ${newStatus}`);
      loadOrders();
      if (selectedOrder?.id === orderId) {
        setSelectedOrder({ ...selectedOrder, status: newStatus });
      }
    } catch (err) {
      toast.error('Status update failed');
    }
  };

  const viewOrder = async (id) => {
    try {
      const res = await ordersAPI.get(id);
      setSelectedOrder(res.data);
    } catch (err) {
      toast.error('Failed to load order details');
    }
  };

  const statusColor = (s) => ({ pending: 'warning', confirmed: 'info', preparing: 'primary', ready: 'success', completed: 'success', cancelled: 'danger' }[s] || 'muted');

  return (
    <div>
      <div className="page-header">
        <h1>Orders</h1>
        <p>View and manage orders received via AI voice calls</p>
        <div className="page-actions">
          <select className="form-input" style={{ width: 160 }} value={statusFilter} onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}>
            <option value="">All Statuses</option>
            <option value="pending">Pending</option>
            <option value="confirmed">Confirmed</option>
            <option value="preparing">Preparing</option>
            <option value="ready">Ready</option>
            <option value="completed">Completed</option>
            <option value="cancelled">Cancelled</option>
          </select>
          <button className="btn btn-secondary" onClick={handleExport}><HiOutlineDownload /> Export Excel</button>
        </div>
      </div>

      <div className="card">
        {loading ? (
          <div className="loading"><div className="spinner" /></div>
        ) : data.orders.length === 0 ? (
          <div className="empty-state">
            <h3>No orders found</h3>
            <p>Orders placed via AI voice calls will appear here</p>
          </div>
        ) : (
          <>
            <div className="table-container">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>#</th>
                    <th>Customer</th>
                    <th>Phone</th>
                    <th>Items</th>
                    <th>Total</th>
                    <th>Type</th>
                    <th>Status</th>
                    <th>Time</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {data.orders.map((o) => (
                    <tr key={o.id}>
                      <td style={{ fontWeight: 600 }}>#{o.id}</td>
                      <td>{o.customer_name}</td>
                      <td style={{ fontFamily: 'monospace', fontSize: 12 }}>{o.customer_phone}</td>
                      <td>{o.items?.length || 0} items</td>
                      <td style={{ fontWeight: 700, color: 'var(--success)' }}>${o.total?.toFixed(2)}</td>
                      <td><span className="badge badge-muted">{o.order_type}</span></td>
                      <td><span className={`badge badge-${statusColor(o.status)}`}>{o.status}</span></td>
                      <td style={{ color: 'var(--text-muted)', fontSize: 12 }}>{o.created_at ? new Date(o.created_at).toLocaleString() : '-'}</td>
                      <td>
                        <button className="btn btn-sm btn-secondary btn-icon" onClick={() => viewOrder(o.id)} title="View"><HiOutlineEye /></button>
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

      {/* ── Order Detail Modal ────────────────────────────────────────────── */}
      {selectedOrder && (
        <div className="modal-overlay" onClick={() => setSelectedOrder(null)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>Order #{selectedOrder.id}</h2>
              <button className="modal-close" onClick={() => setSelectedOrder(null)}><HiOutlineX /></button>
            </div>

            <div style={{ display: 'grid', gap: 12, fontSize: 14 }}>
              <div><strong>Customer:</strong> {selectedOrder.customer_name}</div>
              <div><strong>Phone:</strong> {selectedOrder.customer_phone}</div>
              <div><strong>Type:</strong> <span className="badge badge-muted">{selectedOrder.order_type}</span></div>
              <div><strong>Status:</strong> <span className={`badge badge-${statusColor(selectedOrder.status)}`}>{selectedOrder.status}</span></div>
              <div><strong>Time:</strong> {selectedOrder.created_at ? new Date(selectedOrder.created_at).toLocaleString() : '-'}</div>

              <h3 style={{ marginTop: 8, fontSize: 15 }}>Items</h3>
              <table className="data-table">
                <thead>
                  <tr><th>Item</th><th>Qty</th><th>Price</th><th>Subtotal</th><th>Notes</th></tr>
                </thead>
                <tbody>
                  {(selectedOrder.items || []).map((item, i) => (
                    <tr key={i}>
                      <td>{item.name}</td>
                      <td>{item.quantity}</td>
                      <td>${item.unit_price?.toFixed(2)}</td>
                      <td style={{ fontWeight: 600 }}>${item.subtotal?.toFixed(2)}</td>
                      <td style={{ color: 'var(--text-muted)' }}>{item.notes || '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <div style={{ textAlign: 'right', fontWeight: 700, fontSize: 16, color: 'var(--success)' }}>Total: ${selectedOrder.total?.toFixed(2)}</div>
            </div>

            <div className="modal-footer">
              <span style={{ fontSize: 12, color: 'var(--text-muted)', marginRight: 'auto' }}>Update status:</span>
              {['confirmed', 'preparing', 'ready', 'completed'].map(s => (
                <button key={s} className={`btn btn-sm ${selectedOrder.status === s ? 'btn-primary' : 'btn-secondary'}`}
                  onClick={() => handleStatusUpdate(selectedOrder.id, s)}>{s}</button>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
