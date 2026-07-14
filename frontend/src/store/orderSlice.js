import { createSlice } from '@reduxjs/toolkit';

const DEFAULT_ORDERS = [
  {
    id: 1001,
    customer_name: 'Rajesh Patel',
    customer_phone: '+44 7911 123456',
    items: [
      { name: 'Masala Dosa', quantity: 2, unit_price: 6.99, subtotal: 13.98, notes: 'Crispy, extra chutney' },
      { name: 'Lassi (Mango)', quantity: 2, unit_price: 4.99, subtotal: 9.98, notes: 'Cold' },
    ],
    total: 23.96,
    order_type: 'call',
    status: 'completed',
    created_at: new Date(Date.now() - 25 * 60000).toISOString(),
  },
  {
    id: 1002,
    customer_name: 'Priya Sharma',
    customer_phone: '+44 7911 987654',
    items: [
      { name: 'Paneer Butter Masala', quantity: 1, unit_price: 9.50, subtotal: 9.50, notes: 'Medium spicy' },
      { name: 'Butter Naan', quantity: 2, unit_price: 2.75, subtotal: 5.50, notes: '' },
    ],
    total: 15.00,
    order_type: 'call',
    status: 'preparing',
    created_at: new Date(Date.now() - 12 * 60000).toISOString(),
  },
  {
    id: 1003,
    customer_name: 'David Miller',
    customer_phone: '+44 7911 445566',
    items: [
      { name: 'South Indian Meals', quantity: 1, unit_price: 10.99, subtotal: 10.99, notes: 'Takeaway' },
    ],
    total: 10.99,
    order_type: 'takeaway',
    status: 'pending',
    created_at: new Date(Date.now() - 5 * 60000).toISOString(),
  },
  {
    id: 1004,
    customer_name: 'Ananya Rao',
    customer_phone: '+44 7911 332211',
    items: [
      { name: 'Idly (3 pcs)', quantity: 1, unit_price: 5.50, subtotal: 5.50, notes: 'Ghee on top' },
      { name: 'Medhu Vada (2 pcs)', quantity: 1, unit_price: 4.50, subtotal: 4.50, notes: '' },
      { name: 'Filter Coffee', quantity: 1, unit_price: 2.50, subtotal: 2.50, notes: '' },
    ],
    total: 12.50,
    order_type: 'eat in',
    status: 'ready',
    created_at: new Date(Date.now() - 8 * 60000).toISOString(),
  },
  {
    id: 1005,
    customer_name: 'James Smith',
    customer_phone: '+44 7911 889900',
    items: [
      { name: 'Gobi 65', quantity: 1, unit_price: 8.50, subtotal: 8.50, notes: '' },
      { name: 'Veg Noodles', quantity: 1, unit_price: 7.99, subtotal: 7.99, notes: 'Less spicy' },
    ],
    total: 16.49,
    order_type: 'call',
    status: 'confirmed',
    created_at: new Date(Date.now() - 2 * 60000).toISOString(),
  },
];

const getStoredOrders = () => {
  const orders = localStorage.getItem('demo_orders');
  if (orders) return JSON.parse(orders);
  localStorage.setItem('demo_orders', JSON.stringify(DEFAULT_ORDERS));
  return DEFAULT_ORDERS;
};

const orderSlice = createSlice({
  name: 'orders',
  initialState: {
    orders: getStoredOrders(),
  },
  reducers: {
    createOrder: (state, action) => {
      const lastId = state.orders.length > 0 ? Math.max(...state.orders.map(o => o.id)) : 1000;
      const newOrder = {
        id: lastId + 1,
        customer_name: action.payload.customer_name || 'Walk-in Customer',
        customer_phone: action.payload.customer_phone || '—',
        items: action.payload.items.map(item => ({
          name: item.name,
          quantity: parseInt(item.quantity) || 1,
          unit_price: parseFloat(item.price),
          subtotal: parseFloat(item.price) * (parseInt(item.quantity) || 1),
          notes: item.notes || '',
        })),
        total: parseFloat(action.payload.total),
        order_type: action.payload.order_type || 'call',
        status: action.payload.status || 'pending',
        created_at: new Date().toISOString(),
      };
      state.orders.unshift(newOrder); // Add to the beginning
      localStorage.setItem('demo_orders', JSON.stringify(state.orders));
    },
    updateOrderStatus: (state, action) => {
      const { id, status } = action.payload;
      const index = state.orders.findIndex(o => o.id === parseInt(id));
      if (index !== -1) {
        state.orders[index].status = status;
        localStorage.setItem('demo_orders', JSON.stringify(state.orders));
      }
    },
    deleteOrder: (state, action) => {
      state.orders = state.orders.filter(o => o.id !== parseInt(action.payload));
      localStorage.setItem('demo_orders', JSON.stringify(state.orders));
    },
  },
});

export const { createOrder, updateOrderStatus, deleteOrder } = orderSlice.actions;
export default orderSlice.reducer;
