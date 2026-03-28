import { useState, useEffect, useRef } from 'react';
import { HiOutlinePlus, HiOutlineUpload, HiOutlineDownload, HiOutlinePencil, HiOutlineTrash, HiOutlineX } from 'react-icons/hi';
import toast from 'react-hot-toast';
import { menuAPI } from '../services/api';

export default function Menu() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [editItem, setEditItem] = useState(null);
  const [selectedIds, setSelectedIds] = useState([]);
  const fileRef = useRef(null);

  // Form state
  const [form, setForm] = useState({ name: '', price: '', description: '', category: '', available: true, customisations: '' });

  useEffect(() => { loadMenu(); }, []);

  const loadMenu = async () => {
    try {
      const res = await menuAPI.list();
      setItems(res.data);
    } catch (err) {
      toast.error('Failed to load menu');
    } finally { setLoading(false); }
  };

  const openAdd = () => {
    setEditItem(null);
    setForm({ name: '', price: '', description: '', category: '', available: true, customisations: '' });
    setShowModal(true);
  };

  const openEdit = (item) => {
    setEditItem(item);
    setForm({
      name: item.name,
      price: item.price.toString(),
      description: item.description || '',
      category: item.category || '',
      available: item.available,
      customisations: (item.customisations || []).join(', '),
    });
    setShowModal(true);
  };

  const handleSave = async () => {
    if (!form.name || !form.price || !form.category) {
      toast.error('Name, price, and category are required');
      return;
    }

    const data = {
      name: form.name,
      price: parseFloat(form.price),
      description: form.description,
      category: form.category,
      available: form.available,
      customisations: form.customisations.split(',').map(s => s.trim()).filter(Boolean),
    };

    try {
      if (editItem) {
        await menuAPI.update(editItem.id, data);
        toast.success('Menu item updated');
      } else {
        await menuAPI.create(data);
        toast.success('Menu item added');
      }
      setShowModal(false);
      loadMenu();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to save');
    }
  };

  const handleDelete = async (id, name) => {
    if (!confirm(`Delete "${name}"?`)) return;
    try {
      await menuAPI.delete(id);
      toast.success('Item deleted');
      setSelectedIds(prev => prev.filter(i => i !== id));
      loadMenu();
    } catch (err) {
      toast.error('Failed to delete');
    }
  };

  const handleBulkDelete = async () => {
    if (selectedIds.length === 0) return;
    if (!confirm(`Delete ${selectedIds.length} items?`)) return;
    try {
      await menuAPI.bulkDelete(selectedIds);
      toast.success(`Deleted ${selectedIds.length} items`);
      setSelectedIds([]);
      loadMenu();
    } catch (err) {
      toast.error('Bulk delete failed');
    }
  };

  const toggleSelect = (id) => {
    setSelectedIds(prev =>
      prev.includes(id) ? prev.filter(i => i !== id) : [...prev, id]
    );
  };

  const toggleSelectAll = (catItems) => {
    const catIds = catItems.map(i => i.id);
    const allSelected = catIds.every(id => selectedIds.includes(id));

    if (allSelected) {
      setSelectedIds(prev => prev.filter(id => !catIds.includes(id)));
    } else {
      setSelectedIds(prev => [...new Set([...prev, ...catIds])]);
    }
  };

  const handleUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      const res = await menuAPI.upload(file);
      toast.success(`Imported: ${res.data.created} new, ${res.data.updated} updated`);
      loadMenu();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Upload failed');
    }
    e.target.value = '';
  };

  const handleDownloadTemplate = async () => {
    try {
      const res = await menuAPI.downloadTemplate();
      const url = URL.createObjectURL(new Blob([res.data]));
      const a = document.createElement('a');
      a.href = url; a.download = 'menu_template.xlsx'; a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      toast.error('Failed to download template');
    }
  };

  // Group items by category
  const grouped = items.reduce((acc, item) => {
    const cat = item.category || 'Uncategorized';
    if (!acc[cat]) acc[cat] = [];
    acc[cat].push(item);
    return acc;
  }, {});

  if (loading) return <div className="loading"><div className="spinner" /></div>;

  return (
    <div>
      <div className="page-header">
        <h1>Menu Management</h1>
        <p>Add, edit, or upload menu items for your AI voice assistant</p>
        <div className="page-actions">
          {selectedIds.length > 0 && (
            <button className="btn btn-danger" onClick={handleBulkDelete}>
              <HiOutlineTrash /> Delete Selected ({selectedIds.length})
            </button>
          )}
          <button className="btn btn-primary" onClick={openAdd}><HiOutlinePlus /> Add Item</button>
          <button className="btn btn-secondary" onClick={() => fileRef.current?.click()}><HiOutlineUpload /> Upload CSV/Excel</button>
          <button className="btn btn-secondary" onClick={handleDownloadTemplate}><HiOutlineDownload /> Download Template</button>
          <input ref={fileRef} type="file" className="file-input-hidden" accept=".csv,.xlsx,.xls" onChange={handleUpload} />
        </div>
      </div>

      {Object.keys(grouped).length === 0 ? (
        <div className="card">
          <div className="empty-state">
            <h3>No menu items yet</h3>
            <p>Add items manually or upload a CSV/Excel file</p>
          </div>
        </div>
      ) : (
        Object.entries(grouped).map(([category, catItems]) => (
          <div key={category} className="card" style={{ marginBottom: 16 }}>
            <div className="card-header">
              <span className="card-title">{category}</span>
              <span className="badge badge-muted">{catItems.length} items</span>
            </div>
            <div className="table-container">
              <table className="data-table">
                <thead>
                  <tr>
                    <th style={{ width: 40 }}>
                      <input
                        type="checkbox"
                        checked={catItems.every(i => selectedIds.includes(i.id))}
                        onChange={() => toggleSelectAll(catItems)}
                      />
                    </th>
                    <th>Name</th>
                    <th>Price</th>
                    <th>Description</th>
                    <th>Available</th>
                    <th>Customisations</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {catItems.map((item) => (
                    <tr key={item.id} className={selectedIds.includes(item.id) ? 'row-selected' : ''}>
                      <td>
                        <input
                          type="checkbox"
                          checked={selectedIds.includes(item.id)}
                          onChange={() => toggleSelect(item.id)}
                          onClick={(e) => e.stopPropagation()}
                        />
                      </td>
                      <td style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{item.name}</td>
                      <td style={{ fontWeight: 600, color: 'var(--success)' }}>£{item.price?.toFixed(2)}</td>
                      <td style={{ maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis' }}>{item.description}</td>
                      <td>
                        <span className={`badge ${item.available ? 'badge-success' : 'badge-danger'}`}>
                          {item.available ? 'Yes' : 'No'}
                        </span>
                      </td>
                      <td style={{ maxWidth: 150, overflow: 'hidden', textOverflow: 'ellipsis' }}>{(item.customisations || []).join(', ') || '—'}</td>
                      <td>
                        <button className="btn btn-sm btn-secondary btn-icon" onClick={() => openEdit(item)} title="Edit"><HiOutlinePencil /></button>{' '}
                        <button className="btn btn-sm btn-danger btn-icon" onClick={() => handleDelete(item.id, item.name)} title="Delete"><HiOutlineTrash /></button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ))
      )}

      {/* ── Add/Edit Modal ────────────────────────────────────────────────── */}
      {showModal && (
        <div className="modal-overlay" onClick={() => setShowModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>{editItem ? 'Edit Menu Item' : 'Add Menu Item'}</h2>
              <button className="modal-close" onClick={() => setShowModal(false)}><HiOutlineX /></button>
            </div>

            <div className="grid-2">
              <div className="form-group">
                <label className="form-label">Name *</label>
                <input className="form-input" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="e.g. Classic Burger" />
              </div>
              <div className="form-group">
                <label className="form-label">Price *</label>
                <input className="form-input" type="number" step="0.01" value={form.price} onChange={(e) => setForm({ ...form, price: e.target.value })} placeholder="12.99" />
              </div>
            </div>
            <div className="form-group">
              <label className="form-label">Category *</label>
              <input className="form-input" value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })} placeholder="e.g. Mains, Starters, Drinks" />
            </div>
            <div className="form-group">
              <label className="form-label">Description</label>
              <input className="form-input" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} placeholder="Short description of the item" />
            </div>
            <div className="form-group">
              <label className="form-label">Customisations (comma-separated)</label>
              <input className="form-input" value={form.customisations} onChange={(e) => setForm({ ...form, customisations: e.target.value })} placeholder="e.g. no onion, extra cheese" />
            </div>
            <div className="form-group">
              <label className="checkbox-label">
                <input type="checkbox" checked={form.available} onChange={(e) => setForm({ ...form, available: e.target.checked })} />
                Available for ordering
              </label>
            </div>

            <div className="modal-footer">
              <button className="btn btn-secondary" onClick={() => setShowModal(false)}>Cancel</button>
              <button className="btn btn-primary" onClick={handleSave}>{editItem ? 'Save Changes' : 'Add Item'}</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
