import React, { useState, useEffect } from 'react';
import { X } from 'lucide-react';
import { API_BASE } from '../api';

export const EditTransactionModal = ({ isOpen, onClose, onRefresh, transaction, type, token }) => {
    const [formData, setFormData] = useState({});
    const [loading, setLoading] = useState(false);

    useEffect(() => {
        if (transaction) {
            if (type === 'history') {
                setFormData({
                    bill_no: transaction.bill_no || '',
                    contact_name: transaction.contact_name || '',
                    comment: transaction.comment || '',
                    quantity: transaction.quantity || 0,
                    unit_price: transaction.unit_price || 0
                });
            } else {
                setFormData({
                    merchant: transaction.merchant || '',
                    comment: transaction.comment || '',
                    amount: transaction.credit > 0 ? transaction.credit : transaction.debit
                });
            }
        }
    }, [transaction, type]);

    if (!isOpen || !transaction) return null;

    const handleSubmit = async (e) => {
        e.preventDefault();
        setLoading(true);
        try {
            const url = type === 'history' ? `${API_BASE}/history/${transaction.id}` : `${API_BASE}/transactions/${transaction.id}`;
            const res = await fetch(url, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
                body: JSON.stringify(formData)
            });

            if (res.ok) {
                onRefresh();
                onClose();
            } else {
                const err = await res.json();
                alert(err.error || err.message || "Update failed");
            }
        } catch (err) {
            alert("Network error");
        }
        setLoading(false);
    };

    return (
        <div className="modal-overlay" onClick={onClose}>
            <div className="modal-content" onClick={e => e.stopPropagation()} style={{ width: '400px' }}>
                <div className="modal-header">
                    <h3>Edit {type === 'history' ? 'Inventory Log' : 'Ledger Entry'}</h3>
                    <button className="btn-icon" onClick={onClose}><X size={20} /></button>
                </div>
                
                <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '16px', marginTop: '16px' }}>
                    {type === 'history' ? (
                        <>
                            <div>
                                <label style={{ display: 'block', marginBottom: '8px', fontSize: '14px', color: 'var(--text-secondary)' }}>Bill No</label>
                                <input type="text" className="form-input" value={formData.bill_no} onChange={e => setFormData({...formData, bill_no: e.target.value})} />
                            </div>
                            <div>
                                <label style={{ display: 'block', marginBottom: '8px', fontSize: '14px', color: 'var(--text-secondary)' }}>Contact / Supplier</label>
                                <input type="text" className="form-input" value={formData.contact_name} onChange={e => setFormData({...formData, contact_name: e.target.value})} />
                            </div>
                            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                                <div>
                                    <label style={{ display: 'block', marginBottom: '8px', fontSize: '14px', color: 'var(--text-secondary)' }}>Quantity</label>
                                    <input type="number" className="form-input" min="0.01" step="0.01" required value={formData.quantity} onChange={e => setFormData({...formData, quantity: e.target.value})} />
                                </div>
                                <div>
                                    <label style={{ display: 'block', marginBottom: '8px', fontSize: '14px', color: 'var(--text-secondary)' }}>Unit Price ₹</label>
                                    <input type="number" className="form-input" min="0" step="0.01" value={formData.unit_price} onChange={e => setFormData({...formData, unit_price: e.target.value})} />
                                </div>
                            </div>
                            <div>
                                <label style={{ display: 'block', marginBottom: '8px', fontSize: '14px', color: 'var(--text-secondary)' }}>Comment</label>
                                <input type="text" className="form-input" value={formData.comment} onChange={e => setFormData({...formData, comment: e.target.value})} />
                            </div>
                        </>
                    ) : (
                        <>
                            <div>
                                <label style={{ display: 'block', marginBottom: '8px', fontSize: '14px', color: 'var(--text-secondary)' }}>Merchant / Name</label>
                                <input type="text" className="form-input" required value={formData.merchant} onChange={e => setFormData({...formData, merchant: e.target.value})} />
                            </div>
                            <div>
                                <label style={{ display: 'block', marginBottom: '8px', fontSize: '14px', color: 'var(--text-secondary)' }}>Amount ₹</label>
                                <input type="number" className="form-input" min="0" step="0.01" required value={formData.amount} onChange={e => setFormData({...formData, amount: e.target.value})} />
                            </div>
                            <div>
                                <label style={{ display: 'block', marginBottom: '8px', fontSize: '14px', color: 'var(--text-secondary)' }}>Comment</label>
                                <input type="text" className="form-input" value={formData.comment} onChange={e => setFormData({...formData, comment: e.target.value})} />
                            </div>
                        </>
                    )}
                    
                    <button type="submit" className="btn-action btn-credit" style={{ width: '100%', justifyContent: 'center', marginTop: '8px' }} disabled={loading}>
                        {loading ? 'Saving...' : 'Save Changes'}
                    </button>
                </form>
            </div>
        </div>
    );
};
