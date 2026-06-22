import React, { useState } from 'react';
import { ArrowRight, User, Lock } from 'lucide-react';
import { API_BASE } from '../api';

export const LoginView = ({ onLoginSuccess }) => {
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);

    const handleLogin = async (e) => {
        e.preventDefault();
        if (!username || !password) {
            setError("Please enter both username and password.");
            return;
        }

        setLoading(true);
        setError("");
        
        try {
            const res = await fetch(`${API_BASE}/auth/login`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, password })
            });
            
            const data = await res.json();
            
            if (res.ok && data.token) {
                // Persistent login using localStorage
                localStorage.setItem('apiToken', data.token);
                localStorage.setItem('userEmail', data.username); // reusing 'userEmail' key for backwards compat
                onLoginSuccess(data.token);
            } else {
                setError(data.message || "Invalid credentials.");
            }
        } catch (err) {
            setError("Network error connecting to server.");
        }
        
        setLoading(false);
    };

    return (
        <div style={{
            display: 'flex', flexDirection: 'column', alignItems: 'center', 
            justifyContent: 'center', height: '100vh', padding: '20px',
            backgroundColor: 'var(--bg-base)'
        }}>
            <div className="card" style={{ maxWidth: '400px', width: '100%', padding: '40px 30px' }}>
                <div style={{ display: 'flex', justifyContent: 'center', marginBottom: '20px' }}>
                    <img src="/sde-logo.svg" alt="Inven" style={{ width: '60px', height: '60px', borderRadius: '16px' }} />
                </div>
                
                <h1 style={{ textAlign: 'center', marginBottom: '10px', fontSize: '24px', color: 'var(--text-primary)' }}>
                    Admin Login
                </h1>
                <p style={{ textAlign: 'center', color: 'var(--text-secondary)', marginBottom: '30px', fontSize: '14px', lineHeight: '1.5' }}>
                    Please enter your username and password to access the dashboard.
                </p>
                
                {error && (
                    <div style={{ 
                        marginBottom: '20px', padding: '12px', 
                        backgroundColor: 'var(--accent-red-dim)', 
                        color: 'var(--accent-red)', 
                        borderRadius: '8px', fontSize: '14px' 
                    }}>
                        {error}
                    </div>
                )}

                <form onSubmit={handleLogin} style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                    <div>
                        <label style={{ display: 'block', marginBottom: '8px', fontSize: '14px', color: 'var(--text-secondary)' }}>Username</label>
                        <div style={{ position: 'relative' }}>
                            <div style={{ position: 'absolute', left: '14px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-secondary)' }}>
                                <User size={18} />
                            </div>
                            <input 
                                type="text" 
                                placeholder="Username" 
                                value={username}
                                onChange={(e) => setUsername(e.target.value)}
                                style={{ 
                                    width: '100%', padding: '12px 16px 12px 42px', borderRadius: '8px',
                                    border: '1px solid var(--border-color)', backgroundColor: 'var(--bg-elevated)',
                                    color: 'var(--text-primary)', fontSize: '16px', boxSizing: 'border-box'
                                }}
                                autoFocus
                            />
                        </div>
                    </div>
                    <div>
                        <label style={{ display: 'block', marginBottom: '8px', fontSize: '14px', color: 'var(--text-secondary)' }}>Password</label>
                        <div style={{ position: 'relative' }}>
                            <div style={{ position: 'absolute', left: '14px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-secondary)' }}>
                                <Lock size={18} />
                            </div>
                            <input 
                                type="password" 
                                placeholder="••••••••" 
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                style={{ 
                                    width: '100%', padding: '12px 16px 12px 42px', borderRadius: '8px',
                                    border: '1px solid var(--border-color)', backgroundColor: 'var(--bg-elevated)',
                                    color: 'var(--text-primary)', fontSize: '16px', boxSizing: 'border-box'
                                }}
                            />
                        </div>
                    </div>
                    <button 
                        type="submit" 
                        disabled={loading || !username || !password}
                        style={{ 
                            width: '100%', padding: '14px', borderRadius: '8px',
                            backgroundColor: 'var(--accent-teal)', color: '#fff',
                            border: 'none', fontSize: '16px', fontWeight: '600',
                            cursor: (loading || !username || !password) ? 'not-allowed' : 'pointer',
                            opacity: (loading || !username || !password) ? 0.7 : 1,
                            display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '8px',
                            marginTop: '10px'
                        }}
                    >
                        {loading ? <div className="spin" style={{ width: '20px', height: '20px', border: '2px solid rgba(255,255,255,0.3)', borderTopColor: '#fff', borderRadius: '50%' }} /> : 'Sign In'}
                        {!loading && <ArrowRight size={18} />}
                    </button>
                </form>
            </div>
        </div>
    );
};
