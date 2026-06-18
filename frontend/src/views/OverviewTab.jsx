import React, { useState, useEffect, useMemo } from 'react';
import { API_BASE } from '../api';
import { formatMoney } from '../utils/money';
import { getFilterRange } from '../utils/dateFilters';

export const OverviewTab = ({ token, onNavigate, refreshTrigger }) => {
    const [stats, setStats] = useState(null);
    const [summary, setSummary] = useState(null);
    const [timeFilter, setTimeFilter] = useState('all');
    const [customStart, setCustomStart] = useState('');
    const [customEnd, setCustomEnd] = useState('');

    const { start, end, label: periodLabel } = useMemo(
        () => getFilterRange(timeFilter, customStart, customEnd),
        [timeFilter, customStart, customEnd]
    );

    useEffect(() => {
        const fetchStats = async () => {
            const params = new URLSearchParams();
            if (start) params.set('start', start);
            if (end) params.set('end', end);
            const summaryQuery = params.toString() ? `?${params.toString()}` : '';

            const [statsRes, summaryRes] = await Promise.all([
                fetch(`${API_BASE}/stats`, { headers: { 'Authorization': `Bearer ${token}` } }),
                fetch(`${API_BASE}/summary${summaryQuery}`, { headers: { 'Authorization': `Bearer ${token}` } }),
            ]);

            if (statsRes.status === 401 || summaryRes.status === 401) {
                localStorage.removeItem('apiToken');
                return window.location.reload();
            }
            if (statsRes.ok) setStats(await statsRes.json());
            if (summaryRes.ok) setSummary(await summaryRes.json());
        };
        fetchStats();
    }, [token, refreshTrigger, start, end]);

    if (!stats || !summary || summary.balance === undefined) {
        if (summary && summary.message === 'Unauthorized') {
            localStorage.removeItem('apiToken');
            window.location.reload();
        }
        return (
            <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '60vh', color: 'var(--text-secondary)' }}>
                <div className="spin" style={{ width: '24px', height: '24px', border: '3px solid var(--accent-green)', borderTopColor: 'transparent', borderRadius: '50%', marginRight: '12px' }}></div>
                <span style={{ fontSize: '16px', fontWeight: 500 }}>Loading overview...</span>
            </div>
        );
    }

    const totalCash = summary.balance ?? 0;
    const cashPart = summary.cash_balance ?? 0;
    const bankPart = summary.bank_balance ?? 0;

    return (
        <div className="fade-in">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px', flexWrap: 'wrap', gap: '16px' }}>
                <h1 className="page-title">Overview</h1>
                <div style={{ display: 'flex', gap: '12px', alignItems: 'center', flexWrap: 'wrap' }}>
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
                        <>
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
                        </>
                    )}
                </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '24px', marginBottom: '24px' }}>
                <div className="card hover-card card-gradient bg-grad-purple" style={{ cursor: 'pointer' }} onClick={() => onNavigate('ledger')}>
                    <div className="metric-label">Total Cash ({periodLabel})</div>
                    <div className="metric-value">{formatMoney(totalCash)}</div>
                    <div style={{ marginTop: '8px', fontSize: '13px', color: 'rgba(255,255,255,0.75)' }}>
                        Cash {formatMoney(cashPart)} · Bank {formatMoney(bankPart)}
                    </div>
                </div>
                <div className="card hover-card card-gradient bg-grad-green" style={{ cursor: 'pointer' }} onClick={() => onNavigate('ledger')}>
                    <div className="metric-label">Cash IN ({periodLabel})</div>
                    <div className="metric-value">{formatMoney(summary.income ?? 0)}</div>
                </div>
                <div className="card hover-card card-gradient bg-grad-red" style={{ cursor: 'pointer' }} onClick={() => onNavigate('ledger')}>
                    <div className="metric-label">Cash OUT ({periodLabel})</div>
                    <div className="metric-value">{formatMoney(summary.expense ?? 0)}</div>
                </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '24px' }}>
                <div className="card hover-card card-gradient bg-grad-blue" style={{ cursor: 'pointer' }} onClick={() => onNavigate('inventory')}>
                    <div className="metric-label">Total Inventory Items</div>
                    <div className="metric-value">{stats.total_items}</div>
                </div>
                <div className="card hover-card card-gradient bg-grad-red" style={{ cursor: 'pointer' }} onClick={() => onNavigate('inventory')}>
                    <div className="metric-label">Low Stock Alerts</div>
                    <div className="metric-value">{stats.low_stock_count}</div>
                </div>
            </div>
        </div>
    );
};
