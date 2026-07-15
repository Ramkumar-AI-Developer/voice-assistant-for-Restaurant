import { useState } from 'react';
import { HiOutlineDownload, HiOutlineEye, HiOutlineX, HiOutlinePlus, HiOutlineTrash } from 'react-icons/hi';
import toast from 'react-hot-toast';
import { useSelector, useDispatch } from 'react-redux';
import { createOrder, updateOrderStatus } from '../store/orderSlice';

export default function Orders() {
  const orders = useSelector(state => state.orders.orders);
  const menuItems = useSelector(state => state.menu.items);
  const dispatch = useDispatch();

  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState('');
  const [selectedOrder, setSelectedOrder] = useState(null);

  // Manual Order Creation Modal state
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [customerName, setCustomerName] = useState('');
  const [customerPhone, setCustomerPhone] = useState('');
  const [orderType, setOrderType] = useState('call');
  const [cart, setCart] = useState([]);
  const [activeCategory, setActiveCategory] = useState('All');
  const [searchQuery, setSearchQuery] = useState('');

  // Filtering orders
  const filteredOrders = orders.filter(o => {
    if (statusFilter && o.status !== statusFilter) return false;
    return true;
  });

  const perPage = 20;
  const total = filteredOrders.length;
  const pages = Math.ceil(total / perPage) || 1;
  const startIdx = (page - 1) * perPage;
  const paginatedOrders = filteredOrders.slice(startIdx, startIdx + perPage);

  const handleExport = () => {
    try {
      const headers = ['Order #', 'Customer Name', 'Phone', 'Items Count', 'Total (₹)', 'Type', 'Status', 'Date/Time'];
      const rows = filteredOrders.map(o => {
        const itemNames = (o.items || []).map(itm => `${itm.name} (x${itm.quantity})`).join('; ');
        return [
          o.id,
          o.customer_name,
          `"${o.customer_phone}"`,
          o.items?.length || 0,
          o.total?.toFixed(2),
          o.order_type,
          o.status,
          new Date(o.created_at).toLocaleString(),
        ];
      });

      const csvContent = [headers.join(','), ...rows.map(r => r.join(','))].join('\n');
      const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `orders_export_${Date.now()}.csv`;
      a.click();
      URL.revokeObjectURL(url);
      toast.success('Orders exported successfully');
    } catch (err) {
      toast.error('Export failed');
    }
  };

  const handleStatusUpdate = (orderId, newStatus) => {
    dispatch(updateOrderStatus({ id: orderId, status: newStatus }));
    toast.success(`Order #${orderId} status → ${newStatus}`);
    if (selectedOrder?.id === orderId) {
      setSelectedOrder({ ...selectedOrder, status: newStatus });
    }
  };

  const viewOrder = (id) => {
    const order = orders.find(o => o.id === id);
    if (order) {
      setSelectedOrder(order);
    } else {
      toast.error('Failed to load order details');
    }
  };

  const statusColor = (s) => ({
    pending: 'warning', confirmed: 'info', preparing: 'primary', ready: 'success', completed: 'success', cancelled: 'danger'
  }[s] || 'muted');

  // Menu Categories for creation modal
  const categories = ['All', ...new Set(menuItems.filter(item => item.available).map(item => item.category))];

  // Filtered menu items for order creation
  const filteredMenuItems = menuItems.filter(item => {
    if (!item.available) return false;
    if (activeCategory !== 'All' && item.category !== activeCategory) return false;
    if (searchQuery && !item.name.toLowerCase().includes(searchQuery.toLowerCase())) return false;
    return true;
  });

  const addToCart = (item) => {
    setCart(prev => {
      const existing = prev.find(cartItem => cartItem.id === item.id);
      if (existing) {
        return prev.map(cartItem =>
          cartItem.id === item.id
            ? { ...cartItem, quantity: cartItem.quantity + 1 }
            : cartItem
        );
      }
      return [...prev, { ...item, quantity: 1, notes: '' }];
    });
    toast.success(`${item.name} added to cart`, { duration: 1000 });
  };

  const updateCartQty = (id, val) => {
    setCart(prev =>
      prev.map(item =>
        item.id === id ? { ...item, quantity: Math.max(1, parseInt(val) || 1) } : item
      )
    );
  };

  const updateCartNotes = (id, notes) => {
    setCart(prev =>
      prev.map(item =>
        item.id === id ? { ...item, notes } : item
      )
    );
  };

  const removeFromCart = (id) => {
    setCart(prev => prev.filter(item => item.id !== id));
  };

  const cartTotal = cart.reduce((sum, item) => sum + (item.price * item.quantity), 0);

  const handlePlaceOrder = () => {
    if (cart.length === 0) {
      toast.error('Cart is empty');
      return;
    }
    if (!customerName.trim()) {
      toast.error('Customer name is required');
      return;
    }

    const orderData = {
      customer_name: customerName,
      customer_phone: customerPhone || 'Walk-in',
      order_type: orderType,
      items: cart,
      total: cartTotal,
      status: 'pending',
    };

    dispatch(createOrder(orderData));
    toast.success('Order placed successfully!');
    setShowCreateModal(false);
    // Reset state
    setCustomerName('');
    setCustomerPhone('');
    setCart([]);
  };

  return (
    <div>
      <div className="page-header">
        <h1>Orders</h1>
        <p>View and manage orders received via AI voice calls or manual entry</p>
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
          <button className="btn btn-primary" onClick={() => setShowCreateModal(true)}><HiOutlinePlus /> Create Order</button>
          <button className="btn btn-secondary" onClick={handleExport}><HiOutlineDownload /> Export CSV</button>
        </div>
      </div>

      <div className="card">
        {paginatedOrders.length === 0 ? (
          <div className="empty-state">
            <h3>No orders found</h3>
            <p>Orders placed via AI voice calls or manually will appear here</p>
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
                  {paginatedOrders.map((o) => (
                    <tr key={o.id}>
                      <td style={{ fontWeight: 600 }}>#{o.id}</td>
                      <td>{o.customer_name}</td>
                      <td style={{ fontFamily: 'monospace', fontSize: 12 }}>{o.customer_phone}</td>
                      <td>{o.items?.length || 0} items</td>
                      <td style={{ fontWeight: 700, color: 'var(--success)' }}>₹{o.total?.toFixed(2)}</td>
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
              <span>Page {page} of {pages}</span>
              <button disabled={page >= pages} onClick={() => setPage(page + 1)}>Next</button>
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
                      <td>₹{item.unit_price?.toFixed(2)}</td>
                      <td style={{ fontWeight: 600 }}>₹{item.subtotal?.toFixed(2)}</td>
                      <td style={{ color: 'var(--text-muted)' }}>{item.notes || '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <div style={{ textAlign: 'right', fontWeight: 700, fontSize: 16, color: 'var(--success)' }}>Total: ₹{selectedOrder.total?.toFixed(2)}</div>
            </div>

            <div className="modal-footer">
              <span style={{ fontSize: 12, color: 'var(--text-muted)', marginRight: 'auto' }}>Update status:</span>
              {['pending', 'confirmed', 'preparing', 'ready', 'completed', 'cancelled'].map(s => (
                <button key={s} className={`btn btn-sm ${selectedOrder.status === s ? 'btn-primary' : 'btn-secondary'}`}
                  onClick={() => handleStatusUpdate(selectedOrder.id, s)}>{s}</button>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* ── Create Order Modal ─────────────────────────────────────────────── */}
      {showCreateModal && (
        <div className="modal-overlay" onClick={() => setShowCreateModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 900, width: '90%' }}>
            <div className="modal-header">
              <h2>Create New Order</h2>
              <button className="modal-close" onClick={() => setShowCreateModal(false)}><HiOutlineX /></button>
            </div>

            <div className="grid-2" style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: 20 }}>
              {/* Left Panel: Customer info and Menu Picker */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: 16, borderRight: '1px solid var(--border)', paddingRight: 20 }}>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                  <div className="form-group" style={{ marginBottom: 0 }}>
                    <label className="form-label">Customer Name *</label>
                    <input className="form-input" value={customerName} onChange={(e) => setCustomerName(e.target.value)} placeholder="Rajesh Patel" />
                  </div>
                  <div className="form-group" style={{ marginBottom: 0 }}>
                    <label className="form-label">Customer Phone</label>
                    <input className="form-input" value={customerPhone} onChange={(e) => setCustomerPhone(e.target.value)} placeholder="+44 7911 123456" />
                  </div>
                </div>

                <div className="form-group" style={{ marginBottom: 0 }}>
                  <label className="form-label">Order Type</label>
                  <select className="form-input" value={orderType} onChange={(e) => setOrderType(e.target.value)}>
                    <option value="call">Voice Call</option>
                    <option value="takeaway">Takeaway</option>
                    <option value="eat in">Eat In</option>
                  </select>
                </div>

                {/* Menu items picker */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: 10, flex: 1, minHeight: 0 }}>
                  <label className="form-label" style={{ marginBottom: 0 }}>Select Menu Items</label>
                  
                  {/* Category Tabs */}
                  <div style={{ display: 'flex', gap: 6, overflowX: 'auto', paddingBottom: 4, whiteSpace: 'nowrap' }}>
                    {categories.slice(0, 10).map(cat => (
                      <button
                        key={cat}
                        className={`btn btn-sm ${activeCategory === cat ? 'btn-primary' : 'btn-secondary'}`}
                        style={{ padding: '4px 10px', fontSize: 11 }}
                        onClick={() => setActiveCategory(cat)}
                      >
                        {cat}
                      </button>
                    ))}
                  </div>

                  <input
                    className="form-input"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder="Search dishes..."
                    style={{ padding: '8px 12px', fontSize: 13 }}
                  />

                  {/* Items list */}
                  <div style={{ maxHeight: 220, overflowY: 'auto', border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)', padding: 8 }}>
                    {filteredMenuItems.length === 0 ? (
                      <div style={{ textAlign: 'center', padding: 20, color: 'var(--text-muted)', fontSize: 12 }}>No items match filter</div>
                    ) : (
                      filteredMenuItems.map(item => (
                        <div key={item.id} style={{
                          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                          padding: '8px 10px', borderBottom: '1px solid var(--border)', fontSize: 13
                        }}>
                          <div>
                            <span style={{ fontWeight: 600 }}>{item.name}</span>
                            <span style={{ marginLeft: 8, color: 'var(--success)', fontWeight: 600 }}>₹{item.price?.toFixed(2)}</span>
                            {item.description && <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>{item.description}</div>}
                          </div>
                          <button className="btn btn-sm btn-success" style={{ padding: '4px 8px' }} onClick={() => addToCart(item)}>
                            <HiOutlinePlus /> Add
                          </button>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              </div>

              {/* Right Panel: Active Cart */}
              <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between', height: '100%' }}>
                <div>
                  <h3 style={{ fontSize: 16, marginBottom: 12 }}>Order Basket</h3>
                  
                  <div style={{ maxHeight: 300, overflowY: 'auto', border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)', padding: 8 }}>
                    {cart.length === 0 ? (
                      <div style={{ textAlign: 'center', padding: 40, color: 'var(--text-muted)', fontSize: 13 }}>Basket is empty. Select items on the left to add.</div>
                    ) : (
                      cart.map(item => (
                        <div key={item.id} style={{
                          padding: '10px 0', borderBottom: '1px solid var(--border)',
                          display: 'flex', flexDirection: 'column', gap: 6
                        }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <span style={{ fontWeight: 600, fontSize: 13 }}>{item.name}</span>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                              <input
                                type="number"
                                className="form-input"
                                style={{ width: 50, padding: 4, textAlign: 'center', fontSize: 12 }}
                                value={item.quantity}
                                onChange={(e) => updateCartQty(item.id, e.target.value)}
                              />
                              <span style={{ fontWeight: 700, fontSize: 13, minWidth: 50, textAlign: 'right' }}>
                                ₹{(item.price * item.quantity).toFixed(2)}
                              </span>
                              <button className="btn btn-sm btn-danger btn-icon" onClick={() => removeFromCart(item.id)}>
                                <HiOutlineTrash />
                              </button>
                            </div>
                          </div>
                          <input
                            className="form-input"
                            style={{ padding: '4px 8px', fontSize: 11 }}
                            placeholder="Add customization notes..."
                            value={item.notes}
                            onChange={(e) => updateCartNotes(item.id, e.target.value)}
                          />
                        </div>
                      ))
                    )}
                  </div>
                </div>

                <div style={{ borderTop: '1px solid var(--border)', paddingTop: 16, marginTop: 16 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
                    <span style={{ fontSize: 15, fontWeight: 600 }}>Total Order Value:</span>
                    <span style={{ fontSize: 20, fontWeight: 800, color: 'var(--success)' }}>₹{cartTotal.toFixed(2)}</span>
                  </div>
                  <div className="modal-footer" style={{ padding: 0, justifyContent: 'flex-end', gap: 10 }}>
                    <button className="btn btn-secondary" onClick={() => setShowCreateModal(false)}>Cancel</button>
                    <button className="btn btn-primary" onClick={handlePlaceOrder} style={{ padding: '12px 24px' }}>Place Order</button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
