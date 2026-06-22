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

        // Mock Inventory Data
        const mockInventory = [
            { Item_ID: 'ITM001', Item_Name: 'Premium Wireless Headphones', Current_Stock: 45, Min_Stock: 10, Purchase_Price: 120.00, Supplier_ID: 'SUP01' },
            { Item_ID: 'ITM002', Item_Name: 'Mechanical Keyboard (Red Switches)', Current_Stock: 12, Min_Stock: 15, Purchase_Price: 85.50, Supplier_ID: 'SUP02' },
            { Item_ID: 'ITM003', Item_Name: 'Ergonomic Office Chair', Current_Stock: 5, Min_Stock: 8, Purchase_Price: 250.00, Supplier_ID: 'SUP01' },
            { Item_ID: 'ITM004', Item_Name: '27" 4K Monitor', Current_Stock: 22, Min_Stock: 5, Purchase_Price: 320.00, Supplier_ID: 'SUP03' },
            { Item_ID: 'ITM005', Item_Name: 'USB-C Hub (7-in-1)', Current_Stock: 105, Min_Stock: 20, Purchase_Price: 25.00, Supplier_ID: 'SUP02' },
            { Item_ID: 'ITM006', Item_Name: 'Wireless Mouse', Current_Stock: 8, Min_Stock: 10, Purchase_Price: 45.00, Supplier_ID: 'SUP03' }
        ];

        // Mock Stats Data
        if (url.includes('/stats')) {
            const totalItems = mockInventory.reduce((sum, item) => sum + item.Current_Stock, 0);
            const lowStockCount = mockInventory.filter(item => item.Current_Stock <= item.Min_Stock).length;
            
            return new Response(JSON.stringify({
                total_items: totalItems,
                low_stock_count: lowStockCount
            }), { status: 200, headers: { 'Content-Type': 'application/json' } });
        }

        // Return Mock Inventory Data
        if (url.includes('/inventory')) {
            return new Response(JSON.stringify(mockInventory), { status: 200, headers: { 'Content-Type': 'application/json' } });
        }

        // Mock Inventory History Data
        if (url.includes('/history')) {
            return new Response(JSON.stringify([
                { id: 1, item_name: 'Premium Wireless Headphones', action: 'RESTOCK', quantity: 50, unit_price: 120.00, timestamp: '2026-06-20 09:15:00', contact_name: 'TechSupplier Inc', bill_no: 'BILL-001' },
                { id: 2, item_name: 'Ergonomic Office Chair', action: 'RESTOCK', quantity: 10, unit_price: 250.00, timestamp: '2026-06-18 11:30:00', contact_name: 'TechSupplier Inc', bill_no: 'BILL-001' },
                { id: 3, item_name: 'Premium Wireless Headphones', action: 'CONSUME', quantity: 5, unit_price: 150.00, timestamp: '2026-06-21 14:00:00', contact_name: 'Walk-in Customer', bill_no: 'BILL-002', comment: 'Sold to walk-in customer' }
            ]), { status: 200, headers: { 'Content-Type': 'application/json' } });
        }

        // Mock Ledger / Transactions Data
        if (url.includes('/ledger') || url.includes('/transactions')) {
            return new Response(JSON.stringify([
                { id: 105, date: '2026-06-21 14:30:00', type: 'Credit', amount: 4500.00, merchant: 'Sales', account: 'Bank', category: 'Sales', description: 'Bulk order #8921', balance_after: 45200.50, credit: 4500.00, debit: 0, balance: 45200.50 },
                { id: 104, date: '2026-06-20 09:15:00', type: 'Debit', amount: 1200.00, merchant: 'Inventory', account: 'Bank', category: 'Inventory', description: 'Restock ITM001', balance_after: 40700.50, credit: 0, debit: 1200.00, balance: 40700.50 },
                { id: 103, date: '2026-06-19 16:45:00', type: 'Credit', amount: 320.00, merchant: 'Sales', account: 'Cash', category: 'Sales', description: 'Store walk-in', balance_after: 41900.50, credit: 320.00, debit: 0, balance: 41900.50 },
                { id: 102, date: '2026-06-18 11:00:00', type: 'Debit', amount: 85.00, merchant: 'Utilities', account: 'Cash', category: 'Utilities', description: 'Internet bill', balance_after: 41580.50, credit: 0, debit: 85.00, balance: 41580.50 },
                { id: 101, date: '2026-06-15 10:00:00', type: 'Credit', amount: 15000.00, merchant: 'Investment', account: 'Bank', category: 'Investment', description: 'Initial capital', balance_after: 41665.50, credit: 15000.00, debit: 0, balance: 41665.50 },
                { id: 100, date: '2026-05-28 14:00:00', type: 'Credit', amount: 26665.50, merchant: 'Sales', account: 'Bank', category: 'Sales', description: 'May bulk order', balance_after: 26665.50, credit: 26665.50, debit: 0, balance: 26665.50 }
            ]), { status: 200, headers: { 'Content-Type': 'application/json' } });
        }

        // Default empty array response to prevent .filter() crashes
        return new Response('[]', { status: 200, headers: { 'Content-Type': 'application/json' } });
    };
}
