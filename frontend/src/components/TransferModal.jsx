import React, { useState } from 'react';
import { Modal } from './Modal';
import { API_BASE } from '../api';

export const TransferModal = ({ isOpen, onClose, onRefresh, token }) => {
    const [amount, setAmount] = useState('');
    const [description, setDescription] = useState('Self Transfer');
    const [txDate, setTxDate] = useState(new Date().toISOString().split('T')[0]);
    const [direction, setDirection] = useState('bank_to_cash'); // 'cash_to_bank' or 'bank_to_cash'
    const [loading, setLoading] = useState(false);

    const handleSubmit = async (e) => {
        e.preventDefault();
        if (loading) return;
        const parsedAmount = Number(amount);
        if (!parsedAmount || parsedAmount <= 0) return alert("Amount must be greater than 0");
        setLoading(true);
        try {
            const res = await fetch(`${API_BASE}/transfer`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
                body: JSON.stringify({ amount: parsedAmount, direction, description, date: txDate })
            });
            if (res.ok) {
                onRefresh();
                onClose();
                setAmount('');
                setDescription('Self Transfer');
                setTxDate(new Date().toISOString().split('T')[0]);
            } else {
                const errData = await res.json();
                alert(errData.error || "Failed to add transfer");
            }
        } catch (err) { alert("Network error"); }
        setLoading(false);
    };

    return (
        <Modal isOpen={isOpen} onClose={onClose} title="Self Transfer">
            <form onSubmit={handleSubmit}>
                <div style={{ display: 'flex', gap: '12px' }}>
                    <div className="form-group" style={{ flex: 1 }}>
                        <label className="form-label">Date *</label>
                        <input type="date" className="form-input" value={txDate} onChange={e => setTxDate(e.target.value)} required />
                    </div>
                </div>

                <div className="form-group">
                    <label className="form-label">Transfer Direction *</label>
                    <select className="form-input" value={direction} onChange={e => setDirection(e.target.value)} required>
                        <option value="bank_to_cash">Bank to Cash (Withdrawal)</option>
                        <option value="cash_to_bank">Cash to Bank (Deposit)</option>
                    </select>
                </div>

                <div className="form-group">
                    <label className="form-label">Amount (₹) *</label>
                    <input type="number" className="form-input" value={amount} onChange={e => setAmount(e.target.value)} required min="0.01" step="0.01" />
                </div>
                
                <div className="form-group">
                    <label className="form-label">Description (Optional)</label>
                    <input type="text" className="form-input" value={description} onChange={e => setDescription(e.target.value)} placeholder="e.g. ATM Withdrawal" />
                </div>

                <button type="submit" className="btn-action" style={{ width: '100%', justifyContent: 'center', backgroundColor: 'var(--accent-teal)', color: '#fff', border: 'none' }} disabled={loading}>
                    {loading ? 'Processing...' : 'Complete Transfer'}
                </button>
            </form>
        </Modal>
    );
};
