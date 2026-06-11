import React, { useState, useEffect } from 'react';
import { Download } from 'lucide-react';
import { API_BASE } from '../api';

export const HistoryView = ({ token }) => {
    const [activeTab, setActiveTab] = useState('inventory');
    const [inventoryHistory, setInventoryHistory] = useState([]);
    const [ledgerHistory, setLedgerHistory] = useState([]);
    const [loading, setLoading] = useState(false);

    useEffect(() => {
        if (activeTab === 'inventory' && inventoryHistory.length === 0) {
            fetchInventoryHistory();
        } else if (activeTab === 'ledger' && ledgerHistory.length === 0) {
            fetchLedgerHistory();
        }
    }, [activeTab]);

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

    const exportToExcel = () => {
        let csvContent = "";
        if (activeTab === 'inventory') {
            csvContent += "Date,Item,Action,Qty,Contact,Comment\n";
            inventoryHistory.forEach(row => {
                const r = [
                    new Date(row.timestamp).toLocaleString(), 
                    row.item_name, 
                    row.action, 
                    row.quantity, 
                    row.contact_name || '-', 
                    row.comment || '-'
                ].map(v => `"${(v||'').toString().replace(/"/g, '""')}"`).join(",");
                csvContent += r + "\n";
            });
        } else {
            csvContent += "ID,Date,Merchant,Credit,Debit,Balance\n";
            ledgerHistory.forEach(row => {
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
                                <th>Contact</th>
                                <th>Comment</th>
                            </tr>
                        </thead>
                        <tbody>
                            {inventoryHistory.map((row, i) => (
                                <tr key={i}>
                                    <td style={{ color: 'var(--text-secondary)' }}>{new Date(row.timestamp).toLocaleString()}</td>
                                    <td style={{ fontWeight: 600 }}>{row.item_name}</td>
                                    <td>
                                        <span style={{ padding: '4px 8px', borderRadius: '4px', fontSize: '12px', fontWeight: 600, backgroundColor: row.action === 'RESTOCK' ? 'var(--accent-green-dim)' : 'var(--accent-red-dim)', color: row.action === 'RESTOCK' ? 'var(--accent-teal)' : 'var(--accent-red)' }}>
                                            {row.action}
                                        </span>
                                    </td>
                                    <td style={{ fontWeight: 'bold' }}>{row.quantity}</td>
                                    <td style={{ color: 'var(--text-secondary)' }}>{row.contact_name || '-'}</td>
                                    <td style={{ color: 'var(--text-secondary)' }}>{row.comment || '-'}</td>
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
                            </tr>
                        </thead>
                        <tbody>
                            {ledgerHistory.map((row, i) => (
                                <tr key={i}>
                                    <td style={{ color: 'var(--text-secondary)' }}>{row.id}</td>
                                    <td style={{ color: 'var(--text-secondary)', whiteSpace: 'nowrap' }}>{row.date}</td>
                                    <td style={{ fontWeight: 600 }}>{row.merchant}</td>
                                    <td style={{ color: 'var(--accent-teal)', fontWeight: 600 }}>{row.credit > 0 ? `₹${row.credit.toLocaleString()}` : '-'}</td>
                                    <td style={{ color: 'var(--accent-red)', fontWeight: 600 }}>{row.debit > 0 ? `₹${row.debit.toLocaleString()}` : '-'}</td>
                                    <td style={{ fontWeight: 'bold' }}>₹{row.balance.toLocaleString()}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                )}
            </div>
        </div>
    );
};
