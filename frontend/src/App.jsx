import React, { useState, useEffect } from 'react';
import { PieChart, Package, BookOpen, Sun, Moon, Menu, Camera, Printer, Plus, X, Pencil } from 'lucide-react';

import { OverviewTab } from './views/OverviewTab';
import { InventoryView } from './views/InventoryView';
import { LedgerView } from './views/LedgerView';
import { HistoryView } from './views/HistoryView';
import { ScannerModal } from './components/ScannerModal';

const FABMenu = ({ onScan, onManual }) => {
    const [open, setOpen] = useState(false);
    
    return (
        <>
            {open && <div className="fab-menu-overlay" onClick={() => setOpen(false)} />}
            
            {open && (
                <div className="fab-menu" style={{ bottom: '92px', right: '24px' }}>
                    <div className="fab-menu-item" onClick={() => { setOpen(false); onScan(); }}>
                        <span>Scan Receipt</span>
                        <button style={{ backgroundColor: 'var(--accent-green)', color: '#fff' }}>
                            <Camera size={22} />
                        </button>
                    </div>
                    <div className="fab-menu-item" onClick={() => { setOpen(false); onManual(); }}>
                        <span>Enter Manually</span>
                        <button style={{ backgroundColor: 'var(--accent-blue)', color: '#fff' }}>
                            <Pencil size={22} />
                        </button>
                    </div>
                </div>
            )}
            
            <button 
                className="fab-camera"
                onClick={() => setOpen(!open)}
                style={{ 
                    position: 'fixed', right: '24px', bottom: '24px',
                    transform: open ? 'rotate(45deg)' : 'none',
                    transition: 'transform 0.2s ease'
                }}
            >
                <Plus size={28} />
            </button>
        </>
    );
};

function App() {
    const [token, setToken] = useState('dummy_token');
    const [mode, setMode] = useState('overview');
    const [theme, setTheme] = useState(localStorage.getItem('theme') || 'dark');
    const [sidebarOpen, setSidebarOpen] = useState(true);
    const [scannerOpen, setScannerOpen] = useState(false);
    const [scannerMode, setScannerMode] = useState('scan'); // 'scan' or 'manual'
    const [inventoryItems, setInventoryItems] = useState([]);

    const loadInventoryItems = async () => {
        try {
            const res = await fetch(`/api/inventory`, { headers: { 'Authorization': `Bearer ${token}` } });
            if (res.ok) setInventoryItems(await res.json());
        } catch (e) { console.error(e); }
    };

    useEffect(() => {
        loadInventoryItems();
    }, [token]);

    useEffect(() => {
        document.body.className = theme === 'light' ? 'light-theme' : '';
        localStorage.setItem('theme', theme);
    }, [theme]);

    return (
        <>
            <div className="mobile-header">
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <img src="/sde-logo.svg" alt="SDE Logo" style={{ height: '32px', borderRadius: '6px' }} />
                    <span className="brand-name" style={{ fontFamily: 'Inter, sans-serif', fontWeight: 800, letterSpacing: '3px', fontSize: '22px', textTransform: 'uppercase' }}>SDE</span>
                </div>
                <button className="btn-action" onClick={() => setTheme(t => t === 'dark' ? 'light' : 'dark')} style={{ padding: '8px' }}>
                    {theme === 'dark' ? <Sun size={20} /> : <Moon size={20} />}
                </button>
            </div>

            <aside className={`sidebar ${!sidebarOpen ? 'collapsed' : ''}`}>
                <div className="brand" style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <button onClick={() => setSidebarOpen(!sidebarOpen)} style={{ background: 'transparent', border: 'none', color: 'var(--text-primary)', cursor: 'pointer', padding: 0, display: 'flex', alignItems: 'center' }}>
                        <Menu style={{ width: '28px', height: '28px' }} />
                    </button>
                </div>
                <nav>
                    <ul className="nav-menu">
                        <li className={`nav-item ${mode === 'overview' ? 'active' : ''}`} onClick={() => setMode('overview')}>
                            <PieChart size={20} /> <span className="nav-text">Overview</span>
                        </li>
                        <li className={`nav-item ${mode === 'inventory' ? 'active' : ''}`} onClick={() => setMode('inventory')}>
                            <Package size={20} /> <span className="nav-text">Inventory</span>
                        </li>
                        <li className={`nav-item ${mode === 'ledger' ? 'active' : ''}`} onClick={() => setMode('ledger')}>
                            <BookOpen size={20} /> <span className="nav-text">Ledger</span>
                        </li>
                        <li className={`nav-item ${mode === 'history' ? 'active' : ''}`} onClick={() => setMode('history')}>
                            <Printer size={20} /> <span className="nav-text">Print</span>
                        </li>
                    </ul>
                </nav>
                <div className="sidebar-footer" style={{ marginTop: 'auto', paddingTop: '24px', borderTop: '1px solid var(--border-color)', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    <button className="btn-action" onClick={() => setTheme(t => t === 'dark' ? 'light' : 'dark')} style={{ width: '100%', justifyContent: 'center' }}>
                        {theme === 'dark' ? <Sun size={20} /> : <Moon size={20} />}
                        <span className="nav-text" style={{ marginLeft: '8px' }}>Toggle Theme</span>
                    </button>
                </div>
            </aside>

            <main className="main-content">
                <div style={{ display: mode === 'overview' ? 'block' : 'none' }}>
                    <OverviewTab token={token} onNavigate={setMode} />
                </div>
                <div style={{ display: mode === 'inventory' ? 'block' : 'none' }}>
                    <InventoryView token={token} />
                </div>
                <div style={{ display: mode === 'ledger' ? 'block' : 'none' }}>
                    <LedgerView token={token} />
                </div>
                <div style={{ display: mode === 'history' ? 'block' : 'none' }}>
                    <HistoryView token={token} />
                </div>
            </main>

            <FABMenu 
                onScan={() => { setScannerMode('scan'); setScannerOpen(true); }} 
                onManual={() => { setScannerMode('manual'); setScannerOpen(true); }} 
            />

            <ScannerModal token={token} isOpen={scannerOpen} onClose={() => setScannerOpen(false)} items={inventoryItems} onRefresh={loadInventoryItems} initialMode={scannerMode} />
        </>
    );
}

export default App;
