import React, { useState, useEffect, useMemo } from 'react';
import { Download, Search } from 'lucide-react';
import { API_BASE } from '../api';
import { getPreviousMonthRange, matchesTimeFilter } from '../utils/dateFilters';

export const ExportView = ({ token, refreshTrigger }) => {
    const [activeTab, setActiveTab] = useState('inventory');
    const [inventoryHistory, setInventoryHistory] = useState([]);
    const [ledgerHistory, setLedgerHistory] = useState([]);
    const [loading, setLoading] = useState(false);
    const [searchQuery, setSearchQuery] = useState('');
    const [timeFilter, setTimeFilter] = useState('all');
    const [customStart, setCustomStart] = useState('');
    const [customEnd, setCustomEnd] = useState('');

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

    const fetchInventoryHistory = async () => {
        setLoading(true);
        const res = await fetch(`${API_BASE}/history`, { headers: { 'Authorization': `Bearer ${token}` } });
        if (res.ok) setInventoryHistory(await res.json());
        setLoading(false);
    };

    const fetchLedgerHistory = async () => {
        setLoading(true);
        const res = await fetch(`${API_BASE}/transactions`, { headers: { 'Authorization': `Bearer ${token}` } });
        if (res.ok) setLedgerHistory(await res.json());
        setLoading(false);
    };

    useEffect(() => {
        if (activeTab === 'inventory') fetchInventoryHistory();
        else fetchLedgerHistory();
    }, [activeTab, token, refreshTrigger]);

    const filteredInventory = useMemo(() => {
        return inventoryHistory.filter(r => {
            if (!matchesTimeFilter(r.timestamp, timeFilter, rangeStart, rangeEnd)) return false;
            if (!searchQuery) return true;
            const q = searchQuery.toLowerCase();
            return (
                String(r.item_name).toLowerCase().includes(q) ||
                String(r.action).toLowerCase().includes(q) ||
                String(r.contact_name).toLowerCase().includes(q) ||
                String(r.bill_no).toLowerCase().includes(q)
            );
        });
    }, [inventoryHistory, searchQuery, timeFilter, rangeStart, rangeEnd]);

    const filteredLedger = useMemo(() => {
        return ledgerHistory.filter(r => {
            if (!matchesTimeFilter(r.date, timeFilter, rangeStart, rangeEnd)) return false;
            if (!searchQuery) return true;
            const q = searchQuery.toLowerCase();
            return (
                String(r.merchant).toLowerCase().includes(q) ||
                String(r.txn_id).toLowerCase().includes(q)
            );
        });
    }, [ledgerHistory, searchQuery, timeFilter, rangeStart, rangeEnd]);

    const exportInventoryCSV = () => {
        let csv = "Date,Bill No,Item,Action,Qty,Unit Price,Total,Contact,Comment\n";
        filteredInventory.forEach(r => {
            const row = [
                r.timestamp, r.bill_no || '', r.item_name, r.action,
                r.quantity, r.unit_price || 0,
                r.unit_price ? (r.unit_price * r.quantity) : 0,
                r.contact_name || '', r.comment || ''
            ].map(v => `"${(v ?? '').toString().replace(/"/g, '""')}"`).join(",");
            csv += row + "\n";
        });
        downloadCSV(csv, 'inventory_history.csv');
    };

    const exportLedgerCSV = () => {
        let csv = "ID,Date,Merchant,Credit,Debit,Balance\n";
        filteredLedger.forEach(r => {
            const row = [
                r.id, r.date, r.merchant,
                r.credit || 0, r.debit || 0, r.balance
            ].map(v => `"${(v ?? '').toString().replace(/"/g, '""')}"`).join(",");
            csv += row + "\n";
        });
        downloadCSV(csv, 'ledger_history.csv');
    };

    const downloadCSV = (content, filename) => {
        const blob = new Blob([content], { type: 'text/csv;charset=utf-8;' });
        const link = document.createElement("a");
        link.href = URL.createObjectURL(blob);
        link.setAttribute("download", filename);
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    };

    return (
        <div className="fade-in">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
                <h1 className="page-title">Export</h1>
            </div>

            <div style={{ display: 'flex', gap: '0', marginBottom: '24px' }}>
                <button
                    onClick={() => { setActiveTab('inventory'); setSearchQuery(''); }}
                    style={{
                        padding: '10px 24px', border: '1px solid var(--border-color)',
                        borderRadius: '8px 0 0 8px', cursor: 'pointer', fontWeight: 600,
                        backgroundColor: activeTab === 'inventory' ? 'var(--accent-teal)' : 'var(--bg-elevated)',
                        color: activeTab === 'inventory' ? '#fff' : 'var(--text-secondary)'
                    }}
                >Inventory</button>
                <button
                    onClick={() => { setActiveTab('ledger'); setSearchQuery(''); }}
                    style={{
                        padding: '10px 24px', border: '1px solid var(--border-color)',
                        borderRadius: '0 8px 8px 0', cursor: 'pointer', fontWeight: 600,
                        backgroundColor: activeTab === 'ledger' ? 'var(--accent-teal)' : 'var(--bg-elevated)',
                        color: activeTab === 'ledger' ? '#fff' : 'var(--text-secondary)'
                    }}
                >Ledger</button>
            </div>

            <div style={{ display: 'flex', gap: '16px', marginBottom: '24px', flexWrap: 'wrap', alignItems: 'center' }}>
                <div style={{ position: 'relative', flex: 1, minWidth: '200px', maxWidth: '300px' }}>
                    <Search size={18} style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-secondary)' }} />
                    <input 
                        type="text" 
                        className="form-input" 
                        placeholder={`Filter ${activeTab}...`}
                        value={searchQuery} 
                        onChange={(e) => setSearchQuery(e.target.value)}
                        style={{ paddingLeft: '40px', backgroundColor: 'var(--bg-elevated)', width: '100%' }}
                    />
                </div>
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
                {timeFilter === 'custom' && customStart && customEnd && customStart > customEnd && (
                    <span style={{ color: 'var(--accent-red)', fontSize: '12px' }}>Dates swapped (From was after To)</span>
                )}
                {timeFilter === 'custom' && (
                    <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
                        <input
                            type="date"
                            className="form-input"
                            value={customStart}
                            onChange={e => setCustomStart(e.target.value)}
                            style={{ backgroundColor: 'var(--bg-elevated)', padding: '8px 12px' }}
                        />
                        <span style={{ color: 'var(--text-secondary)' }}>to</span>
                        <input
                            type="date"
                            className="form-input"
                            value={customEnd}
                            onChange={e => setCustomEnd(e.target.value)}
                            style={{ backgroundColor: 'var(--bg-elevated)', padding: '8px 12px' }}
                        />
                    </div>
                )}
                <button
                    className="btn-action btn-credit"
                    onClick={activeTab === 'inventory' ? exportInventoryCSV : exportLedgerCSV}
                    style={{ padding: '10px 20px' }}
                >
                    <Download size={18} style={{ marginRight: '8px' }} />
                    Download CSV
                </button>
            </div>

            <div className="card table-card" style={{ padding: 0, overflowX: 'auto' }}>
                {loading && <div style={{ padding: '24px', textAlign: 'center', color: 'var(--text-secondary)' }}>Loading...</div>}

                {!loading && activeTab === 'inventory' && (
                    <table className="data-table">
                        <thead>
                            <tr>
                                <th>Date</th>
                                <th>Bill No</th>
                                <th>Item</th>
                                <th>Action</th>
                                <th>Qty</th>
                                <th>Unit ₹</th>
                                <th>Contact</th>
                                <th>Comment</th>
                            </tr>
                        </thead>
                        <tbody>
                            {filteredInventory.map((row, i) => (
                                <tr key={i}>
                                    <td style={{ color: 'var(--text-secondary)', whiteSpace: 'nowrap' }}>{new Date(row.timestamp).toLocaleString()}</td>
                                    <td>{row.bill_no || '-'}</td>
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
                                </tr>
                            ))}
                            {filteredInventory.length === 0 && <tr><td colSpan="8" style={{ textAlign: 'center', padding: '24px', color: 'var(--text-secondary)' }}>No records found</td></tr>}
                        </tbody>
                    </table>
                )}

                {!loading && activeTab === 'ledger' && (
                    <table className="data-table">
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
                            {filteredLedger.map((row, i) => (
                                <tr key={i}>
                                    <td style={{ color: 'var(--text-secondary)' }}>{row.id}</td>
                                    <td style={{ color: 'var(--text-secondary)', whiteSpace: 'nowrap' }}>{row.date}</td>
                                    <td style={{ fontWeight: 600 }}>{row.merchant}</td>
                                    <td style={{ color: 'var(--accent-teal)', fontWeight: 600 }}>{row.credit > 0 ? `₹${row.credit.toLocaleString()}` : '-'}</td>
                                    <td style={{ color: 'var(--accent-red)', fontWeight: 600 }}>{row.debit > 0 ? `₹${row.debit.toLocaleString()}` : '-'}</td>
                                    <td style={{ fontWeight: 'bold' }}>₹{row.balance.toLocaleString()}</td>
                                </tr>
                            ))}
                            {filteredLedger.length === 0 && <tr><td colSpan="6" style={{ textAlign: 'center', padding: '24px', color: 'var(--text-secondary)' }}>No records found</td></tr>}
                        </tbody>
                    </table>
                )}
            </div>
        </div>
    );
};
