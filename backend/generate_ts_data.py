import json

data = json.load(open(r'src\app\data\actual-activity-records.json'))

FINANCIAL_TYPES = {'Quotation', 'Sales Order', 'Sales Invoice', 'Payment Entry', 'Sales Opportunity'}

lines = []
lines.append("""/**
 * Activity Analytics Dashboard — Complete PDF Dataset & Helpers
 *
 * Contains 1,780 real activity records extracted from the BoxTech
 * Activity Graph UI source data, plus pure-function helpers that
 * power the KPI cards, time-slot bucketing, trend curves, and
 * record-log filtering.
 *
 * NO dummy/random/synthetic data — every record originates from the
 * actual PDF dataset.
 */

// ─── Types ───────────────────────────────────────────────────────

export type GroupByMode = 'hour' | '30min' | 'day' | 'week' | 'month';

export interface ActivityRecord {
  id: number;
  date: string;          // 'YYYY-MM-DD'
  time: string;          // 'HH:mm'
  hourSlot: number;      // 0–23
  halfHourSlot: string;  // '00:00', '00:30', …, '23:30'
  salesperson: string;
  country: string;
  activityType: string;
  client: string;
  amount: number;
  isFinancial: boolean;
}

export interface TimeSlotPoint {
  slot: string;
  label: string;
  activityCount: number;
  uniqueClients: number;
  amount: number;
  isPeak?: boolean;
}

export interface SalespersonBreakdownItem {
  name: string;
  count: number;
  pct: number;
  amount: number;
}

export interface CountryBreakdownItem {
  country: string;
  count: number;
  pct: number;
  clientCount: number;
  amount: number;
}

export interface ActivityTypeBreakdownItem {
  type: string;
  count: number;
  pct: number;
  isFinancial: boolean;
  amount: number;
}

export interface KpiResult {
  totalActivities: number;
  uniqueClients: number;
  sumAmount: number;
  emptyTimeSlots: number;
  totalSlots: number;
  financialCount: number;
  peakSlot: TimeSlotPoint | null;
  avgPerSlot: number;
}

// ─── Constants (derived from the actual PDF data) ────────────────

export const AA_SALESPERSONS = ['Ahmed', 'Ali', 'Fatima', 'Omar', 'Sara'];
export const AA_COUNTRIES    = ['Iraq', 'Jordan', 'Pakistan', 'Saudi Arabia', 'UAE'];
export const AA_ACTIVITY_TYPES = [
  'Comment', 'Communication', 'Email', 'Event', 'Follow-Up',
  'Lead', 'Meeting', 'Note', 'Payment Entry', 'Phone Call',
  'Quotation', 'Sales Invoice', 'Sales Opportunity', 'Sales Order',
  'Task', 'ToDo', 'Visit',
];
export const AA_FINANCIAL_TYPES = new Set([
  'Quotation', 'Sales Order', 'Sales Invoice', 'Payment Entry', 'Sales Opportunity'
]);

// ─── Complete dataset (1,780 records from the PDF) ───────────────

export const ACTIVITY_RECORDS: ActivityRecord[] = [""")

for i, rec in enumerate(data):
    is_fin = rec['amount'] > 0 or rec['activityType'] in FINANCIAL_TYPES
    line = "  {" + \
        f"id:{rec['id']}," + \
        f"date:'{rec['date']}'," + \
        f"time:'{rec['time']}'," + \
        f"hourSlot:{rec['hourSlot']}," + \
        f"halfHourSlot:'{rec['halfHourSlot']}'," + \
        f"salesperson:'{rec['salesperson']}'," + \
        f"country:'{rec['country']}'," + \
        f"activityType:'{rec['activityType']}'," + \
        f"client:'{rec['client']}'," + \
        f"amount:{rec['amount']}," + \
        f"isFinancial:{'true' if is_fin else 'false'}" + \
        "}" + ("," if i < len(data) - 1 else "")
    lines.append(line)

lines.append("""];

// ─── Filter helper ───────────────────────────────────────────────

export function filterRecords(
  records: ActivityRecord[],
  filters: {
    activityType?: string;
    country?: string;
    salesperson?: string;
    fromDate?: string;
    toDate?: string;
  }
): ActivityRecord[] {
  return records.filter(r => {
    if (filters.activityType && filters.activityType !== 'All Activities' && r.activityType !== filters.activityType) return false;
    if (filters.country && filters.country !== 'All Countries' && r.country !== filters.country) return false;
    if (filters.salesperson && filters.salesperson !== 'All Salespersons' && r.salesperson !== filters.salesperson) return false;
    if (filters.fromDate && r.date < filters.fromDate) return false;
    if (filters.toDate && r.date > filters.toDate) return false;
    return true;
  });
}

// ─── Time-slot & Group By trend builder ─────────────────────────

function getWeekNumber(d: Date): { year: number; week: number } {
  const target = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()));
  const dayNr = (target.getUTCDay() + 6) % 7;
  target.setUTCDate(target.getUTCDate() - dayNr + 3);
  const firstThursday = target.getTime();
  target.setUTCMonth(0, 1);
  if (target.getUTCDay() !== 4) {
    target.setUTCMonth(0, 1 + ((4 - target.getUTCDay()) + 7) % 7);
  }
  const weekNumber = 1 + Math.ceil((firstThursday - target.getTime()) / 604800000);
  return { year: target.getUTCFullYear(), week: weekNumber };
}

function formatDate(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

export function buildTimeSlotTrend(
  filtered: ActivityRecord[],
  groupBy: GroupByMode,
  fromDate?: string,
  toDate?: string
): TimeSlotPoint[] {
  if (groupBy === 'hour') {
    const slots: TimeSlotPoint[] = [];
    const countMap = new Map<number, number>();
    const clientMap = new Map<number, Set<string>>();
    const amountMap = new Map<number, number>();

    for (let h = 0; h < 24; h++) {
      countMap.set(h, 0);
      clientMap.set(h, new Set());
      amountMap.set(h, 0);
    }

    for (const r of filtered) {
      countMap.set(r.hourSlot, (countMap.get(r.hourSlot) || 0) + 1);
      clientMap.get(r.hourSlot)?.add(r.client);
      amountMap.set(r.hourSlot, (amountMap.get(r.hourSlot) || 0) + r.amount);
    }

    let maxCount = 0;
    for (let h = 0; h < 24; h++) {
      const c = countMap.get(h) || 0;
      if (c > maxCount) maxCount = c;
    }

    for (let h = 0; h < 24; h++) {
      const slotStr = `${String(h).padStart(2, '0')}:00`;
      const count = countMap.get(h) || 0;
      slots.push({
        slot: slotStr,
        label: slotStr,
        activityCount: count,
        uniqueClients: clientMap.get(h)?.size || 0,
        amount: amountMap.get(h) || 0,
        isPeak: count === maxCount && count > 0,
      });
    }
    return slots;
  }

  if (groupBy === '30min') {
    const slots: TimeSlotPoint[] = [];
    const countMap = new Map<string, number>();
    const clientMap = new Map<string, Set<string>>();
    const amountMap = new Map<string, number>();

    const halfHourList: string[] = [];
    for (let h = 0; h < 24; h++) {
      const s0 = `${String(h).padStart(2, '0')}:00`;
      const s1 = `${String(h).padStart(2, '0')}:30`;
      halfHourList.push(s0, s1);
      countMap.set(s0, 0);
      countMap.set(s1, 0);
      clientMap.set(s0, new Set());
      clientMap.set(s1, new Set());
      amountMap.set(s0, 0);
      amountMap.set(s1, 0);
    }

    for (const r of filtered) {
      const k = r.halfHourSlot;
      countMap.set(k, (countMap.get(k) || 0) + 1);
      clientMap.get(k)?.add(r.client);
      amountMap.set(k, (amountMap.get(k) || 0) + r.amount);
    }

    let maxCount = 0;
    for (const s of halfHourList) {
      const c = countMap.get(s) || 0;
      if (c > maxCount) maxCount = c;
    }

    for (const s of halfHourList) {
      const count = countMap.get(s) || 0;
      slots.push({
        slot: s,
        label: s,
        activityCount: count,
        uniqueClients: clientMap.get(s)?.size || 0,
        amount: amountMap.get(s) || 0,
        isPeak: count === maxCount && count > 0,
      });
    }
    return slots;
  }

  if (groupBy === 'day') {
    // Determine bounds
    let minDateStr = fromDate;
    let maxDateStr = toDate;

    if (!minDateStr || !maxDateStr) {
      const dates = filtered.map(r => r.date).sort();
      minDateStr = minDateStr || (dates.length ? dates[0] : '2025-01-01');
      maxDateStr = maxDateStr || (dates.length ? dates[dates.length - 1] : '2026-08-09');
    }

    const countMap = new Map<string, number>();
    const clientMap = new Map<string, Set<string>>();
    const amountMap = new Map<string, number>();

    const start = new Date(minDateStr + 'T00:00:00');
    const end = new Date(maxDateStr + 'T00:00:00');
    const current = new Date(start);
    const dayKeys: string[] = [];

    // Max 400 days safeguard if wide span
    while (current <= end) {
      const ds = formatDate(current);
      dayKeys.push(ds);
      countMap.set(ds, 0);
      clientMap.set(ds, new Set());
      amountMap.set(ds, 0);
      current.setDate(current.getDate() + 1);
      if (dayKeys.length > 700) break;
    }

    for (const r of filtered) {
      if (countMap.has(r.date)) {
        countMap.set(r.date, (countMap.get(r.date) || 0) + 1);
        clientMap.get(r.date)?.add(r.client);
        amountMap.set(r.date, (amountMap.get(r.date) || 0) + r.amount);
      }
    }

    let maxCount = 0;
    for (const dk of dayKeys) {
      const c = countMap.get(dk) || 0;
      if (c > maxCount) maxCount = c;
    }

    return dayKeys.map(dk => {
      const dObj = new Date(dk + 'T00:00:00');
      const label = dObj.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
      const count = countMap.get(dk) || 0;
      return {
        slot: dk,
        label,
        activityCount: count,
        uniqueClients: clientMap.get(dk)?.size || 0,
        amount: amountMap.get(dk) || 0,
        isPeak: count === maxCount && count > 0,
      };
    });
  }

  if (groupBy === 'week') {
    let minDateStr = fromDate;
    let maxDateStr = toDate;
    if (!minDateStr || !maxDateStr) {
      const dates = filtered.map(r => r.date).sort();
      minDateStr = minDateStr || (dates.length ? dates[0] : '2025-01-01');
      maxDateStr = maxDateStr || (dates.length ? dates[dates.length - 1] : '2026-08-09');
    }

    const countMap = new Map<string, number>();
    const clientMap = new Map<string, Set<string>>();
    const amountMap = new Map<string, number>();
    const weekLabels = new Map<string, string>();
    const weekKeys: string[] = [];

    const start = new Date(minDateStr + 'T00:00:00');
    const end = new Date(maxDateStr + 'T00:00:00');
    const current = new Date(start);

    while (current <= end) {
      const wn = getWeekNumber(current);
      const wk = `${wn.year}-W${String(wn.week).padStart(2, '0')}`;
      if (!countMap.has(wk)) {
        weekKeys.push(wk);
        countMap.set(wk, 0);
        clientMap.set(wk, new Set());
        amountMap.set(wk, 0);
        const wStart = new Date(current);
        const wEnd = new Date(current);
        wEnd.setDate(wEnd.getDate() + 6);
        const l = `${wStart.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}`;
        weekLabels.set(wk, `W${wn.week} (${l})`);
      }
      current.setDate(current.getDate() + 7);
    }

    for (const r of filtered) {
      const dObj = new Date(r.date + 'T00:00:00');
      const wn = getWeekNumber(dObj);
      const wk = `${wn.year}-W${String(wn.week).padStart(2, '0')}`;
      if (countMap.has(wk)) {
        countMap.set(wk, (countMap.get(wk) || 0) + 1);
        clientMap.get(wk)?.add(r.client);
        amountMap.set(wk, (amountMap.get(wk) || 0) + r.amount);
      }
    }

    let maxCount = 0;
    for (const wk of weekKeys) {
      const c = countMap.get(wk) || 0;
      if (c > maxCount) maxCount = c;
    }

    return weekKeys.map(wk => {
      const count = countMap.get(wk) || 0;
      return {
        slot: wk,
        label: weekLabels.get(wk) || wk,
        activityCount: count,
        uniqueClients: clientMap.get(wk)?.size || 0,
        amount: amountMap.get(wk) || 0,
        isPeak: count === maxCount && count > 0,
      };
    });
  }

  // Month
  let minDateStr = fromDate;
  let maxDateStr = toDate;
  if (!minDateStr || !maxDateStr) {
    const dates = filtered.map(r => r.date).sort();
    minDateStr = minDateStr || (dates.length ? dates[0] : '2025-01-01');
    maxDateStr = maxDateStr || (dates.length ? dates[dates.length - 1] : '2026-08-09');
  }

  const start = new Date(minDateStr + 'T00:00:00');
  const end = new Date(maxDateStr + 'T00:00:00');
  const current = new Date(start.getFullYear(), start.getMonth(), 1);
  const endMonth = new Date(end.getFullYear(), end.getMonth(), 1);

  const monthKeys: string[] = [];
  const countMap = new Map<string, number>();
  const clientMap = new Map<string, Set<string>>();
  const amountMap = new Map<string, number>();
  const monthLabels = new Map<string, string>();

  while (current <= endMonth) {
    const mk = `${current.getFullYear()}-${String(current.getMonth() + 1).padStart(2, '0')}`;
    monthKeys.push(mk);
    countMap.set(mk, 0);
    clientMap.set(mk, new Set());
    amountMap.set(mk, 0);
    monthLabels.set(mk, current.toLocaleDateString('en-US', { month: 'short', year: 'numeric' }));
    current.setMonth(current.getMonth() + 1);
  }

  for (const r of filtered) {
    const mk = r.date.substring(0, 7);
    if (countMap.has(mk)) {
      countMap.set(mk, (countMap.get(mk) || 0) + 1);
      clientMap.get(mk)?.add(r.client);
      amountMap.set(mk, (amountMap.get(mk) || 0) + r.amount);
    }
  }

  let maxCount = 0;
  for (const mk of monthKeys) {
    const c = countMap.get(mk) || 0;
    if (c > maxCount) maxCount = c;
  }

  return monthKeys.map(mk => {
    const count = countMap.get(mk) || 0;
    return {
      slot: mk,
      label: monthLabels.get(mk) || mk,
      activityCount: count,
      uniqueClients: clientMap.get(mk)?.size || 0,
      amount: amountMap.get(mk) || 0,
      isPeak: count === maxCount && count > 0,
    };
  });
}

// ─── KPI helpers ─────────────────────────────────────────────────

export function computeKpis(
  filtered: ActivityRecord[],
  trendData: TimeSlotPoint[]
): KpiResult {
  const totalActivities = filtered.length;
  const uniqueClients = new Set(filtered.map(r => r.client)).size;
  const sumAmount = filtered.reduce((s, r) => s + r.amount, 0);
  const financialCount = filtered.filter(r => r.isFinancial).length;

  const totalSlots = trendData.length;
  const emptyTimeSlots = trendData.filter(p => p.activityCount === 0).length;

  let peakSlot: TimeSlotPoint | null = null;
  if (trendData.length) {
    peakSlot = trendData.reduce((best, p) => p.activityCount > (best?.activityCount || 0) ? p : best, trendData[0]);
    if (peakSlot && peakSlot.activityCount === 0) peakSlot = null;
  }

  const avgPerSlot = totalSlots > 0 ? Number((totalActivities / totalSlots).toFixed(1)) : 0;

  return {
    totalActivities,
    uniqueClients,
    sumAmount,
    emptyTimeSlots,
    totalSlots,
    financialCount,
    peakSlot,
    avgPerSlot,
  };
}

// ─── Salesperson Breakdown ──────────────────────────────────────

export function buildSalespersonBreakdown(filtered: ActivityRecord[]): SalespersonBreakdownItem[] {
  const countMap = new Map<string, number>();
  const amountMap = new Map<string, number>();
  for (const sp of AA_SALESPERSONS) {
    countMap.set(sp, 0);
    amountMap.set(sp, 0);
  }
  for (const r of filtered) {
    countMap.set(r.salesperson, (countMap.get(r.salesperson) || 0) + 1);
    amountMap.set(r.salesperson, (amountMap.get(r.salesperson) || 0) + r.amount);
  }
  const total = filtered.length || 1;
  return AA_SALESPERSONS.map(name => {
    const count = countMap.get(name) || 0;
    return {
      name,
      count,
      pct: Math.round((count / total) * 100),
      amount: amountMap.get(name) || 0,
    };
  }).sort((a, b) => b.count - a.count);
}

// ─── Country Breakdown ──────────────────────────────────────────

export function buildCountryBreakdown(filtered: ActivityRecord[]): CountryBreakdownItem[] {
  const countMap = new Map<string, number>();
  const clientMap = new Map<string, Set<string>>();
  const amountMap = new Map<string, number>();
  for (const c of AA_COUNTRIES) {
    countMap.set(c, 0);
    clientMap.set(c, new Set());
    amountMap.set(c, 0);
  }
  for (const r of filtered) {
    countMap.set(r.country, (countMap.get(r.country) || 0) + 1);
    clientMap.get(r.country)?.add(r.client);
    amountMap.set(r.country, (amountMap.get(r.country) || 0) + r.amount);
  }
  const total = filtered.length || 1;
  return AA_COUNTRIES.map(country => {
    const count = countMap.get(country) || 0;
    return {
      country,
      count,
      pct: Math.round((count / total) * 100),
      clientCount: clientMap.get(country)?.size || 0,
      amount: amountMap.get(country) || 0,
    };
  }).sort((a, b) => b.count - a.count);
}

// ─── Activity Type Breakdown ────────────────────────────────────

export function buildActivityTypeBreakdown(filtered: ActivityRecord[]): ActivityTypeBreakdownItem[] {
  const countMap = new Map<string, number>();
  const amountMap = new Map<string, number>();
  for (const r of filtered) {
    countMap.set(r.activityType, (countMap.get(r.activityType) || 0) + 1);
    amountMap.set(r.activityType, (amountMap.get(r.activityType) || 0) + r.amount);
  }
  const total = filtered.length || 1;
  return [...countMap.entries()]
    .map(([type, count]) => ({
      type,
      count,
      pct: Math.round((count / total) * 100),
      isFinancial: (amountMap.get(type) || 0) > 0 || AA_FINANCIAL_TYPES.has(type),
      amount: amountMap.get(type) || 0,
    }))
    .sort((a, b) => b.count - a.count);
}
""")

output = '\n'.join(lines)
with open(r'src\app\data\activity-analytics-data.ts', 'w', encoding='utf-8') as f:
    f.write(output)

print(f'Generated activity-analytics-data.ts with {len(data)} records')
print(f'File size: {len(output)} bytes')
