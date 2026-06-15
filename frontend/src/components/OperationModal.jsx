import React, { useState, useEffect } from 'react';
import { Modal } from './Modal';
import { SearchableSelect } from './SearchableSelect';
import { PromptModal } from './PromptModal';
import { ConfirmModal } from './ConfirmModal';
import { API_BASE } from '../api';
import { Plus, Trash2 } from 'lucide-react';

export const OperationModal = ({ isOpen, onClose, onRefresh, type, items, token, onAddNewItem }) => {
    const [rows, setRows] = useState([{ itemId: '', qty: '', price: '' }]);
    const [supplier, setSupplier] = useState('');
    const [billNo, setBillNo] = useState('');
    const [txDate, setTxDate] = useState(new Date().toISOString().split('T')[0] + 'T' + new Date().toTimeString().split(' ')[0]);
    const [loading, setLoading] = useState(false);
    
    const [suppliers, setSuppliers] = useState([]);
    const [consumers, setConsumers] = useState([]);
    const [promptOpen, setPromptOpen] = useState(null); // 'supplier' or 'consumer'
    const [confirmOpen, setConfirmOpen] = useState(null); // { type: 'supplier'|'consumer', data: object }

    useEffect(() => {
        if(isOpen) {
            setRows([{ itemId: '', qty: '', price: '' }]);
            setSupplier('');
            setBillNo('');
            setTxDate(new Date().toISOString().split('T')[0] + 'T' + new Date().toTimeString().split(' ')[0]);
            fetch(`${API_BASE}/suppliers`, { headers: { 'Authorization': `Bearer ${token}` } })
                .then(r=>r.json()).then(data => setSuppliers(Array.isArray(data) ? data : [])).catch(console.error);
            fetch(`${API_BASE}/consumers`, { headers: { 'Authorization': `Bearer ${token}` } })
                .then(r=>r.json()).then(data => setConsumers(Array.isArray(data) ? data : [])).catch(console.error);
        }
    }, [isOpen, token]);

    const handleAddSupplierSubmit = async (nameToUse) => {
        const res = await fetch(`${API_BASE}/suppliers`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
            body: JSON.stringify({ name: nameToUse })
        });
        if(res.ok) {
            const data = await res.json();
            setSuppliers(prev => [...prev, data]);
            setSupplier(data.name);
            setPromptOpen(null);
        } else {
            alert("Failed to add supplier");
        }
    };

    const handleAddSupplier = async (newS) => {
        if (!newS) {
            setPromptOpen('supplier');
        } else {
            handleAddSupplierSubmit(newS);
        }
    };

    const handleDeleteSupplier = (sup) => {
        setConfirmOpen({ type: 'supplier', data: sup });
    };

    const actualDeleteSupplier = async (sup) => {
        const res = await fetch(`${API_BASE}/suppliers/${sup.supplier_id}`, {
            method: 'DELETE',
            headers: { 'Authorization': `Bearer ${token}` }
        });
        if(res.ok) {
            setSuppliers(prev => prev.filter(s => s.supplier_id !== sup.supplier_id));
            if(supplier === sup.name) setSupplier('');
        }
    };

    const handleAddConsumerSubmit = async (nameToUse) => {
        const res = await fetch(`${API_BASE}/consumers`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
            body: JSON.stringify({ name: nameToUse })
        });
        if(res.ok) {
            const data = await res.json();
            setConsumers(prev => [...prev, data]);
            setSupplier(data.name); // Using 'supplier' state for the contact selection in consume mode as well
            setPromptOpen(null);
        } else {
            alert("Failed to add consumer");
        }
    };

    const handleAddConsumer = async (newC) => {
        if (!newC) {
            setPromptOpen('consumer');
        } else {
            handleAddConsumerSubmit(newC);
        }
    };

    const handleDeleteConsumer = (con) => {
        setConfirmOpen({ type: 'consumer', data: con });
    };

    const actualDeleteConsumer = async (con) => {
        const res = await fetch(`${API_BASE}/consumers/${con.consumer_id}`, {
            method: 'DELETE',
            headers: { 'Authorization': `Bearer ${token}` }
        });
        if(res.ok) {
            setConsumers(prev => prev.filter(c => c.consumer_id !== con.consumer_id));
            if(supplier === con.name) setSupplier('');
        }
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        
        // Validation
        const validRows = rows.filter(r => r.itemId && r.qty > 0);
        if (validRows.length === 0) return alert("Please add at least one valid item with a quantity greater than 0.");
        
        if (type === 'restock') {
            const missingPrice = validRows.some(r => !r.price || Number(r.price) < 0);
            if (missingPrice) return alert("Unit price is mandatory for all items when restocking to calculate average price.");
        }

        setLoading(true);
        try {
            const payload = {
                type,
                supplier,
                bill_no: billNo,
                date: txDate.replace('T', ' '),
                items: validRows.map(r => ({
                    item_id: r.itemId,
                    qty: Number(r.qty),
                    price: Number(r.price || 0) * Number(r.qty)
                }))
            };

            const res = await fetch(`${API_BASE}/inventory/update`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
                body: JSON.stringify(payload)
            });

            if (res.ok) {
                onRefresh();
                onClose();
            } else {
                const errData = await res.json();
                alert(errData.error || "Failed to update inventory");
            }
        } catch (err) { alert("Network error"); }
        setLoading(false);
    };

    const updateRow = (index, field, value) => {
        const newRows = [...rows];
        newRows[index][field] = value;
        setRows(newRows);
    };

    const removeRow = (index) => {
        const newRows = [...rows];
        newRows.splice(index, 1);
        if (newRows.length === 0) newRows.push({ itemId: '', qty: '', price: '' });
        setRows(newRows);
    };

    const itemOptions = items.map(i => ({ value: i.Item_ID, label: `[${i.Item_ID}] ${i.Item_Name} (Qty: ${i.Current_Stock})` }));

    return (
        <Modal isOpen={isOpen} onClose={onClose} title={type === 'restock' ? 'Restock Items' : 'Consume Items'} width="1000px">
            <form onSubmit={handleSubmit}>
                <div style={{ display: 'flex', gap: '12px' }}>
                    <div className="form-group" style={{ flex: 1 }}>
                        <label className="form-label">{type === 'restock' ? 'Supplier Name *' : 'Consumer/Site Name *'}</label>
                        <SearchableSelect 
                            options={type === 'restock' ? suppliers.map(s => ({ value: s.name, label: s.name, raw: s })) : consumers.map(c => ({ value: c.name, label: c.name, raw: c }))}
                            value={supplier}
                            onChange={setSupplier}
                            placeholder={`Select or Search ${type === 'restock' ? 'Supplier' : 'Consumer'}`}
                            onAddNew={type === 'restock' ? handleAddSupplier : handleAddConsumer}
                            onDelete={type === 'restock' ? handleDeleteSupplier : handleDeleteConsumer}
                            addNewText={`Add New ${type === 'restock' ? 'Supplier' : 'Consumer'}`}
                            freeText={true}
                            required={true}
                        />
                    </div>
                </div>

                <div style={{ display: 'flex', gap: '12px' }}>
                    <div className="form-group" style={{ flex: 1 }}>
                        <label className="form-label">Date & Time *</label>
                        <input type="datetime-local" className="form-input" value={txDate} onChange={e => setTxDate(e.target.value)} required />
                    </div>
                </div>

                <div className="form-group">
                    <label className="form-label">Bill Number (Optional)</label>
                    <input 
                        type="text" 
                        className="form-input" 
                        value={billNo} 
                        onChange={e => setBillNo(e.target.value)} 
                        placeholder="e.g. INV-12345"
                    />
                </div>

                <div style={{ backgroundColor: 'var(--bg-elevated)', borderRadius: '8px', padding: '16px', marginBottom: '24px' }}>
                    <div className="operation-row-header">
                        <div style={{ flex: 2 }}>Item *</div>
                        <div style={{ flex: 1 }}>Qty *</div>
                        <div style={{ flex: 1 }}>{type === 'restock' ? 'Unit ₹ *' : 'Unit ₹ (Opt)'}</div>
                        <div style={{ width: '32px' }}></div>
                    </div>

                    {rows.map((row, idx) => (
                        <div key={idx} className="operation-row">
                            <div className="col-item" style={{ flex: 2 }}>
                                <SearchableSelect 
                                    options={itemOptions}
                                    value={row.itemId}
                                    onChange={(v) => updateRow(idx, 'itemId', v)}
                                    placeholder="Select an item..."
                                    required={true}
                                />
                            </div>
                            <div className="col-qty" style={{ flex: 1 }}>
                                <input 
                                    type="number" 
                                    className="form-input" 
                                    value={row.qty} 
                                    onChange={e => updateRow(idx, 'qty', e.target.value)} 
                                    required 
                                    min="1" 
                                    placeholder="Quantity *"
                                    style={{ width: '100%' }}
                                />
                            </div>
                            <div className="col-price" style={{ flex: 1 }}>
                                <input 
                                    type="number" 
                                    className="form-input" 
                                    value={row.price} 
                                    onChange={e => updateRow(idx, 'price', e.target.value)} 
                                    min="0" 
                                    step="0.01" 
                                    required={type === 'restock' && !!row.itemId}
                                    placeholder={type === 'restock' ? "Unit ₹ *" : "Unit ₹ (Opt)"}
                                    style={{ width: '100%' }}
                                />
                            </div>
                            <div className="col-action" style={{ width: '32px', display: 'flex', alignItems: 'center', justifyContent: 'center', height: '40px' }}>
                                <button type="button" onClick={() => removeRow(idx)} style={{ background: 'transparent', border: 'none', color: 'var(--accent-red)', cursor: 'pointer', padding: 0 }} title="Remove row">
                                    <Trash2 size={18} />
                                </button>
                            </div>
                        </div>
                    ))}

                    <button type="button" onClick={() => setRows([...rows, { itemId: '', qty: '', price: '' }])} style={{ background: 'transparent', border: '1px dashed var(--border-color)', color: 'var(--text-primary)', width: '100%', padding: '12px', borderRadius: '8px', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px', marginTop: '12px' }}>
                        <Plus size={16} /> Add Another Item
                    </button>
                </div>

                <button type="submit" className={`btn-action ${type === 'consume' ? 'btn-debit' : 'btn-credit'}`} style={{ width: '100%', justifyContent: 'center' }} disabled={loading}>
                    {loading ? 'Saving...' : type === 'consume' ? 'Submit Consume' : 'Submit Restock'}
                </button>
            </form>

            <PromptModal
                isOpen={!!promptOpen}
                onClose={() => setPromptOpen(null)}
                title={promptOpen === 'supplier' ? "New Supplier" : "New Consumer"}
                label={promptOpen === 'supplier' ? "Supplier Name" : "Consumer Name"}
                placeholder="e.g. Acme Corp"
                onSubmit={(val) => {
                    if (promptOpen === 'supplier') handleAddSupplierSubmit(val);
                    else handleAddConsumerSubmit(val);
                }}
            />

            <ConfirmModal
                isOpen={!!confirmOpen}
                onClose={() => setConfirmOpen(null)}
                title={confirmOpen?.type === 'supplier' ? "Delete Supplier" : "Delete Consumer"}
                message={`Are you sure you want to delete the ${confirmOpen?.type} "${confirmOpen?.data?.name}"?`}
                onConfirm={() => {
                    if (confirmOpen?.type === 'supplier') actualDeleteSupplier(confirmOpen.data);
                    else if (confirmOpen?.type === 'consumer') actualDeleteConsumer(confirmOpen.data);
                }}
            />
        </Modal>
    );
};
