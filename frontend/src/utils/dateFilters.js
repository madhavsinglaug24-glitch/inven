/** @returns {{ start: string, end: string }} YYYY-MM-DD bounds for the previous calendar month */
export function getPreviousMonthRange(refDate = new Date()) {
    const year = refDate.getFullYear();
    const month = refDate.getMonth();
    const startDate = new Date(year, month - 1, 1);
    const endDate = new Date(year, month, 0);

    const toYmd = (d) => {
        const y = d.getFullYear();
        const m = String(d.getMonth() + 1).padStart(2, '0');
        const day = String(d.getDate()).padStart(2, '0');
        return `${y}-${m}-${day}`;
    };

    return { start: toYmd(startDate), end: toYmd(endDate) };
}

export function isDateInRange(dateValue, rangeStart, rangeEnd) {
    const d = new Date(dateValue);
    if (rangeStart) {
        const startD = new Date(rangeStart);
        startD.setHours(0, 0, 0, 0);
        if (d < startD) return false;
    }
    if (rangeEnd) {
        const endD = new Date(rangeEnd);
        endD.setHours(23, 59, 59, 999);
        if (d > endD) return false;
    }
    return true;
}

export function matchesTimeFilter(dateValue, timeFilter, rangeStart, rangeEnd, refDate = new Date()) {
    if (timeFilter === 'all') return true;
    const d = new Date(dateValue);
    if (timeFilter === 'month') {
        return d.getMonth() === refDate.getMonth() && d.getFullYear() === refDate.getFullYear();
    }
    if (timeFilter === 'year') {
        return d.getFullYear() === refDate.getFullYear();
    }
    if (timeFilter === 'custom' || timeFilter === 'last_month') {
        return isDateInRange(dateValue, rangeStart, rangeEnd);
    }
    return true;
}
