
import React, { useState, useRef, useEffect } from 'react';
import { Modal } from './Modal';
import { Camera, PackagePlus, PackageMinus, Loader } from 'lucide-react';
import { API_BASE } from '../api';

export const ScannerModal = ({ isOpen, onClose, token, items, onRefresh, initialMode }) => {
    const [file, setFile] = useState(null);
    const [preview, setPreview] = useState(null);
    const [loading, setLoading] = useState(false);
    const [result, setResult] = useState(null); // { amount, merchant }
    const [error, setError] = useState('');
    const [step, setStep] = useState('upload'); // 'upload' | 'manual' | 'scanned' | 'confirm'
    const [stockType, setStockType] = useState(null); // 'restock' | 'consume'
    const [selectedItem, setSelectedItem] = useState('');
    const [qty, setQty] = useState('1');
    const [saving, setSaving] = useState(false);
    // Manual entry fields
    const [manualMerchant, setManualMerchant] = useState('');
    const [manualAmount, setManualAmount] = useState('');
    const fileInput = useRef(null);

    // Reset when modal opens with a new mode
    useEffect(() => {
        if (isOpen) {
            reset();
            if (initialMode === 'manual') {
                setStep('manual');
            } else {
                setStep('upload');
            }
        }
    }, [isOpen, initialMode]);

    const reset = () => {
        setFile(null);
        setPreview(null);
        setResult(null);
        setError('');
        setStep('upload');
        setStockType(null);
        setSelectedItem('');
        setQty('1');
        setSaving(false);
        setManualMerchant('');
        setManualAmount('');
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
                        setResult(null);
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
                setResult(data);
                setStep('scanned');
            } else {
                setError(data.error || 'Scan failed. Please try again.');
            }
        } catch (e) { 
            setError('Network error. Please check your connection.'); 
        }
        setLoading(false);
    };

    const handleManualSubmit = () => {
        const amt = parseFloat(manualAmount);
        if (!manualMerchant.trim()) { setError('Please enter a merchant/supplier name.'); return; }
        if (isNaN(amt) || amt <= 0) { setError('Please enter a valid amount.'); return; }
        setResult({ amount: amt, merchant: manualMerchant.trim() });
        setStep('scanned');
        setError('');
    };

    const handleStockSubmit = async () => {
        if (!stockType || !selectedItem || !qty) return;
        setSaving(true);
        setError('');
        try {
            const payload = {
                type: stockType,
                supplier: result?.merchant || 'Manual Entry',
                items: [{
                    item_id: selectedItem,
                    qty: Number(qty),
                    price: Number(result?.amount || 0)
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

    const modalTitle = step === 'manual' ? 'Enter Transaction' : 'Scan Receipt';

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
                    
                    {error && <div style={{ color: 'var(--accent-red)', marginBottom: '16px', fontSize: '14px', textAlign: 'center', padding: '12px', backgroundColor: 'var(--accent-red-dim)', borderRadius: '8px' }}>{error}</div>}
                    
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
                    {error && <div style={{ color: 'var(--accent-red)', marginBottom: '16px', fontSize: '14px', textAlign: 'center', padding: '12px', backgroundColor: 'var(--accent-red-dim)', borderRadius: '8px' }}>{error}</div>}
                    
                    <div style={{ marginBottom: '16px' }}>
                        <label style={{ display: 'block', marginBottom: '6px', fontSize: '13px', color: 'var(--text-secondary)', fontWeight: 500 }}>Merchant / Supplier *</label>
                        <input 
                            type="text" 
                            className="form-input" 
                            value={manualMerchant} 
                            onChange={e => setManualMerchant(e.target.value)}
                            placeholder="e.g. Big Bazaar, Amazon..."
                            style={{ width: '100%', backgroundColor: 'var(--bg-elevated)' }}
                        />
                    </div>

                    <div style={{ marginBottom: '24px' }}>
                        <label style={{ display: 'block', marginBottom: '6px', fontSize: '13px', color: 'var(--text-secondary)', fontWeight: 500 }}>Total Amount (₹) *</label>
                        <input 
                            type="number" 
                            className="form-input" 
                            value={manualAmount} 
                            onChange={e => setManualAmount(e.target.value)}
                            placeholder="e.g. 1500"
                            min="0"
                            step="0.01"
                            style={{ width: '100%', backgroundColor: 'var(--bg-elevated)' }}
                        />
                    </div>

                    <button className="btn-action btn-credit" style={{ width: '100%', justifyContent: 'center' }} onClick={handleManualSubmit}>
                        Continue
                    </button>
                </div>
            )}

            {/* STEP: Scanned Result - Ask Stock In or Out */}
            {step === 'scanned' && result && (
                <div>
                    {preview && <img src={preview} alt="Receipt" style={{ width: '100%', maxHeight: '150px', objectFit: 'contain', borderRadius: '8px', marginBottom: '16px', backgroundColor: '#000' }} />}
                    
                    <div style={{ backgroundColor: 'var(--bg-elevated)', padding: '16px', borderRadius: '8px', marginBottom: '20px', border: '1px solid var(--border-color)' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                            <span style={{ color: 'var(--text-secondary)' }}>Merchant</span>
                            <span style={{ fontWeight: 600 }}>{result.merchant || 'Unknown'}</span>
                        </div>
                        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                            <span style={{ color: 'var(--text-secondary)' }}>Amount</span>
                            <span style={{ color: 'var(--accent-green)', fontWeight: 600, fontSize: '18px' }}>₹{Number(result.amount).toLocaleString()}</span>
                        </div>
                    </div>

                    {error && <div style={{ color: 'var(--accent-red)', marginBottom: '16px', fontSize: '14px', textAlign: 'center', padding: '12px', backgroundColor: 'var(--accent-red-dim)', borderRadius: '8px' }}>{error}</div>}

                    <p style={{ color: 'var(--text-secondary)', textAlign: 'center', marginBottom: '16px', fontSize: '14px' }}>What type of transaction is this?</p>

                    <div style={{ display: 'flex', gap: '12px', marginBottom: '20px' }}>
                        <button 
                            className="btn-action" 
                            onClick={() => { setStockType('restock'); setStep('confirm'); }}
                            style={{ 
                                flex: 1, justifyContent: 'center', display: 'flex', alignItems: 'center', gap: '8px', padding: '16px',
                                backgroundColor: 'var(--accent-green-dim)', color: 'var(--accent-green)', borderColor: 'var(--accent-green)',
                                fontSize: '15px', fontWeight: 600
                            }}
                        >
                            <PackagePlus size={22} /> Stock IN
                        </button>
                        <button 
                            className="btn-action"
                            onClick={() => { setStockType('consume'); setStep('confirm'); }}
                            style={{ 
                                flex: 1, justifyContent: 'center', display: 'flex', alignItems: 'center', gap: '8px', padding: '16px',
                                backgroundColor: 'var(--accent-red-dim)', color: 'var(--accent-red)', borderColor: 'var(--accent-red)',
                                fontSize: '15px', fontWeight: 600
                            }}
                        >
                            <PackageMinus size={22} /> Stock OUT
                        </button>
                    </div>

                    <button className="btn-action" style={{ width: '100%', justifyContent: 'center' }} onClick={reset}>
                        Start Over
                    </button>
                </div>
            )}

            {/* STEP: Confirm - Select Item + Qty */}
            {step === 'confirm' && result && (
                <div>
                    <div style={{ backgroundColor: 'var(--bg-elevated)', padding: '12px 16px', borderRadius: '8px', marginBottom: '20px', border: '1px solid var(--border-color)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <div>
                            <span style={{ color: 'var(--text-secondary)', fontSize: '12px' }}>
                                {stockType === 'restock' ? '📦 STOCK IN' : '📤 STOCK OUT'}
                            </span>
                            <div style={{ fontWeight: 600 }}>{result.merchant}</div>
                        </div>
                        <span style={{ color: 'var(--accent-green)', fontWeight: 600, fontSize: '18px' }}>₹{Number(result.amount).toLocaleString()}</span>
                    </div>

                    {error && <div style={{ color: 'var(--accent-red)', marginBottom: '16px', fontSize: '14px', textAlign: 'center', padding: '12px', backgroundColor: 'var(--accent-red-dim)', borderRadius: '8px' }}>{error}</div>}

                    <div style={{ marginBottom: '16px' }}>
                        <label style={{ display: 'block', marginBottom: '6px', fontSize: '13px', color: 'var(--text-secondary)', fontWeight: 500 }}>Select Item *</label>
                        <select 
                            className="form-input" 
                            value={selectedItem} 
                            onChange={e => setSelectedItem(e.target.value)}
                            style={{ width: '100%', backgroundColor: 'var(--bg-elevated)', cursor: 'pointer' }}
                        >
                            <option value="">-- Choose an item --</option>
                            {(items || []).map(item => (
                                <option key={item.Item_ID} value={item.Item_ID}>
                                    [{item.Item_ID}] {item.Item_Name} (Stock: {item.Current_Stock})
                                </option>
                            ))}
                        </select>
                    </div>

                    <div style={{ marginBottom: '20px' }}>
                        <label style={{ display: 'block', marginBottom: '6px', fontSize: '13px', color: 'var(--text-secondary)', fontWeight: 500 }}>Quantity *</label>
                        <input 
                            type="number" 
                            className="form-input" 
                            value={qty} 
                            onChange={e => setQty(e.target.value)}
                            min="1"
                            style={{ width: '100%', backgroundColor: 'var(--bg-elevated)' }}
                        />
                    </div>

                    <div style={{ display: 'flex', gap: '12px' }}>
                        <button className="btn-action" style={{ flex: 1, justifyContent: 'center' }} onClick={() => { setStep('scanned'); setStockType(null); setError(''); }}>
                            Back
                        </button>
                        <button 
                            className={`btn-action ${stockType === 'consume' ? 'btn-debit' : 'btn-credit'}`}
                            style={{ flex: 2, justifyContent: 'center' }} 
                            onClick={handleStockSubmit} 
                            disabled={saving || !selectedItem || !qty}
                        >
                            {saving ? 'Saving...' : stockType === 'restock' ? 'Confirm Stock IN' : 'Confirm Stock OUT'}
                        </button>
                    </div>
                </div>
            )}
        </Modal>
    );
};
