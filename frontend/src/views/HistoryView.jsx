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
            const res = await fetch(`${API_BASE}/ledger`);
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
            csvContent += "Timestamp,Item ID,Item Name,Action,Quantity,User Phone,Prev Stock,New Stock,Contact Type,Contact Name,Comment,Txn ID\n";
            inventoryHistory.forEach(row => {
                const r = [row.timestamp, row.item_id, row.item_name, row.action, row.quantity, row.user_phone, row.previous_stock, row.new_stock, row.contact_type, row.contact_name, row.comment, row.txn_id].map(v => `"${(v||'').toString().replace(/"/g, '""')}"`).join(",");
                csvContent += r + "\n";
            });
        } else {
            csvContent += "Date,Type,Amount,Name,Comment,Logged By,Txn ID\n";
            ledgerHistory.forEach(row => {
                const r = [row.Date, row.Type, row.Amount, row.Name, row.Comment, row.Logged_By, row.Txn_ID].map(v => `"${(v||'').toString().replace(/"/g, '""')}"`).join(",");
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
                                <th>Timestamp</th>
                                <th>Item ID</th>
                                <th>Item Name</th>
                                <th>Action</th>
                                <th>Quantity</th>
                                <th>User Phone</th>
                                <th>Prev Stock</th>
                                <th>New Stock</th>
                                <th>Contact Type</th>
                                <th>Contact Name</th>
                                <th>Comment</th>
                                <th>Txn ID</th>
                            </tr>
                        </thead>
                        <tbody>
                            {inventoryHistory.map((row, i) => (
                                <tr key={i}>
                                    <td>{row.timestamp}</td>
                                    <td>{row.item_id}</td>
                                    <td>{row.item_name}</td>
                                    <td>{row.action}</td>
                                    <td>{row.quantity}</td>
                                    <td>{row.user_phone}</td>
                                    <td>{row.previous_stock}</td>
                                    <td>{row.new_stock}</td>
                                    <td>{row.contact_type}</td>
                                    <td>{row.contact_name}</td>
                                    <td>{row.comment}</td>
                                    <td>{row.txn_id}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                )}

                {!loading && activeTab === 'ledger' && (
                    <table className="excel-table">
                        <thead>
                            <tr>
                                <th>Date</th>
                                <th>Type</th>
                                <th>Amount</th>
                                <th>Name</th>
                                <th>Comment</th>
                                <th>Logged By</th>
                                <th>Txn ID</th>
                            </tr>
                        </thead>
                        <tbody>
                            {ledgerHistory.map((row, i) => (
                                <tr key={i}>
                                    <td>{row.Date}</td>
                                    <td>{row.Type}</td>
                                    <td>{row.Amount}</td>
                                    <td>{row.Name}</td>
                                    <td>{row.Comment}</td>
                                    <td>{row.Logged_By}</td>
                                    <td>{row.Txn_ID}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                )}
            </div>
        </div>
    );
};
