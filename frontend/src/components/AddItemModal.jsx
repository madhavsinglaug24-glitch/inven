import React, { useState, useEffect } from 'react';
import { Modal } from './Modal';
import { API_BASE } from '../api';

export const AddItemModal = ({ isOpen, onClose, onRefresh, token, initialId }) => {
    const [itemId, setItemId] = useState('');
    const [name, setName] = useState('');
    const [minStock, setMinStock] = useState('10');
    const [loading, setLoading] = useState(false);

    useEffect(() => {
        if (initialId) setItemId(initialId);
    }, [initialId]);

    const handleSubmit = async (e) => {
        e.preventDefault();
        if (!itemId || !name) return alert("ID and Name are mandatory!");
        setLoading(true);
        try {
            const res = await fetch(`${API_BASE}/inventory/add`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
                body: JSON.stringify({ id: itemId, name, min_stock: Number(minStock) })
            });
            if (res.ok) {
                onRefresh();
                onClose();
                setItemId(''); setName(''); setMinStock('10');
            } else {
                const data = await res.json();
                alert(data.error || "Failed to add item");
            }
        } catch (err) { alert("Network error"); }
        setLoading(false);
    };

    return (
        <Modal isOpen={isOpen} onClose={onClose} title="Add New Item">
            <form onSubmit={handleSubmit}>
                <div className="form-group">
                    <label className="form-label">Item ID *</label>
                    <input type="text" className="form-input" value={itemId} onChange={e => setItemId(e.target.value)} required placeholder="e.g. SUGAR-1KG" />
                </div>
                
                <div className="form-group">
                    <label className="form-label">Item Name *</label>
                    <input type="text" className="form-input" value={name} onChange={e => setName(e.target.value)} required placeholder="e.g. Sugar 1kg Packet" />
                </div>
                
                <div className="form-group">
                    <label className="form-label">Min Stock Alert</label>
                    <input type="number" className="form-input" value={minStock} onChange={e => setMinStock(e.target.value)} min="0" />
                </div>

                <button type="submit" className="btn-action btn-credit" style={{ width: '100%', justifyContent: 'center' }} disabled={loading}>
                    {loading ? 'Saving...' : 'Add Item'}
                </button>
            </form>
        </Modal>
    );
};
