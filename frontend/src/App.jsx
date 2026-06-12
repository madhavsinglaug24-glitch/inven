import React, { useState, useEffect } from 'react';
import { PieChart, Package, BookOpen, Sun, Moon, Menu, Camera, Plus, X, Pencil, LogOut, Download } from 'lucide-react';
import io from 'socket.io-client';

import { LoginView } from './views/LoginView';

import { OverviewTab } from './views/OverviewTab';
import { InventoryView } from './views/InventoryView';
import { LedgerView } from './views/LedgerView';
import { ExportView } from './views/ExportView';
import { ScannerModal } from './components/ScannerModal';

const FABMenu = ({ onScan, onManual }) => {
    const [open, setOpen] = useState(false);
    
    return (
        <>
            {open && <div className="fab-menu-overlay" onClick={() => setOpen(false)} />}
            
            {open && (
                <div className="fab-menu">
                    <div className="fab-menu-item" onClick={() => { setOpen(false); onScan(); }}>
                        <span>Scan Receipt</span>
                        <button style={{ backgroundColor: 'var(--accent-teal)', color: '#fff' }}>
                            <Camera size={22} />
                        </button>
                    </div>
                    <div className="fab-menu-item" onClick={() => { setOpen(false); onManual(); }}>
                        <span>Enter Manually</span>
                        <button style={{ backgroundColor: 'var(--accent-teal)', color: '#fff' }}>
                            <Pencil size={22} />
                        </button>
                    </div>
                </div>
            )}
            
            <button 
                className="fab-camera"
                onClick={() => setOpen(!open)}
                style={{ 
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
    const [token, setToken] = useState(localStorage.getItem('apiToken') || null);
    const [userEmail, setUserEmail] = useState(localStorage.getItem('userEmail') || '');
    const [mode, setMode] = useState('overview');
    const [theme, setTheme] = useState(localStorage.getItem('theme') || 'dark');
    const [sidebarOpen, setSidebarOpen] = useState(true);
    const [scannerOpen, setScannerOpen] = useState(false);
    const [scannerMode, setScannerMode] = useState('scan'); // 'scan' or 'manual'
    const [inventoryItems, setInventoryItems] = useState([]);
    const [refreshTrigger, setRefreshTrigger] = useState(0);

    const loadInventoryItems = async () => {
        try {
            const res = await fetch(`/api/inventory`, { headers: { 'Authorization': `Bearer ${token}` } });
            if (res.ok) setInventoryItems(await res.json());
        } catch (e) { console.error(e); }
    };

    useEffect(() => {
        loadInventoryItems();
        
        // Initialize Socket.IO connection for real-time updates
        const socket = io(window.location.origin, {
            path: '/socket.io'
        });
        
        socket.on('connect', () => {
            console.log('Connected to real-time sync server');
        });
        
        socket.on('inventory_updated', (data) => {
            console.log('Real-time update received:', data.message);
            loadInventoryItems(); // Instantly refresh data when someone else edits it!
            setRefreshTrigger(prev => prev + 1);
        });
        
        return () => {
            socket.disconnect();
        };
    }, [token]);

    const handleLogout = () => {
        localStorage.removeItem('apiToken');
        localStorage.removeItem('userEmail');
        setToken(null);
        setUserEmail('');
    };

    useEffect(() => {
        document.body.className = theme === 'light' ? 'light-theme' : '';
        localStorage.setItem('theme', theme);
    }, [theme]);

    if (!token) {
        return (
            <LoginView onLoginSuccess={(newToken) => {
                setToken(newToken);
                setUserEmail(localStorage.getItem('userEmail'));
            }} />
        );
    }

    return (
        <div id="root">
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
                        <li className={`nav-item ${mode === 'export' ? 'active' : ''}`} onClick={() => setMode('export')}>
                            <Download size={20} /> <span className="nav-text">Export</span>
                        </li>
                        <li className="nav-item mobile-nav-logout" onClick={handleLogout} style={{ color: 'var(--accent-red)' }}>
                            <LogOut size={20} /> <span className="nav-text">Log Out</span>
                        </li>
                    </ul>
                </nav>
                <div className="sidebar-footer" style={{ width: '100%', marginTop: 'auto' }}>
                    {userEmail && (
                        <div className="nav-text" style={{ marginBottom: '15px', fontSize: '12px', color: 'var(--text-secondary)', wordBreak: 'break-all' }}>
                            Logged in as:<br/><strong>{userEmail}</strong>
                        </div>
                    )}
                    <button 
                        className="btn-action" 
                        onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
                        style={{ marginBottom: '10px', width: '100%', justifyContent: 'center' }}
                    >
                        {theme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}
                        <span className="nav-text">{theme === 'dark' ? 'Light Mode' : 'Dark Mode'}</span>
                    </button>
                    <button 
                        className="btn-action" 
                        onClick={handleLogout}
                        style={{ borderColor: 'var(--accent-red)', color: 'var(--accent-red)', width: '100%', justifyContent: 'center' }}
                    >
                        <LogOut size={18} />
                        <span className="nav-text">Sign Out</span>
                    </button>
                </div>
            </aside>

            <main className="main-content">
                <div style={{ display: mode === 'overview' ? 'block' : 'none' }}>
                    <OverviewTab token={token} onNavigate={setMode} refreshTrigger={refreshTrigger} />
                </div>
                <div style={{ display: mode === 'inventory' ? 'block' : 'none' }}>
                    <InventoryView token={token} refreshTrigger={refreshTrigger} />
                </div>
                <div style={{ display: mode === 'ledger' ? 'block' : 'none' }}>
                    <LedgerView token={token} refreshTrigger={refreshTrigger} />
                </div>
                <div style={{ display: mode === 'export' ? 'block' : 'none' }}>
                    <ExportView token={token} refreshTrigger={refreshTrigger} />
                </div>
            </main>

            <FABMenu 
                onScan={() => { setScannerMode('scan'); setScannerOpen(true); }} 
                onManual={() => { setScannerMode('manual'); setScannerOpen(true); }} 
            />

            <ScannerModal 
                isOpen={scannerOpen} 
                onClose={() => setScannerOpen(false)} 
                mode={scannerMode}
                token={token} 
                onRefresh={loadInventoryItems}
                items={inventoryItems}
            />
        </div>
    );
}

export default App;
