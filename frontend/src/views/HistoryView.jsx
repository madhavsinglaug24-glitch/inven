import React, { useState, useEffect } from 'react';
import { Download, Trash2, Search, Edit2 } from 'lucide-react';
import { EditTransactionModal } from '../components/EditTransactionModal';
import { API_BASE } from '../api';

export const HistoryView = ({ token, refreshTrigger }) => {
    const [activeTab, setActiveTab] = useState('inventory');
    const [inventoryHistory, setInventoryHistory] = useState([]);
    const [ledgerHistory, setLedgerHistory] = useState([]);
    const [loading, setLoading] = useState(false);
    const [searchQuery, setSearchQuery] = useState('');
    const [editingTransaction, setEditingTransaction] = useState(null);

    useEffect(() => {
        if (activeTab === 'inventory') {
            fetchInventoryHistory();
        } else if (activeTab === 'ledger') {
            fetchLedgerHistory();
        }
    }, [activeTab, refreshTrigger]);

    const fetchInventoryHistory = async () => {
        setLoading(true);
        try {
            const res = await fetch(`${API_BASE}/history`);
            if (res.ok) {
                const data = await res.json();
                setInventoryHistory(data);
            }
        } catch (e) { console.error(e); }
        setLoading(false);
    };

    const handleDeleteHistory = async (id) => {
        if (!window.confirm("Are you sure you want to delete this log AND reverse its stock change?")) return;
        try {
            const res = await fetch(`${API_BASE}/history/${id}`, {
                method: 'DELETE',
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (res.ok) {
                fetchInventoryHistory();
            } else {
                const data = await res.json();
                alert(data.error || "Failed to delete");
            }
        } catch (e) { alert("Network error"); }
    };

    const fetchLedgerHistory = async () => {
        setLoading(true);
        try {
            const res = await fetch(`${API_BASE}/transactions`);
            if (res.ok) {
                const data = await res.json();
                setLedgerHistory(data);
            }
        } catch (e) { console.error(e); }
        setLoading(false);
    };

    const filteredInventory = inventoryHistory.filter(h => {
        const q = searchQuery.toLowerCase();
        return (
            String(h.item_name || '').toLowerCase().includes(q) ||
            String(h.contact_name || '').toLowerCase().includes(q) ||
            String(h.action || '').toLowerCase().includes(q)
        );
    });

    const filteredLedger = ledgerHistory.filter(h => {
        const q = searchQuery.toLowerCase();
        return (
            String(h.merchant || '').toLowerCase().includes(q) ||
            String(h.id || '').toLowerCase().includes(q)
        );
    });

    const exportToExcel = () => {
        let csvContent = "";
        if (activeTab === 'inventory') {
            csvContent += "Date,Item,Action,Qty,Unit ₹,Contact,Comment\n";
            filteredInventory.forEach(row => {
                const r = [
                    new Date(row.timestamp).toLocaleString(), 
                    row.item_name, 
                    row.action, 
                    row.quantity, 
                    row.unit_price || '-',
                    row.contact_name || '-', 
                    row.comment || '-'
                ].map(v => `"${(v||'').toString().replace(/"/g, '""')}"`).join(",");
                csvContent += r + "\n";
            });
        } else {
            csvContent += "ID,Date,Merchant,Credit,Debit,Balance\n";
            filteredLedger.forEach(row => {
                const r = [
                    row.id, 
                    row.date, 
                    row.merchant, 
                    row.credit || 0, 
                    row.debit || 0, 
                    row.balance
                ].map(v => `"${(v||'').toString().replace(/"/g, '""')}"`).join(",");
                csvContent += r + "\n";
            });
        }
        const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
        const link = document.createElement("a");
        link.href = URL.createObjectURL(blob);
        link.setAttribute("download", `${activeTab}_history.csv`);
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    };

    return (
        <div className="fade-in">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
                <h2 className="page-title">Print</h2>
                <button className="btn-action" onClick={exportToExcel}>
                    <Download size={20} style={{marginRight: 8}}/> Download Excel
                </button>
            </div>
            
            <div style={{ display: 'flex', gap: '16px', marginBottom: '24px' }}>
                <button 
                    className={`btn-action ${activeTab === 'inventory' ? 'btn-credit' : ''}`} 
                    onClick={() => setActiveTab('inventory')}
                >
                    Inventory History
                </button>
                <button 
                    className={`btn-action ${activeTab === 'ledger' ? 'btn-credit' : ''}`} 
                    onClick={() => setActiveTab('ledger')}
                >
                    Ledger History
                </button>
            </div>

            <div style={{ position: 'relative', marginBottom: '24px' }}>
                <Search size={18} style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-secondary)' }} />
                <input 
                    type="text" 
                    className="form-input"
                    placeholder="Filter by contact, item, or action..." 
                    value={searchQuery}
                    onChange={e => setSearchQuery(e.target.value)}
                    style={{ paddingLeft: '40px', width: '300px', backgroundColor: 'var(--bg-elevated)' }}
                />
            </div>

            <div className="excel-container">
                {loading && <div style={{ padding: '20px' }}>Loading...</div>}
                
                {!loading && activeTab === 'inventory' && (
                    <table className="excel-table">
                        <thead>
                            <tr>
                                <th>Date</th>
                                <th>Item</th>
                                <th>Action</th>
                                <th>Qty</th>
                                <th>Unit ₹</th>
                                <th>Contact</th>
                                <th>Comment</th>
                                <th></th>
                            </tr>
                        </thead>
                        <tbody>
                            {filteredInventory.map((row, i) => (
                                <tr key={i}>
                                    <td style={{ color: 'var(--text-secondary)' }}>{new Date(row.timestamp).toLocaleString()}</td>
                                    <td style={{ fontWeight: 600 }}>{row.item_name}</td>
                                    <td>
                                        <span style={{ padding: '4px 8px', borderRadius: '4px', fontSize: '12px', fontWeight: 600, backgroundColor: row.action === 'RESTOCK' ? 'var(--accent-green-dim)' : 'var(--accent-red-dim)', color: row.action === 'RESTOCK' ? 'var(--accent-teal)' : 'var(--accent-red)' }}>
                                            {row.action}
                                        </span>
                                    </td>
                                    <td style={{ fontWeight: 'bold' }}>{row.quantity}</td>
                                    <td>{row.unit_price ? `₹${row.unit_price.toLocaleString()}` : '-'}</td>
                                    <td style={{ color: 'var(--text-secondary)' }}>{row.contact_name || '-'}</td>
                                    <td style={{ color: 'var(--text-secondary)' }}>{row.comment || '-'}</td>
                                    <td style={{ display: 'flex', gap: '8px' }}>
                                        <button onClick={() => setEditingTransaction({ type: 'history', data: row })} style={{ background: 'transparent', border: 'none', color: 'var(--text-secondary)', cursor: 'pointer', padding: '4px' }}>
                                            <Edit2 size={16} />
                                        </button>
                                        <button onClick={() => handleDeleteHistory(row.id)} style={{ background: 'transparent', border: 'none', color: 'var(--accent-red)', cursor: 'pointer', padding: '4px' }}>
                                            <Trash2 size={16} />
                                        </button>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                )}

                {!loading && activeTab === 'ledger' && (
                    <table className="excel-table">
                        <thead>
                            <tr>
                                <th>ID</th>
                                <th>Date</th>
                                <th>Merchant</th>
                                <th>Credit</th>
                                <th>Debit</th>
                                <th>Balance</th>
                                <th></th>
                            </tr>
                        </thead>
                        <tbody>
                            {filteredLedger.map((row, i) => (
                                <tr key={i}>
                                    <td style={{ color: 'var(--text-secondary)' }}>{row.id}</td>
                                    <td style={{ color: 'var(--text-secondary)', whiteSpace: 'nowrap' }}>{row.date}</td>
                                    <td style={{ fontWeight: 600 }}>{row.merchant}</td>
                                    <td style={{ color: 'var(--accent-teal)', fontWeight: 600 }}>{row.credit > 0 ? `₹${row.credit.toLocaleString()}` : '-'}</td>
                                    <td style={{ color: 'var(--accent-red)', fontWeight: 600 }}>{row.debit > 0 ? `₹${row.debit.toLocaleString()}` : '-'}</td>
                                    <td style={{ fontWeight: 'bold' }}>₹{row.balance.toLocaleString()}</td>
                                    <td>
                                        <button onClick={() => setEditingTransaction({ type: 'ledger', data: row })} style={{ background: 'transparent', border: 'none', color: 'var(--text-secondary)', cursor: 'pointer', padding: '4px' }}>
                                            <Edit2 size={16} />
                                        </button>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                )}
            </div>

            <EditTransactionModal 
                isOpen={!!editingTransaction} 
                onClose={() => setEditingTransaction(null)} 
                onRefresh={() => {
                    if (editingTransaction?.type === 'history') fetchInventoryHistory();
                    else fetchLedgerHistory();
                }} 
                transaction={editingTransaction?.data} 
                type={editingTransaction?.type} 
                token={token} 
            />
        </div>
    );
};
