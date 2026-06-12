
import React, { useState, useEffect, useMemo } from 'react';
import { PlusCircle, MinusCircle, Search, ChevronDown, ChevronUp, Trash2, Download } from 'lucide-react';
import { API_BASE } from '../api';
import { TxModal } from '../components/TxModal';
import { ConfirmModal } from '../components/ConfirmModal';
import { PrintModal } from '../components/PrintModal';
import { ManageMerchantsModal } from '../components/ManageMerchantsModal';

export const LedgerView = ({ token, refreshTrigger }) => {
    const [txs, setTxs] = useState([]);
    const [txModalType, setTxModalType] = useState(null); // 'income' or 'expense'
    const [expandedTxn, setExpandedTxn] = useState(null);
    const [confirmDelete, setConfirmDelete] = useState(null); // id of tx to delete
    const [printModalOpen, setPrintModalOpen] = useState(false);
    const [loading, setLoading] = useState(true);
    
    // Search & Filter State
    const [search, setSearch] = useState('');
    const [timeFilter, setTimeFilter] = useState('all');
    const [customStart, setCustomStart] = useState('');
    const [customEnd, setCustomEnd] = useState('');

    const loadTxs = async () => {
        setLoading(true);
        try {
            const res = await fetch(`${API_BASE}/transactions`, { headers: { 'Authorization': `Bearer ${token}` } });
            if (res.status === 401) {
                localStorage.removeItem('apiToken');
                return window.location.reload();
            }
            setTxs(await res.json());
        } finally {
            setLoading(false);
        }
    };

    const handleDeleteClick = (id, e) => {
        if (e) e.stopPropagation();
        setConfirmDelete(id);
    };

    const confirmAndDeleteTxn = async () => {
        if (!confirmDelete) return;
        const id = confirmDelete;
        try {
            const res = await fetch(`${API_BASE}/transactions/${id}`, {
                method: 'DELETE',
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (res.ok) {
                setConfirmDelete(null);
                loadTxs();
            } else {
                alert("Failed to delete transaction");
            }
        } catch (err) {
            console.error(err);
        }
    };

    useEffect(() => { loadTxs(); }, [token, refreshTrigger]);

    const existingMerchants = [...new Set(txs.map(t => t.merchant))].filter(Boolean);

    // Filter Logic
    const filteredTxs = useMemo(() => {
        return txs.filter(t => {
            if (timeFilter !== 'all') {
                const txDate = new Date(t.date);
                const now = new Date();
                if (timeFilter === 'month') {
                    if (txDate.getMonth() !== now.getMonth() || txDate.getFullYear() !== now.getFullYear()) return false;
                } else if (timeFilter === 'year') {
                    if (txDate.getFullYear() !== now.getFullYear()) return false;
                } else if (timeFilter === 'custom') {
                    if (customStart && new Date(t.date) < new Date(customStart)) return false;
                    if (customEnd) {
                        const endD = new Date(customEnd);
                        endD.setHours(23, 59, 59, 999);
                        if (new Date(t.date) > endD) return false;
                    }
                }
            }
            if (search) {
                const query = search.toLowerCase();
                return (
                    String(t.merchant).toLowerCase().includes(query) ||
                    String(t.txn_id).toLowerCase().includes(query) ||
                    String(t.credit).includes(query) ||
                    String(t.debit).includes(query)
                );
            }
            return true;
        });
    }, [txs, search, timeFilter, customStart, customEnd]);

    const totalFilteredBalance = useMemo(() => {
        return filteredTxs.reduce((sum, t) => sum + (t.credit || 0) - (t.debit || 0), 0);
    }, [filteredTxs]);



    const ledgerColumns = [
        { key: 'id', label: 'ID' },
        { key: 'date', label: 'Date' },
        { key: 'merchant', label: 'Merchant' },
        { key: 'credit', label: 'Credit', render: r => r.credit > 0 ? `₹${r.credit.toLocaleString()}` : '-' },
        { key: 'debit', label: 'Debit', render: r => r.debit > 0 ? `₹${r.debit.toLocaleString()}` : '-' },
        { key: 'balance', label: 'Balance', render: r => `₹${r.balance.toLocaleString()}` }
    ];

    return (
        <div className="fade-in">
            <div className="header" style={{ marginBottom: '24px' }}>
                <h1 className="brand">Ledger</h1>
                <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
                    <button className="btn-action" onClick={() => setPrintModalOpen(true)} style={{ padding: '8px 16px', borderRadius: '24px', justifyContent: 'center' }} title="Print Ledger">
                        Print
                    </button>
                </div>
            </div>

            <TxModal 
                isOpen={!!txModalType} 
                onClose={() => setTxModalType(null)} 
                onRefresh={loadTxs} 
                type={txModalType} 
                token={token} 
                existingMerchants={existingMerchants}
            />


            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px', flexWrap: 'wrap', gap: '16px' }}>
                <div style={{ display: 'flex', gap: '16px', flex: 1, alignItems: 'center', flexWrap: 'wrap' }}>
                    <div style={{ position: 'relative', minWidth: '200px', maxWidth: '300px' }}>
                        <Search size={18} style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-secondary)' }} />
                        <input 
                            type="text" 
                            className="form-input" 
                            placeholder="Search Ledger..." 
                            value={search} 
                            onChange={(e) => setSearch(e.target.value)}
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
                        <option value="month">This Month</option>
                        <option value="year">This Year</option>
                        <option value="custom">Custom Range...</option>
                    </select>

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
                                min={customStart}
                                style={{ backgroundColor: 'var(--bg-elevated)', padding: '8px 12px' }}
                            />
                        </div>
                    )}
                </div>
                
                <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
                    <button className="btn-action" onClick={() => setTxModalType('income')} style={{ backgroundColor: 'var(--accent-green-dim)', color: 'var(--accent-green)', padding: '12px', borderRadius: '50%', width: '48px', height: '48px', justifyContent: 'center' }}>
                        <PlusCircle size={24} />
                    </button>
                    <button className="btn-action" onClick={() => setTxModalType('expense')} style={{ backgroundColor: 'var(--accent-red-dim)', color: 'var(--accent-red)', padding: '12px', borderRadius: '50%', width: '48px', height: '48px', justifyContent: 'center' }}>
                        <MinusCircle size={24} />
                    </button>
                </div>
            </div>

            <div className="card table-card" style={{ padding: 0, overflowX: 'auto' }}>
                <div style={{ padding: '24px', borderBottom: '1px solid var(--border-color)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <h2 style={{ fontSize: '16px', fontWeight: 600 }}>Transactions</h2>
                    <div style={{ fontSize: '14px', fontWeight: 600 }}>
                        <span style={{ color: 'var(--text-secondary)' }}>Net Amount: </span>
                        <span style={{ color: totalFilteredBalance >= 0 ? 'var(--accent-green)' : 'var(--accent-red)' }}>
                            {totalFilteredBalance >= 0 ? '+' : '-'}₹{Math.abs(totalFilteredBalance).toLocaleString()}
                        </span>
                    </div>
                </div>
                
                <div className="desktop-only">
                    <table className="data-table">
                        <thead><tr><th>ID</th><th>Date</th><th>Merchant</th><th>Credit</th><th>Debit</th><th>Balance</th><th></th></tr></thead>
                        <tbody>
                            {filteredTxs.map((tx, i) => {
                                return (
                                    <tr key={i} className="hover-row">
                                        <td style={{ color: 'var(--text-secondary)' }}>{tx.id}</td>
                                        <td style={{ color: 'var(--text-secondary)', whiteSpace: 'nowrap' }}>{tx.date}</td>
                                        <td style={{ fontWeight: 600 }}>{tx.merchant}</td>
                                        <td style={{ color: 'var(--accent-green)', fontWeight: 600 }}>{tx.credit > 0 ? `₹${tx.credit.toLocaleString()}` : '-'}</td>
                                        <td style={{ color: 'var(--accent-red)', fontWeight: 600 }}>{tx.debit > 0 ? `₹${tx.debit.toLocaleString()}` : '-'}</td>
                                        <td style={{ fontWeight: 'bold' }}>₹{tx.balance.toLocaleString()}</td>
                                        <td>
                                            <button className="btn-action" onClick={(e) => handleDeleteClick(tx.id, e)} style={{ padding: '8px', color: 'var(--accent-red)' }}>
                                                <Trash2 size={16} />
                                            </button>
                                        </td>
                                    </tr>
                                )
                            })}
                            {loading ? (
                                <tr><td colSpan="7" style={{ textAlign: 'center', padding: '40px', color: 'var(--text-secondary)' }}><div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '8px' }}><div className="spin" style={{ width: '20px', height: '20px', border: '2px solid var(--accent-green)', borderTopColor: 'transparent', borderRadius: '50%' }}></div> Loading transactions...</div></td></tr>
                            ) : filteredTxs.length === 0 ? (
                                <tr><td colSpan="7" style={{ textAlign: 'center', padding: '40px', color: 'var(--text-secondary)' }}>No transactions found</td></tr>
                            ) : null}
                        </tbody>
                    </table>
                </div>

                <div className="mobile-only" style={{ padding: '0' }}>
                    {filteredTxs.map((tx, i) => (
                        <div key={i} style={{ borderBottom: '1px solid var(--border-color)' }}>
                            <div 
                                style={{ padding: '16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', cursor: 'pointer' }}
                                onClick={() => setExpandedTxn(expandedTxn === i ? null : i)}
                            >
                                <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                                    <span style={{ fontWeight: 600, fontSize: '15px' }}>{tx.merchant}</span>
                                    <span style={{ color: 'var(--text-secondary)', fontSize: '13px' }}>ID: {tx.id}</span>
                                </div>
                                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                                    <span style={{ 
                                        fontWeight: 600, 
                                        color: tx.credit > 0 ? 'var(--accent-green)' : 'var(--accent-red)' 
                                    }}>
                                        {tx.credit > 0 ? `+₹${tx.credit.toLocaleString()}` : `-₹${tx.debit.toLocaleString()}`}
                                    </span>
                                    {expandedTxn === i ? <ChevronUp size={20} color="var(--text-secondary)"/> : <ChevronDown size={20} color="var(--text-secondary)"/>}
                                </div>
                            </div>
                            
                            {expandedTxn === i && (
                                <div style={{ padding: '0 16px 16px 16px', backgroundColor: 'var(--bg-elevated)', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '13px' }}>
                                        <span style={{ color: 'var(--text-secondary)' }}>Date</span>
                                        <span>{tx.date}</span>
                                    </div>
                                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '13px' }}>
                                        <span style={{ color: 'var(--text-secondary)' }}>Balance After</span>
                                        <span style={{ fontWeight: 'bold' }}>₹{tx.balance.toLocaleString()}</span>
                                    </div>
                                    <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '8px' }}>
                                        <button 
                                            className="btn-action" 
                                            onClick={(e) => handleDeleteClick(tx.id, e)}
                                            style={{ backgroundColor: 'var(--accent-red-dim)', color: 'var(--accent-red)', padding: '8px 16px', fontSize: '13px', borderRadius: '8px' }}
                                        >
                                            <Trash2 size={14} style={{ marginRight: '6px' }} /> Delete
                                        </button>
                                    </div>
                                </div>
                            )}
                        </div>
                    ))}
                    {loading ? (
                        <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-secondary)' }}>
                            <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '8px' }}>
                                <div className="spin" style={{ width: '20px', height: '20px', border: '2px solid var(--accent-green)', borderTopColor: 'transparent', borderRadius: '50%' }}></div> Loading...
                            </div>
                        </div>
                    ) : filteredTxs.length === 0 ? (
                        <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-secondary)' }}>No transactions found</div>
                    ) : null}
                </div>
            </div>

            <ConfirmModal
                isOpen={!!confirmDelete}
                onClose={() => setConfirmDelete(null)}
                title="Delete Transaction"
                message="Are you sure you want to delete this transaction from the ledger?"
                onConfirm={confirmAndDeleteTxn}
            />

            <PrintModal
                isOpen={printModalOpen}
                onClose={() => setPrintModalOpen(false)}
                columns={ledgerColumns}
                data={filteredTxs}
                title="Ledger Report"
            />
        </div>
    );
};
