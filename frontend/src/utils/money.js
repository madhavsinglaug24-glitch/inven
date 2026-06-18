/** Format rupee amounts consistently (max 2 decimal places, Indian grouping). */
export function formatMoney(value) {
    const n = Number(value);
    if (!Number.isFinite(n)) return '₹0';
    return `₹${n.toLocaleString('en-IN', { minimumFractionDigits: 0, maximumFractionDigits: 2 })}`;
}

/** Prefix + or - for mobile ledger rows. */
export function formatSignedMoney(value, sign) {
    return `${sign}${formatMoney(value).slice(1)}`;
}
