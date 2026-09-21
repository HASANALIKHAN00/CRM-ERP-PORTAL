/**
 * Activity Analytics — pure-function helpers.
 *
 * These functions are data-source agnostic: they take an ActivityRecord[]
 * (now fetched live from QueryService.getActivityLogRecords(), see
 * activity-analysis.ts) and compute the KPI cards, time-slot bucketing,
 * trend curves, and record-log filtering/grouping used by the Activity
 * Analysis page. No records are hardcoded here.
 *
 * Some real records have null salesperson/country/client fields where the
 * underlying ERPNext table genuinely has no such column (e.g. Sales Order
 * has no owner field) -- see get_activity_log_records on the backend for
 * the full per-source breakdown. These functions treat null the same as
 * "unattributed" rather than crashing or guessing a value.
 */

// ─── Types ───────────────────────────────────────────────────────

export type GroupByMode = 'hour' | '30min' | 'day' | 'week' | 'month' | 'year';

export interface ActivityRecord {
  id: string;             // e.g. 'CAD-123', 'CALL-a1b2', 'OPP-...' -- source-tagged, unique across all branches
  date: string;           // 'YYYY-MM-DD'
  time: string;           // 'HH:mm', or '' when the source record has no time component
  hourSlot: number;       // 0–23, or -1 when the source record has no time component
  halfHourSlot: string;   // '00:00'…'23:30', or '' when the source record has no time component
  salesperson: string;    // '' when the underlying table has no salesperson/owner column (see backend docstring)
  country: string;        // '' when not resolvable from a customer join
  activityType: string;
  client: string;         // '' when the underlying table has no customer link (e.g. Task, ToDo)
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

// ─── Constants ─────────────────────────────────────────────────────
//
// AA_SALESPERSONS / AA_COUNTRIES were a hardcoded 5-value fake list in the
// old mock build -- buildSalespersonBreakdown/buildCountryBreakdown below
// used to iterate ONLY over those 5 names/countries, so any real employee
// or country outside that exact set was silently dropped from those two
// panels even though it was still counted in the overall total (breaking
// the percentages). Both breakdown functions now derive their category
// list from whatever is actually present in the records passed in, so
// real data is no longer capped at 5 fake values.
//
// AA_ACTIVITY_TYPES was assumed to be a fixed, exhaustive list mirroring
// the backend's 8 source tables -- confirmed WRONG against production on
// 2026-08-22: customer_activity_details.activity_type is a free-form/
// org-configured field, not a fixed enum, and real data included types
// never anticipated here (Text Message, WhatsApp, Presentation,
// "Meeting/ Visit", "Quotation / Commercial Offer", Samples Sales, Online
// Meeting, LinkedIn, Pilot Order, Development), while several assumed
// types (Comment, Communication, Follow-Up, Note, Task, Visit, Meeting)
// had zero real occurrences. A hardcoded list here would silently make
// real records unselectable in the Activity Type filter, so the
// component now derives its dropdown options live from fetched records
// (see activity-analysis.ts's ngOnInit) instead of importing this.
// Left exported for reference/documentation only -- not used by the
// component's filter UI.
export const AA_ACTIVITY_TYPES = [
  'Comment', 'Communication', 'Email', 'Event', 'Follow-Up',
  'Lead', 'Meeting', 'Note', 'Payment Entry', 'Phone Call',
  'Quotation', 'Sales Invoice', 'Sales Opportunity', 'Sales Order',
  'Task', 'ToDo', 'Visit',
];
export const AA_FINANCIAL_TYPES = new Set([
  'Quotation', 'Sales Order', 'Sales Invoice', 'Payment Entry', 'Sales Opportunity'
]);



export interface ActivityFilterCriteria {
  activityType?: string;
  country?: string;
  region?: string;
  salesperson?: string;
  team?: string;
  leadStatus?: string;
  salesStage?: string;
  callResult?: string;
  followupStatus?: string;
  timeOfDay?: string;
  timeFrom?: string;
  timeTo?: string;
  customer?: string;
  fromDate?: string;
  toDate?: string;
  selectedRange?: number;
}

export function filterRecords(
  records: ActivityRecord[],
  filters: ActivityFilterCriteria
): ActivityRecord[] {
  let resolvedFromDate = filters.fromDate;
  let resolvedToDate = filters.toDate;

  if (!resolvedFromDate && !resolvedToDate && filters.selectedRange) {
    const dates = records.map(r => r.date).sort();
    const maxDateStr = dates.length ? dates[dates.length - 1] : '2026-08-08';
    const maxDateObj = new Date(maxDateStr + 'T00:00:00');

    if (filters.selectedRange === 1) {
      resolvedFromDate = maxDateStr;
      resolvedToDate = maxDateStr;
    } else {
      const fromObj = new Date(maxDateObj);
      fromObj.setDate(fromObj.getDate() - (filters.selectedRange - 1));
      resolvedFromDate = formatDate(fromObj);
      resolvedToDate = maxDateStr;
    }
  }

  const cleanCallResult = (res?: string) => {
    if (!res || res === 'All') return undefined;
    return res.replace(/^[^\w]+/, '').trim().toLowerCase();
  };

  const normCallResult = cleanCallResult(filters.callResult);

  return records.filter(r => {
    // Salesperson
    if (filters.salesperson && filters.salesperson !== 'All' && filters.salesperson !== 'All Salespersons') {
      if (r.salesperson.toLowerCase() !== filters.salesperson.toLowerCase()) return false;
    }

    // Country / Region
    const region = filters.region || filters.country;
    if (region && region !== 'All' && region !== 'All Countries') {
      if (r.country.toLowerCase() !== region.toLowerCase()) return false;
    }

    // Activity Type
    if (filters.activityType && filters.activityType !== 'All' && filters.activityType !== 'All Activities') {
      const actLower = filters.activityType.toLowerCase();
      const rActLower = r.activityType.toLowerCase();
      if (actLower === 'call') {
        if (rActLower !== 'phone call' && rActLower !== 'call') return false;
      } else if (rActLower !== actLower) {
        return false;
      }
    }

    // Team: ActivityRecord has no department field (it's not derivable
    // from any of the 8 unioned source tables), so team filtering isn't
    // supported here. Team-scoped views should use QueryService's real
    // department-joined endpoints (e.g. getActivityByTeam) instead.

    // Lead Status
    if (filters.leadStatus && filters.leadStatus !== 'All') {
      const lsLower = filters.leadStatus.toLowerCase();
      if (lsLower === 'lead' || lsLower === 'open' || lsLower === 'interested') {
        if (r.activityType !== 'Lead' && r.activityType !== 'Note' && r.activityType !== 'Comment') return false;
      } else if (lsLower === 'converted' || lsLower === 'opportunity') {
        if (r.activityType !== 'Sales Opportunity' && r.activityType !== 'Quotation' && r.activityType !== 'Sales Order') return false;
      } else if (lsLower === 'lost' || lsLower === 'do not contact') {
        if (r.amount > 0) return false;
      }
    }

    // Sales Stage
    if (filters.salesStage && filters.salesStage !== 'All') {
      const ssLower = filters.salesStage.toLowerCase();
      if (ssLower.includes('prospect') || ssLower.includes('qualif') || ssLower.includes('need') || ssLower.includes('value') || ssLower.includes('decision')) {
        if (r.activityType !== 'Sales Opportunity' && r.activityType !== 'Meeting' && r.activityType !== 'Communication' && r.activityType !== 'Phone Call') return false;
      } else if (ssLower.includes('proposal') || ssLower.includes('quote')) {
        if (r.activityType !== 'Quotation' && r.activityType !== 'Sales Opportunity') return false;
      } else if (ssLower.includes('won') || ssLower.includes('order') || ssLower.includes('invoice')) {
        if (r.activityType !== 'Sales Order' && r.activityType !== 'Sales Invoice' && r.activityType !== 'Payment Entry') return false;
      }
    }

    // Call Result
    if (normCallResult) {
      if (normCallResult === 'complete') {
        if (r.activityType === 'Phone Call' || r.isFinancial || r.amount > 0 || r.activityType === 'Meeting' || r.activityType === 'Event' || r.activityType === 'Visit') {
          // matches
        } else {
          return false;
        }
      } else if (normCallResult === 'in progress') {
        if (r.activityType !== 'ToDo' && r.activityType !== 'Task' && r.activityType !== 'Follow-Up') return false;
      } else if (normCallResult === 'rejected') {
        if (r.isFinancial || r.amount > 0) return false;
      }
    }

    // Follow-up Status
    if (filters.followupStatus && filters.followupStatus !== 'All') {
      const fuLower = filters.followupStatus.toLowerCase();
      if (fuLower === 'overdue' || fuLower === 'open') {
        if (r.activityType !== 'ToDo' && r.activityType !== 'Task' && r.activityType !== 'Follow-Up') return false;
      } else if (fuLower === 'closed') {
        if (r.activityType === 'ToDo' || r.activityType === 'Task' || r.activityType === 'Follow-Up') return false;
      }
    }

    // Time of Day
    if (filters.timeOfDay && filters.timeOfDay !== 'All') {
      const tod = filters.timeOfDay.toLowerCase();
      const h = r.hourSlot;
      if (tod === 'morning' && !(h >= 6 && h < 12)) return false;
      if (tod === 'afternoon' && !(h >= 12 && h < 17)) return false;
      if (tod === 'evening' && !(h >= 17 && h < 21)) return false;
      if (tod === 'night' && !(h >= 21 || h < 6)) return false;
    }

    // Time Range
    if (filters.timeFrom && r.time < filters.timeFrom) return false;
    if (filters.timeTo && r.time > filters.timeTo) return false;

    // Customer
    if (filters.customer && filters.customer !== 'All') {
      const cust = filters.customer.toLowerCase().trim();
      const client = r.client.toLowerCase();
      if (!client.includes(cust) && client !== cust) return false;
    }

    // Date Range (From / To)
    if (resolvedFromDate && r.date < resolvedFromDate) return false;
    if (resolvedToDate && r.date > resolvedToDate) return false;

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

function eachDateInRange(start: Date, end: Date): Date[] {
  const dates: Date[] = [];
  for (const current = new Date(start); current <= end; current.setDate(current.getDate() + 1)) {
    dates.push(new Date(current));
  }
  return dates;
}

/** Builds Activity Analysis buckets from the child periods of the selected parent. */
export function buildHierarchicalTimeSlotTrend(
  filtered: ActivityRecord[], groupBy: GroupByMode, fromDate?: string, toDate?: string
): TimeSlotPoint[] {
  const latestRecordDate = filtered.length ? filtered.map(record => record.date).sort().at(-1) : undefined;
  const anchor = new Date(`${fromDate || toDate || latestRecordDate || '2026-08-08'}T00:00:00`);
  const makePoints = (slots: { slot: string; label: string; records: ActivityRecord[] }[]): TimeSlotPoint[] => {
    const maxCount = Math.max(0, ...slots.map(slot => slot.records.length));
    return slots.map(slot => ({
      slot: slot.slot, label: slot.label, activityCount: slot.records.length,
      uniqueClients: new Set(slot.records.map(record => record.client).filter(Boolean)).size,
      amount: slot.records.reduce((sum, record) => sum + record.amount, 0),
      isPeak: slot.records.length === maxCount && maxCount > 0,
    }));
  };

  const rangeStart = new Date(`${fromDate || (filtered.map(record => record.date).sort()[0] || formatDate(anchor))}T00:00:00`);
  const rangeEnd = new Date(`${toDate || (filtered.map(record => record.date).sort().at(-1) || formatDate(anchor))}T00:00:00`);

  // Hour / 30-minute views must keep date + time so a multi-day range is
  // not collapsed into a single 24/48-slot day. Empty slots stay zero-filled.
  if (groupBy === '30min') {
    const slots: { slot: string; label: string; records: ActivityRecord[] }[] = [];
    for (const current of eachDateInRange(rangeStart, rangeEnd)) {
      const dateStr = formatDate(current);
      const dayLabel = current.toLocaleDateString('en-GB', { day: '2-digit', month: 'short' });
      for (let index = 0; index < 48; index++) {
        const hour = Math.floor(index / 2);
        const time = `${String(hour).padStart(2, '0')}:${index % 2 ? '30' : '00'}`;
        slots.push({
          slot: `${dateStr} ${time}`,
          label: `${dayLabel} ${time}`,
          records: filtered.filter(record => record.date === dateStr && record.halfHourSlot === time),
        });
      }
    }
    return makePoints(slots);
  }

  if (groupBy === 'hour') {
    const slots: { slot: string; label: string; records: ActivityRecord[] }[] = [];
    for (const current of eachDateInRange(rangeStart, rangeEnd)) {
      const dateStr = formatDate(current);
      const dayLabel = current.toLocaleDateString('en-GB', { day: '2-digit', month: 'short' });
      for (let hour = 0; hour < 24; hour++) {
        const time = `${String(hour).padStart(2, '0')}:00`;
        slots.push({
          slot: `${dateStr} ${time}`,
          label: `${dayLabel} ${time}`,
          records: filtered.filter(record => record.date === dateStr && record.hourSlot === hour),
        });
      }
    }
    return makePoints(slots);
  }

  // Day -> every calendar day in the selected range.
  if (groupBy === 'day') {
    const start = new Date(`${fromDate || (filtered.map(record => record.date).sort()[0] || formatDate(anchor))}T00:00:00`);
    const end = new Date(`${toDate || (filtered.map(record => record.date).sort().at(-1) || formatDate(anchor))}T00:00:00`);
    const slots: { slot: string; label: string; records: ActivityRecord[] }[] = [];
    for (const current = new Date(start); current <= end; current.setDate(current.getDate() + 1)) {
      const slot = formatDate(current);
      slots.push({ slot, label: current.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }), records: filtered.filter(record => record.date === slot) });
    }
    return makePoints(slots);
  }

  // Week -> complete calendar-week buckets spanning the selected range.
  if (groupBy === 'week') {
    const start = new Date(`${fromDate || (filtered.map(record => record.date).sort()[0] || formatDate(anchor))}T00:00:00`);
    const end = new Date(`${toDate || (filtered.map(record => record.date).sort().at(-1) || formatDate(anchor))}T00:00:00`);
    start.setDate(start.getDate() - ((start.getDay() + 6) % 7));
    const slots: { slot: string; label: string; records: ActivityRecord[] }[] = [];
    for (const current = new Date(start); current <= end; current.setDate(current.getDate() + 7)) {
      const slot = formatDate(current);
      const weekEnd = new Date(current); weekEnd.setDate(weekEnd.getDate() + 6);
      slots.push({ slot, label: `${slot} – ${formatDate(weekEnd)}`, records: filtered.filter(record => record.date >= slot && record.date <= formatDate(weekEnd)) });
    }
    return makePoints(slots);
  }

  // Month -> calendar-month buckets spanning the selected range.
  if (groupBy === 'month') {
    const start = new Date(`${fromDate || (filtered.map(record => record.date).sort()[0] || formatDate(anchor))}T00:00:00`);
    const end = new Date(`${toDate || (filtered.map(record => record.date).sort().at(-1) || formatDate(anchor))}T00:00:00`);
    start.setDate(1);
    const slots: { slot: string; label: string; records: ActivityRecord[] }[] = [];
    for (const current = new Date(start.getFullYear(), start.getMonth(), 1); current <= end; current.setMonth(current.getMonth() + 1)) {
      const slot = `${current.getFullYear()}-${String(current.getMonth() + 1).padStart(2, '0')}`;
      slots.push({ slot, label: current.toLocaleDateString('en-US', { month: 'short', year: 'numeric' }), records: filtered.filter(record => record.date.startsWith(slot)) });
    }
    return makePoints(slots);
  }

  // Year -> calendar-year buckets spanning the selected range.
  const startYear = new Date(`${fromDate || (filtered.map(record => record.date).sort()[0] || formatDate(anchor))}T00:00:00`).getFullYear();
  const endYear = new Date(`${toDate || (filtered.map(record => record.date).sort().at(-1) || formatDate(anchor))}T00:00:00`).getFullYear();
  return makePoints(Array.from({ length: endYear - startYear + 1 }, (_, index) => {
    const slot = String(startYear + index);
    return { slot, label: slot, records: filtered.filter(record => record.date.startsWith(`${slot}-`)) };
  }));
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

  // 1. DAY VIEW (30-minute intervals: exactly 48 half-hour slots)
  if (groupBy === '30min') {
    const halfHourList: string[] = [];
    const countMap = new Map<string, number>();
    const clientMap = new Map<string, Set<string>>();
    const amountMap = new Map<string, number>();

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
      if (countMap.has(k)) {
        countMap.set(k, (countMap.get(k) || 0) + 1);
        clientMap.get(k)?.add(r.client);
        amountMap.set(k, (amountMap.get(k) || 0) + r.amount);
      }
    }

    let maxCount = 0;
    for (const s of halfHourList) {
      const c = countMap.get(s) || 0;
      if (c > maxCount) maxCount = c;
    }

    return halfHourList.map(s => {
      const count = countMap.get(s) || 0;
      return {
        slot: s,
        label: s,
        activityCount: count,
        uniqueClients: clientMap.get(s)?.size || 0,
        amount: amountMap.get(s) || 0,
        isPeak: count === maxCount && count > 0,
      };
    });
  }

  // 2. WEEK VIEW (Weekly periods: Sunday → Saturday)
  if (groupBy === 'week') {
    let minDateStr = fromDate;
    let maxDateStr = toDate;

    if (!minDateStr || !maxDateStr) {
      const dates = filtered.map(r => r.date).sort();
      minDateStr = minDateStr || (dates.length ? dates[0] : '2026-08-02');
      maxDateStr = maxDateStr || (dates.length ? dates[dates.length - 1] : '2026-08-08');
    }

    const startObj = new Date(minDateStr + 'T00:00:00');
    const endObj = new Date(maxDateStr + 'T00:00:00');

    // Align start to the Sunday of that week (Sunday = 0)
    const currentSunday = new Date(startObj);
    currentSunday.setDate(currentSunday.getDate() - currentSunday.getDay());

    const weekSlots: {
      weekKey: string;
      label: string;
      sundayStr: string;
      saturdayStr: string;
      records: ActivityRecord[];
    }[] = [];

    let weekNum = 1;
    while (currentSunday <= endObj || weekSlots.length === 0) {
      const sundayStr = formatDate(currentSunday);
      const sat = new Date(currentSunday);
      sat.setDate(sat.getDate() + 6);
      const saturdayStr = formatDate(sat);

      const sLabel = currentSunday.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
      const eLabel = sat.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
      const label = `Week ${weekNum}`;

      const matchingRecords = filtered.filter(r => r.date >= sundayStr && r.date <= saturdayStr);

      weekSlots.push({
        weekKey: `Week ${weekNum} (${sLabel} – ${eLabel})`,
        label,
        sundayStr,
        saturdayStr,
        records: matchingRecords,
      });

      weekNum++;
      currentSunday.setDate(currentSunday.getDate() + 7);
      if (weekNum > 60) break;
    }

    let maxCount = 0;
    for (const ws of weekSlots) {
      if (ws.records.length > maxCount) maxCount = ws.records.length;
    }

    return weekSlots.map(ws => {
      const count = ws.records.length;
      const uniqueClients = new Set(ws.records.map(r => r.client)).size;
      const amount = ws.records.reduce((sum, r) => sum + r.amount, 0);
      return {
        slot: ws.weekKey,
        label: ws.label,
        activityCount: count,
        uniqueClients,
        amount,
        isPeak: count === maxCount && count > 0,
      };
    });
  }

  // 3. MONTH VIEW (Days in the month / range: e.g. Aug 1, Aug 2 ... Aug 31)
  if (groupBy === 'day') {
    let minDateStr = fromDate;
    let maxDateStr = toDate;

    if (!minDateStr || !maxDateStr) {
      if (filtered.length) {
        const dates = filtered.map(r => r.date).sort();
        const latest = dates[dates.length - 1];
        const [y, m] = latest.split('-');
        const lastDay = new Date(Number(y), Number(m), 0).getDate();
        minDateStr = `${y}-${m}-01`;
        maxDateStr = `${y}-${m}-${String(lastDay).padStart(2, '0')}`;
      } else {
        minDateStr = '2026-08-01';
        maxDateStr = '2026-08-31';
      }
    }

    const startObj = new Date(minDateStr + 'T00:00:00');
    const endObj = new Date(maxDateStr + 'T00:00:00');
    const current = new Date(startObj);

    const daySlots: {
      dateStr: string;
      label: string;
      records: ActivityRecord[];
    }[] = [];

    while (current <= endObj) {
      const ds = formatDate(current);
      const label = current.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
      const matchingRecords = filtered.filter(r => r.date === ds);
      daySlots.push({
        dateStr: ds,
        label,
        records: matchingRecords,
      });
      current.setDate(current.getDate() + 1);
      if (daySlots.length > 70) break;
    }

    let maxCount = 0;
    for (const ds of daySlots) {
      if (ds.records.length > maxCount) maxCount = ds.records.length;
    }

    return daySlots.map(ds => {
      const count = ds.records.length;
      const uniqueClients = new Set(ds.records.map(r => r.client)).size;
      const amount = ds.records.reduce((sum, r) => sum + r.amount, 0);
      return {
        slot: ds.dateStr,
        label: ds.label,
        activityCount: count,
        uniqueClients,
        amount,
        isPeak: count === maxCount && count > 0,
      };
    });
  }

  // 5. YEAR VIEW — one bar per calendar year
  if (groupBy === 'year') {
    const yearMap = new Map<number, ActivityRecord[]>();
    for (const r of filtered) {
      const y = new Date(r.date + 'T00:00:00').getFullYear();
      if (!yearMap.has(y)) yearMap.set(y, []);
      yearMap.get(y)!.push(r);
    }
    const years = [...yearMap.keys()].sort();
    if (years.length === 0) years.push(2026);

    let maxCount = 0;
    for (const y of years) {
      const list = yearMap.get(y) || [];
      if (list.length > maxCount) maxCount = list.length;
    }

    return years.map(y => {
      const list = yearMap.get(y) || [];
      const count = list.length;
      const uniqueClients = new Set(list.map(r => r.client)).size;
      const amount = list.reduce((sum, r) => sum + r.amount, 0);
      return {
        slot: String(y),
        label: String(y),
        activityCount: count,
        uniqueClients,
        amount,
        isPeak: count === maxCount && count > 0,
      };
    });
  }

  // 4. YEAR VIEW (Months: Jan | Feb | Mar | Apr | May | Jun | Jul | Aug | Sep | Oct | Nov | Dec)
  let year = 2026;
  if (fromDate) {
    year = new Date(fromDate + 'T00:00:00').getFullYear();
  } else if (filtered.length) {
    const dates = filtered.map(r => r.date).sort();
    year = new Date(dates[dates.length - 1] + 'T00:00:00').getFullYear();
  }

  const monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const monthSlots: TimeSlotPoint[] = [];

  const monthMap = new Map<number, ActivityRecord[]>();
  for (let m = 0; m < 12; m++) monthMap.set(m, []);

  for (const r of filtered) {
    const dObj = new Date(r.date + 'T00:00:00');
    if (dObj.getFullYear() === year || !fromDate) {
      monthMap.get(dObj.getMonth())?.push(r);
    }
  }

  let maxCount = 0;
  for (let m = 0; m < 12; m++) {
    const list = monthMap.get(m) || [];
    if (list.length > maxCount) maxCount = list.length;
  }

  for (let m = 0; m < 12; m++) {
    const list = monthMap.get(m) || [];
    const count = list.length;
    const uniqueClients = new Set(list.map(r => r.client)).size;
    const amount = list.reduce((sum, r) => sum + r.amount, 0);
    monthSlots.push({
      slot: `${year}-${String(m + 1).padStart(2, '0')}`,
      label: monthNames[m],
      activityCount: count,
      uniqueClients,
      amount,
      isPeak: count === maxCount && count > 0,
    });
  }

  return monthSlots;
}

/**
 * Records actually represented by the current Group By buckets
 * (same windows as buildTimeSlotTrend). KPI cards must use this set
 * so they follow Hour / 30min / Day / Week / Month / Year, not the
 * unscoped filtered list.
 */
export function getGroupByScopedRecords(
  filtered: ActivityRecord[],
  groupBy: GroupByMode,
  fromDate?: string,
  toDate?: string
): ActivityRecord[] {
  if (groupBy === 'hour' || groupBy === '30min') {
    return filtered;
  }

  if (groupBy === 'week') {
    let minDateStr = fromDate;
    let maxDateStr = toDate;
    if (!minDateStr || !maxDateStr) {
      const dates = filtered.map(r => r.date).sort();
      minDateStr = minDateStr || (dates.length ? dates[0] : '2026-08-02');
      maxDateStr = maxDateStr || (dates.length ? dates[dates.length - 1] : '2026-08-08');
    }

    const startObj = new Date(minDateStr + 'T00:00:00');
    const endObj = new Date(maxDateStr + 'T00:00:00');
    const currentSunday = new Date(startObj);
    currentSunday.setDate(currentSunday.getDate() - currentSunday.getDay());

    const includedDates = new Set<string>();
    let weekNum = 1;
    while (currentSunday <= endObj || includedDates.size === 0) {
      for (let d = 0; d < 7; d++) {
        const day = new Date(currentSunday);
        day.setDate(day.getDate() + d);
        includedDates.add(formatDate(day));
      }
      weekNum++;
      currentSunday.setDate(currentSunday.getDate() + 7);
      if (weekNum > 60) break;
    }
    return filtered.filter(r => includedDates.has(r.date));
  }

  if (groupBy === 'day') {
    let minDateStr = fromDate;
    let maxDateStr = toDate;
    if (!minDateStr || !maxDateStr) {
      if (filtered.length) {
        const dates = filtered.map(r => r.date).sort();
        const latest = dates[dates.length - 1];
        const [y, m] = latest.split('-');
        const lastDay = new Date(Number(y), Number(m), 0).getDate();
        minDateStr = `${y}-${m}-01`;
        maxDateStr = `${y}-${m}-${String(lastDay).padStart(2, '0')}`;
      } else {
        minDateStr = '2026-08-01';
        maxDateStr = '2026-08-31';
      }
    }

    const startObj = new Date(minDateStr + 'T00:00:00');
    const endObj = new Date(maxDateStr + 'T00:00:00');
    const includedDates = new Set<string>();
    const current = new Date(startObj);
    while (current <= endObj) {
      includedDates.add(formatDate(current));
      current.setDate(current.getDate() + 1);
      if (includedDates.size > 70) break;
    }
    return filtered.filter(r => includedDates.has(r.date));
  }

  if (groupBy === 'year') {
    return filtered;
  }

  let year = 2026;
  if (fromDate) {
    year = new Date(fromDate + 'T00:00:00').getFullYear();
  } else if (filtered.length) {
    const dates = filtered.map(r => r.date).sort();
    year = new Date(dates[dates.length - 1] + 'T00:00:00').getFullYear();
  }

  return filtered.filter(r => {
    const dObj = new Date(r.date + 'T00:00:00');
    return dObj.getFullYear() === year || !fromDate;
  });
}

// ─── KPI helpers ─────────────────────────────────────────────────

export function computeKpis(
  scopedRecords: ActivityRecord[],
  trendData: TimeSlotPoint[]
): KpiResult {
  const totalActivities = trendData.reduce((s, p) => s + p.activityCount, 0);
  const uniqueClients = new Set(scopedRecords.map(r => r.client)).size;
  const sumAmount = trendData.reduce((s, p) => s + p.amount, 0);
  const financialCount = scopedRecords.filter(r => r.isFinancial).length;

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

/** KPI totals for Activity Analysis: active filters/date range, independent of chart bucket count. */
export function computeActivityAnalysisKpis(
  filteredRecords: ActivityRecord[],
  trendData: TimeSlotPoint[]
): KpiResult {
  const chartKpis = computeKpis(filteredRecords, trendData);
  return {
    ...chartKpis,
    totalActivities: filteredRecords.length,
    uniqueClients: new Set(filteredRecords.map(record => record.client).filter(Boolean)).size,
    sumAmount: filteredRecords.reduce((sum, record) => sum + record.amount, 0),
    financialCount: filteredRecords.filter(record => record.isFinancial).length,
  };
}

// ─── Salesperson Breakdown ──────────────────────────────────────

export function buildSalespersonBreakdown(filtered: ActivityRecord[]): SalespersonBreakdownItem[] {
  const countMap = new Map<string, number>();
  const amountMap = new Map<string, number>();
  for (const r of filtered) {
    // Records with no salesperson column on their source table (Sales
    // Order, Sales Invoice, Task-with-no-completer, etc.) come through
    // with salesperson === '' -- excluded here rather than shown as a
    // fake "employee" named "". They're still counted in the overall
    // totalActivities KPI, just not attributed to any one person.
    if (!r.salesperson) continue;
    countMap.set(r.salesperson, (countMap.get(r.salesperson) || 0) + 1);
    amountMap.set(r.salesperson, (amountMap.get(r.salesperson) || 0) + r.amount);
  }
  const total = filtered.length || 1;
  return [...countMap.keys()].map(name => {
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
  for (const r of filtered) {
    // Same reasoning as buildSalespersonBreakdown -- '' means the source
    // table has no customer link to resolve a country from (Task, ToDo),
    // not a real country called "".
    if (!r.country) continue;
    countMap.set(r.country, (countMap.get(r.country) || 0) + 1);
    if (!clientMap.has(r.country)) clientMap.set(r.country, new Set());
    if (r.client) clientMap.get(r.country)!.add(r.client);
    amountMap.set(r.country, (amountMap.get(r.country) || 0) + r.amount);
  }
  const total = filtered.length || 1;
  return [...countMap.keys()].map(country => {
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
  const financialMap = new Map<string, boolean>();
  for (const r of filtered) {
    countMap.set(r.activityType, (countMap.get(r.activityType) || 0) + 1);
    amountMap.set(r.activityType, (amountMap.get(r.activityType) || 0) + r.amount);
    // Real per-record flag from the backend, not a fixed type-name list --
    // same class of bug as the old hardcoded 5-salesperson/5-country caps,
    // see AA_ACTIVITY_TYPES's comment above for the production mismatch
    // that motivated this. OR'd across all records of this type, since
    // isFinancial is set consistently per source table (e.g. every Sales
    // Order row is true), not per individual record.
    if (r.isFinancial) financialMap.set(r.activityType, true);
  }
  const total = filtered.length || 1;
  return [...countMap.entries()]
    .map(([type, count]) => ({
      type,
      count,
      pct: Math.round((count / total) * 100),
      isFinancial: financialMap.get(type) || (amountMap.get(type) || 0) > 0,
      amount: amountMap.get(type) || 0,
    }))
    .sort((a, b) => b.count - a.count);
}