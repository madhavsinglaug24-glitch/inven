import React, { useState, useEffect } from 'react';
import { X, Trash2, Plus } from 'lucide-react';
import { Modal } from './Modal';
import { API_BASE } from '../api';

export const ManageMerchantsModal = ({ isOpen, onClose, token }) => {
    const [merchants, setMerchants] = useState([]);
    const [loading, setLoading] = useState(true);
    const [newMerchant, setNewMerchant] = useState('');

    useEffect(() => {
        if (isOpen) {
            loadMerchants();
        }
    }, [isOpen]);

    const loadMerchants = async () => {
        setLoading(true);
        try {
            const res = await fetch(`${API_BASE}/merchants`, { headers: { 'Authorization': `Bearer ${token}` } });
            if (res.ok) {
                setMerchants(await res.json());
            }
        } finally {
            setLoading(false);
        }
    };

    const handleAdd = async (e) => {
        e.preventDefault();
        if (!newMerchant.trim()) return;
        
        try {
            const res = await fetch(`${API_BASE}/merchants`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
                body: JSON.stringify({ name: newMerchant.trim() })
            });
            if (res.ok) {
                setNewMerchant('');
                loadMerchants();
            } else {
                alert('Failed to add merchant');
            }
        } catch (err) {
            console.error(err);
        }
    };

    const handleDelete = async (id, name) => {
        if (!window.confirm(`Delete merchant "${name}"?`)) return;
        try {
            const res = await fetch(`${API_BASE}/merchants/${id}`, {
                method: 'DELETE',
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (res.ok) {
                loadMerchants();
            } else {
                alert('Failed to delete merchant');
            }
        } catch (err) {
            console.error(err);
        }
    };

    return (
        <Modal isOpen={isOpen} onClose={onClose} title="Manage Merchants">
            <form onSubmit={handleAdd} style={{ display: 'flex', gap: '8px', marginBottom: '24px' }}>
                <input 
                    type="text" 
                    className="form-input" 
                    placeholder="New merchant name..." 
                    value={newMerchant}
                    onChange={e => setNewMerchant(e.target.value)}
                    style={{ flex: 1 }}
                />
                <button type="submit" className="btn-action btn-credit" style={{ padding: '0 16px' }}>
                    <Plus size={18} /> Add
                </button>
            </form>

            <div style={{ maxHeight: '400px', overflowY: 'auto' }}>
                {loading ? (
                    <div style={{ textAlign: 'center', padding: '20px', color: 'var(--text-secondary)' }}>Loading...</div>
                ) : merchants.length === 0 ? (
                    <div style={{ textAlign: 'center', padding: '20px', color: 'var(--text-secondary)' }}>No merchants found.</div>
                ) : (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                        {merchants.map(m => (
                            <div key={m.merchant_id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '12px', backgroundColor: 'var(--bg-elevated)', borderRadius: '8px', border: '1px solid var(--border-color)' }}>
                                <span style={{ fontWeight: 500 }}>{m.name}</span>
                                <button 
                                    className="btn-action" 
                                    onClick={() => handleDelete(m.merchant_id, m.name)}
                                    style={{ padding: '8px', color: 'var(--accent-red)', background: 'transparent', border: 'none' }}
                                    title="Delete Merchant"
                                >
                                    <Trash2 size={16} />
                                </button>
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </Modal>
    );
};
