import { Component, OnInit, AfterViewInit, ViewChild, ElementRef, HostListener, Output, EventEmitter } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { forkJoin, of } from 'rxjs';
import * as XLSX from 'xlsx';
import { QueryService, DailySummary } from '../services/query';
import { ChangeDetectorRef } from '@angular/core';
import { AuthService } from '../auth';
import { AppConfigService } from '../services/app-config';
import { ActivityAnalysisComponent } from '../activity-analysis/activity-analysis';
import { SelectDropdownComponent } from '../select-dropdown/select-dropdown';
import { MarkdownPipe } from '../markdown.pipe';

interface KpiCard {
  label: string;
  value: string;
}

interface SalespersonBar {
  name: string;
  count: number;
  pct: number;
}

interface DailyBar {
  date: string;
  count: number;
  pct: number;
  isPeak: boolean;
  isLow: boolean;
  showValueLabel: boolean;
  showXLabel: boolean;
  deltaLabel: string;
}

interface ActivityVsSalesRow {
  employee: string;
  activityCount: number;
  salesValue: number;
}

interface RankedEmployee {
  employee: string;
  count: number;
  pct: number;
}

interface EmployeeActivityDay {
  employee: string;
  date: string;
  first_activity_time: string | null;
  last_activity_time: string | null;
  activity_count: number;
}

interface EmployeeDay {
  employee_id: string;
  employee_name: string;
  date: string;
  first_checkin: string | null;
  last_checkin: string | null;
  checkin_count: number;
  working_hours: number | null;
  status: string | null;
}

interface DecliningEmployee {
  employee: string;
  recent: number;
  baseline: number;
}

interface ContactedCustomer {
  customer_id: string;
  customer_name: string;
  contact_count: number;
  last_contact_date?: string | null;
  pct: number;
  monthly_recurring_value_usd: number;
}

interface QuietCustomer {
  customer_name: string;
  total_sales_value: number;
  monthly_recurring_value_usd: number;
  combined_value_usd: number;
}



@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [CommonModule, FormsModule, ActivityAnalysisComponent, SelectDropdownComponent, MarkdownPipe],
  templateUrl: './dashboard.html',
  styleUrl: './dashboard.scss'
})

export class DashboardComponent implements OnInit, AfterViewInit {
  @ViewChild('filterScroller') filterScrollerRef?: ElementRef<HTMLDivElement>;
  @ViewChild('customerInput') customerInputRef?: ElementRef<HTMLInputElement>;
  @ViewChild('summaryTrigger') summaryTriggerRef?: ElementRef<HTMLButtonElement>;

  readonly customerActivityColumns = [
    { key: 'date', label: 'Date' },
    { key: 'type', label: 'Type' },
    { key: 'status', label: 'Status' },
    { key: 'result', label: 'Result' },
  ];

  readonly activityVsSalesColumns = [
    { key: 'employee', label: 'Salesperson' },
    { key: 'activityCount', label: 'Activities' },
    { key: 'salesValue', label: 'Sales value' },
  ];

  readonly opportunitiesInStageColumns = [
    { key: 'customer_name', label: 'Customer' },
    { key: 'owner_user', label: 'Owner' },
    { key: 'total_value_usd', label: 'Value (USD)' },
    { key: 'days_open', label: 'Days open' },
    { key: 'expected_closing_date', label: 'Expected close' },
    { key: 'days_until_close', label: 'Days until close' },
  ];

  readonly employeeDailySummaryColumns = [
    { key: 'employee_name', label: 'Employee' },
    { key: 'date', label: 'Date' },
    { key: 'first_checkin', label: 'First check-in' },
    { key: 'last_checkin', label: 'Last check-in' },
    { key: 'working_hours', label: 'Working hours' },
    { key: 'status', label: 'Status' },
  ];

  readonly employeeActivityWindowColumns = [
    { key: 'employee', label: 'Employee' },
    { key: 'date', label: 'Date' },
    { key: 'first_activity_time', label: 'First activity' },
    { key: 'last_activity_time', label: 'Last activity' },
    { key: 'activity_count', label: 'Activity count' },
  ];

  readonly customerContactFrequencyColumns = [
    { key: 'customer_name', label: 'Customer' },
    { key: 'contact_count', label: 'Contact count' },
    { key: 'monthly_recurring_value_usd', label: 'Monthly value' },
    { key: 'last_contact_date', label: 'Last contact' },
  ];

  readonly highValueQuietCustomersColumns = [
    { key: 'customer_name', label: 'Customer' },
    { key: 'total_sales_value', label: 'Historical sales' },
    { key: 'monthly_recurring_value_usd', label: 'Monthly recurring' },
    { key: 'combined_value_usd', label: 'Combined value' },
  ];

// Sidebar UI state (presentational only -- does not affect filtering/data logic)
  sidebarExpanded = false;
  mobileSidebarOpen = false;

  // KPI category tabs (presentational grouping only -- does not affect
  // any KPI calculation, API call, or filter logic; only changes which
  // already-computed KPI cards are displayed at once)
  selectedKpiCategory = 'today';
  private readonly kpiCategoryIds = ['today', 'sales', 'pipeline', 'trends'];

  // Real timestamp of the last completed backend data sync (from SyncRun),
  // for the "Updated ..." label in the header. This reflects when the
  // underlying data was actually refreshed from ERPNext, not just when
  // the browser last called the API.
  lastSyncCompletedAt: Date | null = null;

  customerDropdownTop = 0;
  customerDropdownLeft = 0;
  customerDropdownWidth = 0;

  summaryDropdownOpen = false;
  summaryDropdownTop = 0;
  summaryDropdownLeft = 0;
  summaryDropdownWidth = 0;

  showFilterArrows = false;
  canScrollLeft = false;
  canScrollRight = false;

  kpis: KpiCard[] = [];
  bars: SalespersonBar[] = [];
  salespeople: string[] = [];
  loading = true;

  area: 'dashboard' | 'activity' = 'dashboard';
  @Output() areaChange = new EventEmitter<'dashboard' | 'activity'>();

  selectedRange = 7;
  selectedSalesperson = 'All';
  customStartDate = '';
  customEndDate = '';

  // Time Range + Group By trend widget -- powers the daily trend chart via
  // real backend aggregation (get_activities_by_time_slot / _by_period),
  // scoped to real Customer Activity Detail records only.
  timeFrom = '';
  timeTo = '';
  groupBy = 'Day';
  readonly groupByOptions: string[] = ['Hour', '30 Minutes', 'Day', 'Week', 'Month', 'Year'];

  ranges = [
    { label: 'Today', days: 1 },
    { label: 'This week', days: 7 },
    { label: 'This month', days: 30 },
  ];

  dailySummaries: DailySummary[] = [];
  selectedSummaryIndex = 0;
  summariesLoading = false;
  generatingSummary = false;

  // New KPI dashboard section (Modernist design)
  kpiActivitiesToday = 0;
  kpiCallsToday = 0;
  kpiClientsContactedToday = 0;
  kpiNewLeads = 0;
  kpiNewOpportunities = 0;
  kpiInvoicesCreated = 0;
  kpiSalesOrdersCreated = 0;
  kpiSalesValue = 0;
  kpiMonthlyRecurringRevenue = 0;
  kpiPendingPayments = 0;
  kpiOverdueFollowups = 0;
  kpiClientsNeedingFollowup = 0;

  // Phase D
  dailyTrend: DailyBar[] = [];
  dailyTrendTotal = 0;
  dailyTrendRangeLabel = '';
  dailyTrendNiceMax = 0;
  dailyTrendTicks: number[] = [];
  dailyTrendAverage = 0;
  dailyTrendAveragePct = 0;
  busiestHours: { hour: number; count: number; pct: number }[] = [];
  busiestDays: { day: string; count: number; pct: number }[] = [];
  activityVsSales: ActivityVsSalesRow[] = [];
  staleCustomerList: { customer_id: string; customer_name: string; last_activity_date: string | null; days_since_activity: number | null; monthly_recurring_value_usd: number }[] = [];
  leadCount = 0;
  opportunityCount = 0;
  leadToOppLinkageAvailable = false;
  leadToOppFromLeadCount = 0;

  // Phase E — filter options + selections
  customerOptions: { customer_id: string; customer_name: string; country: string; monthly_recurring_value_usd: number }[] = [];
  regionOptions: string[] = [];
  activityTypeOptions: string[] = [];
  leadStatusOptions: string[] = [];
  opportunityStageOptions: string[] = [];

  selectedCustomer = '';
  customerQuery = '';
  customerDropdownOpen = false;
  selectedRegion = 'All';
  selectedActivityType = 'All';
  selectedLeadStatus = 'All';
  selectedOpportunityStage = 'All';
  selectedCallResult = 'All';
  callResultOptions: string[] = ['\u2705Complete', '\u23f3In Progress', 'Rejected'];
  selectedFollowupStatus = 'All';
  followupStatusOptions: string[] = ['Open', 'Closed', 'Cancelled', 'Overdue'];
  selectedTimeOfDay = 'All';
  timeOfDayOptions: string[] = ['Morning', 'Afternoon', 'Evening', 'Night'];
  selectedTeam = 'All';
  teamOptions: string[] = [];
activityByTeam: { department: string; count: number; pct: number; priorCount: number; pctChange: number | null; employees: { employeeName: string; count: number; pct: number; salesValue: number }[] }[] = [];
  // Roster headcount by department, independent of CRM activity -- a
  // companion to activityByTeam above, which only surfaces departments
  // that actually logged something. This one answers "who exists" while
  // that one answers "who's active".
  employeeHeadcount: { department: string; count: number; pct: number }[] = [];
  employeeDailySummary: EmployeeDay[] = [];
  employeeActivityWindow: EmployeeActivityDay[] = [];

  customersByCountry: { country: string; count: number; monthlyRecurringValueUsd: number; pct: number }[] = [];
  invoiceAging: { bucket: string; count: number; amount: number; pct: number }[] = [];
  invoiceAgingTotalAmount = 0;
  invoiceAgingTotalCount = 0;
  mrrByManufacturer: { manufacturer: string; count: number; amount: number; pct: number }[] = [];
  mrrStackbarSegments: { manufacturer: string; amount: number; pct: number }[] = [];
  mrrTopCustomers: { customer_name: string; count: number; amount: number; pct: number }[] = [];
  mrrTotalDeviceCount = 0;
  quotationStatusBreakdown: { status: string; count: number; value: number; pct: number }[] = [];
  quotationStatusTotalValue = 0;
  quotationStatusTotalCount = 0;
  sampleTestingFunnel: { stage: string; count: number; pct: number; retainedPct: number }[] = [];
  sampleTestingTotalCount = 0;
  opportunityCloseForecast: { bucket: string; count: number; value: number; pct: number }[] = [];
  opportunityCloseForecastTotalCount = 0;
  opportunitiesByStage: { stage: string; count: number; totalValueUsd: number; pct: number }[] = [];
  opportunitiesInStage: { opportunity_id: string; customer_name: string; pipeline_stage: string; owner_user: string; total_value_usd: number; days_open: number | null; expected_closing_date: string | null; days_until_close: number | null }[] = [];
  customerActivities: { date: string; type: string; status: string; result: string }[] = [];
  customerActivityLoading = false;

  // Phase F -- wiring in previously-unused backend functions
  kpiWeeklyActivityThis = 0;
  kpiWeeklyActivityLast = 0;
  kpiWeeklyActivityChangeLabel = '';
  kpiUniqueCustomersContactedRange = 0;
  kpiOppToQuoteLinked = 0;
  kpiOppToQuoteTotal = 0;
  kpiMonthlyActivityThis = 0;
  kpiMonthlyActivityLast = 0;
  kpiMonthlyDailyAvgThis = 0;
  kpiMonthlyDailyAvgLast = 0;
  kpiMonthlyChangeLabel = '';

  mostActiveEmployees: RankedEmployee[] = [];
  leastActiveEmployees: RankedEmployee[] = [];
  decliningEmployees: DecliningEmployee[] = [];
  mostContactedCustomers: ContactedCustomer[] = [];
  customerContactFrequency: ContactedCustomer[] = [];
  kpiCallToSalesCalled = 0;
  kpiCallToSalesOverlap = 0;
  kpiCallToSalesRate = 0;
  mostCalledCustomers: ContactedCustomer[] = [];
  highValueQuietCustomers: QuietCustomer[] = [];

  constructor(private queryService: QueryService, private cdr: ChangeDetectorRef, public auth: AuthService, public appConfig: AppConfigService) { }

  get teamSelectOptions(): string[] {
    return ['All', ...this.teamOptions];
  }

  get timeOfDaySelectOptions(): string[] {
    return ['All', ...this.timeOfDayOptions];
  }


  get isAdmin(): boolean {
    return this.auth.currentUser()?.role === 'admin';
  }

  get selectedSummary(): DailySummary | undefined {
    return this.dailySummaries[this.selectedSummaryIndex];
  }

get conversionRatioDisplay(): string {
    // Uses the real linked count (opportunities actually created via
    // ERPNext's Lead-conversion workflow) rather than dividing two
    // unrelated monthly totals. See get_lead_to_opportunity_conversion --
    // confirmed 2026-07-16 that this org's process almost always creates
    // Opportunities directly against a Customer, so a low/zero percentage
    // here reflects real workflow, not missing data.
    if (!this.leadToOppLinkageAvailable) return 'Not measurable';
    if (this.leadCount === 0) return '0%';
    return `${Math.round((this.leadToOppFromLeadCount / this.leadCount) * 100)}%`;
  }

  get selectedCustomerName(): string {
    const c = this.customerOptions.find(c => c.customer_id === this.selectedCustomer);
    return c ? c.customer_name : '';
  }

  get salespersonOptions(): string[] {
    return ['All', ...this.salespeople];
  }

  get followupStatusSelectOptions(): string[] {
    return ['All', ...this.followupStatusOptions];
  }

  get callResultSelectOptions(): string[] {
    return ['All', ...this.callResultOptions];
  }

  get regionSelectOptions(): string[] {
    return ['All', ...this.regionOptions];
  }

  get activityTypeSelectOptions(): string[] {
    return ['All', ...this.activityTypeOptions];
  }

  get leadStatusSelectOptions(): string[] {
    return ['All', ...this.leadStatusOptions];
  }

  get opportunityStageSelectOptions(): string[] {
    return ['All', ...this.opportunityStageOptions];
  }

  get filteredCustomerOptions(): { customer_id: string; customer_name: string; country: string }[] {
    const q = this.customerQuery.trim().toLowerCase();
    if (!q) return this.customerOptions.slice(0, 8);
    return this.customerOptions
      .filter(c => c.customer_name.toLowerCase().includes(q))
      .slice(0, 8);
  }

ngOnInit(): void {
    this.areaChange.emit(this.area);
    this.restoreKpiCategory();
    this.loadFilterOptions();
    this.loadData();
    if (this.isAdmin) {
      this.loadSummaries();
    }
    this.loadLastSyncTime();
  }

  private loadLastSyncTime(): void {
    this.queryService.getLastSyncTime().subscribe({
      next: (records) => {
        const completedAt = records[0]?.completed_at;
        this.lastSyncCompletedAt = completedAt ? new Date(completedAt) : null;
        this.cdr.detectChanges();
      },
      error: (err) => {
        console.error('Failed to load last sync time', err);
      }
    });
  }

  private restoreKpiCategory(): void {
    try {
      const saved = localStorage.getItem('boxtech_kpi_category');
      if (saved && this.kpiCategoryIds.includes(saved)) {
        this.selectedKpiCategory = saved;
      }
    } catch {
      // localStorage may be unavailable (e.g. private browsing) -- fall back to 'today'
    }
  }

  selectKpiCategory(id: string): void {
    this.selectedKpiCategory = id;
    try {
      localStorage.setItem('boxtech_kpi_category', id);
    } catch {
      // ignore write failures -- category selection still works for this session
    }
  }

  private loadFilterOptions(): void {
    this.queryService.getDepartmentOptions().subscribe(list => {
      this.teamOptions = list.map(d => d.department);
      this.cdr.detectChanges();
    });
    this.queryService.getCustomerList().subscribe(list => {
      this.customerOptions = list;
      this.regionOptions = [...new Set(list.map(c => c.country).filter(Boolean))].sort();
      this.cdr.detectChanges();
    });
    this.queryService.getActivityTypeOptions().subscribe(list => {
      this.activityTypeOptions = list.map(a => a.activity_type);
      this.cdr.detectChanges();
    });
    this.queryService.getLeadStatusOptions().subscribe(list => {
      this.leadStatusOptions = list.map(s => s.status);
      this.cdr.detectChanges();
    });
    this.queryService.getOpportunityStageOptions().subscribe(list => {
      this.opportunityStageOptions = list.map(s => s.pipeline_stage);
      this.cdr.detectChanges();
    });
  }

  loadSummaries(): void {
    this.summariesLoading = true;
    this.queryService.listDailySummaries(365).subscribe({
      next: (list) => {
        this.dailySummaries = list;
        this.selectedSummaryIndex = 0;
        this.summariesLoading = false;
        this.cdr.detectChanges();
      },
      error: () => {
        this.summariesLoading = false;
        this.cdr.detectChanges();
      },
    });
  }

  selectSummary(index: number): void {
    this.selectedSummaryIndex = index;
    this.summaryDropdownOpen = false;
  }

  toggleSummaryDropdown(): void {
    if (this.summaryDropdownOpen) {
      this.summaryDropdownOpen = false;
      this.cdr.detectChanges();
      return;
    }
    const el = this.summaryTriggerRef?.nativeElement;
    if (el) {
      const rect = el.getBoundingClientRect();
      this.summaryDropdownTop = rect.bottom + 4;
      this.summaryDropdownLeft = rect.left;
      this.summaryDropdownWidth = rect.width;
    }
    this.summaryDropdownOpen = true;
    this.cdr.detectChanges();
  }

  @HostListener('document:click', ['$event'])
  onDocumentClickForSummary(event: MouseEvent): void {
    if (!this.summaryDropdownOpen) return;
    const trigger = this.summaryTriggerRef?.nativeElement;
    const target = event.target as Node;
    if (trigger && !trigger.contains(target) && !(target as HTMLElement).closest('.rt-summary-dropdown-panel')) {
      this.summaryDropdownOpen = false;
      this.cdr.detectChanges();
    }
  }

  generateSummaryNow(): void {
    this.generatingSummary = true;
    this.queryService.generateDailySummary(false).subscribe({
      next: () => {
        this.generatingSummary = false;
        this.loadSummaries();
      },
      error: () => {
        this.generatingSummary = false;
        this.cdr.detectChanges();
      },
    });
  }

switchArea(area: 'dashboard' | 'activity'): void {
    this.area = area;
    this.areaChange.emit(area);
    this.closeMobileSidebar();
  }

  toggleSidebarExpanded(): void {
    this.sidebarExpanded = !this.sidebarExpanded;
  }

  openMobileSidebar(): void {
    this.mobileSidebarOpen = true;
  }

  closeMobileSidebar(): void {
    this.mobileSidebarOpen = false;
  }

  @HostListener('document:keydown.escape')
  onEscapeKey(): void {
    if (this.mobileSidebarOpen) this.closeMobileSidebar();
  }

  normalizeGroupBy(g: string): 'hour' | '30min' | 'day' | 'week' | 'month' | 'year' {
    const s = (g || '').toLowerCase().trim();
    if (s.includes('30') || s.includes('half')) return '30min';
    if (s.includes('hour')) return 'hour';
    if (s.includes('week')) return 'week';
    if (s.includes('month')) return 'month';
    if (s.includes('year')) return 'year';
    return 'day';
  }

  resetAllFilters(): void {
    this.selectedRange = 7;
    this.customStartDate = '';
    this.customEndDate = '';
    this.selectedSalesperson = 'All';
    this.selectedTeam = 'All';
    this.selectedRegion = 'All';
    this.selectedActivityType = 'All';
    this.selectedLeadStatus = 'All';
    this.selectedOpportunityStage = 'All';
    this.selectedCallResult = 'All';
    this.selectedFollowupStatus = 'All';
    this.selectedTimeOfDay = 'All';
    this.timeFrom = '';
    this.timeTo = '';
    this.groupBy = 'Day';
    this.clearCustomerSelection();
    this.onFilterChange();
  }

  selectRange(days: number): void {
    this.selectedRange = days;
    this.customStartDate = '';
    this.customEndDate = '';
    this.onFilterChange();
  }

  onCustomDateChange(): void {
    // An arbitrary range, once both ends are set, takes priority over the
    // preset buttons on the backend (see resolve_period's priority order) --
    // no need to touch selectedRange here.
    if (this.customStartDate && this.customEndDate) {
      this.onFilterChange();
    }
  }

  clearCustomRange(): void {
    this.customStartDate = '';
    this.customEndDate = '';
    this.onFilterChange();
  }

  onFilterChange(): void {
    this.loadData();
  }

  onCustomerSelected(): void {
    if (!this.selectedCustomer) {
      this.customerActivities = [];
      return;
    }
    this.customerActivityLoading = true;
    this.queryService.getActivitiesForCustomer(this.selectedCustomer).subscribe({
      next: (activities) => {
        this.customerActivities = activities;
        this.customerActivityLoading = false;
        this.cdr.detectChanges();
      },
      error: () => {
        this.customerActivityLoading = false;
        this.cdr.detectChanges();
      },
    });
  }

  clearCustomerSelection(): void {
    this.selectedCustomer = '';
    this.customerQuery = '';
    this.customerActivities = [];
  }

private positionCustomerDropdown(): void {
    const el = this.customerInputRef?.nativeElement;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const dropdownMaxHeight = 240;
    const margin = 4;
    const spaceBelow = window.innerHeight - rect.bottom;
    const spaceAbove = rect.top;
    if (spaceBelow < dropdownMaxHeight + margin && spaceAbove > spaceBelow) {
      // Not enough room below -- flip above the input instead so the
      // list never gets clipped by the bottom of the viewport.
      this.customerDropdownTop = Math.max(margin, rect.top - Math.min(dropdownMaxHeight, spaceAbove) - margin);
    } else {
      this.customerDropdownTop = rect.bottom + margin;
    }
    this.customerDropdownLeft = rect.left;
    this.customerDropdownWidth = rect.width;
  }

  onCustomerInputChange(value: string): void {
    this.customerQuery = value;
    this.customerDropdownOpen = true;
    this.positionCustomerDropdown();
    // Typing away from a previously selected customer clears the
    // selection itself, not just the visible text -- otherwise the
    // drill-down panel would keep showing a customer that no longer
    // matches what's in the box.
    if (this.selectedCustomer && value !== this.selectedCustomerName) {
      this.selectedCustomer = '';
      this.customerActivities = [];
    }
    this.cdr.detectChanges();
  }

  onCustomerInputFocus(): void {
    this.customerDropdownOpen = true;
    this.positionCustomerDropdown();
    this.cdr.detectChanges();
  }

  onCustomerInputBlur(): void {
    // Delay so a mousedown on a suggestion fires and registers the
    // selection before blur closes the dropdown out from under it.
    setTimeout(() => {
      this.customerDropdownOpen = false;
      this.cdr.detectChanges();
    }, 150);
  }

  selectCustomerOption(c: { customer_id: string; customer_name: string }): void {
    this.selectedCustomer = c.customer_id;
    this.customerQuery = c.customer_name;
    this.customerDropdownOpen = false;
    this.onCustomerSelected();
  }

  private loadData(): void {
    this.loading = true;

    if (this.isAdmin) {
      this.loadAdminData();
    } else {
      this.loadOwnData();
    }
  }

  private loadAdminData(): void {
    const activityTypeFilter = this.selectedActivityType === 'All' ? undefined : this.selectedActivityType;
    const leadStatusFilter = this.selectedLeadStatus === 'All' ? undefined : this.selectedLeadStatus;
    const stageFilter = this.selectedOpportunityStage === 'All' ? undefined : this.selectedOpportunityStage;
    const employeeFilter = this.selectedSalesperson === 'All' ? undefined : this.selectedSalesperson;
    const regionFilter = this.selectedRegion === 'All' ? undefined : this.selectedRegion;
    const callResultFilter = this.selectedCallResult === 'All' ? undefined : this.selectedCallResult;
    const followupStatusFilter = this.selectedFollowupStatus === 'All' ? 'Overdue' : this.selectedFollowupStatus;
    const timeOfDayFilter = this.selectedTimeOfDay === 'All' ? undefined : this.selectedTimeOfDay;
    const startDateFilter = (this.customStartDate && this.customEndDate) ? this.customStartDate : undefined;
    const endDateFilter = (this.customStartDate && this.customEndDate) ? this.customEndDate : undefined;
    const teamFilter = this.selectedTeam === 'All' ? undefined : this.selectedTeam;
    const timeFromFilter = this.timeFrom || undefined;
    const timeToFilter = this.timeTo || undefined;
    const groupByParam = this.normalizeGroupBy(this.groupBy);

   forkJoin({
      calls: this.queryService.getCallsByEmployee(this.selectedRange, callResultFilter, timeOfDayFilter, startDateFilter, endDateFilter),
      stale: this.queryService.getStaleCustomers(7, regionFilter, startDateFilter, endDateFilter),
      sales: this.queryService.getSalesValueBySalesperson(this.selectedRange, startDateFilter, endDateFilter),
      monthlyRecurringRevenue: this.queryService.getMonthlyRecurringRevenue(),
      monthlyRecurringRevenueByCustomer: this.queryService.getMonthlyRecurringRevenueByCustomer(8),
      quotationStatusBreakdown: this.queryService.getQuotationStatusBreakdown(),
      sampleTestingFunnel: this.queryService.getSampleTestingFunnel(),
      opportunityCloseForecast: this.queryService.getOpportunityCloseForecast(employeeFilter),
      invoices: this.queryService.getTotalSalesValueRecords(this.selectedRange, employeeFilter, startDateFilter, endDateFilter),
      activitiesToday: this.queryService.getActivitiesToday(activityTypeFilter, callResultFilter, timeOfDayFilter, employeeFilter),
      clientsToday: this.queryService.getClientsContactedToday(activityTypeFilter, callResultFilter, timeOfDayFilter, employeeFilter),
      newLeads: this.queryService.getNewLeadsThisMonthFiltered(leadStatusFilter),
      newOpportunities: this.queryService.getNewOpportunitiesThisMonthFiltered(stageFilter),
      pendingPayments: this.queryService.getCustomersWithPendingPayments(),
      invoiceAging: this.queryService.getInvoiceAging(),
      callsToday: this.queryService.getCallsToday(callResultFilter, timeOfDayFilter, employeeFilter),
      salesOrders: this.queryService.getSalesOrdersCreated(this.selectedRange, employeeFilter, startDateFilter, endDateFilter),
      overdueTodos: this.queryService.getTodosByStatus(followupStatusFilter, employeeFilter),
      dailyPattern: this.queryService.getDailyActivityPattern(this.selectedRange, activityTypeFilter, callResultFilter, timeOfDayFilter, employeeFilter, startDateFilter, endDateFilter),
      activitiesByGroup: (groupByParam === 'hour' || groupByParam === '30min')
        ? this.queryService.getActivitiesByTimeSlot(this.selectedRange, timeFromFilter, timeToFilter, activityTypeFilter, callResultFilter, employeeFilter, regionFilter, groupByParam, startDateFilter, endDateFilter)
        : this.queryService.getActivitiesByPeriod(this.selectedRange, timeFromFilter, timeToFilter, activityTypeFilter, callResultFilter, employeeFilter, regionFilter, groupByParam, startDateFilter, endDateFilter),
      activitiesByEmployee: this.queryService.getActivitiesByEmployee(this.selectedRange, startDateFilter, endDateFilter),
      busiestHour: this.queryService.getBusiestHourOfDay(this.selectedRange, callResultFilter, employeeFilter, startDateFilter, endDateFilter),
      busiestDay: this.queryService.getBusiestCallDayOfWeek(this.selectedRange, callResultFilter, timeOfDayFilter, employeeFilter, startDateFilter, endDateFilter),
      customersByCountry: this.queryService.getCustomerList(),
      opportunitiesByStage: this.queryService.getOpportunitiesByStage(employeeFilter),
      opportunitiesInStage: stageFilter ? this.queryService.getOpportunitiesInStage(stageFilter, employeeFilter) : of([]),
      weeklyCompare: this.queryService.compareWeeklyActivity(),
      monthlyCompare: this.queryService.compareMonthlyActivity(),
      clientsReachedRange: this.queryService.getClientsReached(this.selectedRange, employeeFilter, startDateFilter, endDateFilter),
      employeesBelowAvg: this.queryService.getEmployeesBelowAverage(),
  activityByTeam: this.queryService.getActivityByTeam(this.selectedRange, startDateFilter, endDateFilter),
      employeeHeadcount: this.queryService.getEmployeeHeadcount(),
      employeeDailySummary: this.queryService.getEmployeeDailySummary(this.selectedRange, employeeFilter, teamFilter, startDateFilter, endDateFilter),
      employeeActivityWindow: this.queryService.getEmployeeActivityWindow(this.selectedRange, employeeFilter, startDateFilter, endDateFilter),
      callToSalesRatio: this.queryService.getCallToSalesRatio(this.selectedRange, employeeFilter, startDateFilter, endDateFilter),
      mostContacted: this.queryService.getMostAndLeastContactedClients(this.selectedRange, regionFilter, callResultFilter, timeOfDayFilter, startDateFilter, endDateFilter),
      callsByCustomer: this.queryService.getCallsByCustomer(this.selectedRange, regionFilter, callResultFilter, timeOfDayFilter, startDateFilter, endDateFilter),
      oppToQuote: this.queryService.getOpportunityToQuotationConversion(),
      leadToOppConversion: this.queryService.getLeadToOpportunityConversion(),
      highValueQuiet: this.queryService.getHighValueLowEngagementCustomers(14, 1000, regionFilter, startDateFilter, endDateFilter),
    }).subscribe({
      next: (r) => {
        if (this.salespeople.length === 0) {
          this.salespeople = [...new Set(r.calls.map(c => c.employee).filter(Boolean))];
        }

        const filteredCalls = this.selectedSalesperson === 'All'
          ? r.calls
          : r.calls.filter(c => c.employee === this.selectedSalesperson);

        const filteredSales = this.selectedSalesperson === 'All'
          ? r.sales
          : r.sales.filter(s => s.salesperson === this.selectedSalesperson);

        const totalSalesValue = filteredSales.reduce((sum, s) => sum + s.total_value, 0);
        const pendingTotal = r.pendingPayments.reduce((sum, p) => sum + (p.outstanding || 0), 0);
        const mrrTotal = r.monthlyRecurringRevenue.reduce((sum, m) => sum + m.monthly_value, 0);

        this.leadCount = r.newLeads.length;
        this.opportunityCount = r.newOpportunities.length;

        this.kpiActivitiesToday = r.activitiesToday[0]?.activity_count ?? 0;
        this.kpiCallsToday = r.callsToday.length;
        this.kpiClientsContactedToday = r.clientsToday[0]?.clients_contacted ?? 0;
        this.kpiNewLeads = r.newLeads.length;
        this.kpiNewOpportunities = r.newOpportunities.length;
        this.kpiInvoicesCreated = r.invoices.length;
        this.kpiSalesOrdersCreated = r.salesOrders.length;
        this.kpiSalesValue = totalSalesValue;
        this.kpiMonthlyRecurringRevenue = mrrTotal;
        this.kpiPendingPayments = pendingTotal;
        this.kpiOverdueFollowups = r.overdueTodos.length;
        this.kpiClientsNeedingFollowup = r.stale.length;

        this.kpis = [
          { label: 'Activities today', value: `${r.activitiesToday[0]?.activity_count ?? 0}` },
          { label: 'Calls today', value: `${r.callsToday.length}` },
          { label: 'Clients contacted today', value: `${r.clientsToday[0]?.clients_contacted ?? 0}` },
          { label: 'New leads (month)', value: `${r.newLeads.length}` },
          { label: 'New opportunities (month)', value: `${r.newOpportunities.length}` },
          { label: 'Lead -> opportunity conversion', value: this.conversionRatioDisplay },
          { label: `Invoices created (${this.rangeLabel()})`, value: `${r.invoices.length}` },
          { label: `Sales orders created (${this.rangeLabel()})`, value: `${r.salesOrders.length}` },
          { label: `Sales value (${this.rangeLabel()})`, value: `$${totalSalesValue.toLocaleString()}` },
          { label: 'Monthly recurring device revenue', value: `$${mrrTotal.toLocaleString()}` },
          { label: 'Pending payments', value: `$${pendingTotal.toLocaleString()}` },
          { label: this.selectedFollowupStatus === 'All' ? 'Overdue follow-ups' : `${this.selectedFollowupStatus} follow-ups`, value: `${r.overdueTodos.length}` },
          { label: 'Clients needing follow-up', value: `${r.stale.length}` },
        ];

        const max = Math.max(1, ...filteredCalls.map(c => c.call_count));
        this.bars = filteredCalls
          .sort((a, b) => b.call_count - a.call_count)
          .map(c => ({ name: c.employee, count: c.call_count, pct: Math.round((c.call_count / max) * 100) }));

        this.buildDailyTrendChart(r.dailyPattern, r.activitiesByGroup);

        const hourMax = Math.max(1, ...r.busiestHour.map(h => h.count));
        this.busiestHours = r.busiestHour
          .sort((a, b) => a.hour - b.hour)
          .map(h => ({ hour: h.hour, count: h.count, pct: Math.round((h.count / hourMax) * 100) }));

        const dayOrder = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
        const dayMax = Math.max(1, ...r.busiestDay.map(d => d.count));
        this.busiestDays = [...r.busiestDay]
          .sort((a, b) => dayOrder.indexOf(a.day) - dayOrder.indexOf(b.day))
          .map(d => ({ day: d.day, count: d.count, pct: Math.round((d.count / dayMax) * 100) }));

        const salesByEmployee = new Map(r.sales.map(s => [s.salesperson, s.total_value]));
        this.activityVsSales = r.activitiesByEmployee
          .filter(a => a.employee)
          .map(a => ({
            employee: a.employee,
            activityCount: a.count,
            salesValue: salesByEmployee.get(a.employee) || 0,
          }))
          .sort((a, b) => b.activityCount - a.activityCount);

        this.staleCustomerList = r.stale.slice(0, 10);

        // Region breakdown, filtered client-side by selected region if set
        const regionSource = this.selectedRegion === 'All'
          ? r.customersByCountry
          : r.customersByCountry.filter(c => c.country === this.selectedRegion);
        const countryCounts = new Map<string, number>();
        const countryValues = new Map<string, number>();
        for (const c of regionSource) {
          const key = c.country || 'Unspecified';
          countryCounts.set(key, (countryCounts.get(key) || 0) + 1);
          countryValues.set(key, (countryValues.get(key) || 0) + (c.monthly_recurring_value_usd || 0));
        }
        const countryValueMax = Math.max(1, ...Array.from(countryValues.values()));
        this.customersByCountry = Array.from(countryCounts.entries())
          .sort((a, b) => (countryValues.get(b[0]) || 0) - (countryValues.get(a[0]) || 0))
          .slice(0, 10)
          .map(([country, count]) => ({
            country,
            count,
            monthlyRecurringValueUsd: countryValues.get(country) || 0,
            pct: Math.round(((countryValues.get(country) || 0) / countryValueMax) * 100),
          }));

        const agingTotalAmount = r.invoiceAging.reduce((sum, a) => sum + a.amount, 0);
        this.invoiceAgingTotalAmount = agingTotalAmount;
        this.invoiceAgingTotalCount = r.invoiceAging.reduce((sum, a) => sum + a.count, 0);
        this.invoiceAging = r.invoiceAging.map(a => ({
          bucket: a.bucket,
          count: a.count,
          amount: a.amount,
          pct: agingTotalAmount > 0 ? Math.round((a.amount / agingTotalAmount) * 100) : 0,
        }));

        this.mrrTotalDeviceCount = r.monthlyRecurringRevenue.reduce((sum, m) => sum + m.device_count, 0);
        const sortedMfrs = [...r.monthlyRecurringRevenue].sort((a, b) => b.monthly_value - a.monthly_value);
        this.mrrByManufacturer = sortedMfrs.map(m => ({
          manufacturer: m.manufacturer,
          count: m.device_count,
          amount: m.monthly_value,
          pct: mrrTotal > 0 ? Math.round((m.monthly_value / mrrTotal) * 100) : 0,
        }));

        // Stacked bar stays readable with a mix of many small manufacturers --
        // top 4 individually, everything else rolled into "Other".
        const mrrStackTopN = 4;
        const mrrStackTop = sortedMfrs.slice(0, mrrStackTopN);
        const mrrStackOtherAmount = sortedMfrs.slice(mrrStackTopN).reduce((sum, m) => sum + m.monthly_value, 0);
        this.mrrStackbarSegments = [
          ...mrrStackTop.map(m => ({
            manufacturer: m.manufacturer,
            amount: m.monthly_value,
            pct: mrrTotal > 0 ? Math.round((m.monthly_value / mrrTotal) * 100) : 0,
          })),
          ...(mrrStackOtherAmount > 0 ? [{
            manufacturer: 'Other',
            amount: mrrStackOtherAmount,
            pct: mrrTotal > 0 ? Math.round((mrrStackOtherAmount / mrrTotal) * 100) : 0,
          }] : []),
        ];

        this.mrrTopCustomers = r.monthlyRecurringRevenueByCustomer.map(c => ({
          customer_name: c.customer_name,
          count: c.device_count,
          amount: c.monthly_value,
          pct: mrrTotal > 0 ? Math.round((c.monthly_value / mrrTotal) * 100) : 0,
        }));

        const quotationTotalValue = r.quotationStatusBreakdown.reduce((sum, q) => sum + q.value, 0);
        this.quotationStatusTotalValue = quotationTotalValue;
        this.quotationStatusTotalCount = r.quotationStatusBreakdown.reduce((sum, q) => sum + q.count, 0);
        this.quotationStatusBreakdown = r.quotationStatusBreakdown.map(q => ({
          status: q.status,
          count: q.count,
          value: q.value,
          pct: quotationTotalValue > 0 ? Math.round((q.value / quotationTotalValue) * 100) : 0,
        }));

        this.sampleTestingTotalCount = r.sampleTestingFunnel.reduce((sum, s) => sum + s.count, 0);
        const sampleTestingTotal = this.sampleTestingTotalCount;
        const sampleTestingEntryCount = r.sampleTestingFunnel[0]?.count ?? 0;
        this.sampleTestingFunnel = r.sampleTestingFunnel.map(s => ({
          stage: s.stage,
          count: s.count,
          pct: sampleTestingTotal > 0 ? Math.round((s.count / sampleTestingTotal) * 100) : 0,
          retainedPct: sampleTestingEntryCount > 0 ? Math.round((s.count / sampleTestingEntryCount) * 100) : 0,
        }));

        // Bar length is based on deal COUNT, not dollar value -- total_value_usd
        // is sparsely populated on Opportunity rows (confirmed via direct query),
        // so count is the more trustworthy signal here even though value is
        // still shown per bucket for whatever coverage exists.
        this.opportunityCloseForecastTotalCount = r.opportunityCloseForecast.reduce((sum, o) => sum + o.count, 0);
        const forecastTotalCount = this.opportunityCloseForecastTotalCount;
        this.opportunityCloseForecast = r.opportunityCloseForecast.map(o => ({
          bucket: o.bucket,
          count: o.count,
          value: o.value,
          pct: forecastTotalCount > 0 ? Math.round((o.count / forecastTotalCount) * 100) : 0,
        }));

        const stageValueMax = Math.max(1, ...r.opportunitiesByStage.map(s => s.total_value_usd));
        this.opportunitiesByStage = r.opportunitiesByStage.map(s => ({
          stage: s.stage,
          count: s.count,
          totalValueUsd: s.total_value_usd,
          pct: Math.round((s.total_value_usd / stageValueMax) * 100),
        }));

        this.opportunitiesInStage = r.opportunitiesInStage;

        // Weekly comparison
        const thisWeek = r.weeklyCompare.find(w => w.period === 'This week')?.count ?? 0;
        const lastWeek = r.weeklyCompare.find(w => w.period === 'Last week')?.count ?? 0;
        const weeklyChange = thisWeek - lastWeek;
        this.kpiWeeklyActivityThis = thisWeek;
        this.kpiWeeklyActivityLast = lastWeek;
        this.kpiWeeklyActivityChangeLabel = `${weeklyChange >= 0 ? '+' : ''}${weeklyChange}`;

        // Monthly comparison -- daily average is the fair number, since
        // "this month" is always partial (see compare_monthly_activity)
        const thisMonthRec = r.monthlyCompare.find(m => m.period === 'This month (to date)');
        const lastMonthRec = r.monthlyCompare.find(m => m.period === 'Last month (full)');
        this.kpiMonthlyActivityThis = thisMonthRec?.count ?? 0;
        this.kpiMonthlyActivityLast = lastMonthRec?.count ?? 0;
        this.kpiMonthlyDailyAvgThis = thisMonthRec?.daily_avg ?? 0;
        this.kpiMonthlyDailyAvgLast = lastMonthRec?.daily_avg ?? 0;
        const monthlyAvgChange = Math.round((this.kpiMonthlyDailyAvgThis - this.kpiMonthlyDailyAvgLast) * 10) / 10;
        this.kpiMonthlyChangeLabel = `${monthlyAvgChange >= 0 ? '+' : ''}${monthlyAvgChange}`;

        // Unique customers contacted over the selected range (distinct from the fixed "today" KPI)
        this.kpiUniqueCustomersContactedRange = r.clientsReachedRange[0]?.clients_reached ?? 0;

        // Opportunity -> Quotation link rate
        this.kpiOppToQuoteTotal = r.oppToQuote.find(m => m.metric === 'Total opportunities')?.value ?? 0;
        this.kpiOppToQuoteLinked = r.oppToQuote.find(m => m.metric === 'Quotations linked to an opportunity')?.value ?? 0;

        // Lead -> Opportunity linkage availability (see conversionRatioDisplay getter)
        this.leadToOppLinkageAvailable = !!r.leadToOppConversion.find(m => m.metric === 'linkage_available')?.value;
        this.leadToOppFromLeadCount = Number(r.leadToOppConversion.find(m => m.metric === 'Opportunities created from a Lead (month)')?.value ?? 0);

        // Most / least active employees -- reuses the activitiesByEmployee data already
        // fetched above (general activity volume), independent of the calls-only chart.
        const namedActivities = r.activitiesByEmployee.filter(a => a.employee);
        const activityMax = Math.max(1, ...namedActivities.map(a => a.count));
        this.mostActiveEmployees = [...namedActivities]
          .sort((a, b) => b.count - a.count)
          .slice(0, 5)
          .map(a => ({ employee: a.employee, count: a.count, pct: Math.round((a.count / activityMax) * 100) }));
        this.leastActiveEmployees = [...namedActivities]
          .sort((a, b) => a.count - b.count)
          .slice(0, 5)
          .map(a => ({ employee: a.employee, count: a.count, pct: Math.round((a.count / activityMax) * 100) }));

        // Employees below their own recent-activity baseline (a different signal than
        // ranking above: this flags a *drop*, not a low absolute rank).
        this.decliningEmployees = r.employeesBelowAvg.map(e => ({
          employee: e.employee,
          recent: e.recent_daily_avg,
          baseline: e.baseline_daily_avg,
        }));

        // Activity by team -- real Team filter, built on ERPNext Department
        // data. Empty until Employee/Department access is granted; the
        // dropdown options are derived from whatever this returns, so it
        // naturally stays empty (showing just "All") until then too.
        const teamMax = Math.max(1, ...r.activityByTeam.map(t => t.count));
        this.activityByTeam = r.activityByTeam.map(t => {
          const empMax = Math.max(1, ...t.employees.map(e => e.count));
          return {
            department: t.department,
            count: t.count,
            pct: Math.round((t.count / teamMax) * 100),
            priorCount: t.prior_count,
            pctChange: t.pct_change,
            employees: t.employees.map(e => ({
              employeeName: e.employee_name,
              count: e.count,
              pct: Math.round((e.count / empMax) * 100),
              salesValue: e.sales_value,
            })),
          };
        });

      // Roster headcount -- a plain snapshot, not time-windowed like
        // everything else on this page, so it doesn't depend on
        // selectedRange/startDateFilter/endDateFilter at all.
        const headcountMax = Math.max(1, ...r.employeeHeadcount.map(t => t.employee_count));
        this.employeeHeadcount = r.employeeHeadcount.map(t => ({
          department: t.department,
          count: t.employee_count,
          pct: Math.round((t.employee_count / headcountMax) * 100),
        }));

        this.employeeDailySummary = r.employeeDailySummary;
        this.employeeActivityWindow = r.employeeActivityWindow;

       // Most contacted customers -- join customer_id back to a display name
        // (and recurring value, for context alongside contact frequency)
        const custNameMap = new Map(this.customerOptions.map(c => [c.customer_id, c.customer_name]));
        const custValueMap = new Map(this.customerOptions.map(c => [c.customer_id, c.monthly_recurring_value_usd]));
        const contactedTop = r.mostContacted.slice(0, 10);
        const contactedMax = Math.max(1, ...contactedTop.map(c => c.contact_count));
        this.mostContactedCustomers = contactedTop.map(c => ({
          customer_id: c.customer_id,
          customer_name: custNameMap.get(c.customer_id) || c.customer_id,
          contact_count: c.contact_count,
          last_contact_date: c.last_contact_date,
          pct: Math.round((c.contact_count / contactedMax) * 100),
          monthly_recurring_value_usd: custValueMap.get(c.customer_id) || 0,
        }));

        // Customer contact frequency + last contact date -- explicit table
        // form of the checklist's "customer contact frequency and last
        // contact date" ask. Reuses the same fetched data as the chart
        // above (no extra backend call), just with more rows (top 25).
        const freqTop = r.mostContacted.slice(0, 25);
        const freqMax = Math.max(1, ...freqTop.map(c => c.contact_count));
        this.customerContactFrequency = freqTop.map(c => ({
          customer_id: c.customer_id,
          customer_name: custNameMap.get(c.customer_id) || c.customer_id,
          contact_count: c.contact_count,
          last_contact_date: c.last_contact_date,
          pct: Math.round((c.contact_count / freqMax) * 100),
          monthly_recurring_value_usd: custValueMap.get(c.customer_id) || 0,
        }));

        // Most called customers (calls only, matching the activity_scenario filter
        // used elsewhere for "calls" as distinct from general contact/activity)
        const calledTop = r.callsByCustomer.slice(0, 10);
        const calledMax = Math.max(1, ...calledTop.map(c => c.call_count));
        this.mostCalledCustomers = calledTop.map(c => ({
          customer_id: c.customer_id,
          customer_name: custNameMap.get(c.customer_id) || c.customer_id,
          contact_count: c.call_count,
          pct: Math.round((c.call_count / calledMax) * 100),
          monthly_recurring_value_usd: custValueMap.get(c.customer_id) || 0,
        }));

       // Call-to-sales correlation (customer-level, not a causal record
        // link -- see get_call_to_sales_ratio's docstring)
        this.kpiCallToSalesCalled = Number(r.callToSalesRatio.find(m => m.metric === 'Customers called')?.value ?? 0);
        this.kpiCallToSalesOverlap = Number(r.callToSalesRatio.find(m => m.metric === 'Customers called AND with a new sales order')?.value ?? 0);
        this.kpiCallToSalesRate = Number(r.callToSalesRatio.find(m => m.metric === 'Correlation rate (%)')?.value ?? 0);

        // High-value customers with no recent engagement
        this.highValueQuietCustomers = r.highValueQuiet.slice(0, 10);

        this.loading = false;
        this.cdr.detectChanges();
      },
      error: (err) => {
        console.error('Dashboard load failed', err);
        this.loading = false;
        this.cdr.detectChanges();
      }
    });
  }

  private loadOwnData(): void {
    const leadStatusFilter = this.selectedLeadStatus === 'All' ? undefined : this.selectedLeadStatus;
    const stageFilter = this.selectedOpportunityStage === 'All' ? undefined : this.selectedOpportunityStage;
    const timeFromFilter = this.timeFrom || undefined;
    const timeToFilter = this.timeTo || undefined;
    const groupByParam = this.normalizeGroupBy(this.groupBy);

    forkJoin({
      calls: this.queryService.getCallsBySalespersonThisWeek(),
      stale: this.queryService.getStaleCustomers(7),
      invoices: this.queryService.getTotalSalesValueRecords(this.selectedRange),
      activitiesToday: this.queryService.getActivitiesToday(),
      clientsToday: this.queryService.getClientsContactedToday(),
      newLeads: this.queryService.getNewLeadsThisMonthFiltered(leadStatusFilter),
      newOpportunities: this.queryService.getNewOpportunitiesThisMonthFiltered(stageFilter),
      pendingPayments: this.queryService.getCustomersWithPendingPayments(),
      monthlyRecurringRevenue: this.queryService.getMonthlyRecurringRevenue(),
      callsToday: this.queryService.getCallsToday(),
      salesOrders: this.queryService.getSalesOrdersCreated(this.selectedRange),
      overdueTodos: this.queryService.getOverdueTodos(),
      // Admin-only report -- returns empty records for sales_user (see
      // BLOCKED_FOR_SALES_USER on the backend), so this renders an empty
      // trend chart rather than an error for that role.
      activitiesByGroup: (groupByParam === 'hour' || groupByParam === '30min')
        ? this.queryService.getActivitiesByTimeSlot(this.selectedRange, timeFromFilter, timeToFilter, undefined, undefined, undefined, undefined, groupByParam, undefined, undefined)
        : this.queryService.getActivitiesByPeriod(this.selectedRange, timeFromFilter, timeToFilter, undefined, undefined, undefined, undefined, groupByParam, undefined, undefined),
    }).subscribe({

      next: ({ calls, stale, invoices, activitiesToday, clientsToday, newLeads, newOpportunities, pendingPayments, monthlyRecurringRevenue, callsToday, salesOrders, overdueTodos, activitiesByGroup }) => {
        const totalSalesValue = invoices.reduce((sum, i) => sum + (i.value || 0), 0);
        const pendingTotal = pendingPayments.reduce((sum, p) => sum + (p.outstanding || 0), 0);
        const mrrTotal = monthlyRecurringRevenue.reduce((sum, m) => sum + m.monthly_value, 0);

        this.leadCount = newLeads.length;
        this.opportunityCount = newOpportunities.length;

        this.kpiActivitiesToday = activitiesToday[0]?.activity_count ?? 0;
        this.kpiCallsToday = callsToday.length;
        this.kpiClientsContactedToday = clientsToday[0]?.clients_contacted ?? 0;
        this.kpiNewLeads = newLeads.length;
        this.kpiNewOpportunities = newOpportunities.length;
        this.kpiInvoicesCreated = invoices.length;
        this.kpiSalesOrdersCreated = salesOrders.length;
        this.kpiSalesValue = totalSalesValue;
        this.kpiMonthlyRecurringRevenue = mrrTotal;
        this.kpiPendingPayments = pendingTotal;
        this.kpiOverdueFollowups = overdueTodos.length;
        this.kpiClientsNeedingFollowup = stale.length;

        this.kpis = [
          { label: 'Activities today', value: `${activitiesToday[0]?.activity_count ?? 0}` },
          { label: 'Calls today', value: `${callsToday.length}` },
          { label: 'Clients contacted today', value: `${clientsToday[0]?.clients_contacted ?? 0}` },
          { label: 'New leads (month)', value: `${newLeads.length}` },
          { label: 'New opportunities (month)', value: `${newOpportunities.length}` },
          { label: 'Lead -> opportunity conversion', value: this.conversionRatioDisplay },
          { label: `Invoices created (${this.rangeLabel()})`, value: `${invoices.length}` },
          { label: `Sales orders created (${this.rangeLabel()})`, value: `${salesOrders.length}` },
          { label: `Sales value (${this.rangeLabel()})`, value: `$${totalSalesValue.toLocaleString()}` },
          { label: 'Monthly recurring device revenue', value: `$${mrrTotal.toLocaleString()}` },
          { label: 'Pending payments', value: `$${pendingTotal.toLocaleString()}` },
          { label: 'Overdue follow-ups', value: `${overdueTodos.length}` },
          { label: 'Clients needing follow-up', value: `${stale.length}` },
        ];

        const max = Math.max(1, ...calls.map(c => c.count));
        this.bars = calls
          .sort((a, b) => b.count - a.count)
          .map(c => ({ name: c.salesperson, count: c.count, pct: Math.round((c.count / max) * 100) }));

        this.buildDailyTrendChart([], activitiesByGroup);

        this.loading = false;
        this.cdr.detectChanges();
      },
      error: (err) => {
        console.error('Dashboard load failed', err);
        this.loading = false;
        this.cdr.detectChanges();
      }
    });
  }

  private buildDailyTrendChart(pattern: { date: string; count: number }[], groupedActivities?: { time_slot?: string; period?: string; activity_count?: number }[]): void {
    // When the Group By widget selects Hour/30min/Week/Month/Year, the
    // chart is driven by get_activities_by_time_slot / _by_period instead
    // of the plain daily pattern -- both are real, backend-aggregated data
    // over customer_activity_details, just bucketed differently.
    if (groupedActivities && groupedActivities.length > 0) {
      const data = groupedActivities;
      const total = data.reduce((sum, d) => sum + (d.activity_count ?? 0), 0);
      const rawMax = Math.max(1, ...data.map(d => d.activity_count ?? 0));
      const rawMin = Math.min(...data.map(d => d.activity_count ?? 0));
      const niceMax = Math.ceil(rawMax / 20) * 20 || 20;
      const step = niceMax / 4;
      const peakValue = rawMax;
      const average = total / data.length;

      this.dailyTrend = data.map((d, i) => {
        const count = d.activity_count ?? 0;
        const label = d.time_slot ?? d.period ?? '';
        const isPeak = count === peakValue && peakValue > 0;
        const isLow = count === rawMin && rawMax > rawMin;
        const prev = i > 0 ? data[i - 1] : null;
        let deltaLabel = '';
        if (prev) {
          const prevCount = prev.activity_count ?? 0;
          if (prevCount > 0) {
            const deltaPct = Math.round(((count - prevCount) / prevCount) * 100);
            deltaLabel = deltaPct === 0 ? ' \u00b7 flat vs prior' : ` \u00b7 ${deltaPct > 0 ? '+' : ''}${deltaPct}% vs prior`;
          } else if (count > 0) {
            deltaLabel = ' \u00b7 up from 0 prior';
          }
        }
        return {
          date: label,
          count,
          pct: Math.round((count / niceMax) * 100),
          isPeak,
          isLow,
          showValueLabel: isPeak || (peakValue > 0 && count >= peakValue * 0.95),
          showXLabel: isPeak || i % 2 === 0,
          deltaLabel,
        };
      });

      this.dailyTrendTotal = total;
      this.dailyTrendRangeLabel = this.rangeLabel();
      this.dailyTrendNiceMax = niceMax;
      this.dailyTrendTicks = [4, 3, 2, 1, 0].map(m => Math.round(step * m));
      this.dailyTrendAverage = Math.round(average * 10) / 10;
      this.dailyTrendAveragePct = Math.round((average / niceMax) * 100);
      return;
    }

    if (pattern.length === 0) {
      this.dailyTrend = [];
      this.dailyTrendTotal = 0;
      this.dailyTrendRangeLabel = '';
      this.dailyTrendNiceMax = 0;
      this.dailyTrendTicks = [];
      this.dailyTrendAverage = 0;
      this.dailyTrendAveragePct = 0;
      return;
    }

    const sorted = [...pattern].sort((a, b) => a.date.localeCompare(b.date));
    const total = sorted.reduce((sum, d) => sum + d.count, 0);
    const rawMax = Math.max(1, ...sorted.map(d => d.count));
    const rawMin = Math.min(...sorted.map(d => d.count));
    const niceMax = Math.ceil(rawMax / 20) * 20 || 20;
    const step = niceMax / 4;
    const peakValue = rawMax;
    const average = total / sorted.length;

    const formatLabel = (iso: string): string => {
      const d = new Date(iso + 'T00:00:00');
      return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    };

    this.dailyTrend = sorted.map((d, i) => {
      const isPeak = d.count === peakValue && peakValue > 0;
      const isLow = d.count === rawMin && rawMax > rawMin;
      const prev = i > 0 ? sorted[i - 1] : null;
      let deltaLabel = '';
      if (prev) {
        if (prev.count > 0) {
          const deltaPct = Math.round(((d.count - prev.count) / prev.count) * 100);
          deltaLabel = deltaPct === 0 ? ' \u00b7 flat vs prior day' : ` \u00b7 ${deltaPct > 0 ? '+' : ''}${deltaPct}% vs prior day`;
        } else if (d.count > 0) {
          deltaLabel = ' \u00b7 up from 0 the prior day';
        }
      }
      return {
        date: formatLabel(d.date),
        count: d.count,
        pct: Math.round((d.count / niceMax) * 100),
        isPeak,
        isLow,
        showValueLabel: isPeak || (peakValue > 0 && d.count >= peakValue * 0.95),
        // Thin x-axis labels to every other day, but always keep the peak visible.
        showXLabel: isPeak || i % 2 === 0,
        deltaLabel,
      };
    });

    this.dailyTrendTotal = total;
    this.dailyTrendNiceMax = niceMax;
    this.dailyTrendTicks = [4, 3, 2, 1, 0].map(m => Math.round(step * m));
    this.dailyTrendAverage = Math.round(average * 10) / 10;
    this.dailyTrendAveragePct = Math.round((average / niceMax) * 100);

    const first = formatLabel(sorted[0].date);
    const last = formatLabel(sorted[sorted.length - 1].date);
    const year = new Date(sorted[sorted.length - 1].date + 'T00:00:00').getFullYear();
    this.dailyTrendRangeLabel = `${first} \u2013 ${last}, ${year}`;
  }

private rangeLabel(): string {
    if (this.customStartDate && this.customEndDate) {
      return `${this.customStartDate} to ${this.customEndDate}`;
    }
    return this.ranges.find(r => r.days === Number(this.selectedRange))?.label ?? '';
  }

  rangeLabelLower(): string {
    return this.rangeLabel().toLowerCase();
  }

  /** Real link-rate percentage behind the Opportunity -> Quotation circular progress ring. */
  oppToQuoteRatePct(): number {
    if (!this.kpiOppToQuoteTotal) return 0;
    return (this.kpiOppToQuoteLinked / this.kpiOppToQuoteTotal) * 100;
  }

  oppToQuoteRateLabel(): string {
    return this.oppToQuoteRatePct().toFixed(1);
  }

  /** stroke-dasharray for the r=13 progress ring (circumference = 2*PI*13 = 81.68). */
  oppToQuoteRateDashArray(): string {
    const circumference = 81.68;
    const filled = (this.oppToQuoteRatePct() / 100) * circumference;
    return `${filled.toFixed(2)} ${circumference}`;
  }

  summaryParagraphs(content: string | undefined | null): string[] {
    if (!content) return [];
    return content
      .split(/\n\s*\n/)
      .map(p => p.trim())
      .filter(Boolean);
  }

  summaryIconType(paragraph: string): 'positive' | 'warning' | 'info' {
    const text = (paragraph || '').toLowerCase();
    const warningWords = [
      'no activity', 'no recent', 'no new', 'zero', 'follow-up needed', 'needs attention',
      'overdue', 'at risk', 'declin', 'drop', 'no leads', 'no calls', 'missing',
    ];
    if (warningWords.some(w => text.includes(w))) return 'warning';

    const positiveWords = [
      'top performing', 'top performer', 'increase', 'growth', 'strong', 'healthy',
      'up ', 'highest', 'best', 'exceeded', 'improved',
    ];
    if (positiveWords.some(w => text.includes(w))) return 'positive';

    return 'info';
  }

  employeeInitials(identifier: string): string {
    const raw = (identifier || '').trim();
    if (!raw) return '?';
    const localPart = raw.includes('@') ? raw.split('@')[0] : raw;
    const parts = localPart.split(/[\s._-]+/).filter(Boolean);
    if (parts.length === 0) return '?';
    if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
    return (parts[0].charAt(0) + parts[parts.length - 1].charAt(0)).toUpperCase();
  }

  private readonly avatarPalette = ['#3B6CF0', '#8B5CF6', '#E39A2D', '#E0533D', '#2F6B4F'];
  private readonly avatarPaletteSoft = ['#E8EFFD', '#F1EBFE', '#FCF1E1', '#FBEAE7', '#E7F0EA'];

  avatarColor(index: number): string {
    return this.avatarPalette[index % this.avatarPalette.length];
  }

  avatarColorSoft(index: number): string {
    return this.avatarPaletteSoft[index % this.avatarPaletteSoft.length];
  }

  activityBarWidth(count: number): number {
    const max = Math.max(1, ...this.activityVsSales.map(r => r.activityCount));
    return Math.round((count / max) * 100);
  }

  daysAgoLabel(days: number | null): string {
    if (days === null || days === undefined) return 'No activity on record';
    if (days === 0) return 'Today';
    if (days === 1) return '1 day ago';
    return `${days} days ago`;
  }

  updatedLabel(): string {
    if (!this.lastSyncCompletedAt) return '';
    const datePart = this.lastSyncCompletedAt.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
    const timePart = this.lastSyncCompletedAt.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' });
    return `Updated ${datePart} at ${timePart}`;
  }

  displayHours(): { hour: number; count: number; pct: number }[] {
    const byHour = new Map(this.busiestHours.map(h => [h.hour, h]));
    const result: { hour: number; count: number; pct: number }[] = [];
    for (let hour = 9; hour <= 21; hour++) {
      result.push(byHour.get(hour) ?? { hour, count: 0, pct: 0 });
    }
    return result;
  }

  peakHours(): { hour: number; count: number }[] {
    if (!this.busiestHours.length) return [];
    const max = Math.max(...this.busiestHours.map(h => h.count));
    return this.busiestHours.filter(h => h.count === max);
  }

  highestDays(): { day: string; count: number }[] {
    if (!this.busiestDays.length) return [];
    const max = Math.max(...this.busiestDays.map(d => d.count));
    return this.busiestDays.filter(d => d.count === max);
  }

  lowestDays(): { day: string; count: number }[] {
    if (!this.busiestDays.length) return [];
    const min = Math.min(...this.busiestDays.map(d => d.count));
    return this.busiestDays.filter(d => d.count === min);
  }

  formatHourList(hours: { hour: number; count: number }[]): string {
    return hours.map(h => `${h.hour}:00`).join(' & ');
  }

  formatDayList(days: { day: string; count: number }[]): string {
    return days.map(d => d.day).join(' & ');
  }

  private readonly countryIsoCodes: Record<string, string> = {
    'saudi arabia': 'sa',
    'pakistan': 'pk',
    'united arab emirates': 'ae',
    'uae': 'ae',
    'afghanistan': 'af',
    'iraq': 'iq',
    'united states': 'us',
    'usa': 'us',
    'iran': 'ir',
    'lebanon': 'lb',
    'syria': 'sy',
    'egypt': 'eg',
    'jordan': 'jo',
    'kuwait': 'kw',
    'qatar': 'qa',
    'bahrain': 'bh',
    'oman': 'om',
    'yemen': 'ye',
    'india': 'in',
    'china': 'cn',
    'turkey': 'tr',
    'united kingdom': 'gb',
    'uk': 'gb',
    'germany': 'de',
    'france': 'fr',
  };

  countryFlagCode(country: string): string | null {
    return this.countryIsoCodes[(country || '').trim().toLowerCase()] || null;
  }

  countryFlagUrl(country: string): string {
    const code = this.countryFlagCode(country);
    return code ? `https://flagcdn.com/24x18/${code}.png` : '';
  }

  stageIconKey(stage: string): string {
    const s = (stage || '').toLowerCase();
    if (s.includes('lead') || s.includes('prospect')) return 'user-plus';
    if (s.includes('inquiry') || s.includes('contact')) return 'message-square';
    if (s.includes('stock') || s.includes('inventory') || s.includes('availab')) return 'package';
    if (s.includes('proposal') || s.includes('quote') || s.includes('quotation')) return 'file-text';
    if (s.includes('negotiat')) return 'handshake';
    if (s.includes('ship') || s.includes('deliver')) return 'truck';
    if (s.includes('commercial')) return 'briefcase';
    if (s.includes('technical') || s.includes('requirement')) return 'settings';
    if (s.includes('complete') || s.includes('won')) return 'check-circle';
    if (s.includes('feedback') || s.includes('review')) return 'star';
    if (s.includes('lost') || s.includes('cancel') || s.includes('reject')) return 'x-circle';
    if (s.includes('confirm')) return 'shield-check';
    if (s.includes('qualif')) return 'clipboard-check';
    return 'circle';
  }

  agingIconKey(bucket: string): string {
    const b = (bucket || '').toLowerCase();
    if (b.includes('not yet due')) return 'calendar';
    if (b.includes('1-30')) return 'clock';
    if (b.includes('31-60')) return 'alert-circle';
    if (b.includes('60+')) return 'alert-triangle';
    return 'help-circle';
  }

  quotationIconKey(status: string): string {
    const s = (status || '').toLowerCase();
    if (s.includes('draft')) return 'file-text';
    if (s.includes('open')) return 'send';
    if (s.includes('order')) return 'check-circle';
    if (s.includes('expir')) return 'clock';
    if (s.includes('cancel') || s.includes('reject') || s.includes('lost')) return 'x-circle';
    return 'help-circle';
  }

  sampleTestingIconKey(stage: string): string {
    const s = (stage || '').toLowerCase();
    if (s.includes('initial contact')) return 'user-plus';
    if (s.includes('device proposed') || s.includes('sample requested')) return 'package';
    if (s.includes('testing approved') || s.includes('sample delivered')) return 'truck';
    if (s.includes('technical setup') || s.includes('installation')) return 'settings';
    if (s.includes('issue resolution')) return 'alert-circle';
    if (s.includes('completed') || s.includes('feedback')) return 'check-circle';
    return 'help-circle';
  }

  closeForecastIconKey(bucket: string): string {
    const b = (bucket || '').toLowerCase();
    if (b.includes('30 days')) return 'calendar';
    if (b.includes('90 days')) return 'clock';
    if (b.includes('later')) return 'file-text';
    if (b.includes('overdue')) return 'alert-triangle';
    return 'help-circle';
  }

  highestStages(): { stage: string; count: number }[] {
    if (!this.opportunitiesByStage.length) return [];
    const max = Math.max(...this.opportunitiesByStage.map(s => s.count));
    return this.opportunitiesByStage.filter(s => s.count === max);
  }

  topPerformers(): { employee: string; count: number; pct: number }[] {
    if (!this.mostActiveEmployees.length) return [];
    const max = Math.max(...this.mostActiveEmployees.map(e => e.count));
    return this.mostActiveEmployees.filter(e => e.count === max);
  }

  lowestActivityEmployees(): { employee: string; count: number; pct: number }[] {
    if (!this.leastActiveEmployees.length) return [];
    const min = Math.min(...this.leastActiveEmployees.map(e => e.count));
    return this.leastActiveEmployees.filter(e => e.count === min);
  }

  formatEmployeeList(employees: { employee: string; count: number }[]): string {
    return employees.map(e => e.employee).join(' & ');
  }

  isAdministrator(employee: string): boolean {
    return (employee || '').trim().toLowerCase() === 'administrator';
  }

  performanceDiffPct(recent: number, baseline: number): number | null {
    if (!baseline) return null;
    return Math.round(((recent - baseline) / baseline) * 100);
  }

  performanceDiffLabel(recent: number, baseline: number): string {
    const pct = this.performanceDiffPct(recent, baseline);
    return pct === null ? '\u2014' : `${pct}%`;
  }

  highestContactedCustomers(): { customer_name: string; contact_count: number }[] {
    if (!this.mostContactedCustomers.length) return [];
    const max = Math.max(...this.mostContactedCustomers.map(c => c.contact_count));
    return this.mostContactedCustomers.filter(c => c.contact_count === max);
  }

  highestCalledCustomers(): { customer_name: string; contact_count: number }[] {
    if (!this.mostCalledCustomers.length) return [];
    const max = Math.max(...this.mostCalledCustomers.map(c => c.contact_count));
    return this.mostCalledCustomers.filter(c => c.contact_count === max);
  }

  formatCustomerList(customers: { customer_name: string; contact_count: number }[]): string {
    return customers.map(c => c.customer_name).join(' & ');
  }

  statusBadgeKey(status: string | null): string {
    const s = (status || '').trim().toLowerCase();
    if (!s) return 'missing';
    if (s === 'present') return 'present';
    if (s === 'absent') return 'absent';
    return 'other';
  }

  statusBadgeLabel(status: string | null): string {
    const s = (status || '').trim();
    return s ? s : 'Incomplete';
  }

  formatWorkingHours(hours: number | null): string {
    if (hours === null || hours === undefined) return '\u2014';
    const totalMinutes = Math.round(hours * 60);
    const h = Math.floor(totalMinutes / 60);
    const m = totalMinutes % 60;
    if (h === 0) return `${m}m`;
    if (m === 0) return `${h}h`;
    return `${h}h ${m}m`;
  }

  formatDatePill(dateStr: string): string {
    const d = new Date(dateStr);
    if (isNaN(d.getTime())) return dateStr;
    return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
  }

  maxActivityWindowCount(): number {
    if (!this.employeeActivityWindow.length) return 0;
    return Math.max(...this.employeeActivityWindow.map(e => e.activity_count));
  }

  maxContactFrequency(): number {
    if (!this.customerContactFrequency.length) return 0;
    return Math.max(...this.customerContactFrequency.map(c => c.contact_count));
  }

  isRecentContact(dateStr: string | null | undefined): boolean {
    if (!dateStr) return false;
    const d = new Date(dateStr);
    if (isNaN(d.getTime())) return false;
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    d.setHours(0, 0, 0, 0);
    const diffDays = Math.round((today.getTime() - d.getTime()) / 86400000);
    return diffDays >= 0 && diffDays <= 1;
  }

  peakTrendDays(): { date: string; count: number }[] {
    return this.dailyTrend.filter(d => d.isPeak);
  }

  formatTrendDayList(days: { date: string; count: number }[]): string {
    return days.map(d => d.date).join(' & ');
  }

  isSalesValueLong(): boolean {
    return `$${this.kpiSalesValue.toLocaleString()}`.length > 9;
  }

  exportTableToExcel(rows: any[], columns: { key: string; label: string }[], filename: string): void {
    if (!rows || !rows.length) return;
    const data = rows.map(row => {
      const obj: Record<string, any> = {};
      for (const col of columns) {
        obj[col.label] = row[col.key] ?? '';
      }
      return obj;
    });
    const worksheet = XLSX.utils.json_to_sheet(data);
    const workbook = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(workbook, worksheet, 'Sheet1');
    const datedFilename = `${filename}-${new Date().toISOString().slice(0, 10)}.xlsx`;
    XLSX.writeFile(workbook, datedFilename);
  }

  totalTeamActivity(): number {
    return this.activityByTeam.reduce((sum, t) => sum + t.count, 0);
  }

highestTeams(): { department: string; count: number }[] {
    if (!this.activityByTeam.length) return [];
    const max = Math.max(...this.activityByTeam.map(t => t.count));
    return this.activityByTeam.filter(t => t.count === max);
  }

  // Cross-references activityByTeam (employees who logged activity in
  // the selected window -- can vary window to window) against
  // employeeHeadcount (the full roster, window-independent) so the
  // "why only 3 employees" question has a real, live answer instead of
  // a static number that goes stale the moment the real roster changes.
  headcountForDepartment(department: string): number | null {
    const match = this.employeeHeadcount.find(h => h.department === department);
    return match ? match.count : null;
  }

  teamActivityRatioLabel(t: { department: string; employees: { employeeName: string; count: number; pct: number; salesValue: number }[] }): string {
    const roster = this.headcountForDepartment(t.department);
    const activeCount = t.employees.length;
    const plural = (n: number) => n === 1 ? '' : 's';
    if (!roster) {
      return `${activeCount} ${t.department} employee${plural(activeCount)} logged activity during the selected period.`;
    }
    return `${activeCount} of ${roster} ${t.department} employee${plural(roster)} logged activity during the selected period \u2014 the rest exist on the roster but haven't logged anything.`;
  }

  totalHeadcount(): number {
    return this.employeeHeadcount.reduce((sum, t) => sum + t.count, 0);
  }

  highestHeadcountTeams(): { department: string; count: number }[] {
    if (!this.employeeHeadcount.length) return [];
    const max = Math.max(...this.employeeHeadcount.map(t => t.count));
    return this.employeeHeadcount.filter(t => t.count === max);
  }

  formatTeamList(teams: { department: string; count: number }[]): string {
    return teams.map(t => t.department).join(' & ');
  }

  weeklyAverageActivity(): number {
    if (!this.busiestDays.length) return 0;
    const total = this.busiestDays.reduce((sum, d) => sum + d.count, 0);
    return Math.round(total / this.busiestDays.length);
  }

  ngAfterViewInit(): void {
    setTimeout(() => this.updateFilterArrows(), 300);
  }

  @HostListener('window:resize')
  onWindowResize(): void {
    this.updateFilterArrows();
  }

  onFilterScroll(): void {
    this.updateFilterArrows();
  }

  private updateFilterArrows(): void {
    const el = this.filterScrollerRef?.nativeElement;
    if (!el) return;
    this.showFilterArrows = el.scrollWidth > el.clientWidth + 2;
    this.canScrollLeft = el.scrollLeft > 4;
    this.canScrollRight = el.scrollLeft + el.clientWidth < el.scrollWidth - 4;
    this.cdr.detectChanges();
  }

  prevFilter(): void {
    const el = this.filterScrollerRef?.nativeElement;
    if (el) el.scrollBy({ left: -220, behavior: 'smooth' });
    setTimeout(() => this.updateFilterArrows(), 300);
  }

  nextFilter(): void {
    const el = this.filterScrollerRef?.nativeElement;
    if (el) el.scrollBy({ left: 220, behavior: 'smooth' });
    setTimeout(() => this.updateFilterArrows(), 300);
  }
}