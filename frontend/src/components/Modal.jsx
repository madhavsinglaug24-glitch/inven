
import React from 'react';
import { X } from 'lucide-react';

export const Modal = ({ isOpen, onClose, title, width, children }) => {
    if (!isOpen) return null;
    return (
        <div className="modal-overlay" onClick={onClose}>
            <div className="modal-content fade-in" onClick={e => e.stopPropagation()} style={width ? { maxWidth: width, width: '100%' } : {}}>
                <button className="modal-close" onClick={onClose}><X size={20} /></button>
                <h2 style={{ fontSize: '20px', marginBottom: '24px' }}>{title}</h2>
                {children}
            </div>
        </div>
    );
};
