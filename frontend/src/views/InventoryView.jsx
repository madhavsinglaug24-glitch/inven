import React, { useState, useEffect } from 'react';
import { PackagePlus, PackageMinus, Plus, Search, ChevronDown, ChevronUp, Trash2, Download } from 'lucide-react';
import { API_BASE } from '../api';
import { OperationModal } from '../components/OperationModal';
import { AddItemModal } from '../components/AddItemModal';

export const InventoryView = ({ token, refreshTrigger }) => {
    const [items, setItems] = useState([]);
    const [history, setHistory] = useState([]);
    const [viewMode, setViewMode] = useState('stock'); // 'stock' or 'history'
    
    const [opModalType, setOpModalType] = useState(null); // 'restock' or 'consume'
    const [addModalOpen, setAddModalOpen] = useState(false);
    
    const [expandedStock, setExpandedStock] = useState(null);
    const [expandedHistory, setExpandedHistory] = useState(null);
    
    // Filters
    const [search, setSearch] = useState('');
    const [timeFilter, setTimeFilter] = useState('all');
    const [customStart, setCustomStart] = useState('');
    const [customEnd, setCustomEnd] = useState('');

    const loadItems = async () => {
        const res = await fetch(`${API_BASE}/inventory`, { headers: { 'Authorization': `Bearer ${token}` } });
        if (res.status === 401) {
            localStorage.removeItem('apiToken');
            return window.location.reload();
        }
        setItems(await res.json());
    };

    const loadHistory = async () => {
        const res = await fetch(`${API_BASE}/history`, { headers: { 'Authorization': `Bearer ${token}` } });
        if (res.ok) {
            setHistory(await res.json());
        }
    };

    useEffect(() => { 
        loadItems(); 
        loadHistory();
    }, [token, refreshTrigger]);

    const handleDeleteHistory = async (id) => {
        if (!window.confirm("Are you sure you want to delete this log AND reverse its stock change?")) return;
        try {
            const res = await fetch(`${API_BASE}/history/${id}`, {
                method: 'DELETE',
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (res.ok) {
                loadHistory();
                loadItems();
            } else {
                const data = await res.json();
                alert(data.error || "Failed to delete");
            }
        } catch (e) { alert("Network error"); }
    };

    const filteredItems = items.filter(i => {
        const query = search.toLowerCase();
        return (
            String(i.id).toLowerCase().includes(query) ||
            String(i.Item_Name).toLowerCase().includes(query) ||
            String(i.Purchase_Price).includes(query)
        );
    });

    const filteredHistory = history.filter(h => {
        // Time filter
        if (timeFilter !== 'all') {
            const hDate = new Date(h.timestamp);
            const now = new Date();
            if (timeFilter === 'month') {
                if (hDate.getMonth() !== now.getMonth() || hDate.getFullYear() !== now.getFullYear()) return false;
            } else if (timeFilter === 'year') {
                if (hDate.getFullYear() !== now.getFullYear()) return false;
            } else if (timeFilter === 'custom') {
                if (customStart && new Date(h.timestamp) < new Date(customStart)) return false;
                if (customEnd) {
                    const endD = new Date(customEnd);
                    endD.setHours(23, 59, 59, 999);
                    if (new Date(h.timestamp) > endD) return false;
                }
            }
        }
        // Search filter
        if (search) {
            const query = search.toLowerCase();
            return (
                String(h.item_name).toLowerCase().includes(query) ||
                String(h.action).toLowerCase().includes(query) ||
                String(h.contact_name).toLowerCase().includes(query) ||
                String(h.comment).toLowerCase().includes(query)
            );
        }
        return true;
    });

    const exportToExcel = () => {
        let csvContent = "Date,Item,Action,Qty,Unit ₹,Total ₹,Contact,Comment\n";
        filteredHistory.forEach(row => {
            const r = [
                new Date(row.timestamp).toLocaleString(), 
                row.item_name, 
                row.action, 
                row.quantity, 
                row.unit_price || '-',
                row.unit_price ? (row.unit_price * row.quantity) : '-',
                row.contact_name || '-', 
                row.comment || '-'
            ].map(v => `"${(v||'').toString().replace(/"/g, '""')}"`).join(",");
            csvContent += r + "\n";
        });
        const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
        const link = document.createElement("a");
        link.href = URL.createObjectURL(blob);
        link.setAttribute("download", `inventory_history.csv`);
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    };

    return (
        <div className="fade-in">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px', flexWrap: 'wrap', gap: '16px' }}>
                <h1 className="page-title" style={{ margin: 0 }}>Inventory</h1>
                
                <div style={{ display: 'flex', gap: '8px', backgroundColor: 'var(--bg-elevated)', padding: '4px', borderRadius: '8px' }}>
                    <button className={`btn-action ${viewMode === 'stock' ? 'active' : ''}`} style={{ borderColor: viewMode === 'stock' ? 'var(--accent-blue)' : 'transparent' }} onClick={() => setViewMode('stock')}>Current Stock</button>
                    <button className={`btn-action ${viewMode === 'history' ? 'active' : ''}`} style={{ borderColor: viewMode === 'history' ? 'var(--accent-blue)' : 'transparent' }} onClick={() => setViewMode('history')}>History</button>
                </div>

                <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', alignItems: 'center' }}>
                    <div style={{ position: 'relative' }}>
                        <Search size={18} style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-secondary)' }} />
                        <input 
                            type="text" 
                            className="form-input" 
                            placeholder={viewMode === 'stock' ? "Search Inventory..." : "Search History..."}
                            value={search} 
                            onChange={(e) => setSearch(e.target.value)}
                            style={{ paddingLeft: '40px', width: '250px', backgroundColor: 'var(--bg-elevated)' }}
                        />
                    </div>
                    {viewMode === 'history' && (
                        <>
                            <select 
                                className="form-input" 
                                value={timeFilter} 
                                onChange={e => setTimeFilter(e.target.value)}
                                style={{ width: 'auto', backgroundColor: 'var(--bg-elevated)', cursor: 'pointer', paddingRight: '32px' }}
                            >
                                <option value="all">All Time</option>
                                <option value="month">This Month</option>
                                <option value="year">This Year</option>
                                <option value="custom">Custom Range...</option>
                            </select>

                            {timeFilter === 'custom' && (
                                <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
                                    <input type="date" className="form-input" value={customStart} onChange={e => setCustomStart(e.target.value)} style={{ backgroundColor: 'var(--bg-elevated)', padding: '8px 12px' }}/>
                                    <span style={{ color: 'var(--text-secondary)' }}>to</span>
                                    <input type="date" className="form-input" value={customEnd} onChange={e => setCustomEnd(e.target.value)} min={customStart} style={{ backgroundColor: 'var(--bg-elevated)', padding: '8px 12px' }}/>
                                </div>
                            )}
                            <button className="btn-action" onClick={exportToExcel} style={{ padding: '8px 16px' }} title="Download Excel">
                                <Download size={20} style={{ marginRight: '8px' }} /> Export
                            </button>
                        </>
                    )}
                    
                    <button className="btn-action" style={{ padding: '12px', borderRadius: '50%', width: '48px', height: '48px', justifyContent: 'center' }} onClick={() => setAddModalOpen(true)}>
                        <Plus size={24} />
                    </button>
                    <button className="btn-action" onClick={() => setOpModalType('consume')} style={{ backgroundColor: 'var(--accent-red-dim)', color: 'var(--accent-red)', padding: '12px', borderRadius: '50%', width: '48px', height: '48px', justifyContent: 'center' }}>
                        <PackageMinus size={24} />
                    </button>
                    <button className="btn-action" onClick={() => setOpModalType('restock')} style={{ backgroundColor: 'var(--accent-green-dim)', color: 'var(--accent-green)', padding: '12px', borderRadius: '50%', width: '48px', height: '48px', justifyContent: 'center' }}>
                        <PackagePlus size={24} />
                    </button>
                </div>
            </div>

            <OperationModal 
                isOpen={!!opModalType} 
                onClose={() => setOpModalType(null)} 
                onRefresh={() => { loadItems(); loadHistory(); }} 
                type={opModalType} 
                items={items}
                token={token}
                onAddNewItem={(newId) => setAddModalOpen(newId || true)}
            />
            
            <AddItemModal
                isOpen={!!addModalOpen}
                onClose={() => setAddModalOpen(false)}
                onRefresh={loadItems}
                token={token}
                initialId={typeof addModalOpen === 'string' ? addModalOpen : ''}
            />

            <div className="card table-card" style={{ padding: 0, overflowX: 'auto' }}>
                {viewMode === 'stock' ? (
                    <table className="data-table">
                        <thead><tr><th>ID</th><th>Name</th><th>Stock</th><th>Avg Cost</th><th>Min Stock</th></tr></thead>
                        <tbody>
                            {filteredItems.map((i, idx) => (
                                <tr key={idx} className="hover-row">
                                    <td style={{ color: 'var(--text-secondary)' }}>{i.Item_ID}</td>
                                    <td style={{ fontWeight: 600 }}>{i.Item_Name}</td>
                                    <td style={{ color: i.Current_Stock <= i.Min_Stock ? 'var(--accent-red)' : 'var(--text-primary)', fontWeight: i.Current_Stock <= i.Min_Stock ? 'bold' : 'normal' }}>
                                        {i.Current_Stock}
                                    </td>
                                    <td>₹{i.Purchase_Price?.toLocaleString() || 0}</td>
                                    <td style={{ color: 'var(--text-secondary)' }}>{i.Min_Stock}</td>
                                </tr>
                            ))}
                            {filteredItems.length === 0 && <tr><td colSpan="5" style={{ textAlign: 'center', padding: '24px', color: 'var(--text-secondary)' }}>No items found</td></tr>}
                        </tbody>
                    </table>
                ) : (
                    <>
                        <div className="desktop-only">
                            <table className="data-table">
                                <thead><tr><th>Date</th><th>Item</th><th>Action</th><th>Qty</th><th>Unit ₹</th><th>Total ₹</th><th>Contact</th><th>Comment</th><th></th></tr></thead>
                                <tbody>
                                    {filteredHistory.map((h, idx) => (
                                        <tr key={idx} className="hover-row">
                                            <td style={{ color: 'var(--text-secondary)' }}>{new Date(h.timestamp).toLocaleString()}</td>
                                            <td style={{ fontWeight: 600 }}>{h.item_name}</td>
                                            <td>
                                                <span style={{ padding: '4px 8px', borderRadius: '4px', fontSize: '12px', fontWeight: 600, backgroundColor: h.action === 'RESTOCK' ? 'var(--accent-green-dim)' : 'var(--accent-red-dim)', color: h.action === 'RESTOCK' ? 'var(--accent-green)' : 'var(--accent-red)' }}>
                                                    {h.action}
                                                </span>
                                            </td>
                                            <td style={{ fontWeight: 'bold' }}>{h.quantity}</td>
                                            <td>{h.unit_price ? `₹${h.unit_price.toLocaleString()}` : '-'}</td>
                                            <td style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{h.unit_price ? `₹${(h.unit_price * h.quantity).toLocaleString()}` : '-'}</td>
                                            <td style={{ color: 'var(--text-secondary)' }}>{h.contact_name || '-'}</td>
                                            <td style={{ color: 'var(--text-secondary)' }}>{h.comment || '-'}</td>
                                            <td>
                                                <button onClick={() => handleDeleteHistory(h.id)} style={{ background: 'transparent', border: 'none', color: 'var(--accent-red)', cursor: 'pointer', padding: '4px' }}>
                                                    <Trash2 size={16} />
                                                </button>
                                            </td>
                                        </tr>
                                    ))}
                                    {filteredHistory.length === 0 && <tr><td colSpan="9" style={{ textAlign: 'center', padding: '24px', color: 'var(--text-secondary)' }}>No history found</td></tr>}
                                </tbody>
                            </table>
                        </div>
                        <div className="mobile-only" style={{ padding: 0 }}>
                            {filteredHistory.map((h, idx) => (
                                <div key={idx} style={{ borderBottom: '1px solid var(--border-color)' }}>
                                    <div 
                                        style={{ padding: '16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', cursor: 'pointer' }}
                                        onClick={() => setExpandedHistory(expandedHistory === idx ? null : idx)}
                                    >
                                        <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', flex: 1 }}>
                                            <span style={{ fontWeight: 600, fontSize: '15px' }}>{h.item_name}</span>
                                            <span style={{ color: 'var(--text-secondary)', fontSize: '12px' }}>
                                                {new Date(h.timestamp).toLocaleDateString()}
                                            </span>
                                        </div>
                                        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                                            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '2px' }}>
                                                <span style={{ 
                                                    fontWeight: 600, fontSize: '14px',
                                                    color: h.action === 'RESTOCK' ? 'var(--accent-green)' : 'var(--accent-red)' 
                                                }}>
                                                    {h.action === 'RESTOCK' ? '+' : '-'}{h.quantity}
                                                </span>
                                            </div>
                                            {expandedHistory === idx ? <ChevronUp size={20} color="var(--text-secondary)"/> : <ChevronDown size={20} color="var(--text-secondary)"/>}
                                        </div>
                                    </div>
                                    {expandedHistory === idx && (
                                        <div style={{ padding: '0 16px 16px 16px', backgroundColor: 'var(--bg-elevated)', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                                            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '13px' }}>
                                                <span style={{ color: 'var(--text-secondary)' }}>Time</span>
                                                <span>{new Date(h.timestamp).toLocaleTimeString()}</span>
                                            </div>
                                            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '13px' }}>
                                                <span style={{ color: 'var(--text-secondary)' }}>Unit Price</span>
                                                <span>{h.unit_price ? `₹${h.unit_price.toLocaleString()}` : '-'}</span>
                                            </div>
                                            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '13px', fontWeight: 600 }}>
                                                <span style={{ color: 'var(--text-primary)' }}>Total Price</span>
                                                <span>{h.unit_price ? `₹${(h.unit_price * h.quantity).toLocaleString()}` : '-'}</span>
                                            </div>
                                            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '13px' }}>
                                                <span style={{ color: 'var(--text-secondary)' }}>Contact</span>
                                                <span>{h.contact_name || '-'}</span>
                                            </div>
                                            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '13px' }}>
                                                <span style={{ color: 'var(--text-secondary)' }}>Comment</span>
                                                <span>{h.comment || '-'}</span>
                                            </div>
                                            <button onClick={() => handleDeleteHistory(h.id)} style={{ marginTop: '8px', padding: '8px', backgroundColor: 'var(--accent-red-dim)', color: 'var(--accent-red)', border: 'none', borderRadius: '4px', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px' }}>
                                                <Trash2 size={14} /> Delete & Reverse Stock
                                            </button>
                                        </div>
                                    )}
                                </div>
                            ))}
                            {filteredHistory.length === 0 && <div style={{ textAlign: 'center', padding: '24px', color: 'var(--text-secondary)' }}>No history found</div>}
                        </div>
                    </>
                )}
            </div>
        </div>
    );
};
