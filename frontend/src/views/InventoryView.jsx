import React, { useState, useEffect, useMemo } from 'react';
import { PackagePlus, PackageMinus, Plus, Search, ChevronDown, ChevronUp, Trash2, Download, Edit2 } from 'lucide-react';
import { API_BASE } from '../api';
import { OperationModal } from '../components/OperationModal';
import { AddItemModal } from '../components/AddItemModal';
import { PrintModal } from '../components/PrintModal';
import { EditTransactionModal } from '../components/EditTransactionModal';
import { ConfirmModal } from '../components/ConfirmModal';
import { getPreviousMonthRange, matchesTimeFilter } from '../utils/dateFilters';

export const InventoryView = ({ token, refreshTrigger }) => {
    const [items, setItems] = useState([]);
    const [history, setHistory] = useState([]);
    const [loading, setLoading] = useState(true);
    const [viewMode, setViewMode] = useState('stock'); // 'stock' or 'history'
    
    const [opModalType, setOpModalType] = useState(null); // 'restock' or 'consume'
    const [addModalOpen, setAddModalOpen] = useState(false);
    
    const [expandedStock, setExpandedStock] = useState(null);
    const [expandedHistory, setExpandedHistory] = useState(null);
    const [printModalOpen, setPrintModalOpen] = useState(false);
    
    // Filters
    const [search, setSearch] = useState('');
    const [timeFilter, setTimeFilter] = useState('all');
    const [customStart, setCustomStart] = useState('');
    const [customEnd, setCustomEnd] = useState('');
    const [editingTransaction, setEditingTransaction] = useState(null);
    const [confirmDeleteHistoryId, setConfirmDeleteHistoryId] = useState(null);

    const { rangeStart, rangeEnd } = useMemo(() => {
        if (timeFilter === 'last_month') {
            return getPreviousMonthRange();
        }
        if (timeFilter !== 'custom' || !customStart || !customEnd) {
            return { rangeStart: customStart, rangeEnd: customEnd };
        }
        if (customStart > customEnd) {
            return { rangeStart: customEnd, rangeEnd: customStart };
        }
        return { rangeStart: customStart, rangeEnd: customEnd };
    }, [timeFilter, customStart, customEnd]);

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
        setLoading(true);
        Promise.all([loadItems(), loadHistory()]).finally(() => setLoading(false));
    }, [token, refreshTrigger]);

    const [confirmDeleteStockId, setConfirmDeleteStockId] = useState(null);

    const handleDeleteStock = (id) => {
        setConfirmDeleteStockId(id);
    };

    const confirmAndDeleteStock = async () => {
        if (!confirmDeleteStockId) return;
        const id = confirmDeleteStockId;
        try {
            const res = await fetch(`${API_BASE}/inventory/${id}`, {
                method: 'DELETE',
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (res.ok) {
                loadItems();
            } else {
                const data = await res.json();
                alert(data.error || "Failed to delete");
            }
        } catch (e) { alert("Network error"); }
        setConfirmDeleteStockId(null);
    };

    const handleDeleteHistory = (id) => {
        setConfirmDeleteHistoryId(id);
    };

    const confirmAndDeleteHistory = async () => {
        if (!confirmDeleteHistoryId) return;
        const id = confirmDeleteHistoryId;
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
        setConfirmDeleteHistoryId(null);
    };

    const filteredItems = useMemo(() => {
        return items.filter(i => {
            const query = search.toLowerCase();
            return (
                String(i.id).toLowerCase().includes(query) ||
                String(i.Item_Name).toLowerCase().includes(query) ||
                String(i.Purchase_Price).includes(query)
            );
        });
    }, [items, search]);

    const filteredHistory = useMemo(() => {
        return history.filter(h => {
            if (!matchesTimeFilter(h.timestamp, timeFilter, rangeStart, rangeEnd)) return false;
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
    }, [history, search, timeFilter, rangeStart, rangeEnd]);

    // Group filtered history by bill_no for collapsible view
    const groupedHistory = useMemo(() => {
        const groups = [];
        const billMap = {};
        filteredHistory.forEach(h => {
            const key = h.bill_no || `__single_${h.id}`;
            if (h.bill_no && billMap[key] !== undefined) {
                groups[billMap[key]].items.push(h);
                groups[billMap[key]].totalQty += h.quantity;
                groups[billMap[key]].totalAmount += (h.unit_price || 0) * h.quantity;
            } else {
                billMap[key] = groups.length;
                groups.push({
                    bill_no: h.bill_no,
                    action: h.action,
                    timestamp: h.timestamp,
                    contact_name: h.contact_name,
                    items: [h],
                    totalQty: h.quantity,
                    totalAmount: (h.unit_price || 0) * h.quantity,
                    isSingle: !h.bill_no
                });
            }
        });
        return groups;
    }, [filteredHistory]);

    const [expandedBill, setExpandedBill] = useState(null);

    const stockColumns = [
        { key: 'Item_ID', label: 'ID' },
        { key: 'Item_Name', label: 'Name' },
        { key: 'Current_Stock', label: 'Stock' },
        { key: 'Purchase_Price', label: 'Avg Cost', render: r => `₹${r.Purchase_Price?.toLocaleString() || 0}` },
        { key: 'Min_Stock', label: 'Min Stock' }
    ];

    const historyColumns = [
        { key: 'bill_no', label: 'Bill No', render: r => r.bill_no || '-' },
        { key: 'item_name', label: 'Item' },
        { key: 'action', label: 'Action' },
        { key: 'quantity', label: 'Qty' },
        { key: 'unit_price', label: 'Unit ₹', render: r => r.unit_price ? `₹${r.unit_price.toLocaleString()}` : '-' },
        { key: 'total', label: 'Total ₹', render: r => r.unit_price ? `₹${(r.unit_price * r.quantity).toLocaleString()}` : '-' }
    ];

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
                                <option value="last_month">Last Month</option>
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
                            <button className="btn-action" onClick={() => setPrintModalOpen(true)} style={{ padding: '8px 16px' }} title="Print History">
                                Print
                            </button>
                        </>
                    )}
                    {viewMode === 'stock' && (
                        <button className="btn-action" onClick={() => setPrintModalOpen(true)} style={{ padding: '8px 16px' }} title="Print Stock">
                            Print
                        </button>
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
                        <thead><tr><th>ID</th><th>Name</th><th>Stock</th><th>Avg Cost</th><th>Min Stock</th><th></th></tr></thead>
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
                                    <td>
                                        <button className="btn-action" onClick={(e) => { e.stopPropagation(); handleDeleteStock(i.Item_ID); }} style={{ padding: '8px', color: 'var(--accent-red)' }}>
                                            <Trash2 size={16} />
                                        </button>
                                    </td>
                                </tr>
                            ))}
                            {loading ? (
                                    <tr><td colSpan="7" style={{ textAlign: 'center', padding: '40px', color: 'var(--text-secondary)' }}><div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '8px' }}><div className="spin" style={{ width: '20px', height: '20px', border: '2px solid var(--accent-green)', borderTopColor: 'transparent', borderRadius: '50%' }}></div> Loading inventory...</div></td></tr>
                                ) : filteredItems.length === 0 ? (
                                    <tr><td colSpan="7" style={{ textAlign: 'center', padding: '40px', color: 'var(--text-secondary)' }}>No items found</td></tr>
                                ) : null}
                        </tbody>
                    </table>
                ) : (
                    <>
                        <div className="desktop-only">
                            <table className="data-table">
                                <thead><tr><th>Bill No</th><th>Items</th><th>Action</th><th>Total Qty</th><th>Total ₹</th><th>Date</th><th></th></tr></thead>
                                <tbody>
                                    {groupedHistory.map((group, gIdx) => (
                                        <React.Fragment key={gIdx}>
                                            <tr className="hover-row" onClick={() => setExpandedBill(expandedBill === gIdx ? null : gIdx)} style={{ cursor: 'pointer' }}>
                                                <td style={{ color: 'var(--text-secondary)' }}>{group.bill_no || '-'}</td>
                                                <td style={{ fontWeight: 600 }}>
                                                    {group.isSingle ? group.items[0].item_name : `${group.items.length} items`}
                                                </td>
                                                <td>
                                                    <span style={{ padding: '4px 8px', borderRadius: '4px', fontSize: '12px', fontWeight: 600, backgroundColor: group.action === 'RESTOCK' ? 'var(--accent-green-dim)' : 'var(--accent-red-dim)', color: group.action === 'RESTOCK' ? 'var(--accent-green)' : 'var(--accent-red)' }}>
                                                        {group.action}
                                                    </span>
                                                </td>
                                                <td style={{ fontWeight: 'bold' }}>{group.totalQty}</td>
                                                <td style={{ fontWeight: 600 }}>{group.totalAmount > 0 ? `₹${group.totalAmount.toLocaleString()}` : '-'}</td>
                                                <td style={{ color: 'var(--text-secondary)', whiteSpace: 'nowrap' }}>{new Date(group.timestamp).toLocaleDateString()}</td>
                                                <td>
                                                    {expandedBill === gIdx ? <ChevronUp size={18} color="var(--text-secondary)"/> : <ChevronDown size={18} color="var(--text-secondary)"/>}
                                                </td>
                                            </tr>
                                            {expandedBill === gIdx && (
                                                <tr style={{ backgroundColor: 'var(--bg-elevated)' }}>
                                                    <td colSpan="7" style={{ padding: '0' }}>
                                                        <div style={{ padding: '12px 16px', fontSize: '13px', color: 'var(--text-secondary)', display: 'flex', gap: '24px', borderBottom: '1px solid var(--border-color)' }}>
                                                            <div><span>Supplier:</span> <span style={{ fontWeight: 500, color: 'var(--text-primary)' }}>{group.contact_name || '-'}</span></div>
                                                            <div><span>Date:</span> <span style={{ fontWeight: 500, color: 'var(--text-primary)' }}>{new Date(group.timestamp).toLocaleString()}</span></div>
                                                        </div>
                                                        <table className="data-table" style={{ marginBottom: 0 }}>
                                                            <thead><tr><th>Item</th><th>Qty</th><th>Unit ₹</th><th>Total ₹</th><th>Comment</th><th></th></tr></thead>
                                                            <tbody>
                                                                {group.items.map((h, hIdx) => (
                                                                    <tr key={hIdx}>
                                                                        <td style={{ fontWeight: 600 }}>{h.item_name}</td>
                                                                        <td style={{ fontWeight: 'bold' }}>{h.quantity}</td>
                                                                        <td>{h.unit_price ? `₹${h.unit_price.toLocaleString()}` : '-'}</td>
                                                                        <td style={{ fontWeight: 600 }}>{h.unit_price ? `₹${(h.unit_price * h.quantity).toLocaleString()}` : '-'}</td>
                                                                        <td style={{ color: 'var(--text-secondary)' }}>{h.comment || '-'}</td>
                                                                        <td style={{ display: 'flex', gap: '4px' }}>
                                                                            <button onClick={(e) => { e.stopPropagation(); setEditingTransaction({ type: 'history', data: h }); }} style={{ background: 'transparent', border: 'none', color: 'var(--text-secondary)', cursor: 'pointer', padding: '4px' }}>
                                                                                <Edit2 size={16} />
                                                                            </button>
                                                                            <button onClick={(e) => { e.stopPropagation(); handleDeleteHistory(h.id); }} style={{ background: 'transparent', border: 'none', color: 'var(--accent-red)', cursor: 'pointer', padding: '4px' }}>
                                                                                <Trash2 size={16} />
                                                                            </button>
                                                                        </td>
                                                                    </tr>
                                                                ))}
                                                            </tbody>
                                                        </table>
                                                    </td>
                                                </tr>
                                            )}
                                        </React.Fragment>
                                    ))}
                                    {loading ? (
                                    <tr><td colSpan="8" style={{ textAlign: 'center', padding: '40px', color: 'var(--text-secondary)' }}><div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '8px' }}><div className="spin" style={{ width: '20px', height: '20px', border: '2px solid var(--accent-green)', borderTopColor: 'transparent', borderRadius: '50%' }}></div> Loading history...</div></td></tr>
                                ) : filteredHistory.length === 0 ? (
                                    <tr><td colSpan="8" style={{ textAlign: 'center', padding: '40px', color: 'var(--text-secondary)' }}>No history found</td></tr>
                                ) : null}
                                </tbody>
                            </table>
                        </div>
                        <div className="mobile-only" style={{ padding: 0 }}>
                            {groupedHistory.map((group, gIdx) => (
                                <div key={gIdx} style={{ borderBottom: '1px solid var(--border-color)' }}>
                                    <div 
                                        style={{ padding: '16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', cursor: 'pointer' }}
                                        onClick={() => setExpandedBill(expandedBill === gIdx ? null : gIdx)}
                                    >
                                        <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', flex: 1 }}>
                                            <span style={{ fontWeight: 600, fontSize: '15px' }}>
                                                {group.isSingle ? group.items[0].item_name : `${group.items.length} items`}
                                            </span>
                                            <span style={{ color: 'var(--text-secondary)', fontSize: '12px' }}>
                                                {group.bill_no ? `Bill: ${group.bill_no} • ${new Date(group.timestamp).toLocaleDateString()}` : new Date(group.timestamp).toLocaleDateString()}
                                            </span>
                                        </div>
                                        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                                            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '2px' }}>
                                                <span style={{ fontWeight: 600, fontSize: '14px', color: group.action === 'RESTOCK' ? 'var(--accent-green)' : 'var(--accent-red)' }}>
                                                    {group.totalAmount > 0 ? `₹${group.totalAmount.toLocaleString()}` : `${group.action === 'RESTOCK' ? '+' : '-'}${group.totalQty}`}
                                                </span>
                                            </div>
                                            {expandedBill === gIdx ? <ChevronUp size={20} color="var(--text-secondary)"/> : <ChevronDown size={20} color="var(--text-secondary)"/>}
                                        </div>
                                    </div>
                                    {expandedBill === gIdx && (
                                        <div style={{ padding: '0 16px 16px 16px', backgroundColor: 'var(--bg-elevated)', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                                            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '13px' }}>
                                                <span style={{ color: 'var(--text-secondary)' }}>Supplier</span>
                                                <span>{group.contact_name || '-'}</span>
                                            </div>
                                            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '13px' }}>
                                                <span style={{ color: 'var(--text-secondary)' }}>Date</span>
                                                <span>{new Date(group.timestamp).toLocaleString()}</span>
                                            </div>
                                            <div style={{ borderTop: '1px solid var(--border-color)', paddingTop: '8px' }}>
                                                {group.items.map((h, hIdx) => (
                                                    <div key={hIdx} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0', borderBottom: hIdx < group.items.length - 1 ? '1px solid var(--border-color)' : 'none' }}>
                                                        <div>
                                                            <div style={{ fontWeight: 600, fontSize: '14px' }}>{h.item_name}</div>
                                                            <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                                                                Qty: {h.quantity} {h.unit_price ? `× ₹${h.unit_price.toLocaleString()}` : ''}
                                                            </div>
                                                        </div>
                                                        <div style={{ display: 'flex', gap: '4px' }}>
                                                            <button onClick={() => setEditingTransaction({ type: 'history', data: h })} style={{ background: 'transparent', border: 'none', color: 'var(--text-secondary)', cursor: 'pointer', padding: '4px' }}>
                                                                <Edit2 size={14} />
                                                            </button>
                                                            <button onClick={() => handleDeleteHistory(h.id)} style={{ background: 'transparent', border: 'none', color: 'var(--accent-red)', cursor: 'pointer', padding: '4px' }}>
                                                                <Trash2 size={14} />
                                                            </button>
                                                        </div>
                                                    </div>
                                                ))}
                                            </div>
                                        </div>
                                    )}
                                </div>
                            ))}
                            {loading ? (
                            <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-secondary)' }}><div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '8px' }}><div className="spin" style={{ width: '20px', height: '20px', border: '2px solid var(--accent-green)', borderTopColor: 'transparent', borderRadius: '50%' }}></div> Loading...</div></div>
                        ) : filteredItems.length === 0 ? (
                            <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-secondary)' }}>No items found</div>
                        ) : null}
                        </div>
                    </>
                )}
            </div>

            <PrintModal
                isOpen={printModalOpen}
                onClose={() => setPrintModalOpen(false)}
                columns={viewMode === 'stock' ? stockColumns : historyColumns}
                data={viewMode === 'stock' ? filteredItems : filteredHistory}
                title={viewMode === 'stock' ? 'Inventory Stock Report' : 'Inventory History Report'}
            />

            <ConfirmModal
                isOpen={!!confirmDeleteHistoryId}
                onClose={() => setConfirmDeleteHistoryId(null)}
                onConfirm={confirmAndDeleteHistory}
                title="Delete Log"
                message="Are you sure you want to delete this log AND reverse its stock change?"
                confirmText="Delete & Reverse"
                isDanger={true}
            />

            <ConfirmModal
                isOpen={!!confirmDeleteStockId}
                onClose={() => setConfirmDeleteStockId(null)}
                onConfirm={confirmAndDeleteStock}
                title="Delete Inventory Item"
                message="Are you sure you want to completely delete this item from inventory? This action cannot be undone."
                confirmText="Delete Item"
                isDanger={true}
            />

            <EditTransactionModal 
                isOpen={!!editingTransaction} 
                onClose={() => setEditingTransaction(null)} 
                onRefresh={() => { loadItems(); loadHistory(); }} 
                transaction={editingTransaction?.data} 
                type={editingTransaction?.type} 
                token={token} 
            />
        </div>
    );
};
