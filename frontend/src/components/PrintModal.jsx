 import React, { useState, useEffect } from 'react';
import { Printer, X } from 'lucide-react';

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
                    // Try to extract text if render returns JSX
                    cellData = c.render(row);
                    if (typeof cellData === 'object' && cellData !== null) {
                        cellData = cellData.props ? cellData.props.children : cellData;
                        // Extremely naive extraction, fallback to raw data if needed
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
                    <p style={{ marginBottom: '12px', fontSize: '14px', color: 'var(--text-secondary)' }}>Select the columns you want to include in the print:</p>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', maxHeight: '300px', overflowY: 'auto', padding: '4px' }}>
                        {columns.map(col => (
                            <label key={col.key} style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer', fontSize: '15px', fontWeight: 500 }}>
                                <input 
                                    type="checkbox" 
                                    checked={selectedCols[col.key] || false}
                                    onChange={(e) => setSelectedCols({...selectedCols, [col.key]: e.target.checked})}
                                    style={{ width: '18px', height: '18px', cursor: 'pointer' }}
                                />
                                {col.label}
                            </label>
                        ))}
                    </div>
                </div>

                <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px' }}>
                    <button className="btn-secondary" onClick={onClose}>Cancel</button>
                    <button className="btn-primary" onClick={handlePrint} style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <Printer size={16} /> Print
                    </button>
                </div>
            </div>
        </div>
    );
};
