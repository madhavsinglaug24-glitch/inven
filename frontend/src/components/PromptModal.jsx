import React, { useState, useEffect } from 'react';
import { Modal } from './Modal';

export const PromptModal = ({ isOpen, onClose, onSubmit, title, label, placeholder }) => {
    const [value, setValue] = useState('');

    useEffect(() => {
        if (isOpen) setValue('');
    }, [isOpen]);

    const handleSubmit = (e) => {
        e.preventDefault();
        if (!value.trim()) return;
        onSubmit(value.trim());
        onClose();
    };

    return (
        <Modal isOpen={isOpen} onClose={onClose} title={title}>
            <form onSubmit={handleSubmit}>
                <div className="form-group">
                    <label className="form-label">{label}</label>
                    <input 
                        type="text" 
                        className="form-input" 
                        value={value} 
                        onChange={e => setValue(e.target.value)} 
                        autoFocus 
                        required 
                        placeholder={placeholder} 
                    />
                </div>
                <div style={{ display: 'flex', gap: '12px', justifyContent: 'flex-end', marginTop: '24px' }}>
                    <button type="button" className="btn-action" onClick={onClose} style={{ color: 'var(--text-secondary)' }}>
                        Cancel
                    </button>
                    <button type="submit" className="btn-action btn-credit">
                        Save
                    </button>
                </div>
            </form>
        </Modal>
    );
};
