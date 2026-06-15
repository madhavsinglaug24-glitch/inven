import React, { useState, useEffect } from 'react';
import { X } from 'lucide-react';
import { API_BASE } from '../api';
import { Modal } from './Modal';

export const EditTransactionModal = ({ isOpen, onClose, onRefresh, transaction, type, token }) => {
    const [formData, setFormData] = useState({});
    const [loading, setLoading] = useState(false);

    useEffect(() => {
        if (transaction) {
            const formatForInput = (dateStr) => {
                if(!dateStr) return '';
                try {
                    return new Date(dateStr).toISOString().slice(0, 16);
                } catch(e) { return ''; }
            };

            if (type === 'history') {
                setFormData({
                    timestamp: formatForInput(transaction.timestamp),
                    bill_no: transaction.bill_no || '',
                    contact_name: transaction.contact_name || '',
                    comment: transaction.comment || '',
                    quantity: transaction.quantity || 0,
                    unit_price: transaction.unit_price || 0
                });
            } else {
                setFormData({
                    timestamp: formatForInput(transaction.date),
                    merchant: transaction.merchant || '',
                    account: transaction.account || 'Cash',
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
            const payload = { ...formData };
            if(payload.timestamp) {
                payload.timestamp = payload.timestamp.replace('T', ' ') + ':00';
            }
            if(type !== 'history' && payload.merchant) {
                payload.name = payload.merchant;
                delete payload.merchant;
            }

            const res = await fetch(url, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
                body: JSON.stringify(payload)
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
        <Modal isOpen={isOpen} onClose={onClose} title={`Edit ${type === 'history' ? 'Inventory Log' : 'Ledger Entry'}`}>
            <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                {type === 'history' ? (
                    <>
                        <div className="form-group">
                            <label className="form-label">Date & Time</label>
                            <input type="datetime-local" className="form-input" value={formData.timestamp || ''} onChange={e => setFormData({...formData, timestamp: e.target.value})} />
                        </div>
                        <div className="form-group">
                            <label className="form-label">Bill No</label>
                            <input type="text" className="form-input" value={formData.bill_no} onChange={e => setFormData({...formData, bill_no: e.target.value})} />
                        </div>
                        <div className="form-group">
                            <label className="form-label">Contact / Supplier</label>
                            <input type="text" className="form-input" value={formData.contact_name} onChange={e => setFormData({...formData, contact_name: e.target.value})} />
                        </div>
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                            <div className="form-group">
                                <label className="form-label">Quantity</label>
                                <input type="number" className="form-input" min="0.01" step="0.01" required value={formData.quantity} onChange={e => setFormData({...formData, quantity: e.target.value})} />
                            </div>
                            <div className="form-group">
                                <label className="form-label">Unit Price ₹</label>
                                <input type="number" className="form-input" min="0" step="0.01" value={formData.unit_price} onChange={e => setFormData({...formData, unit_price: e.target.value})} />
                            </div>
                        </div>
                        <div className="form-group">
                            <label className="form-label">Comment</label>
                            <input type="text" className="form-input" value={formData.comment} onChange={e => setFormData({...formData, comment: e.target.value})} />
                        </div>
                    </>
                ) : (
                    <>
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                            <div className="form-group">
                                <label className="form-label">Date & Time</label>
                                <input type="datetime-local" className="form-input" required value={formData.timestamp || ''} onChange={e => setFormData({...formData, timestamp: e.target.value})} />
                            </div>
                            <div className="form-group">
                                <label className="form-label">Account</label>
                                <select className="form-input" value={formData.account || 'Cash'} onChange={e => setFormData({...formData, account: e.target.value})}>
                                    <option value="Cash">Cash</option>
                                    <option value="Bank">Bank</option>
                                </select>
                            </div>
                        </div>
                        <div className="form-group">
                            <label className="form-label">Merchant / Name</label>
                            <input type="text" className="form-input" required value={formData.merchant} onChange={e => setFormData({...formData, merchant: e.target.value})} />
                        </div>
                        <div className="form-group">
                            <label className="form-label">Amount ₹</label>
                            <input type="number" className="form-input" min="0" step="0.01" required value={formData.amount} onChange={e => setFormData({...formData, amount: e.target.value})} />
                        </div>
                        <div className="form-group">
                            <label className="form-label">Comment</label>
                            <input type="text" className="form-input" value={formData.comment} onChange={e => setFormData({...formData, comment: e.target.value})} />
                        </div>
                    </>
                )}
                
                <button type="submit" className="btn-action btn-credit" style={{ width: '100%', justifyContent: 'center', marginTop: '8px' }} disabled={loading}>
                    {loading ? 'Saving...' : 'Save Changes'}
                </button>
            </form>
        </Modal>
    );
};
