
import React, { useState, useRef, useEffect } from 'react';
import { ChevronDown, ChevronUp, Plus, Trash2 } from 'lucide-react';

export const SearchableSelect = ({ options, value, onChange, placeholder, onAddNew, addNewText, freeText, required, onDelete }) => {
    const [isOpen, setIsOpen] = useState(false);
    const [search, setSearch] = useState('');
    const wrapperRef = useRef(null);
    
    // Close on outside click
    useEffect(() => {
        const handleClickOutside = (event) => {
            if (wrapperRef.current && !wrapperRef.current.contains(event.target)) {
                setIsOpen(false);
            }
        };
        document.addEventListener('mousedown', handleClickOutside);
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, []);

    const normalizedOptions = options.map(o => typeof o === 'string' || typeof o === 'number' ? { value: String(o), label: String(o), raw: o } : { value: String(o.value), label: String(o.label), raw: o.raw !== undefined ? o.raw : o });
    const filtered = normalizedOptions.filter(o => o.label.toLowerCase().includes(search.toLowerCase()) || o.value.toLowerCase().includes(search.toLowerCase()));

    const handleSelect = (val) => {
        onChange(val);
        setIsOpen(false);
        setSearch('');
    };

    return (
        <div ref={wrapperRef} style={{ position: 'relative' }}>
            <div 
                className="form-input" 
                style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', cursor: 'pointer', borderColor: isOpen ? 'var(--accent-green)' : (required && !value ? 'var(--accent-red)' : '') }} 
                onClick={() => setIsOpen(!isOpen)}
            >
                <span style={{ color: value ? 'var(--text-primary)' : 'var(--text-secondary)' }}>
                    {value ? (normalizedOptions.find(o => o.value === String(value))?.label || value) : placeholder}
                </span>
                {isOpen ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
            </div>

            {isOpen && (
                <div style={{ position: 'absolute', top: '100%', left: 0, right: 0, backgroundColor: 'var(--bg-surface)', border: '1px solid var(--border-color)', borderRadius: '8px', marginTop: '4px', zIndex: 100, boxShadow: '0 8px 30px rgba(0,0,0,0.8)', overflow: 'hidden' }}>
                    <div style={{ padding: '8px', borderBottom: '1px solid var(--border-color)' }}>
                        <input 
                            type="text" 
                            className="form-input" 
                            style={{ padding: '8px', fontSize: '14px', borderColor: 'transparent', backgroundColor: 'var(--bg-elevated)' }} 
                            placeholder="Search..." 
                            value={search} 
                            onChange={e => { 
                                setSearch(e.target.value); 
                                if(freeText) onChange(e.target.value); 
                            }}
                            onKeyDown={e => {
                                if (e.key === 'Enter') {
                                    e.preventDefault();
                                    if (onAddNew) {
                                        onAddNew(search);
                                        setIsOpen(false);
                                        setSearch('');
                                    } else if (filtered.length > 0) {
                                        handleSelect(filtered[0].value);
                                    }
                                }
                            }}
                        />
                    </div>
                    <div style={{ maxHeight: '200px', overflowY: 'auto' }}>
                        {filtered.length > 0 ? filtered.map((o, i) => (
                            <div key={i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '12px 16px', cursor: 'pointer', borderBottom: '1px solid rgba(255,255,255,0.02)' }} onMouseOver={(e) => e.currentTarget.style.backgroundColor='var(--bg-elevated)'} onMouseOut={(e) => e.currentTarget.style.backgroundColor='transparent'}>
                                <div style={{ flex: 1 }} onClick={() => handleSelect(o.value)}>{o.label}</div>
                                {onDelete && (
                                    <button onClick={(e) => { e.stopPropagation(); onDelete(o.raw); }} style={{ background: 'transparent', border: 'none', color: 'var(--accent-red)', cursor: 'pointer', padding: '4px' }}>
                                        <Trash2 size={14} />
                                    </button>
                                )}
                            </div>
                        )) : (
                            <div style={{ padding: '12px 16px', color: 'var(--text-secondary)', textAlign: 'center', fontSize: '13px' }}>No results found</div>
                        )}
                    </div>
                    {onAddNew && (
                        <div style={{ padding: '8px', borderTop: '1px solid var(--border-color)', backgroundColor: 'var(--bg-elevated)' }}>
                            <button className="btn-action btn-credit" style={{ width: '100%', justifyContent: 'center', fontSize: '13px', padding: '8px' }} onClick={(e) => { e.preventDefault(); onAddNew(search); setIsOpen(false); setSearch(''); }}>
                                <Plus size={14} /> {addNewText} {search && `"${search}"`}
                            </button>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
};
