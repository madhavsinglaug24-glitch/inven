
import React, { useState, useEffect } from 'react';
import { Modal } from './Modal';
import { PromptModal } from './PromptModal';
import { ConfirmModal } from './ConfirmModal';
import { SearchableSelect } from './SearchableSelect';
import { API_BASE } from '../api';

export const TxModal = ({ isOpen, onClose, onRefresh, type, token }) => {
    const [amount, setAmount] = useState('');
    const [merchant, setMerchant] = useState('');
    const [description, setDescription] = useState('');
    const [txDate, setTxDate] = useState(new Date().toISOString().split('T')[0] + 'T' + new Date().toTimeString().split(' ')[0]);
    const [account, setAccount] = useState('Cash');
    const [loading, setLoading] = useState(false);
    const [merchants, setMerchants] = useState([]);
    const [promptOpen, setPromptOpen] = useState(false);
    const [confirmDeleteMerch, setConfirmDeleteMerch] = useState(null);

    useEffect(() => {
        fetch(`${API_BASE}/merchants`, { headers: { 'Authorization': `Bearer ${token}` } })
            .then(res => res.json())
            .then(data => {
                if (Array.isArray(data)) {
                    setMerchants(data);
                }
            })
            .catch(err => console.error("Failed to load merchants", err));
    }, [token, isOpen]);

    const handleSubmit = async (e) => {
        e.preventDefault();
        if (!amount || !merchant) return alert("Amount and Merchant are mandatory!");
        setLoading(true);
        try {
            const res = await fetch(`${API_BASE}/transactions`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
                body: JSON.stringify({ amount: Number(amount), merchant, description, type, date: txDate.replace('T', ' '), account })
            });
            if (res.ok) {
                onRefresh();
                onClose();
                setAmount('');
                setMerchant('');
                setDescription('');
                setTxDate(new Date().toISOString().split('T')[0] + 'T' + new Date().toTimeString().split(' ')[0]);
                setAccount('Cash');
            } else {
                const errData = await res.json();
                alert(errData.error || "Failed to add transaction");
            }
        } catch (err) { alert("Network error"); }
        setLoading(false);
    };

    const handleAddMerchantSubmit = async (nameToUse) => {
        const res = await fetch(`${API_BASE}/merchants`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
            body: JSON.stringify({ name: nameToUse })
        });
        if(res.ok) {
            const data = await res.json();
            setMerchants(prev => [...prev, data]);
            setMerchant(data.name);
            setPromptOpen(false);
        } else {
            alert("Failed to add merchant");
        }
    };

    const handleDeleteMerchant = async (merchObj) => {
        if (!merchObj || !merchObj.merchant_id) return;
        setConfirmDeleteMerch(merchObj);
    };

    const confirmAndDeleteMerchant = async () => {
        if (!confirmDeleteMerch) return;
        const merchObj = confirmDeleteMerch;
        const res = await fetch(`${API_BASE}/merchants/${merchObj.merchant_id}`, {
            method: 'DELETE',
            headers: { 'Authorization': `Bearer ${token}` }
        });
        if(res.ok) {
            setMerchants(prev => prev.filter(m => m.merchant_id !== merchObj.merchant_id));
            if(merchant === merchObj.name) setMerchant('');
            setConfirmDeleteMerch(null);
        }
    };

    return (
        <Modal isOpen={isOpen} onClose={onClose} title={`Add ${type === 'income' ? 'Cash IN' : 'Cash OUT'}`}>
            <form onSubmit={handleSubmit}>
                <div style={{ display: 'flex', gap: '12px' }}>
                    <div className="form-group" style={{ flex: 1 }}>
                        <label className="form-label">Date & Time *</label>
                        <input type="datetime-local" className="form-input" value={txDate} onChange={e => setTxDate(e.target.value)} required />
                    </div>
                    <div className="form-group" style={{ flex: 1 }}>
                        <label className="form-label">Payment Method *</label>
                        <select className="form-input" value={account} onChange={e => setAccount(e.target.value)} required>
                            <option value="Cash">Cash</option>
                            <option value="Bank">Bank</option>
                        </select>
                    </div>
                </div>

                <div className="form-group">
                    <label className="form-label">Amount (₹) *</label>
                    <input type="number" className="form-input" value={amount} onChange={e => setAmount(e.target.value)} required min="0" step="0.01" />
                </div>
                
                <div className="form-group">
                    <label className="form-label">Merchant / Store *</label>
                    <SearchableSelect 
                        options={merchants.map(m => ({ value: m.name, label: m.name, raw: m }))}
                        value={merchant}
                        onChange={setMerchant}
                        placeholder="Select or Search Merchant"
                        onAddNew={(newM) => {
                            if (!newM) {
                                setPromptOpen(true);
                            } else {
                                handleAddMerchantSubmit(newM);
                            }
                        }}
                        onDelete={handleDeleteMerchant}
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
                    handleAddMerchantSubmit(val);
                }}
            />

            <ConfirmModal 
                isOpen={!!confirmDeleteMerch}
                onClose={() => setConfirmDeleteMerch(null)}
                onConfirm={confirmAndDeleteMerchant}
                title="Delete Merchant"
                message={`Are you sure you want to delete the merchant "${confirmDeleteMerch?.name}"?`}
                confirmText="Delete"
                isDanger={true}
            />
        </Modal>
    );
};
