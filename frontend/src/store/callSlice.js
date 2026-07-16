import { createSlice } from '@reduxjs/toolkit';

const DEFAULT_CALLS = [
  {
    id: 1001,
    phone_number: '+44 7911 123456',
    customer_name: 'Rajesh Patel',
    status: 'completed',
    duration_seconds: 125,
    order_id: 1001,
    started_at: new Date(Date.now() - 30 * 60000).toISOString(),
    messages: [
      { role: 'assistant', content: 'Hello! Welcome to Shiva Vilas. How can I help you today?' },
      { role: 'user', content: 'Hi, I would like to order two Masala Dosas and two Mango Lassis please.' },
      { role: 'assistant', content: 'Sure, that is two Masala Dosas and two Mango Lassis. Would you like anything else or any special customizations?' },
      { role: 'user', content: 'Could you make the dosas extra crispy and make sure we get extra chutney?' },
      { role: 'assistant', content: 'Got it! Extra crispy with extra chutney. Your total is ₹2635.60 Shall I confirm this order?' },
      { role: 'user', content: 'Yes, please confirm.' },
      { role: 'assistant', content: 'Perfect, your order has been placed. Thank you for calling Shiva Vilas!' },
    ],
  },
  {
    id: 1002,
    phone_number: '+44 7911 987654',
    customer_name: 'Priya Sharma',
    status: 'completed',
    duration_seconds: 98,
    order_id: 1002,
    started_at: new Date(Date.now() - 15 * 60000).toISOString(),
    messages: [
      { role: 'assistant', content: 'Hello! Welcome to Shiva Vilas. How can I help you today?' },
      { role: 'user', content: 'Hi, I want a Paneer Butter Masala and two Butter Naans.' },
      { role: 'assistant', content: 'Sure, one Paneer Butter Masala and two Butter Naans. Any customizations?' },
      { role: 'user', content: 'Make it medium spicy.' },
      { role: 'assistant', content: 'No problem, medium spicy Paneer Butter Masala. Your total is ₹1650.00 Confirm order?' },
      { role: 'user', content: 'Yes, please.' },
      { role: 'assistant', content: 'Great, order placed. Thank you!' },
    ],
  },
  {
    id: 1003,
    phone_number: '+44 7911 889900',
    customer_name: 'James Smith',
    status: 'completed',
    duration_seconds: 145,
    order_id: 1005,
    started_at: new Date(Date.now() - 5 * 60000).toISOString(),
    messages: [
      { role: 'assistant', content: 'Hello! Welcome to Shiva Vilas. How can I help you today?' },
      { role: 'user', content: 'Hello, could I get a Gobi sixty-five and some veg noodles?' },
      { role: 'assistant', content: 'Sure, one Gobi 65 and one Veg Noodles. Any special instructions?' },
      { role: 'user', content: 'Can you do the noodles with less spice?' },
      { role: 'assistant', content: 'Understood, less spicy Veg Noodles and one Gobi 65. The total is ₹1813.90 Shall I confirm?' },
      { role: 'user', content: 'Yes, confirm that.' },
      { role: 'assistant', content: 'Thank you, your order is placed!' },
    ],
  },
  {
    id: 1004,
    phone_number: '+44 7911 556677',
    customer_name: 'Sarah Connor',
    status: 'abandoned',
    duration_seconds: 45,
    order_id: null,
    started_at: new Date(Date.now() - 40 * 60000).toISOString(),
    messages: [
      { role: 'assistant', content: 'Hello! Welcome to Shiva Vilas. How can I help you today?' },
      { role: 'user', content: 'Hi, do you have any vegan options on the menu?' },
      { role: 'assistant', content: 'Yes! We have many vegan-friendly options like Pepper Rasam Soup, Gobi 65, Plain Papadum, Plain Dosa, Onion Dosa, and variety rices. Would you like to hear more?' },
      { role: 'user', content: 'Hold on, let me check... [hangs up]' },
    ],
  },
];

const getStoredCalls = () => {
  const calls = localStorage.getItem('demo_calls');
  if (calls) return JSON.parse(calls);
  localStorage.setItem('demo_calls', JSON.stringify(DEFAULT_CALLS));
  return DEFAULT_CALLS;
};

const callSlice = createSlice({
  name: 'calls',
  initialState: {
    calls: getStoredCalls(),
  },
  reducers: {
    addCall: (state, action) => {
      const lastId = state.calls.length > 0 ? Math.max(...state.calls.map(c => c.id)) : 1000;
      const newCall = {
        id: lastId + 1,
        phone_number: action.payload.phone_number || 'Unknown Phone',
        customer_name: action.payload.customer_name || 'Unknown',
        status: action.payload.status || 'completed',
        duration_seconds: action.payload.duration_seconds || 0,
        order_id: action.payload.order_id || null,
        started_at: action.payload.started_at || new Date().toISOString(),
        messages: action.payload.messages || [],
      };
      state.calls.unshift(newCall);
      localStorage.setItem('demo_calls', JSON.stringify(state.calls));
    },
  },
});

export const { addCall } = callSlice.actions;
export default callSlice.reducer;
