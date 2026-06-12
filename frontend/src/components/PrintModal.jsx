import React, { useState, useEffect } from 'react';
import { Printer, X, CheckSquare, Square } from 'lucide-react';

export const PrintModal = ({ isOpen, onClose, columns, data, title }) => {
    const [selectedCols, setSelectedCols] = useState({});

    useEffect(() => {
        const initial = {};
        columns.forEach(c => initial[c.key] = true);
        setSelectedCols(initial);
    }, [columns, isOpen]);

    if (!isOpen) return null;

    const handlePrint = () => {
        const printWindow = window.open('', '_blank');
        const printDoc = printWindow.document;

        const tableHeaders = columns
            .filter(c => selectedCols[c.key])
            .map(c => `<th style="border: 1px solid #ddd; padding: 8px; text-align: left; background-color: #f2f2f2;">${c.label}</th>`)
            .join('');

        const tableRows = data.map(row => {
            return `<tr>${columns.filter(c => selectedCols[c.key]).map(c => {
                let cellData = row[c.key];
                if (c.render) {
                    cellData = c.render(row);
                    if (typeof cellData === 'object' && cellData !== null) {
                        cellData = cellData.props ? cellData.props.children : cellData;
                        if (typeof cellData === 'object') cellData = row[c.key];
                    }
                }
                return `<td style="border: 1px solid #ddd; padding: 8px;">${cellData ?? ''}</td>`;
            }).join('')}</tr>`;
        }).join('');

        printDoc.write(`
            <html>
                <head>
                    <title>Print - ${title}</title>
                    <style>
                        body { font-family: Arial, sans-serif; padding: 20px; color: #333; }
                        h1 { text-align: center; margin-bottom: 20px; }
                        table { width: 100%; border-collapse: collapse; margin-top: 20px; font-size: 14px; }
                        th { font-weight: bold; }
                    </style>
                </head>
                <body>
                    <h1>${title}</h1>
                    <table>
                        <thead><tr>${tableHeaders}</tr></thead>
                        <tbody>${tableRows}</tbody>
                    </table>
                </body>
            </html>
        `);
        printDoc.close();
        printWindow.focus();
        setTimeout(() => {
            printWindow.print();
            printWindow.close();
            onClose();
        }, 250);
    };

    return (
        <div className="modal-overlay">
            <div className="modal-content fade-in" style={{ maxWidth: '400px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                    <h2 style={{ margin: 0, fontSize: '18px' }}>Print Columns</h2>
                    <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-secondary)' }}>
                        <X size={20} />
                    </button>
                </div>
                
                <div style={{ marginBottom: '24px' }}>
                    <p style={{ marginBottom: '16px', fontSize: '14px', color: 'var(--text-secondary)' }}>Select the columns you want to include in the print:</p>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', maxHeight: '300px', overflowY: 'auto' }}>
                        {columns.map(col => (
                            <div 
                                key={col.key} 
                                onClick={() => setSelectedCols({...selectedCols, [col.key]: !selectedCols[col.key]})}
                                style={{ 
                                    display: 'flex', alignItems: 'center', gap: '12px', cursor: 'pointer', 
                                    padding: '12px 16px', borderRadius: '8px', 
                                    backgroundColor: selectedCols[col.key] ? 'var(--accent-green-dim)' : 'transparent',
                                    border: `1px solid ${selectedCols[col.key] ? 'var(--accent-green)' : 'var(--border-color)'}`,
                                    transition: 'all 0.2s'
                                }}
                            >
                                {selectedCols[col.key] ? (
                                    <CheckSquare size={20} color="var(--accent-green)" />
                                ) : (
                                    <Square size={20} color="var(--text-secondary)" />
                                )}
                                <span style={{ fontSize: '15px', fontWeight: 500, color: selectedCols[col.key] ? 'var(--text-primary)' : 'var(--text-secondary)' }}>
                                    {col.label}
                                </span>
                            </div>
                        ))}
                    </div>
                </div>

                <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px' }}>
                    <button className="btn-action" onClick={onClose}>Cancel</button>
                    <button className="btn-action btn-credit" onClick={handlePrint}>
                        <Printer size={16} /> Print
                    </button>
                </div>
            </div>
        </div>
    );
};
