import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, map } from 'rxjs';

export interface ChatSessionInfo {
  id: string;
  title: string;
  created_at: string;
  message_count: number;
}

export interface ChatMessageOut {
  role: 'user' | 'assistant';
  content: string | null;
  records: any[] | null;
  source_note: string | null;
  sources: ChatMessageSource[] | null;
  created_at: string;
}

export interface ChatMessageSource {
  function_called: string;
  arguments_used: Record<string, any>;
  summary: string | null;
  source: string | null;
  records: any[];
}

interface ApiResponse {
  summary: string;
  records: any[];
  source: string;
}

export interface DailySummary {
  id: string;
  summary_date: string;
  content: string;
  email_sent: boolean;
}

@Injectable({ providedIn: 'root' })
export class QueryService {
  private apiUrl = '/api';

  constructor(private http: HttpClient) { }

  listDailySummaries(limit: number = 14): Observable<DailySummary[]> {
    return this.http.get<DailySummary[]>(`${this.apiUrl}/reports/daily-summaries?limit=${limit}`);
  }

  generateDailySummary(sendEmail: boolean = false): Observable<DailySummary> {
    return this.http.post<DailySummary>(`${this.apiUrl}/reports/daily-summaries/generate?send_email=${sendEmail}`, {});
  }

  listSessions(): Observable<ChatSessionInfo[]> {
    return this.http.get<ChatSessionInfo[]>(`${this.apiUrl}/chat/sessions`);
  }

  createSession(): Observable<ChatSessionInfo> {
    return this.http.post<ChatSessionInfo>(`${this.apiUrl}/chat/sessions`, {});
  }

  getMessages(sessionId: string): Observable<ChatMessageOut[]> {
    return this.http.get<ChatMessageOut[]>(`${this.apiUrl}/chat/sessions/${sessionId}/messages`);
  }

  sendMessage(sessionId: string, question: string): Observable<ChatMessageOut> {
    return this.http.post<ChatMessageOut>(`${this.apiUrl}/chat/sessions/${sessionId}/messages`, { question });
  }

  regenerate(sessionId: string): Observable<ChatMessageOut> {
    return this.http.post<ChatMessageOut>(`${this.apiUrl}/chat/sessions/${sessionId}/regenerate`, {});
  }

  private query(functionName: string, params: Record<string, any> = {}): Observable<any[]> {
    let url = `${this.apiUrl}/query/${functionName}`;
    const q = Object.entries(params)
      .filter(([, v]) => v !== undefined && v !== null)
      .map(([k, v]) => `${k}=${encodeURIComponent(v)}`)
      .join('&');
    if (q) url += `?${q}`;
    return this.http.get<ApiResponse>(url).pipe(map(res => res.records || []));
  }

  getCallsByEmployee(days: number, status?: string, timeOfDay?: string, startDate?: string, endDate?: string): Observable<{ employee: string; call_count: number }[]> {
    return this.query('get_calls_by_employee', { days, status, time_of_day: timeOfDay, start_date: startDate, end_date: endDate });
  }

  getLastSyncTime(): Observable<{ completed_at: string; result: string; records_processed: number | null }[]> {
    return this.query('get_last_sync_time');
  }

  getStaleCustomers(days: number, country?: string, startDate?: string, endDate?: string): Observable<{ customer_id: string; customer_name: string; last_activity_date: string | null; days_since_activity: number | null; monthly_recurring_value_usd: number }[]> {
    return this.query('get_stale_customers', { days, country, start_date: startDate, end_date: endDate });
  }

  getSalesValueBySalesperson(days: number, startDate?: string, endDate?: string): Observable<{ salesperson: string; total_value: number }[]> {
    return this.query('get_sales_value_by_salesperson', { days, start_date: startDate, end_date: endDate });
  }

  getMonthlyRecurringRevenue(manufacturer?: string): Observable<{ manufacturer: string; monthly_value: number; device_count: number }[]> {
    return this.query('get_monthly_recurring_revenue', { manufacturer });
  }

  getMonthlyRecurringRevenueByCustomer(limit: number = 10, manufacturer?: string): Observable<{ customer_id: string; customer_name: string; monthly_value: number; device_count: number }[]> {
    return this.query('get_monthly_recurring_revenue_by_customer', { limit, manufacturer });
  }

  getCallsBySalespersonThisWeek(): Observable<{ salesperson: string; count: number }[]> {
    return this.query('get_calls_by_salesperson_this_week');
  }

  getTotalSalesValueRecords(withinDays: number, employee?: string, startDate?: string, endDate?: string): Observable<{ invoice_id: string; customer_name: string; value: number }[]> {
    return this.query('get_total_sales_value', { within_days: withinDays, employee, start_date: startDate, end_date: endDate });
  }

  getActivitiesToday(activityType?: string, status?: string, timeOfDay?: string, employee?: string): Observable<{ date: string; activity_count: number }[]> {
    return this.query('get_activities_today', { activity_type: activityType, status, time_of_day: timeOfDay, employee });
  }

  getClientsContactedToday(activityType?: string, status?: string, timeOfDay?: string, employee?: string): Observable<{ date: string; clients_contacted: number }[]> {
    return this.query('get_clients_contacted_today', { activity_type: activityType, status, time_of_day: timeOfDay, employee });
  }

  getNewLeadsThisMonth(): Observable<{ lead_id: string; client_name: string; status: string }[]> {
    return this.query('get_new_leads_this_month');
  }

  getNewOpportunitiesThisMonth(): Observable<{ opportunity_id: string; customer_name: string; pipeline_stage: string }[]> {
    return this.query('get_new_opportunities_this_month');
  }

  getCustomersWithPendingPayments(): Observable<{ customer_name: string; invoice_id: string; outstanding: number }[]> {
    return this.query('get_customers_with_pending_payments');
  }

  getInvoiceAging(): Observable<{ bucket: string; count: number; amount: number }[]> {
    return this.query('get_invoice_aging');
  }

  getCallsToday(status?: string, timeOfDay?: string, employee?: string): Observable<{ customer_id: string; scenario: string }[]> {
    return this.query('get_calls_today', { status, time_of_day: timeOfDay, employee });
  }

  getSalesOrdersCreated(withinDays: number, employee?: string, startDate?: string, endDate?: string): Observable<{ sales_order_id: string; customer_name: string; order_date: string; value: number }[]> {
    return this.query('get_sales_orders_created', { within_days: withinDays, employee, start_date: startDate, end_date: endDate });
  }

  getOverdueTodos(): Observable<{ todo_id: string; description: string; due_date: string; assigned_to: string }[]> {
    return this.query('get_overdue_todos');
  }

  getDailyActivityPattern(days: number, activityType?: string, status?: string, timeOfDay?: string, employee?: string, startDate?: string, endDate?: string): Observable<{ date: string; count: number }[]> {
    return this.query('get_daily_activity_pattern', { days, activity_type: activityType, status, time_of_day: timeOfDay, employee, start_date: startDate, end_date: endDate });
  }

  getActivitiesByEmployee(days: number, startDate?: string, endDate?: string): Observable<{ employee: string; count: number }[]> {
    return this.query('get_activities_by_employee', { days, start_date: startDate, end_date: endDate });
  }

  getBusiestHourOfDay(days: number, status?: string, timeOfDay?: string, employee?: string, startDate?: string, endDate?: string): Observable<{ hour: number; count: number }[]> {
    return this.query('get_busiest_hour_of_day', { days, status, time_of_day: timeOfDay, employee, start_date: startDate, end_date: endDate });
  }

  getBusiestCallDayOfWeek(days: number, status?: string, timeOfDay?: string, employee?: string, startDate?: string, endDate?: string): Observable<{ day: string; count: number }[]> {
    return this.query('get_busiest_call_day_of_week', { days, status, time_of_day: timeOfDay, employee, start_date: startDate, end_date: endDate });
  }

  getCustomerList(): Observable<{ customer_id: string; customer_name: string; country: string; monthly_recurring_value_usd: number }[]> {
    return this.query('get_customer_list');
  }

  getActivityTypeOptions(): Observable<{ activity_type: string }[]> {
    return this.query('get_activity_type_options');
  }

  getLeadStatusOptions(): Observable<{ status: string }[]> {
    return this.query('get_lead_status_options');
  }

  getOpportunityStageOptions(): Observable<{ pipeline_stage: string }[]> {
    return this.query('get_opportunity_stage_options');
  }

  getOpportunitiesByStage(employee?: string): Observable<{ stage: string; count: number; total_value_usd: number }[]> {
    return this.query('get_opportunities_by_stage', { employee });
  }

  getOpportunitiesInStage(stage?: string, employee?: string): Observable<{ opportunity_id: string; customer_name: string; pipeline_stage: string; owner_user: string; total_value_usd: number; days_open: number | null; expected_closing_date: string | null; days_until_close: number | null }[]> {
    return this.query('get_opportunities_in_stage', { stage, employee });
  }

  getOpportunityCloseForecast(employee?: string): Observable<{ bucket: string; count: number; value: number }[]> {
    return this.query('get_opportunity_close_forecast', { employee });
  }

  getActivitiesForCustomer(customerId: string): Observable<{ date: string; type: string; status: string; result: string }[]> {
    return this.query('get_activities_for_customer', { customer_id: customerId });
  }

  getNewLeadsThisMonthFiltered(status?: string): Observable<{ lead_id: string; client_name: string; status: string }[]> {
    return this.query('get_new_leads_this_month', { status });
  }

  getNewOpportunitiesThisMonthFiltered(pipelineStage?: string, customerId?: string): Observable<{ opportunity_id: string; customer_name: string; pipeline_stage: string }[]> {
    return this.query('get_new_opportunities_this_month', { pipeline_stage: pipelineStage, customer_id: customerId });
  }

  // --- Phase F: wiring in previously-unused backend functions ---

  getEmployeesBelowAverage(recentDays: number = 7, baselineDays: number = 90): Observable<{ employee: string; recent_daily_avg: number; baseline_daily_avg: number }[]> {
    return this.query('get_employees_below_average', { recent_days: recentDays, baseline_days: baselineDays });
  }

getMostAndLeastContactedClients(days: number, country?: string, status?: string, timeOfDay?: string, startDate?: string, endDate?: string): Observable<{ customer_id: string; contact_count: number; last_contact_date: string | null }[]> {
    return this.query('get_most_and_least_contacted_clients', { days, country, status, time_of_day: timeOfDay, start_date: startDate, end_date: endDate });
  }

  getCallsByCustomer(days: number, country?: string, status?: string, timeOfDay?: string, startDate?: string, endDate?: string): Observable<{ customer_id: string; call_count: number }[]> {
    return this.query('get_calls_by_customer', { days, country, status, time_of_day: timeOfDay, start_date: startDate, end_date: endDate });
  }

  compareWeeklyActivity(): Observable<{ period: string; count: number }[]> {
    return this.query('compare_weekly_activity');
  }

  getOpportunityToQuotationConversion(): Observable<{ metric: string; value: number }[]> {
    return this.query('get_opportunity_to_quotation_conversion');
  }

  getQuotationStatusBreakdown(): Observable<{ status: string; count: number; value: number }[]> {
    return this.query('get_quotation_status_breakdown');
  }

  getSampleTestingFunnel(): Observable<{ stage: string; count: number }[]> {
    return this.query('get_sample_testing_funnel');
  }

  getLeadToOpportunityConversion(): Observable<{ metric: string; value: number | boolean }[]> {
    return this.query('get_lead_to_opportunity_conversion');
  }

  getTodosByStatus(status?: string, employee?: string): Observable<{ todo_id: string; description: string; status: string; due_date: string | null; assigned_to: string }[]> {
    return this.query('get_todos_by_status', { status, employee });
  }

  getClientsReached(days: number, employee?: string, startDate?: string, endDate?: string): Observable<{ period: string; clients_reached: number }[]> {
    return this.query('get_clients_reached', { days, employee, start_date: startDate, end_date: endDate });
  }

  getHighValueLowEngagementCustomers(engagementDays: number = 14, minValue: number = 1000, country?: string, startDate?: string, endDate?: string): Observable<{ customer_name: string; total_sales_value: number; monthly_recurring_value_usd: number; combined_value_usd: number }[]> {
    return this.query('get_high_value_low_engagement_customers', { engagement_days: engagementDays, min_value: minValue, country, start_date: startDate, end_date: endDate });
  }

  getCallToSalesRatio(days: number, employee?: string, startDate?: string, endDate?: string): Observable<{ metric: string; value: number }[]> {
    return this.query('get_call_to_sales_ratio', { days, employee, start_date: startDate, end_date: endDate });
  }

  getActivityByTeam(days: number, startDate?: string, endDate?: string): Observable<{ department: string; count: number; prior_count: number; pct_change: number | null; employees: { employee: string | null; employee_name: string; count: number; sales_value: number }[] }[]> {
    return this.query('get_activity_by_team', { days, start_date: startDate, end_date: endDate });
  }

  getEmployeeDailySummary(days: number, employee?: string, department?: string, startDate?: string, endDate?: string): Observable<{ employee_id: string; employee_name: string; date: string; first_checkin: string | null; last_checkin: string | null; checkin_count: number; working_hours: number | null; status: string | null }[]> {
    return this.query('get_employee_daily_summary', { days, employee, department, start_date: startDate, end_date: endDate });
  }

  compareMonthlyActivity(): Observable<{ period: string; count: number; daily_avg: number }[]> {
    return this.query('compare_monthly_activity');
  }
  getEmployeeActivityWindow(days: number, employee?: string, startDate?: string, endDate?: string): Observable<{ employee: string; date: string; first_activity_time: string | null; last_activity_time: string | null; activity_count: number }[]> {
    return this.query('get_employee_activity_window', { days, employee, start_date: startDate, end_date: endDate });
  }

getDepartmentOptions(): Observable<{ department: string }[]> {
    return this.query('get_department_options');
  }

  getEmployeeHeadcount(department?: string): Observable<{ department: string; employee_count: number }[]> {
    return this.query('get_employee_headcount', { department });
  }

  // --- Activity Analysis page: live replacement for the old static dataset ---
  // Fields are pre-shaped server-side to match ActivityRecord; text fields
  // the schema genuinely has no data for (e.g. salesperson on a Sales Order)
  // come back null rather than fabricated.
  getEnabledUsers(): Observable<{ salesperson: string }[]> {
    return this.query('get_enabled_users');
  }

  getActivityLogRecords(activityType?: string, country?: string, employee?: string, startDate?: string, endDate?: string): Observable<{
    id: string; date: string | null; time: string | null; hourSlot: number | null; halfHourSlot: string | null;
    salesperson: string | null; country: string | null; activityType: string; client: string | null;
    amount: number; isFinancial: boolean;
  }[]> {
    return this.query('get_activity_log_records', { activity_type: activityType, country, employee, start_date: startDate, end_date: endDate });
  }

  // --- Dashboard "Group By" trend widget ---
  getActivitiesByTimeSlot(days: number, timeFrom?: string, timeTo?: string, activityType?: string, status?: string, employee?: string, country?: string, groupBy?: string, startDate?: string, endDate?: string): Observable<{ time_slot: string; activity_count: number }[]> {
    return this.query('get_activities_by_time_slot', { days, time_from: timeFrom, time_to: timeTo, activity_type: activityType, status, employee, country, group_by: groupBy, start_date: startDate, end_date: endDate });
  }

  getActivitiesByPeriod(days: number, timeFrom?: string, timeTo?: string, activityType?: string, status?: string, employee?: string, country?: string, groupBy?: string, startDate?: string, endDate?: string): Observable<{ period: string; activity_count: number }[]> {
    return this.query('get_activities_by_period', { days, time_from: timeFrom, time_to: timeTo, activity_type: activityType, status, employee, country, group_by: groupBy, start_date: startDate, end_date: endDate });
  }
}