import { Component, OnInit, ChangeDetectorRef, ElementRef, ViewChild, HostListener } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import * as XLSX from 'xlsx';
import { QueryService } from '../services/query';
import {
  ActivityRecord,
  TimeSlotPoint,
  GroupByMode,
  computeActivityAnalysisKpis,
  buildHierarchicalTimeSlotTrend,
} from '../data/activity-analytics-data';

@Component({
  selector: 'app-activity-analysis',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './activity-analysis.html',
  styleUrl: './activity-analysis.scss',
})
export class ActivityAnalysisComponent implements OnInit {

  constructor(private queryService: QueryService, private cdr: ChangeDetectorRef) {}

  @ViewChild('aaChartBars') aaChartBars?: ElementRef<HTMLElement>;

  /** Same SyncRun timestamp source as Dashboard (`QueryService.getLastSyncTime`). */
  lastSyncCompletedAt: Date | null = null;
  aaHeartbeatPath = '';

  /** True while the initial (or a filter-triggered) fetch is in flight. */
  aaLoading = true;
  aaError = '';

  /** Every record ever fetched, unfiltered -- used only to populate the
   * Country/Salesperson dropdown options and the "X of Y total" label, so
   * those don't disappear/shrink as the person narrows their own filters.
   * Fetched once on init. */
  private aaAllRecords: ActivityRecord[] = [];
  aaGrandTotal = 0;
  // ─── Filter States ─────────────────────────────────────────────
  aaGroupBy: GroupByMode = 'hour';
  aaActivityFilter = 'All Activities';
  aaCountryFilter = 'All Countries';
  aaSalespersonFilter = 'All Salespersons';
  aaFromDate = '';
  aaToDate = '';
  aaDatePreset: 'all' | '2026-08-08' | '2026' | '2025' | 'custom' = 'all';

  // ─── Computed KPIs ─────────────────────────────────────────────
  aaTotalActivities = 0;
  aaUniqueClients = 0;
  aaSumAmount = 0;
  aaEmptyTimeSlots = 0;
  aaTotalSlots = 0;
  aaFinancialCount = 0;
  aaAvgPerSlot = 0;
  aaPeakSlot: TimeSlotPoint | null = null;
  aaTooltipBelowIndex: number | null = null;
  aaTooltipIndex: number | null = null;
  aaTooltipTopPx = 0;
  aaTooltipLeftPx = 0;

  // ─── Computed Data Series ──────────────────────────────────────
  aaFilteredRecords: ActivityRecord[] = [];
  aaTrendData: TimeSlotPoint[] = [];

  // ─── Constants & Options ───────────────────────────────────────
  // Derived from the live dataset (aaAllRecords) once it's loaded, rather
  // than a fixed list -- confirmed 2026-08-22 against production that the
  // real activity_type vocabulary (Text Message, WhatsApp, Presentation,
  // Meeting/ Visit, Quotation / Commercial Offer, Samples Sales, Online
  // Meeting, LinkedIn, Pilot Order, Development, ...) is almost entirely
  // different from the old mock dataset's fixed 17-type list -- a static
  // list here would silently make ~900 real records' activity type
  // unselectable in this filter.
  aaActivityOptions: string[] = ['All Activities'];
  aaCountryOptions: string[] = ['All Countries'];
  aaSalespersonOptions: string[] = ['All Salespersons'];
  readonly aaGroupByOptions: { value: GroupByMode; label: string; sub: string }[] = [
    { value: 'hour', label: 'Hour', sub: '24 Slots' },
    { value: '30min', label: '30 Minutes', sub: '48 Slots' },
    { value: 'day', label: 'Day', sub: 'Daily' },
    { value: 'week', label: 'Week', sub: 'Weekly' },
    { value: 'month', label: 'Month', sub: 'Monthly' },
    { value: 'year', label: 'Year', sub: 'Yearly' },
  ];

  ngOnInit(): void {
    // Fetch everything unfiltered once, purely to derive the Country/
    // Activity Type dropdown options and the grand-total record count --
    // never re-fetched on filter change (that would defeat the point).
    // Salesperson options come from live ERPNext enabled Users, not this log.
    this.queryService.getActivityLogRecords().subscribe({
      next: (rows) => {
        this.aaAllRecords = rows.map(r => this.toActivityRecord(r));
        this.aaGrandTotal = this.aaAllRecords.length;
        this.aaActivityOptions = ['All Activities', ...[...new Set(this.aaAllRecords.map(r => r.activityType).filter(Boolean))].sort()];
        this.aaCountryOptions = ['All Countries', ...[...new Set(this.aaAllRecords.map(r => r.country).filter(Boolean))].sort()];
        this.cdr.detectChanges();
      },
      error: (err) => {
        console.error('Activity Analysis: failed to load filter options', err);
      },
    });
    this.queryService.getEnabledUsers().subscribe({
      next: (rows) => {
        const names = [...new Set(rows.map(r => r.salesperson).filter(Boolean))].sort();
        this.aaSalespersonOptions = ['All Salespersons', ...names];
        if (this.aaSalespersonFilter !== 'All Salespersons' && !names.includes(this.aaSalespersonFilter)) {
          this.aaSalespersonFilter = 'All Salespersons';
        }
        this.cdr.detectChanges();
      },
      error: (err) => {
        console.error('Activity Analysis: failed to load salesperson options', err);
      },
    });
    this.recalculate();
    this.loadLastSyncTime();
  }

  /** Same mechanism as DashboardComponent.loadLastSyncTime / updatedLabel(). */
  private loadLastSyncTime(): void {
    this.queryService.getLastSyncTime().subscribe({
      next: (records) => {
        const completedAt = records[0]?.completed_at;
        this.lastSyncCompletedAt = completedAt ? new Date(completedAt) : null;
        this.cdr.detectChanges();
      },
      error: (err) => {
        console.error('Failed to load last sync time', err);
      },
    });
  }

  updatedLabel(): string {
    if (!this.lastSyncCompletedAt) return '';
    const datePart = this.lastSyncCompletedAt.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
    const timePart = this.lastSyncCompletedAt.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' });
    return `Updated ${datePart} at ${timePart}`;
  }

  /**
   * Coerces a raw API row (nullable text fields, per the backend's
   * documented schema gaps) into the ActivityRecord shape every existing
   * pure helper in activity-analytics-data.ts expects: non-null strings,
   * with '' meaning "not attributed" rather than a real value, and
   * hourSlot -1 meaning "no time component on this source record".
   */
  private toActivityRecord(r: {
    id: string; date: string | null; time: string | null; hourSlot: number | null; halfHourSlot: string | null;
    salesperson: string | null; country: string | null; activityType: string; client: string | null;
    amount: number; isFinancial: boolean;
  }): ActivityRecord {
    return {
      id: r.id,
      date: r.date ?? '',
      time: r.time ?? '',
      hourSlot: r.hourSlot ?? -1,
      halfHourSlot: r.halfHourSlot ?? '',
      salesperson: r.salesperson ?? '',
      country: r.country ?? '',
      activityType: r.activityType,
      client: r.client ?? '',
      amount: Number(r.amount || 0),
      isFinancial: !!r.isFinancial,
    };
  }

  // ─── Filter Actions ────────────────────────────────────────────

  setAaGroupBy(mode: GroupByMode): void {
    this.aaGroupBy = mode;
    this.recalculate();
  }

  setAaDatePreset(preset: 'all' | '2026-08-08' | '2026' | '2025' | 'custom'): void {
    this.aaDatePreset = preset;
    if (preset === 'all') {
      this.aaFromDate = '';
      this.aaToDate = '';
    } else if (preset === '2026-08-08') {
      this.aaFromDate = '2026-08-08';
      this.aaToDate = '2026-08-08';
    } else if (preset === '2026') {
      this.aaFromDate = '2026-01-01';
      this.aaToDate = '2026-12-31';
    } else if (preset === '2025') {
      this.aaFromDate = '2025-01-01';
      this.aaToDate = '2025-12-31';
    }
    this.recalculate();
  }

  onAaCustomDateChange(): void {
    this.aaDatePreset = 'custom';
    this.recalculate();
  }

  onAaFilterChange(): void {
    this.recalculate();
  }

  resetAaFilters(): void {
    this.aaGroupBy = 'hour';
    this.aaActivityFilter = 'All Activities';
    this.aaCountryFilter = 'All Countries';
    this.aaSalespersonFilter = 'All Salespersons';
    this.aaFromDate = '';
    this.aaToDate = '';
    this.aaDatePreset = 'all';
    this.recalculate();
  }

  // ─── Recalculation Core ─────────────────────────────────────────

  private recalculate(): void {
    let resolvedFrom = this.aaFromDate;
    let resolvedTo = this.aaToDate;

    if (resolvedFrom && resolvedTo && resolvedFrom > resolvedTo) {
      [resolvedFrom, resolvedTo] = [resolvedTo, resolvedFrom];
    }

    const activityType =
      this.aaActivityFilter === 'All Activities' ? undefined : this.aaActivityFilter;

    const country =
      this.aaCountryFilter === 'All Countries' ? undefined : this.aaCountryFilter;

    const employee =
      this.aaSalespersonFilter === 'All Salespersons' ? undefined : this.aaSalespersonFilter;

    this.aaLoading = true;
    this.aaError = '';

    this.queryService.getActivityLogRecords(
      activityType,
      country,
      employee,
      resolvedFrom || undefined,
      resolvedTo || undefined
    ).subscribe({
      next: (rows) => {
        const filtered = rows.map(r => this.toActivityRecord(r));
        this.applyRecalculatedState(filtered, resolvedFrom, resolvedTo);
        this.aaLoading = false;
        this.cdr.detectChanges();
      },
      error: (err) => {
        console.error('Activity Analysis API error:', err);
        this.aaError = 'Could not load activity data. Is the reporting service running?';
        this.aaLoading = false;
        this.cdr.detectChanges();
      },
    });
  }

  /** Everything downstream of the fetch -- unchanged from the old
   * mock-data pipeline, just fed by live server-filtered records now. */
  private applyRecalculatedState(filtered: ActivityRecord[], resolvedFrom: string, resolvedTo: string): void {
    this.aaFilteredRecords = filtered;

    this.aaTrendData = buildHierarchicalTimeSlotTrend(
      filtered,
      this.aaGroupBy,
      resolvedFrom || undefined,
      resolvedTo || undefined
    );

    const kpis = computeActivityAnalysisKpis(filtered, this.aaTrendData);
    this.aaTotalActivities = kpis.totalActivities;
    this.aaUniqueClients = kpis.uniqueClients;
    this.aaSumAmount = kpis.sumAmount;
    this.aaEmptyTimeSlots = kpis.emptyTimeSlots;
    this.aaTotalSlots = kpis.totalSlots;
    this.aaFinancialCount = kpis.financialCount;
    this.aaAvgPerSlot = kpis.avgPerSlot;
    this.aaPeakSlot = kpis.peakSlot;
    this.scheduleHeartbeatRebuild();
  }

  // ─── Getters ───────────────────────────────────────────────────

  get aaTrendMax(): number {
    return Math.max(1, ...this.aaTrendData.map(p => p.activityCount));
  }

  /** Nice Y-axis ceiling so ticks use 1/2/5×10^n intervals from live max. */
  get aaChartScaleMax(): number {
    return this.aaYAxisScale.max;
  }

  get aaYAxisTicks(): number[] {
    return this.aaYAxisScale.ticks;
  }

  private get aaYAxisScale(): { max: number; ticks: number[] } {
    const dataMax = this.aaTrendMax;
    const targetTicks = 5;
    const rough = Math.max(1, dataMax) / (targetTicks - 1);
    const exp = Math.floor(Math.log10(rough));
    const mag = Math.pow(10, exp);
    const residual = rough / mag;
    const nice = residual <= 1 ? 1 : residual <= 2 ? 2 : residual <= 5 ? 5 : 10;
    const interval = nice * mag;
    const niceMax = Math.max(interval, Math.ceil(dataMax / interval) * interval);
    const ticks: number[] = [];
    for (let v = niceMax; v >= 0; v -= interval) {
      ticks.push(Math.round(v * 1e6) / 1e6);
      if (ticks.length > 12) break;
    }
    if (ticks[ticks.length - 1] !== 0) ticks.push(0);
    return { max: niceMax, ticks };
  }

  /**
   * Min plot width so Hour/30min slots can overflow and scroll.
   * Month/Year (few columns) must not set an inline min-width: that
   * overrides CSS `min-width: 100%` and collapses the plot to n×16px on the left.
   */
  get aaChartPlotMinWidth(): number | null {
    if (this.aaGroupBy === 'month' || this.aaGroupBy === 'year') return null;
    const col = 16;
    const gap = 6;
    const pad = 16;
    const n = this.aaTrendData.length;
    if (n <= 0) return 0;
    return n * col + Math.max(0, n - 1) * gap + pad;
  }

  get aaChildPeriodLabel(): string {
    switch (this.aaGroupBy) {
      case '30min': return '30-minute slots';
      case 'day':
      case 'hour': return 'hours';
      case 'week':
      case 'month': return 'days';
      case 'year': return 'months';
      default: return 'periods';
    }
  }

  aaBarHeightPct(point: TimeSlotPoint): number {
    const max = this.aaChartScaleMax;
    return point.activityCount > 0 && max > 0 ? (point.activityCount / max) * 100 : 0;
  }

  /** Same Unique Client scale as the purple dots (`uniqueClients / aaChartScaleMax`). */
  aaClientHeightPct(point: TimeSlotPoint): number {
    const max = this.aaChartScaleMax;
    return point.uniqueClients > 0 && max > 0 ? (point.uniqueClients / max) * 100 : 0;
  }

  onAaBarMouseEnter(index: number, point: TimeSlotPoint, event: MouseEvent): void {
    const column = event.currentTarget as HTMLElement | null;
    const tooltip = column?.querySelector('.aa-chart-tooltip') as HTMLElement | null;
    const bar = column?.querySelector('.aa-chart-bar') as HTMLElement | null;
    const clip = column?.closest('.aa-chart-plot-wrap') as HTMLElement | null;
    if (!column || !tooltip || !bar || !clip) return;

    this.aaTooltipIndex = index;
    this.cdr.detectChanges();

    const gap = 8;
    const ttH = tooltip.offsetHeight || 72;
    const ttW = tooltip.offsetWidth || 160;
    const barRect = bar.getBoundingClientRect();
    const clipRect = clip.getBoundingClientRect();
    const minTop = clipRect.top + 2;
    const maxTop = clipRect.bottom - ttH - 2;

    const aboveTop = barRect.top - gap - ttH;
    const belowTop = barRect.bottom + gap;
    let top: number;
    if (aboveTop >= minTop) {
      top = aboveTop;
    } else if (belowTop <= maxTop) {
      top = belowTop;
    } else {
      top = Math.min(Math.max(minTop, aboveTop), maxTop);
    }

    const half = ttW / 2;
    let left = barRect.left + barRect.width / 2;
    const minCenter = clipRect.left + 2 + half;
    const maxCenter = clipRect.right - 2 - half;
    if (minCenter <= maxCenter) {
      left = Math.min(Math.max(left, minCenter), maxCenter);
    } else {
      left = clipRect.left + clipRect.width / 2;
    }

    this.aaTooltipTopPx = top;
    this.aaTooltipLeftPx = left;
    this.aaTooltipBelowIndex = belowTop === top ? index : null;
    this.cdr.detectChanges();
  }

  onAaBarMouseLeave(): void {
    this.aaTooltipBelowIndex = null;
    this.aaTooltipIndex = null;
  }

  get aaFilterSummary(): string {
    const parts: string[] = [];
    if (this.aaActivityFilter !== 'All Activities') {
      parts.push(this.aaActivityFilter);
    } else {
      parts.push('All Activities');
    }

    const groupLabel = this.aaGroupByOptions.find(o => o.value === this.aaGroupBy)?.label || this.aaGroupBy;
    parts.push(groupLabel);

    if (this.aaFromDate && this.aaToDate) {
      if (this.aaFromDate === this.aaToDate) {
        parts.push(this.aaFromDate);
      } else {
        parts.push(`${this.aaFromDate} to ${this.aaToDate}`);
      }
    } else if (this.aaFromDate) {
      parts.push(`From ${this.aaFromDate}`);
    } else if (this.aaToDate) {
      parts.push(`To ${this.aaToDate}`);
    } else {
      parts.push(`All ${this.aaGrandTotal.toLocaleString()} Records`);
    }

    if (this.aaCountryFilter !== 'All Countries') parts.push(this.aaCountryFilter);
    if (this.aaSalespersonFilter !== 'All Salespersons') parts.push(this.aaSalespersonFilter);

    return parts.join(' · ');
  }

  exportAaRecordsToExcel(): void {
    const dataToExport = this.aaFilteredRecords.map(r => ({
      'Record ID': r.id,
      'Date': r.date,
      'Time': r.time,
      'Hour Slot': `${String(r.hourSlot).padStart(2, '0')}:00`,
      'Half Hour Slot': r.halfHourSlot,
      'Salesperson': r.salesperson,
      'Country': r.country,
      'Activity Type': r.activityType,
      'Client': r.client,
      'Amount (USD)': r.amount,
      'Financial': r.isFinancial ? 'Yes' : 'No',
    }));
    const ws = XLSX.utils.json_to_sheet(dataToExport);
    const wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, ws, 'Activity Records');
    XLSX.writeFile(wb, `boxtech_activity_records_${new Date().toISOString().slice(0, 10)}.xlsx`);
  }

  // ─── Visual Colors ─────────────────────────────────────────────

  aaBarColor(_index: number): string {
    return '#2563EB';
  }

  @HostListener('window:resize')
  onAaChartResize(): void {
    this.scheduleHeartbeatRebuild();
  }

  private scheduleHeartbeatRebuild(): void {
    setTimeout(() => {
      const path = this.buildHeartbeatPathFromRenderedBars();
      if (path !== this.aaHeartbeatPath) {
        this.aaHeartbeatPath = path;
        this.cdr.detectChanges();
      }
    });
  }

  /**
   * Unique Client line: same aaTrendData[i].uniqueClients and same
   * aaClientHeightPct Y as the purple dots; X = rendered column/bar center.
   */
  private buildHeartbeatPathFromRenderedBars(): string {
    const pts = this.aaTrendData;
    const n = pts.length;
    const barsEl = this.aaChartBars?.nativeElement;
    if (n < 2 || !barsEl) return '';
    const box = barsEl.getBoundingClientRect();
    if (box.width <= 0 || box.height <= 0) return '';
    const cols = barsEl.querySelectorAll('.aa-chart-col');
    if (cols.length !== n) return '';
    const coords: { x: number; y: number }[] = [];
    cols.forEach((col, i) => {
      const r = (col as HTMLElement).getBoundingClientRect();
      const x = ((r.left + r.width / 2) - box.left) / box.width * 100;
      const y = 100 - this.aaClientHeightPct(pts[i]);
      coords.push({
        x,
        y: Math.min(100, Math.max(0, y)),
      });
    });
    let d = `M ${coords[0].x} ${coords[0].y}`;
    for (let i = 0; i < n - 1; i++) {
      const p0 = coords[Math.max(0, i - 1)];
      const p1 = coords[i];
      const p2 = coords[i + 1];
      const p3 = coords[Math.min(n - 1, i + 2)];
      const c1x = p1.x + (p2.x - p0.x) / 6;
      const c1y = Math.min(100, Math.max(0, p1.y + (p2.y - p0.y) / 6));
      const c2x = p2.x - (p3.x - p1.x) / 6;
      const c2y = Math.min(100, Math.max(0, p2.y - (p3.y - p1.y) / 6));
      d += ` C ${c1x} ${c1y}, ${c2x} ${c2y}, ${p2.x} ${p2.y}`;
    }
    return d;
  }
}