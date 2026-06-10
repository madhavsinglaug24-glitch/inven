
import React, { useState } from 'react';
import { Shield } from 'lucide-react';
import { API_BASE } from '../api';

export const LoginView = ({ onLogin }) => {
    const [password, setPassword] = useState('');
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');

    const handleSubmit = async (e) => {
        e.preventDefault();
        setLoading(true); setError('');
        try {
            const res = await fetch(`${API_BASE}/dashboard/login`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ password }) });
            if (res.ok) {
                const data = await res.json();
                onLogin(data.token);
            } else setError('Invalid password');
        } catch (err) { setError('Login failed'); }
        setLoading(false);
    };

    return (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh', width: '100vw', backgroundColor: 'var(--bg-base)' }}>
            <div className="card" style={{ width: '400px', textAlign: 'center' }}>
                <Shield style={{ width: '48px', height: '48px', color: 'var(--accent-green)', marginBottom: '16px', display: 'inline-block' }} />
                <h2 style={{ marginBottom: '8px' }}>Manager Login</h2>
                <p style={{ color: 'var(--text-secondary)', marginBottom: '24px', fontSize: '14px' }}>Please enter your dashboard password.</p>
                <form onSubmit={handleSubmit}>
                    <input type="password" className="form-input" placeholder="Password" value={password} onChange={e => setPassword(e.target.value)} style={{ marginBottom: '16px' }} autoFocus />
                    {error && <div style={{ color: 'var(--accent-red)', marginBottom: '16px', fontSize: '13px' }}>{error}</div>}
                    <button type="submit" className="btn-action" style={{ width: '100%', justifyContent: 'center', backgroundColor: 'var(--bg-elevated)' }} disabled={loading}>
                        {loading ? 'Authenticating...' : 'Login'}
                    </button>
                </form>
            </div>
        </div>
    );
};
