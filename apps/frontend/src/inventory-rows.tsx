import type { ICellRendererParams } from 'ag-grid-community';
import type { InventoryRow } from './inventory-api';

export function InventoryText(params: ICellRendererParams<InventoryRow>) {
  return <div className="inventory-cell-text">{params.value ?? ''}</div>;
}
