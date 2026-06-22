export function setupMockApi() {
    if (!window.location.hostname.includes('github.io')) {
        return; // Only run in GitHub Pages demo
    }

    const originalFetch = window.fetch;
    window.fetch = async (input, init) => {
        let url = '';
        if (typeof input === 'string') {
            url = input;
        } else if (input instanceof URL) {
            url = input.href;
        } else if (input && input.url) {
            url = input.url;
        } else {
            url = String(input);
        }

        // Pass through non-API calls
        if (!url || (!url.startsWith('/api/') && !url.includes('/api/'))) {
            return originalFetch.call(window, input, init);
        }

        // Simulate network delay for realism
        await new Promise(res => setTimeout(res, 400));

        // Mock Summary Data
        if (url.includes('/summary')) {
            return new Response(JSON.stringify({
                balance: 45200.50,
                cash_balance: 15200.00,
                bank_balance: 30000.50,
                income: 12500.00,
                expense: 3400.00
            }), { status: 200, headers: { 'Content-Type': 'application/json' } });
        }

        // Mock Stats Data
        if (url.includes('/stats')) {
            return new Response(JSON.stringify({
                total_items: 124,
                low_stock_count: 3
            }), { status: 200, headers: { 'Content-Type': 'application/json' } });
        }

        // Mock Inventory Data
        if (url.includes('/inventory')) {
            return new Response(JSON.stringify([
                { item_id: 'ITM001', item_name: 'Premium Wireless Headphones', current_stock: 45, min_stock: 10, purchase_price: 120.00, supplier_id: 'SUP01' },
                { item_id: 'ITM002', item_name: 'Mechanical Keyboard (Red Switches)', current_stock: 12, min_stock: 15, purchase_price: 85.50, supplier_id: 'SUP02' },
                { item_id: 'ITM003', item_name: 'Ergonomic Office Chair', current_stock: 5, min_stock: 8, purchase_price: 250.00, supplier_id: 'SUP01' },
                { item_id: 'ITM004', item_name: '27" 4K Monitor', current_stock: 22, min_stock: 5, purchase_price: 320.00, supplier_id: 'SUP03' },
                { item_id: 'ITM005', item_name: 'USB-C Hub (7-in-1)', current_stock: 105, min_stock: 20, purchase_price: 25.00, supplier_id: 'SUP02' },
                { item_id: 'ITM006', item_name: 'Wireless Mouse', current_stock: 8, min_stock: 10, purchase_price: 45.00, supplier_id: 'SUP03' }
            ]), { status: 200, headers: { 'Content-Type': 'application/json' } });
        }

        // Mock Inventory History Data
        if (url.includes('/history')) {
            return new Response(JSON.stringify([
                { id: 1, item_name: 'Premium Wireless Headphones', action: 'RESTOCK', quantity: 50, unit_price: 120.00, timestamp: '2026-06-20 09:15:00', contact_name: 'TechSupplier Inc', bill_no: 'BILL-001' },
                { id: 2, item_name: 'Ergonomic Office Chair', action: 'RESTOCK', quantity: 10, unit_price: 250.00, timestamp: '2026-06-18 11:30:00', contact_name: 'TechSupplier Inc', bill_no: 'BILL-001' },
                { id: 3, item_name: 'Premium Wireless Headphones', action: 'CONSUME', quantity: 5, unit_price: null, timestamp: '2026-06-21 14:00:00', contact_name: '', comment: 'Sold to walk-in customer' }
            ]), { status: 200, headers: { 'Content-Type': 'application/json' } });
        }

        // Mock Ledger / Transactions Data
        if (url.includes('/ledger') || url.includes('/transactions')) {
            return new Response(JSON.stringify([
                { id: 105, date: '2026-06-21 14:30:00', type: 'Credit', amount: 4500.00, merchant: 'Sales', account: 'Bank', category: 'Sales', description: 'Bulk order #8921', balance_after: 45200.50, credit: 4500.00, debit: 0, balance: 45200.50 },
                { id: 104, date: '2026-06-20 09:15:00', type: 'Debit', amount: 1200.00, merchant: 'Inventory', account: 'Bank', category: 'Inventory', description: 'Restock ITM001', balance_after: 40700.50, credit: 0, debit: 1200.00, balance: 40700.50 },
                { id: 103, date: '2026-06-19 16:45:00', type: 'Credit', amount: 320.00, merchant: 'Sales', account: 'Cash', category: 'Sales', description: 'Store walk-in', balance_after: 41900.50, credit: 320.00, debit: 0, balance: 41900.50 },
                { id: 102, date: '2026-06-18 11:00:00', type: 'Debit', amount: 85.00, merchant: 'Utilities', account: 'Cash', category: 'Utilities', description: 'Internet bill', balance_after: 41580.50, credit: 0, debit: 85.00, balance: 41580.50 },
                { id: 101, date: '2026-06-15 10:00:00', type: 'Credit', amount: 15000.00, merchant: 'Investment', account: 'Bank', category: 'Investment', description: 'Initial capital', balance_after: 41665.50, credit: 15000.00, debit: 0, balance: 41665.50 }
            ]), { status: 200, headers: { 'Content-Type': 'application/json' } });
        }

        // Default empty array response to prevent .filter() crashes
        return new Response('[]', { status: 200, headers: { 'Content-Type': 'application/json' } });
    };
}
