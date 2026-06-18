import React, { useState, useEffect, useMemo } from 'react';
import { PlusCircle, MinusCircle, Search, ChevronDown, ChevronUp, Trash2 } from 'lucide-react';
import { API_BASE } from '../api';
import { formatMoney, formatSignedMoney } from '../utils/money';
import { getFilterRange } from '../utils/dateFilters';
import { TxModal } from '../components/TxModal';
import { ConfirmModal } from '../components/ConfirmModal';
import { PrintModal } from '../components/PrintModal';
import { EditTransactionModal } from '../components/EditTransactionModal';
import { TransferModal } from '../components/TransferModal';
import { Edit2, ArrowRightLeft } from 'lucide-react';

export const LedgerView = ({ token, refreshTrigger }) => {
    const [txs, setTxs] = useState([]);
    const [txModalType, setTxModalType] = useState(null); // 'income' or 'expense'
    const [expandedTxn, setExpandedTxn] = useState(null);
    const [confirmDelete, setConfirmDelete] = useState(null); // id of tx to delete
    const [editTxn, setEditTxn] = useState(null); // the txn object to edit
    const [transferModalOpen, setTransferModalOpen] = useState(false);
    const [printModalOpen, setPrintModalOpen] = useState(false);
    const [loading, setLoading] = useState(true);
    
    // Search & Filter State
    const [search, setSearch] = useState('');
    const [timeFilter, setTimeFilter] = useState('all');
    const [accountFilter, setAccountFilter] = useState('all');
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
                headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
                body: JSON.stringify({ confirmed: true })
            });
            if (res.ok) {
                setConfirmDelete(null);
                if (editTxn?.id === id) setEditTxn(null);
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

    const { start: rangeStart, end: rangeEnd } = useMemo(
        () => getFilterRange(timeFilter, customStart, customEnd),
        [timeFilter, customStart, customEnd]
    );

    const rowBalance = (tx) => {
        if (accountFilter === 'Cash' || accountFilter === 'Bank') return tx.acct_balance ?? tx.balance ?? 0;
        return tx.balance ?? 0;
    };

    const txPassesEndFilter = (t) => {
        if (timeFilter === 'all') return true;
        const txDate = new Date(t.date);
        let endCutoff = null;
        if (timeFilter === 'month') {
            const now = new Date();
            endCutoff = new Date(now.getFullYear(), now.getMonth() + 1, 0, 23, 59, 59, 999);
        } else if (timeFilter === 'year') {
            endCutoff = new Date(new Date().getFullYear(), 11, 31, 23, 59, 59, 999);
        } else if ((timeFilter === 'custom' || timeFilter === 'last_month') && rangeEnd) {
            endCutoff = new Date(rangeEnd);
            endCutoff.setHours(23, 59, 59, 999);
        }
        if (!endCutoff) return true;
        return txDate <= endCutoff;
    };

    const txBeforePeriod = (t) => {
        const txDate = new Date(t.date);
        const now = new Date();
        if (timeFilter === 'month') {
            return txDate < new Date(now.getFullYear(), now.getMonth(), 1);
        }
        if (timeFilter === 'year') {
            return txDate < new Date(now.getFullYear(), 0, 1);
        }
        if ((timeFilter === 'custom' || timeFilter === 'last_month') && rangeStart) {
            const startD = new Date(rangeStart);
            startD.setHours(0, 0, 0, 0);
            return txDate < startD;
        }
        return false;
    };

    const matchesAccount = (t) => {
        if (accountFilter === 'all') return true;
        if (accountFilter === 'Cash') return !t.account || t.account === 'Cash';
        return t.account === 'Bank';
    };

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
                } else if (timeFilter === 'custom' || timeFilter === 'last_month') {
                    if (rangeStart) {
                        const startD = new Date(rangeStart);
                        startD.setHours(0, 0, 0, 0);
                        if (txDate < startD) return false;
                    }
                    if (rangeEnd) {
                        const endD = new Date(rangeEnd);
                        endD.setHours(23, 59, 59, 999);
                        if (txDate > endD) return false;
                    }
                }
            }
            if (accountFilter !== 'all') {
                if (accountFilter === 'Cash' && t.account && t.account !== 'Cash') return false;
                if (accountFilter === 'Bank' && t.account !== 'Bank') return false;
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
        }).reverse();
    }, [txs, search, timeFilter, rangeStart, rangeEnd, accountFilter]);

    const { totalFilteredBalance, totalFilteredCredit, totalFilteredDebit, openingBalance } = useMemo(() => {
        let cred = 0, deb = 0;
        filteredTxs.forEach(t => {
            cred += (t.credit || 0);
            deb += (t.debit || 0);
        });

        let closingBal = 0;
        for (const t of txs) {
            if (!txPassesEndFilter(t) || !matchesAccount(t)) continue;
            closingBal = rowBalance(t);
            break;
        }

        let openBal = 0;
        if (timeFilter !== 'all') {
            const chronological = [...txs].reverse();
            for (const t of chronological) {
                if (!txBeforePeriod(t) || !matchesAccount(t)) continue;
                openBal = rowBalance(t);
            }
        }

        return {
            totalFilteredBalance: closingBal,
            totalFilteredCredit: cred,
            totalFilteredDebit: deb,
            openingBalance: openBal,
        };
    }, [filteredTxs, accountFilter, timeFilter, rangeStart, rangeEnd, txs]);



    const ledgerColumns = [
        { key: 'id', label: 'ID' },
        { key: 'date', label: 'Date' },
        { key: 'merchant', label: 'Merchant' },
        { key: 'credit', label: 'Credit', render: r => r.credit > 0 ? formatMoney(r.credit) : '-' },
        { key: 'debit', label: 'Debit', render: r => r.debit > 0 ? formatMoney(r.debit) : '-' },
        { key: 'balance', label: 'Balance', render: r => formatMoney(r.balance) }
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
                        <option value="last_month">Last Month</option>
                        <option value="month">This Month</option>
                        <option value="year">This Year</option>
                        <option value="custom">Custom Range...</option>
                    </select>

                    <select 
                        className="form-input" 
                        value={accountFilter} 
                        onChange={e => setAccountFilter(e.target.value)}
                        style={{ width: 'auto', backgroundColor: 'var(--bg-elevated)', cursor: 'pointer', paddingRight: '32px' }}
                    >
                        <option value="all">All Accounts</option>
                        <option value="Cash">Cash Only</option>
                        <option value="Bank">Bank Only</option>
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
                </div>
                
                <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
                    <button className="btn-action" onClick={() => setTransferModalOpen(true)} style={{ backgroundColor: 'var(--accent-blue-dim)', color: 'var(--accent-blue)', padding: '12px', borderRadius: '50%', width: '48px', height: '48px', justifyContent: 'center' }} title="Self Transfer">
                        <ArrowRightLeft size={24} />
                    </button>
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

                </div>
                
                <div className="desktop-only">
                    <table className="data-table">
                        <thead><tr><th>ID</th><th>Date</th><th>Merchant</th><th>Credit</th><th>Debit</th><th title="Combined cash + bank balance after this transaction">Balance</th><th></th></tr></thead>
                        <tbody>
                            {timeFilter !== 'all' && (
                                <tr style={{ backgroundColor: 'var(--bg-elevated)', borderBottom: '1px solid var(--border-color)' }}>
                                    <td colSpan="3" style={{ color: 'var(--text-secondary)', fontWeight: 600 }}>Opening Balance</td>
                                    <td></td>
                                    <td></td>
                                    <td style={{ fontWeight: 'bold' }}>{formatMoney(openingBalance)}</td>
                                    <td></td>
                                </tr>
                            )}
                            {filteredTxs.map((tx, i) => {
                                return (
                                    <tr key={i} className="hover-row">
                                        <td style={{ color: 'var(--text-secondary)' }}>{tx.id}</td>
                                        <td style={{ color: 'var(--text-secondary)', whiteSpace: 'nowrap' }}>{tx.date}</td>
                                        <td style={{ fontWeight: 600 }}>
                                            {tx.merchant} 
                                            <span style={{ marginLeft: '8px', fontSize: '12px', padding: '2px 6px', borderRadius: '4px', backgroundColor: 'var(--bg-default)', color: 'var(--text-secondary)', fontWeight: 'normal' }}>
                                                {tx.account === 'Bank' ? '🏦 Bank' : '💵 Cash'}
                                            </span>
                                        </td>
                                        <td style={{ color: 'var(--accent-green)', fontWeight: 600 }}>{tx.credit > 0 ? formatMoney(tx.credit) : '-'}</td>
                                        <td style={{ color: 'var(--accent-red)', fontWeight: 600 }}>{tx.debit > 0 ? formatMoney(tx.debit) : '-'}</td>
                                        <td style={{ fontWeight: 'bold' }}>{formatMoney(rowBalance(tx))}</td>
                                        <td style={{ display: 'flex', gap: '4px' }}>
                                            <button className="btn-action" onClick={(e) => { e.stopPropagation(); setEditTxn(tx); }} style={{ padding: '8px', color: 'var(--accent-teal)' }}>
                                                <Edit2 size={16} />
                                            </button>
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
                        <tfoot>
                                <tr style={{ backgroundColor: 'var(--bg-elevated)', borderTop: '2px solid var(--border-color)' }}>
                                    <td colSpan="3"></td>
                                    <td style={{ color: 'var(--accent-green)', fontWeight: 'bold' }}>{formatMoney(totalFilteredCredit)}</td>
                                    <td style={{ color: 'var(--accent-red)', fontWeight: 'bold' }}>{formatMoney(totalFilteredDebit)}</td>
                                    <td style={{ fontWeight: 'bold' }}>{formatMoney(totalFilteredBalance)}</td>
                                    <td></td>
                                </tr>
                            </tfoot>
                    </table>
                </div>

                <div className="mobile-only" style={{ padding: '0' }}>
                    {timeFilter !== 'all' && (
                        <div style={{ padding: '16px', backgroundColor: 'var(--bg-elevated)', borderBottom: '1px solid var(--border-color)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <span style={{ color: 'var(--text-secondary)', fontWeight: 600, fontSize: '14px' }}>Opening Balance</span>
                            <span style={{ fontSize: '15px', fontWeight: 'bold' }}>{formatMoney(openingBalance)}</span>
                        </div>
                    )}
                    {filteredTxs.map((tx, i) => (
                        <div key={i} style={{ borderBottom: '1px solid var(--border-color)' }}>
                            <div 
                                style={{ padding: '16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', cursor: 'pointer' }}
                                onClick={() => setExpandedTxn(expandedTxn === i ? null : i)}
                            >
                                <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                                    <span style={{ fontWeight: 600, fontSize: '15px' }}>
                                        {tx.merchant}
                                        <span style={{ marginLeft: '8px', fontSize: '12px', padding: '2px 6px', borderRadius: '4px', backgroundColor: 'var(--bg-default)', color: 'var(--text-secondary)', fontWeight: 'normal' }}>
                                            {tx.account === 'Bank' ? '🏦 Bank' : '💵 Cash'}
                                        </span>
                                    </span>
                                    <span style={{ color: 'var(--text-secondary)', fontSize: '13px' }}>ID: {tx.id}</span>
                                </div>
                                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                                    <span style={{ 
                                        fontWeight: 600, 
                                        color: tx.credit > 0 ? 'var(--accent-green)' : 'var(--accent-red)' 
                                    }}>
                                        {tx.credit > 0 ? formatSignedMoney(tx.credit, '+') : formatSignedMoney(tx.debit, '-')}
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
                                        <span style={{ fontWeight: 'bold' }}>{formatMoney(rowBalance(tx))}</span>
                                    </div>
                                    <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '8px', gap: '8px' }}>
                                        <button 
                                            className="btn-action" 
                                            onClick={(e) => { e.stopPropagation(); setEditTxn(tx); }}
                                            style={{ backgroundColor: 'var(--accent-teal-dim)', color: 'var(--accent-teal)', padding: '8px 16px', fontSize: '13px', borderRadius: '8px' }}
                                        >
                                            <Edit2 size={14} style={{ marginRight: '6px' }} /> Edit
                                        </button>
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
                        <div style={{ padding: '16px', backgroundColor: 'var(--bg-elevated)', display: 'flex', justifyContent: 'space-between', borderTop: '2px solid var(--border-color)', borderBottom: '1px solid var(--border-color)' }}>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                                <span style={{ color: 'var(--text-secondary)', fontSize: '13px' }}>Total Credits</span>
                                <span style={{ color: 'var(--accent-green)', fontWeight: 'bold' }}>{formatMoney(totalFilteredCredit)}</span>
                            </div>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', textAlign: 'center' }}>
                                <span style={{ color: 'var(--text-secondary)', fontSize: '13px' }}>Total Debits</span>
                                <span style={{ color: 'var(--accent-red)', fontWeight: 'bold' }}>{formatMoney(totalFilteredDebit)}</span>
                            </div>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', textAlign: 'right' }}>
                                <span style={{ color: 'var(--text-secondary)', fontSize: '13px' }}>Balance</span>
                                <span style={{ fontSize: '15px', fontWeight: 'bold' }}>{formatMoney(totalFilteredBalance)}</span>
                            </div>
                        </div>
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

            <EditTransactionModal
                isOpen={!!editTxn}
                onClose={() => setEditTxn(null)}
                onRefresh={loadTxs}
                transaction={editTxn}
                type="ledger"
                token={token}
            />

            <TransferModal
                isOpen={transferModalOpen}
                onClose={() => setTransferModalOpen(false)}
                onRefresh={loadTxs}
                token={token}
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
