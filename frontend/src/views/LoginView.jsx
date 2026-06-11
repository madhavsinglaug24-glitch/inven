import React, { useState } from 'react';
import { GoogleLogin } from '@react-oauth/google';

const API_BASE = import.meta.env.VITE_API_URL || '/api';

export const LoginView = ({ onLoginSuccess }) => {
    const [error, setError] = useState("");
    const [loading, setLoading] = useState(false);

    const handleSuccess = async (credentialResponse) => {
        setLoading(true);
        setError("");
        
        try {
            const res = await fetch(`${API_BASE}/auth/google`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ credential: credentialResponse.credential })
            });
            
            const data = await res.json();
            
            if (res.ok && data.token) {
                // Persistent login using localStorage
                localStorage.setItem('apiToken', data.token);
                localStorage.setItem('userEmail', data.email);
                onLoginSuccess(data.token);
            } else {
                setError(data.message || "Authentication failed. You may not be authorized.");
            }
        } catch (err) {
            setError("Network error connecting to server.");
        }
        
        setLoading(false);
    };

    const handleError = () => {
        setError("Google Login Failed. Please try again.");
    };

    return (
        <div style={{
            display: 'flex', flexDirection: 'column', alignItems: 'center', 
            justifyContent: 'center', height: '100vh', padding: '20px',
            backgroundColor: 'var(--bg-base)'
        }}>
            <div className="card" style={{ maxWidth: '400px', width: '100%', textAlign: 'center', padding: '40px 20px' }}>
                <h1 style={{ marginBottom: '10px', fontSize: '24px', color: 'var(--accent-teal)' }}>SDE Dashboard</h1>
                <p style={{ color: 'var(--text-secondary)', marginBottom: '30px' }}>
                    Sign in with your authorized Google account to access inventory and ledger management.
                </p>
                
                <div style={{ display: 'flex', justifyContent: 'center', minHeight: '40px' }}>
                    {loading ? (
                        <div className="spin" style={{ 
                            width: '30px', height: '30px', 
                            border: '3px solid var(--accent-teal-dim)', 
                            borderTopColor: 'var(--accent-teal)', 
                            borderRadius: '50%' 
                        }} />
                    ) : (
                        <GoogleLogin
                            onSuccess={handleSuccess}
                            onError={handleError}
                            theme="filled_blue"
                            shape="pill"
                            useOneTap
                        />
                    )}
                </div>
                
                {error && (
                    <div style={{ 
                        marginTop: '20px', padding: '12px', 
                        backgroundColor: 'var(--accent-red-dim)', 
                        color: 'var(--accent-red)', 
                        borderRadius: '8px', fontSize: '14px' 
                    }}>
                        {error}
                    </div>
                )}
            </div>
        </div>
    );
};
