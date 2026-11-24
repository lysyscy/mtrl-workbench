import { useMemo, useState } from 'react';
import Decimal from 'decimal.js';
import Button from 'antd/es/button';
import Form from 'antd/es/form';
import Input from 'antd/es/input';
import InputNumber from 'antd/es/input-number';
import Segmented from 'antd/es/segmented';
import type { ColDef, ColGroupDef, ICellRendererParams } from 'ag-grid-community';
import { BusinessGrid } from './business-grid';
import { equipmentApi as api, exportEquipment } from './equipment-api';
import type { InventoryCategory, InventoryItem, InventoryValues } from './equipment-api';
import { contentWidth, numberColumnWidth } from './grid';
import {
  decimalField,
  formatNum,
  ledgerColumn,
  LedgerModal,
  LoadState,
  options,
  rowId,
  useAccess,
  useLedgerAction,
  useLedgerQuery,
} from './equipment-ui';

const categories = { tool: '在用工具', turnover: '周转材料' };
function InventoryForm({
  category,
  item,
  close,
}: {
  category: InventoryCategory;
  item: InventoryItem | null;
  close: () => void;
}) {
  const [dirty, setDirty] = useState(false),
    action = useLedgerAction(),
    { writable } = useAccess();
  const fields = [
    ['unit_price', '单价'],
    ['book_qty', '帐面数量'],
    ['count_qty', '盘点数量'],
    ['diff_qty', '盈亏数量'],
  ] as const;
  async function save(values: Omit<InventoryValues, 'category'>) {
    if (!writable) return;
    if (item) {
      const changes = Object.fromEntries(
        Object.entries(values).filter(([key, value]) => value !== item[key as keyof InventoryItem])
      );
      await api.editInventory(item.id, changes);
    } else await api.addInventory({ ...values, category });
    close();
  }
  return (
    <LedgerModal
      title={(item ? '编辑' : '新增') + categories[category] + '盘点行'}
      busy={action.busy}
      dirty={dirty}
      close={close}
    >
      <Form
        layout="vertical"
        disabled={!writable || action.busy}
        initialValues={item ?? {}}
        onValuesChange={() => setDirty(true)}
        onFinish={(v) => void action.run(() => save(v))}
      >
        <div className="equipment-fields">
          <Form.Item name="name" label="名称" rules={[{ required: true, message: '请填写名称' }]}>
            <Input />
          </Form.Item>
          <Form.Item name="spec" label="规格">
            <Input />
          </Form.Item>
          <Form.Item name="unit" label="单位">
            <Input />
          </Form.Item>
          {fields.map(([key, label]) => (
            <Form.Item
              key={key}
              name={key}
              label={label}
              rules={[{ required: key === 'book_qty' || key === 'count_qty', message: '请填写' + label }]}
            >
              <InputNumber stringMode {...decimalField} precision={4} {...(key === 'unit_price' ? { min: '0' } : {})} />
            </Form.Item>
          ))}
          <Form.Item name="diff_reason" label="盈亏原因">
            <Input.TextArea />
          </Form.Item>
        </div>
        {action.error && <p role="alert">{action.error}</p>}
        <div className="dialog-actions">
          <Button htmlType="submit" type="primary" loading={action.busy} disabled={!dirty}>
            保存
          </Button>
        </div>
      </Form>
    </LedgerModal>
  );
}
// Keep the same four decimal places used by the Excel amount columns.
function differenceTotal(rows: InventoryItem[]) {
  const values = rows.flatMap((r) => (r.diff_amount === null ? [] : [r.diff_amount]));
  if (!values.length) return null;
  const Amount = Decimal.clone({ precision: 40 });
  return values.reduce((sum, value) => sum.plus(value), new Amount(0)).toFixed(4);
}
type Row = Partial<InventoryItem> & { id: number; name: string };
export function Inventory({ scale, goToDistribution }: {
  scale: number;
  goToDistribution: (ids: readonly number[]) => void;
}) {
  const [category, setCategory] = useState<InventoryCategory>('tool'),
    [edit, setEdit] = useState<InventoryItem | null | undefined>(),
    [selected, setSelected] = useState<number | null>(null);
  const query = useLedgerQuery(['inventory', category], () => api.inventory(category)),
    action = useLedgerAction(),
    { writable } = useAccess(),
    data = query.data;
  const item = data?.items.find((i) => i.id === selected);
  const totals = useMemo<Row[]>(() => data ? [{
    id: -1,
    name: '合计',
    book_amount: data.book_amount,
    count_amount: data.count_amount,
    diff_amount: differenceTotal(data.items),
  }] : [], [data]);
  const columns = useMemo<(ColDef<Row> | ColGroupDef<Row>)[]>(() => {
    function amount(field: 'unit_price' | 'book_amount' | 'count_amount' | 'diff_amount', headerName: string) {
      const values = (data?.items ?? []).map(row => formatNum(row[field]));
      values.push(...totals.map(row => formatNum(row[field])));
      return ledgerColumn<Row>({
        field, headerName, cellClass: 'ag-right-aligned-cell', ...numberColumnWidth(values, scale),
      }, row => row[field], 'number');
    }
    return [
      { colId: 'sequence', headerName: '序号', ...contentWidth(48, 60, scale),
        valueGetter: p => p.node?.rowPinned ? '' : (p.node?.rowIndex ?? 0) + 1 },
      ledgerColumn<Row>({
        field: 'name', headerName: '名称', ...contentWidth(108, 175, scale, 0.7),
        cellRenderer: ({ data }: ICellRendererParams<Row>) => data?.linked_equipment_ids?.length ? (
          <button type="button" className="equipment-row-link" title="定位到设备分布"
            onClick={() => goToDistribution(data.linked_equipment_ids!)}>{data.name}</button>
        ) : data?.name,
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
          options={options(categories)}
          onChange={(v) => {
            setCategory(v as InventoryCategory);
            setSelected(null);
          }}
        />
        <div className="equipment-actions equipment-toolbar-actions">
          <Button disabled={!item?.linked_equipment_ids.length} onClick={() => item && goToDistribution(item.linked_equipment_ids)}>
            定位到分布
          </Button>
          <Button disabled={!writable || !item} onClick={() => item && setEdit(item)}>
            编辑所选行
          </Button>
          <Button type="primary" disabled={!writable} onClick={() => setEdit(null)}>
            新增盘点行
          </Button>
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
            rowSelection: { mode: 'singleRow', checkboxes: false, enableClickSelection: true },
            onSelectionChanged: (e) => setSelected(e.api.getSelectedRows()[0]?.id ?? null),
            onFilterChanged: ({ api }) => {
              const row = api.getSelectedNodes()[0];
              if (row && row.rowIndex === null) row.setSelected(false);
            },
          }}
          totals={totals}
        />
      )}
      {edit !== undefined && (
        <InventoryForm category={category} item={edit} close={() => setEdit(undefined)} />
      )}
    </div>
  );
}
