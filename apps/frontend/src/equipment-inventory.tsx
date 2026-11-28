import { layoutCallback } from './grid-layout-callback';
import { useMemo, useState } from 'react';
import Decimal from 'decimal.js';
import Button from 'antd/es/button';
import Segmented from 'antd/es/segmented';
import type { ColDef, ColGroupDef, ICellRendererParams } from 'ag-grid-community';
import { BusinessGrid } from './business-grid';
import { equipmentApi as api, exportEquipment } from './equipment-api';
import type { InventoryCategory, InventoryItem } from './equipment-api';
import { contentWidth, numberColumnWidth } from './grid';
import {
  formatMoney,
  ledgerColumn,
  LoadState,
  rowId,
  useLedgerAction,
  useLedgerQuery,
} from './equipment-ui';

const categories = { tool: '在用工具', turnover: '周转材料' };
const categoryOptions: { value: InventoryCategory; label: string }[] = [
  { value: 'tool', label: categories.tool },
  { value: 'turnover', label: categories.turnover },
];
function differenceTotal(rows: InventoryItem[]) {
  const values = rows.flatMap((r) => (r.diff_amount === null ? [] : [r.diff_amount]));
  if (!values.length) return null;
  const Amount = Decimal.clone({ precision: 40 });
  return values.reduce((sum, value) => sum.plus(value), new Amount(0)).toFixed(2);
}
type Row = Partial<InventoryItem> & { id: number; name: string };
export function Inventory({ scale, goToDistribution }: {
  scale: number;
  goToDistribution: (ids: readonly number[]) => void;
}) {
  const [category, setCategory] = useState<InventoryCategory>('tool');
  const query = useLedgerQuery(['inventory', category], () => api.inventory(category)),
    action = useLedgerAction(),
    data = query.data;
  const totals = useMemo<Row[]>(() => data ? [{
    id: -1,
    name: '合计',
    book_amount: data.book_amount,
    count_amount: data.count_amount,
    diff_amount: differenceTotal(data.items),
  }] : [], [data]);
  const columns = useMemo<(ColDef<Row> | ColGroupDef<Row>)[]>(() => {
    function amount(field: 'unit_price' | 'book_amount' | 'count_amount' | 'diff_amount', headerName: string) {
      const values = (data?.items ?? []).map(row => formatMoney(row[field]));
      values.push(...totals.map(row => formatMoney(row[field])));
      return ledgerColumn<Row>({
        field, headerName, cellClass: 'ag-right-aligned-cell', ...numberColumnWidth(values, scale),
      }, row => row[field], 'number', formatMoney);
    }
    return [
      { colId: 'sequence', headerName: '序号', ...contentWidth(48, 60, scale),
        valueGetter: layoutCallback(p => p.node?.rowPinned ? '' : (p.node?.rowIndex ?? 0) + 1) },
      ledgerColumn<Row>({
        field: 'name', headerName: '名称', ...contentWidth(108, 175, scale, 0.7),
        cellRenderer: ({ data }: ICellRendererParams<Row>) => {
          const linked = data?.linked_equipment_ids;
          return linked?.length ? (
            <button type="button" className="equipment-row-link" title="定位到设备分布"
              onClick={() => goToDistribution(linked)}>{data?.name}</button>
          ) : data?.name;
        },
      }, row => row.name),
      ledgerColumn<Row>({ field: 'spec', headerName: '规格', ...contentWidth(92, 165, scale, 0.5) }, row => row.spec),
      ledgerColumn<Row>({ field: 'unit', headerName: '单位', ...contentWidth(52, 66, scale) }, row => row.unit),
      amount('unit_price', '单价'),
      { headerName: '帐面数', children: [
        ledgerColumn<Row>({ field: 'book_qty', headerName: '数量', ...contentWidth(65, 100, scale) }, row => row.book_qty, 'number'),
        amount('book_amount', '金额'),
      ] },
      { headerName: '盘点数', children: [
        ledgerColumn<Row>({ field: 'count_qty', headerName: '数量', ...contentWidth(65, 100, scale) }, row => row.count_qty, 'number'),
        amount('count_amount', '金额'),
      ] },
      ledgerColumn<Row>({ field: 'diff_qty', headerName: '盈亏数量', ...contentWidth(78, 112, scale) }, row => row.diff_qty, 'number'),
      amount('diff_amount', '盈亏金额'),
      ledgerColumn<Row>({ field: 'diff_reason', headerName: '盈亏原因', ...contentWidth(160, 400, scale, 2) }, row => row.diff_reason),
    ];
  }, [data, goToDistribution, scale, totals]);
  return (
    <div className="equipment-sheet">
      <div data-page-chrome className="equipment-toolbar equipment-workspace-bar">
        <Segmented
          value={category}
          options={categoryOptions}
          onChange={value => setCategory(value)}
        />
        <div className="equipment-actions equipment-toolbar-actions">
          <Button disabled={action.busy} onClick={() => void action.run(() => exportEquipment('inventory'), false)}>
            导出盘点 Excel
          </Button>
        </div>
      </div>
      <LoadState query={query} />
      {action.error && <p role="alert">{action.error}</p>}
      {data && (
        <BusinessGrid<Row>
          key={category}
          table={'equipment-inventory-' + category}
          label={categories[category] + '盘点表'}
          rows={data.items}
          columns={columns}
          rowId={rowId}
          domLayout="normal"
          scale={scale}
          className="equipment-grid-slot"
          grid={{
            enableFilterHandlers: true,
            popupParent: document.body,
          }}
          totals={totals}
        />
      )}
    </div>
  );
}
