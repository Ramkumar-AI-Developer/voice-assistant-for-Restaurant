import axios from 'axios';

const API_BASE = import.meta.env.VITE_API_URL || '';

const api = axios.create({
  baseURL: API_BASE,
  headers: { 'Content-Type': 'application/json' },
});

// Attach JWT to every request
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Handle 401 globally
api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('token');
      localStorage.removeItem('user');
      window.location.href = '/login';
    }
    return Promise.reject(err);
  }
);

// ── Auth ─────────────────────────────────────────────────────────────────────
export const authAPI = {
  login: (username, password) => api.post('/auth/login', { username, password }),
  register: (data) => api.post('/auth/register', data),
  me: () => api.get('/auth/me'),
};

// ── Menu ─────────────────────────────────────────────────────────────────────
export const menuAPI = {
  list: () => api.get('/api/menu/'),
  create: (data) => api.post('/api/menu/', data),
  update: (id, data) => api.put(`/api/menu/${id}`, data),
  delete: (id) => api.delete(`/api/menu/${id}`),
  bulkDelete: (ids) => api.post('/api/menu/bulk-delete', { ids }),
  upload: (file) => {
    const fd = new FormData();
    fd.append('file', file);
    return api.post('/api/menu/upload', fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  downloadTemplate: () => api.get('/api/menu/template', { responseType: 'blob' }),
  categories: () => api.get('/api/menu/categories'),
};

// ── Orders ───────────────────────────────────────────────────────────────────
export const ordersAPI = {
  list: (page = 1, perPage = 20, status = '') =>
    api.get('/api/orders/', { params: { page, per_page: perPage, status: status || undefined } }),
  get: (id) => api.get(`/api/orders/${id}`),
  export: () => api.get('/api/orders/export', { responseType: 'blob' }),
  updateStatus: (id, status) => api.patch(`/api/orders/${id}/status`, { status }),
};

// ── Calls ────────────────────────────────────────────────────────────────────
export const callsAPI = {
  list: (page = 1, perPage = 20) =>
    api.get('/api/calls/', { params: { page, per_page: perPage } }),
  get: (id) => api.get(`/api/calls/${id}`),
};

// ── Dashboard ────────────────────────────────────────────────────────────────
export const dashboardAPI = {
  stats: () => api.get('/api/dashboard/stats'),
};

export default api;
