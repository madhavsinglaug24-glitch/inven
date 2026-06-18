import React, { useState, useEffect } from 'react';
import { Database } from 'lucide-react';
import { API_BASE } from '../api';
import { formatMoney } from '../utils/money';

export const OverviewTab = ({ token, onNavigate, refreshTrigger }) => {
    const [stats, setStats] = useState(null);
    const [summary, setSummary] = useState(null);
    
    useEffect(() => {
        const fetchStats = async () => {
            const [statsRes, summaryRes] = await Promise.all([
                fetch(`${API_BASE}/stats`, { headers: { 'Authorization': `Bearer ${token}` } }),
                fetch(`${API_BASE}/summary`, { headers: { 'Authorization': `Bearer ${token}` } })
            ]);
            
            if (statsRes.status === 401 || summaryRes.status === 401) {
                localStorage.removeItem('apiToken');
                return window.location.reload();
            }
            if (statsRes.ok) setStats(await statsRes.json());
            if (summaryRes.ok) setSummary(await summaryRes.json());
        };
        fetchStats();
    }, [token, refreshTrigger]);

    if (!stats || !summary || summary.balance === undefined) {
        if (summary && summary.message === "Unauthorized") {
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

    return (
        <div className="fade-in">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
                <h1 className="page-title">Overview</h1>
            </div>
            
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '24px', marginBottom: '24px' }}>
                <div className="card hover-card card-gradient bg-grad-purple" style={{ cursor: 'pointer' }} onClick={() => onNavigate('ledger')}>
                    <div className="metric-label">Cash Balance (All Time)</div>
                    <div className="metric-value">{formatMoney(summary.cash_balance ?? summary.balance ?? 0)}</div>
                </div>
                <div className="card hover-card card-gradient bg-grad-blue" style={{ cursor: 'pointer' }} onClick={() => onNavigate('ledger')}>
                    <div className="metric-label">Bank Balance (All Time)</div>
                    <div className="metric-value">{formatMoney(summary.bank_balance ?? 0)}</div>
                </div>
                <div className="card hover-card card-gradient bg-grad-green" style={{ cursor: 'pointer' }} onClick={() => onNavigate('ledger')}>
                    <div className="metric-label">Total Cash IN (All Time)</div>
                    <div className="metric-value">{formatMoney(summary.income ?? 0)}</div>
                </div>
                <div className="card hover-card card-gradient bg-grad-red" style={{ cursor: 'pointer' }} onClick={() => onNavigate('ledger')}>
                    <div className="metric-label">Total Cash OUT (All Time)</div>
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
