
import React, { useState, useRef } from 'react';
import { Modal } from './Modal';
import { Upload, Camera, FileText } from 'lucide-react';
import { API_BASE } from '../api';

export const ScannerModal = ({ isOpen, onClose, token }) => {
    const [file, setFile] = useState(null);
    const [preview, setPreview] = useState(null);
    const [loading, setLoading] = useState(false);
    const [result, setResult] = useState(null);
    const [error, setError] = useState('');
    const fileInput = useRef(null);

    const handleFile = (e) => {
        const f = e.target.files[0];
        if (f) {
            setFile(f);
            setPreview(URL.createObjectURL(f));
            setResult(null);
            setError('');
        }
    };

    const scan = async () => {
        if (!file) return;
        setLoading(true);
        setError('');
        try {
            const fd = new FormData();
            fd.append('receipt', file);
            const res = await fetch(`${API_BASE}/scan_receipt`, { 
                method: 'POST', 
                body: fd,
                headers: { 'Authorization': `Bearer ${token}` }
            });
            const data = await res.json();
            if (res.ok) setResult(data);
            else setError(data.error || 'Scan failed');
        } catch (e) { setError('Network error'); }
        setLoading(false);
    };

    return (
        <Modal isOpen={isOpen} onClose={() => { onClose(); setFile(null); setPreview(null); setResult(null); setError(''); }} title="Scan Receipt">
            {!preview ? (
                <div 
                    onClick={() => fileInput.current?.click()}
                    style={{ border: '2px dashed var(--border-color)', borderRadius: '12px', padding: '40px', textAlign: 'center', cursor: 'pointer', transition: 'border-color 0.2s' }}
                    onMouseOver={e => e.currentTarget.style.borderColor = 'var(--accent-green)'}
                    onMouseOut={e => e.currentTarget.style.borderColor = 'var(--border-color)'}
                >
                    <input type="file" ref={fileInput} onChange={handleFile} accept="image/*" style={{ display: 'none' }} />
                    <Camera size={48} style={{ color: 'var(--text-secondary)', marginBottom: '16px' }} />
                    <h3 style={{ marginBottom: '8px' }}>Upload Receipt</h3>
                    <p style={{ color: 'var(--text-secondary)', fontSize: '14px' }}>Click to browse or take a photo</p>
                </div>
            ) : (
                <div>
                    <img src={preview} alt="Receipt" style={{ width: '100%', maxHeight: '300px', objectFit: 'contain', borderRadius: '8px', marginBottom: '16px', backgroundColor: '#000' }} />
                    
                    {error && <div style={{ color: 'var(--accent-red)', marginBottom: '16px', fontSize: '14px', textAlign: 'center' }}>{error}</div>}
                    
                    {result && (
                        <div style={{ backgroundColor: 'var(--bg-elevated)', padding: '16px', borderRadius: '8px', marginBottom: '16px', border: '1px solid var(--border-color)' }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                                <span style={{ color: 'var(--text-secondary)' }}>Merchant</span>
                                <span style={{ fontWeight: 600 }}>{result.merchant}</span>
                            </div>
                            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                                <span style={{ color: 'var(--text-secondary)' }}>Amount</span>
                                <span style={{ color: 'var(--accent-green)', fontWeight: 600 }}>₹{result.amount}</span>
                            </div>
                        </div>
                    )}

                    <div style={{ display: 'flex', gap: '12px' }}>
                        <button className="btn-action" style={{ flex: 1, justifyContent: 'center' }} onClick={() => { setFile(null); setPreview(null); setResult(null); setError(''); }}>
                            Retake
                        </button>
                        {!result && (
                            <button className="btn-action btn-credit" style={{ flex: 2, justifyContent: 'center' }} onClick={scan} disabled={loading}>
                                {loading ? 'Scanning...' : 'Extract Data'}
                            </button>
                        )}
                        {result && (
                            <button className="btn-action btn-credit" style={{ flex: 2, justifyContent: 'center' }} onClick={() => {
                                // For now, just close. In real app, pass this to a ledger modal.
                                onClose();
                            }}>
                                Save Transaction
                            </button>
                        )}
                    </div>
                </div>
            )}
        </Modal>
    );
};
