
import React, { useState, useEffect } from 'react';
import { Database } from 'lucide-react';
import { API_BASE } from '../api';

export const OverviewTab = ({ token, onNavigate }) => {
    const [stats, setStats] = useState(null);
    const [summary, setSummary] = useState(null);
    
    useEffect(() => {
        const fetchStats = async () => {
            const statsRes = await fetch(`${API_BASE}/stats`, { headers: { 'Authorization': `Bearer ${token}` } });
            if (statsRes.status === 401) {
                localStorage.removeItem('apiToken');
                return window.location.reload();
            }
            if (statsRes.ok) setStats(await statsRes.json());
            
            const summaryRes = await fetch(`${API_BASE}/summary`, { headers: { 'Authorization': `Bearer ${token}` } });
            if (summaryRes.ok) setSummary(await summaryRes.json());
        };
        fetchStats();
    }, [token]);

    if (!stats || !summary || summary.balance === undefined) {
        if (summary && summary.message === "Unauthorized") {
            localStorage.removeItem('apiToken');
            window.location.reload();
        }
        return <div style={{ color: 'var(--text-secondary)' }}>Loading overview...</div>;
    }

    return (
        <div className="fade-in">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
                <h1 className="page-title">Overview</h1>
            </div>
            
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '24px', marginBottom: '24px' }}>
                <div className="card hover-card" style={{ borderTop: '4px solid var(--text-secondary)', cursor: 'pointer' }} onClick={() => onNavigate('ledger')}>
                    <div className="metric-label">Total Cash Balance</div>
                    <div className="metric-value">₹{summary.balance.toLocaleString()}</div>
                </div>
                <div className="card hover-card" style={{ borderTop: '4px solid var(--accent-teal)', cursor: 'pointer' }} onClick={() => onNavigate('ledger')}>
                    <div className="metric-label">Total Cash IN</div>
                    <div className="metric-value" style={{ color: 'var(--accent-green)' }}>₹{summary.income.toLocaleString()}</div>
                </div>
                <div className="card hover-card" style={{ borderTop: '4px solid var(--accent-red)', cursor: 'pointer' }} onClick={() => onNavigate('ledger')}>
                    <div className="metric-label">Total Cash OUT</div>
                    <div className="metric-value" style={{ color: 'var(--accent-red)' }}>₹{summary.expense.toLocaleString()}</div>
                </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '24px' }}>
                <div className="card hover-card" style={{ borderTop: '4px solid var(--text-secondary)', cursor: 'pointer' }} onClick={() => onNavigate('inventory')}>
                    <div className="metric-label">Total Inventory Items</div>
                    <div className="metric-value">{stats.total_items}</div>
                </div>
                <div className="card hover-card" style={{ borderTop: '4px solid var(--accent-red)', cursor: 'pointer' }} onClick={() => onNavigate('inventory')}>
                    <div className="metric-label">Low Stock Alerts</div>
                    <div className="metric-value" style={{ color: stats.low_stock_count > 0 ? 'var(--accent-red)' : '' }}>{stats.low_stock_count}</div>
                </div>
            </div>
        </div>
    );
};
