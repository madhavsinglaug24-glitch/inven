
import React, { useState, useRef, useEffect } from 'react';
import { Modal } from './Modal';
import { Camera, PackagePlus, PackageMinus, Loader } from 'lucide-react';
import { API_BASE } from '../api';

export const ScannerModal = ({ isOpen, onClose, token, items, onRefresh, initialMode }) => {
    const [file, setFile] = useState(null);
    const [preview, setPreview] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');
    const [step, setStep] = useState('upload'); // 'upload' | 'manual' | 'scanned' | 'confirm'
    const [stockType, setStockType] = useState(null); // 'restock' | 'consume'
    // Editable transaction fields
    const [merchant, setMerchant] = useState('');
    const [amount, setAmount] = useState('');
    const [selectedItem, setSelectedItem] = useState('');
    const [qty, setQty] = useState('1');
    const [saving, setSaving] = useState(false);
    const fileInput = useRef(null);

    useEffect(() => {
        if (isOpen) {
            reset();
            setStep(initialMode === 'manual' ? 'manual' : 'upload');
        }
    }, [isOpen, initialMode]);

    const reset = () => {
        setFile(null);
        setPreview(null);
        setError('');
        setStep('upload');
        setStockType(null);
        setMerchant('');
        setAmount('');
        setSelectedItem('');
        setQty('1');
        setSaving(false);
    };

    const handleFile = (e) => {
        const f = e.target.files[0];
        if (f) {
            const reader = new FileReader();
            reader.readAsDataURL(f);
            reader.onload = (event) => {
                const img = new Image();
                img.src = event.target.result;
                img.onload = () => {
                    const canvas = document.createElement('canvas');
                    let width = img.width;
                    let height = img.height;
                    const MAX_SIZE = 1200;
                    if (width > height && width > MAX_SIZE) {
                        height *= MAX_SIZE / width;
                        width = MAX_SIZE;
                    } else if (height > MAX_SIZE) {
                        width *= MAX_SIZE / height;
                        height = MAX_SIZE;
                    }
                    canvas.width = width;
                    canvas.height = height;
                    const ctx = canvas.getContext('2d');
                    ctx.drawImage(img, 0, 0, width, height);
                    canvas.toBlob((blob) => {
                        const compressedFile = new File([blob], f.name, { type: 'image/jpeg', lastModified: Date.now() });
                        setFile(compressedFile);
                        setPreview(URL.createObjectURL(compressedFile));
                        setError('');
                    }, 'image/jpeg', 0.8);
                };
            };
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
            if (res.ok && data.amount !== undefined) {
                setMerchant(data.merchant || '');
                setAmount(String(data.amount || ''));
                setStep('scanned');
            } else {
                setError(data.error || 'Scan failed. Please try again.');
            }
        } catch (e) { 
            setError('Network error. Please check your connection.'); 
        }
        setLoading(false);
    };

    const handleStockSubmit = async (overrideType) => {
        const typeToUse = (typeof overrideType === 'string') ? overrideType : stockType;
        if (!typeToUse || !selectedItem || !qty) return;
        setSaving(true);
        setError('');
        try {
            const payload = {
                type: typeToUse,
                supplier: merchant || 'Manual Entry',
                items: [{
                    item_id: selectedItem,
                    qty: Number(qty),
                    price: Number(amount || 0)
                }]
            };
            const res = await fetch(`${API_BASE}/inventory/update`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
                body: JSON.stringify(payload)
            });
            if (res.ok) {
                if (onRefresh) onRefresh();
                onClose();
                reset();
            } else {
                const err = await res.json();
                setError(err.error || err.message || 'Failed to save.');
            }
        } catch (e) {
            setError('Network error.');
        }
        setSaving(false);
    };

    const modalTitle = step === 'manual' ? 'Enter Transaction' : step === 'confirm' ? (stockType === 'restock' ? 'Stock IN' : 'Stock OUT') : 'Scan Receipt';

    const ErrorBox = () => error ? (
        <div style={{ color: 'var(--accent-red)', marginBottom: '16px', fontSize: '14px', textAlign: 'center', padding: '12px', backgroundColor: 'var(--accent-red-dim)', borderRadius: '8px' }}>{error}</div>
    ) : null;

    // Shared editable fields for merchant + amount
    const EditableFields = ({ showHeading }) => (
        <div style={{ marginBottom: '20px' }}>
            {showHeading && <p style={{ color: 'var(--text-secondary)', fontSize: '13px', marginBottom: '12px' }}>You can edit the details below:</p>}
            <div style={{ marginBottom: '12px' }}>
                <label style={{ display: 'block', marginBottom: '6px', fontSize: '13px', color: 'var(--text-secondary)', fontWeight: 500 }}>Merchant / Supplier *</label>
                <input 
                    type="text" className="form-input" value={merchant} onChange={e => setMerchant(e.target.value)}
                    placeholder="e.g. Big Bazaar, Amazon..."
                    style={{ width: '100%', backgroundColor: 'var(--bg-elevated)' }}
                />
            </div>
            <div style={{ marginBottom: '12px' }}>
                <label style={{ display: 'block', marginBottom: '6px', fontSize: '13px', color: 'var(--text-secondary)', fontWeight: 500 }}>Total Amount (₹) *</label>
                <input 
                    type="number" className="form-input" value={amount} onChange={e => setAmount(e.target.value)}
                    placeholder="e.g. 1500" min="0" step="0.01"
                    style={{ width: '100%', backgroundColor: 'var(--bg-elevated)' }}
                />
            </div>
            <div style={{ marginBottom: '12px' }}>
                <label style={{ display: 'block', marginBottom: '6px', fontSize: '13px', color: 'var(--text-secondary)', fontWeight: 500 }}>Select Item *</label>
                <select className="form-input" value={selectedItem} onChange={e => setSelectedItem(e.target.value)}
                    style={{ width: '100%', backgroundColor: 'var(--bg-elevated)', cursor: 'pointer' }}>
                    <option value="">-- Choose an item --</option>
                    {(items || []).map(item => (
                        <option key={item.Item_ID} value={item.Item_ID}>
                            [{item.Item_ID}] {item.Item_Name} (Stock: {item.Current_Stock})
                        </option>
                    ))}
                </select>
            </div>
            <div>
                <label style={{ display: 'block', marginBottom: '6px', fontSize: '13px', color: 'var(--text-secondary)', fontWeight: 500 }}>Quantity *</label>
                <input 
                    type="number" className="form-input" value={qty} onChange={e => setQty(e.target.value)}
                    min="1" placeholder="1"
                    style={{ width: '100%', backgroundColor: 'var(--bg-elevated)' }}
                />
            </div>
        </div>
    );

    return (
        <Modal isOpen={isOpen} onClose={() => { onClose(); reset(); }} title={modalTitle} width="480px">
            {/* STEP: Upload (Scan mode) */}
            {step === 'upload' && !preview && (
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
            )}

            {/* STEP: Preview + Scan Button */}
            {step === 'upload' && preview && (
                <div>
                    <img src={preview} alt="Receipt" style={{ width: '100%', maxHeight: '250px', objectFit: 'contain', borderRadius: '8px', marginBottom: '16px', backgroundColor: '#000' }} />
                    <ErrorBox />
                    <div style={{ display: 'flex', gap: '12px' }}>
                        <button className="btn-action" style={{ flex: 1, justifyContent: 'center' }} onClick={() => { setFile(null); setPreview(null); setError(''); }}>
                            Retake
                        </button>
                        <button className="btn-action btn-credit" style={{ flex: 2, justifyContent: 'center', display: 'flex', alignItems: 'center', gap: '8px' }} onClick={scan} disabled={loading}>
                            {loading ? <><Loader size={18} className="spin" /> Scanning...</> : 'Extract Data'}
                        </button>
                    </div>
                </div>
            )}

            {/* STEP: Manual Entry */}
            {step === 'manual' && (
                <div>
                    <ErrorBox />
                    <EditableFields showHeading={false} />
                    <div style={{ display: 'flex', gap: '12px' }}>
                        <button 
                            className="btn-action" 
                            onClick={() => { if (!merchant.trim() || !amount || !selectedItem || !qty) { setError('Please fill all required fields.'); return; } setStockType('restock'); setError(''); handleStockSubmit('restock'); }}
                            disabled={saving}
                            style={{ flex: 1, justifyContent: 'center', display: 'flex', alignItems: 'center', gap: '8px', padding: '14px',
                                backgroundColor: 'var(--accent-green-dim)', color: 'var(--accent-green)', borderColor: 'var(--accent-green)',
                                fontWeight: 600 }}
                        >
                            <PackagePlus size={20} /> {saving ? 'Saving...' : 'Stock IN'}
                        </button>
                        <button 
                            className="btn-action"
                            onClick={() => { if (!merchant.trim() || !amount || !selectedItem || !qty) { setError('Please fill all required fields.'); return; } setStockType('consume'); setError(''); handleStockSubmit('consume'); }}
                            disabled={saving}
                            style={{ flex: 1, justifyContent: 'center', display: 'flex', alignItems: 'center', gap: '8px', padding: '14px',
                                backgroundColor: 'var(--accent-red-dim)', color: 'var(--accent-red)', borderColor: 'var(--accent-red)',
                                fontWeight: 600 }}
                        >
                            <PackageMinus size={20} /> {saving ? 'Saving...' : 'Stock OUT'}
                        </button>
                    </div>
                </div>
            )}

            {/* STEP: Scanned Result - editable fields + Stock IN/OUT */}
            {step === 'scanned' && (
                <div>
                    {preview && <img src={preview} alt="Receipt" style={{ width: '100%', maxHeight: '120px', objectFit: 'contain', borderRadius: '8px', marginBottom: '16px', backgroundColor: '#000' }} />}
                    <ErrorBox />
                    <EditableFields showHeading={true} />
                    <div style={{ display: 'flex', gap: '12px' }}>
                        <button 
                            className="btn-action" 
                            onClick={() => { if (!merchant.trim() || !amount || !selectedItem || !qty) { setError('Please fill all required fields.'); return; } setStockType('restock'); setError(''); }}
                            style={{ flex: 1, justifyContent: 'center', display: 'flex', alignItems: 'center', gap: '8px', padding: '14px',
                                backgroundColor: 'var(--accent-green-dim)', color: 'var(--accent-green)', borderColor: 'var(--accent-green)',
                                fontWeight: 600 }}
                        >
                            <PackagePlus size={20} /> Stock IN
                        </button>
                        <button 
                            className="btn-action"
                            onClick={() => { if (!merchant.trim() || !amount || !selectedItem || !qty) { setError('Please fill all required fields.'); return; } setStockType('consume'); setError(''); }}
                            style={{ flex: 1, justifyContent: 'center', display: 'flex', alignItems: 'center', gap: '8px', padding: '14px',
                                backgroundColor: 'var(--accent-red-dim)', color: 'var(--accent-red)', borderColor: 'var(--accent-red)',
                                fontWeight: 600 }}
                        >
                            <PackageMinus size={20} /> Stock OUT
                        </button>
                    </div>
                    <button className="btn-action" style={{ width: '100%', justifyContent: 'center', marginTop: '12px' }} onClick={reset}>
                        Start Over
                    </button>
                </div>
            )}

            {/* STEP: Confirm */}
            {step === 'scanned' && stockType && (
                <div style={{ marginTop: '20px', padding: '16px', backgroundColor: 'var(--bg-elevated)', borderRadius: '8px', border: '1px solid var(--border-color)' }}>
                    <h4 style={{ marginBottom: '12px', textAlign: 'center' }}>
                        {stockType === 'restock' ? '📦 Confirm Stock IN' : '📤 Confirm Stock OUT'}
                    </h4>
                    <p style={{ fontSize: '13px', color: 'var(--text-secondary)', textAlign: 'center', marginBottom: '16px' }}>
                        {qty}x {(items || []).find(i => i.Item_ID === selectedItem)?.Item_Name || selectedItem} from <strong>{merchant}</strong> for <strong>₹{Number(amount).toLocaleString()}</strong>
                    </p>
                    <div style={{ display: 'flex', gap: '12px' }}>
                        <button className="btn-action" style={{ flex: 1, justifyContent: 'center' }} onClick={() => setStockType(null)}>
                            Cancel
                        </button>
                        <button 
                            className={`btn-action ${stockType === 'consume' ? 'btn-debit' : 'btn-credit'}`}
                            style={{ flex: 2, justifyContent: 'center' }} 
                            onClick={handleStockSubmit} 
                            disabled={saving}
                        >
                            {saving ? 'Saving...' : 'Confirm'}
                        </button>
                    </div>
                </div>
            )}
        </Modal>
    );
};
