import { I8ReportFetch } from './i8-report-fetch';
import type { ReportFetchProps } from './i8-report-fetch';

export function InventoryFetch(props: ReportFetchProps) {
  return <I8ReportFetch {...props} source="inventory"/>;
}
