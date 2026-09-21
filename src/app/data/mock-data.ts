export interface CallRecord {
  id: string;
  customer: string;
  salesperson: string;
  timestamp: string;
  durationMinutes: number;
  status: 'Completed' | 'Missed';
}

export interface CustomerRecord {
  id: string;
  name: string;
  country: string;
  lastContact: string;
}

export interface SaleRecord {
  id: string;
  customer: string;
  salesperson: string;
  amountUsd: number;
  timestamp: string;
}

function daysAgo(n: number, hour = 10): string {
  const d = new Date();
  d.setDate(d.getDate() - n);
  d.setHours(hour, 0, 0, 0);
  return d.toISOString();
}

export const MOCK_CALLS: CallRecord[] = [
  { id: 'C-101', customer: 'Falcon-I Pvt Ltd', salesperson: 'Ahmed', timestamp: daysAgo(0, 9), durationMinutes: 12, status: 'Completed' },
  { id: 'C-102', customer: 'SUPERNET LIMITED', salesperson: 'Ahmed', timestamp: daysAgo(0, 11), durationMinutes: 8, status: 'Completed' },
  { id: 'C-103', customer: 'W11stop', salesperson: 'Bilal', timestamp: daysAgo(0, 14), durationMinutes: 5, status: 'Missed' },
  { id: 'C-104', customer: 'Raqib Tech', salesperson: 'Sara', timestamp: daysAgo(0, 15), durationMinutes: 20, status: 'Completed' },
  { id: 'C-105', customer: 'Safezone Vehicle Tracking Company', salesperson: 'Ahmed', timestamp: daysAgo(1, 10), durationMinutes: 9, status: 'Completed' },
  { id: 'C-106', customer: 'Afghan Prime Zone', salesperson: 'Bilal', timestamp: daysAgo(1, 13), durationMinutes: 6, status: 'Completed' },
  { id: 'C-107', customer: 'Falcon-I Pvt Ltd', salesperson: 'Sara', timestamp: daysAgo(2, 9), durationMinutes: 11, status: 'Completed' },
  { id: 'C-108', customer: 'Solutions Engineering Pvt Ltd', salesperson: 'Ahmed', timestamp: daysAgo(2, 16), durationMinutes: 4, status: 'Missed' },
  { id: 'C-109', customer: 'W11stop', salesperson: 'Bilal', timestamp: daysAgo(3, 10), durationMinutes: 18, status: 'Completed' },
  { id: 'C-110', customer: 'SUPERNET LIMITED', salesperson: 'Sara', timestamp: daysAgo(3, 12), durationMinutes: 7, status: 'Completed' },
  { id: 'C-111', customer: 'Raqib Tech', salesperson: 'Ahmed', timestamp: daysAgo(4, 9), durationMinutes: 10, status: 'Completed' },
  { id: 'C-112', customer: 'Afghan Chatr Company', salesperson: 'Bilal', timestamp: daysAgo(5, 11), durationMinutes: 13, status: 'Completed' },
  { id: 'C-113', customer: 'Falcon-I Pvt Ltd', salesperson: 'Sara', timestamp: daysAgo(6, 10), durationMinutes: 9, status: 'Completed' },
];

export const MOCK_CUSTOMERS: CustomerRecord[] = [
  { id: 'CUST-01', name: 'Falcon-I Pvt Ltd', country: 'Pakistan', lastContact: daysAgo(0) },
  { id: 'CUST-02', name: 'SUPERNET LIMITED', country: 'Pakistan', lastContact: daysAgo(3) },
  { id: 'CUST-03', name: 'W11stop', country: 'Pakistan', lastContact: daysAgo(9) },
  { id: 'CUST-04', name: 'Raqib Tech', country: 'Pakistan', lastContact: daysAgo(11) },
  { id: 'CUST-05', name: 'Safezone Vehicle Tracking Company', country: 'Afghanistan', lastContact: daysAgo(1) },
  { id: 'CUST-06', name: 'Afghan Prime Zone', country: 'Afghanistan', lastContact: daysAgo(14) },
  { id: 'CUST-07', name: 'Afghan Chatr Company', country: 'Afghanistan', lastContact: daysAgo(5) },
  { id: 'CUST-08', name: 'Solutions Engineering Pvt Ltd', country: 'Pakistan', lastContact: daysAgo(10) },
];

export const MOCK_SALES: SaleRecord[] = [
  { id: 'INV-2001', customer: 'Falcon-I Pvt Ltd', salesperson: 'Ahmed', amountUsd: 4200, timestamp: daysAgo(2) },
  { id: 'INV-2002', customer: 'Raqib Tech', salesperson: 'Sara', amountUsd: 8600, timestamp: daysAgo(6) },
  { id: 'INV-2003', customer: 'SUPERNET LIMITED', salesperson: 'Ahmed', amountUsd: 3100, timestamp: daysAgo(9) },
  { id: 'INV-2004', customer: 'W11stop', salesperson: 'Bilal', amountUsd: 5400, timestamp: daysAgo(15) },
  { id: 'INV-2005', customer: 'Afghan Prime Zone', salesperson: 'Bilal', amountUsd: 2300, timestamp: daysAgo(20) },
];