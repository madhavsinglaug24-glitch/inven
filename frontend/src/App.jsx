
import React, { useState, useEffect } from 'react';
import { PieChart, CheckSquare, Package, BookOpen, Sun, Moon, LogOut, Menu, Camera, Printer } from 'lucide-react';

import { LoginView } from './views/LoginView';
import { OverviewTab } from './views/OverviewTab';
import { InventoryView } from './views/InventoryView';
import { LedgerView } from './views/LedgerView';
import { HistoryView } from './views/HistoryView';
import { ScannerModal } from './components/ScannerModal';

const DraggableFAB = ({ onClick }) => {
    const [pos, setPos] = useState({ bottom: 80, right: 24 });
    const dragRef = React.useRef(null);
    const startPos = React.useRef(null);

    const handleTouchStart = (e) => {
        const touch = e.touches[0];
        startPos.current = { x: touch.clientX, y: touch.clientY, bottom: pos.bottom, right: pos.right, isDragging: false };
    };

    const handleTouchMove = (e) => {
        if (!startPos.current) return;
        const touch = e.touches[0];
        const dx = startPos.current.x - touch.clientX;
        const dy = startPos.current.y - touch.clientY;
        if (Math.abs(dx) > 5 || Math.abs(dy) > 5) startPos.current.isDragging = true;
        setPos({ right: startPos.current.right + dx, bottom: startPos.current.bottom + dy });
    };

    const handleTouchEnd = (e) => {
        if (startPos.current && !startPos.current.isDragging) onClick();
        startPos.current = null;
    };

    // For mouse support on desktop
    const handleMouseDown = (e) => {
        startPos.current = { x: e.clientX, y: e.clientY, bottom: pos.bottom, right: pos.right, isDragging: false };
        const handleMouseMove = (me) => {
            if (!startPos.current) return;
            const dx = startPos.current.x - me.clientX;
            const dy = startPos.current.y - me.clientY;
            if (Math.abs(dx) > 5 || Math.abs(dy) > 5) startPos.current.isDragging = true;
            setPos({ right: startPos.current.right + dx, bottom: startPos.current.bottom + dy });
        };
        const handleMouseUp = () => {
            document.removeEventListener('mousemove', handleMouseMove);
            document.removeEventListener('mouseup', handleMouseUp);
            if (startPos.current && !startPos.current.isDragging) onClick();
            startPos.current = null;
        };
        document.addEventListener('mousemove', handleMouseMove);
        document.addEventListener('mouseup', handleMouseUp);
    };

    return (
        <button 
            ref={dragRef} className="fab-camera"
            onTouchStart={handleTouchStart} onTouchMove={handleTouchMove} onTouchEnd={handleTouchEnd}
            onMouseDown={handleMouseDown}
            style={{ right: `${pos.right}px`, bottom: `${pos.bottom}px`, touchAction: 'none', position: 'fixed' }}
        >
            <Camera size={28} />
        </button>
    );
};

function App() {
    const [token, setToken] = useState('dummy_token');
    const [mode, setMode] = useState('overview');
    const [theme, setTheme] = useState(localStorage.getItem('theme') || 'dark');
    const [sidebarOpen, setSidebarOpen] = useState(true);
    const [scannerOpen, setScannerOpen] = useState(false);

    useEffect(() => {
        document.body.className = theme === 'light' ? 'light-theme' : '';
        localStorage.setItem('theme', theme);
    }, [theme]);

    return (
        <>
            <div className="mobile-header">
                <span className="brand-name" style={{ fontFamily: 'Inter, sans-serif', fontWeight: 800, letterSpacing: '3px', fontSize: '22px', textTransform: 'uppercase' }}>SDE</span>
                <button className="btn-action" onClick={() => setTheme(t => t === 'dark' ? 'light' : 'dark')} style={{ padding: '8px' }}>
                    {theme === 'dark' ? <Sun size={20} /> : <Moon size={20} />}
                </button>
            </div>

            <aside className={`sidebar ${!sidebarOpen ? 'collapsed' : ''}`}>
                <div className="brand" style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <button onClick={() => setSidebarOpen(!sidebarOpen)} style={{ background: 'transparent', border: 'none', color: 'var(--text-primary)', cursor: 'pointer', padding: 0, display: 'flex', alignItems: 'center' }}>
                        <Menu style={{ width: '28px', height: '28px' }} />
                    </button>
                    <span className="brand-name" style={{ fontFamily: 'Inter, sans-serif', fontWeight: 800, letterSpacing: '3px', fontSize: '24px', textTransform: 'uppercase' }}>SDE</span>
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

            <DraggableFAB onClick={() => setScannerOpen(true)} />

            <ScannerModal token={token} isOpen={scannerOpen} onClose={() => setScannerOpen(false)} />
        </>
    );
}

export default App;
