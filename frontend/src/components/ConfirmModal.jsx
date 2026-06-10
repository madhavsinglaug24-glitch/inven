import React from 'react';
import { Modal } from './Modal';

export const ConfirmModal = ({ isOpen, onClose, onConfirm, title, message }) => {
    return (
        <Modal isOpen={isOpen} onClose={onClose} title={title} width="400px">
            <div style={{ marginBottom: '24px', color: 'var(--text-secondary)' }}>
                {message}
            </div>
            <div style={{ display: 'flex', gap: '12px', justifyContent: 'flex-end' }}>
                <button type="button" className="btn-action" onClick={onClose} style={{ borderColor: 'var(--border-color)' }}>
                    Cancel
                </button>
                <button type="button" className="btn-action btn-debit" onClick={() => { onConfirm(); onClose(); }}>
                    Confirm
                </button>
            </div>
        </Modal>
    );
};
