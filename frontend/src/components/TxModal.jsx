
import React, { useState, useEffect } from 'react';
import { Modal } from './Modal';
import { PromptModal } from './PromptModal';
import { SearchableSelect } from './SearchableSelect';
import { API_BASE } from '../api';

export const TxModal = ({ isOpen, onClose, onRefresh, type, token, existingMerchants }) => {
    const [amount, setAmount] = useState('');
    const [merchant, setMerchant] = useState('');
    const [description, setDescription] = useState('');
    const [loading, setLoading] = useState(false);
    const [merchants, setMerchants] = useState([]);
    const [promptOpen, setPromptOpen] = useState(false);

    useEffect(() => {
        if(existingMerchants) {
            setMerchants([...new Set(existingMerchants)]);
        }
    }, [existingMerchants]);

    const handleSubmit = async (e) => {
        e.preventDefault();
        if (!amount || !merchant) return alert("Amount and Merchant are mandatory!");
        setLoading(true);
        try {
            const res = await fetch(`${API_BASE}/api/transactions`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
                body: JSON.stringify({ amount: Number(amount), merchant, description, type })
            });
            if (res.ok) {
                onRefresh();
                onClose();
                setAmount('');
                setMerchant('');
                setDescription('');
            } else alert("Failed to add transaction");
        } catch (err) { alert("Network error"); }
        setLoading(false);
    };

    return (
        <Modal isOpen={isOpen} onClose={onClose} title={`Add ${type === 'income' ? 'Cash IN' : 'Cash OUT'}`}>
            <form onSubmit={handleSubmit}>
                <div className="form-group">
                    <label className="form-label">Amount (₹) *</label>
                    <input type="number" className="form-input" value={amount} onChange={e => setAmount(e.target.value)} required min="0" step="0.01" />
                </div>
                
                <div className="form-group">
                    <label className="form-label">Merchant / Store *</label>
                    <SearchableSelect 
                        options={merchants}
                        value={merchant}
                        onChange={setMerchant}
                        placeholder="Select or Search Merchant"
                        onAddNew={(newM) => {
                            if (!newM) {
                                setPromptOpen(true);
                            } else {
                                setMerchants(prev => [...prev, newM]);
                                setMerchant(newM);
                            }
                        }}
                        addNewText="Add New Merchant"
                        freeText={true}
                        required={true}
                    />
                </div>
                
                <div className="form-group">
                    <label className="form-label">Description (Optional)</label>
                    <input type="text" className="form-input" value={description} onChange={e => setDescription(e.target.value)} placeholder="What was this for?" />
                </div>

                <button type="submit" className={`btn-action ${type === 'income' ? 'btn-credit' : 'btn-debit'}`} style={{ width: '100%', justifyContent: 'center' }} disabled={loading}>
                    {loading ? 'Saving...' : 'Save Transaction'}
                </button>
            </form>
            
            <PromptModal
                isOpen={promptOpen}
                onClose={() => setPromptOpen(false)}
                title="New Merchant"
                label="Merchant Name"
                placeholder="e.g. Ali Baba"
                onSubmit={(val) => {
                    setMerchants(prev => [...prev, val]);
                    setMerchant(val);
                }}
            />
        </Modal>
    );
};
