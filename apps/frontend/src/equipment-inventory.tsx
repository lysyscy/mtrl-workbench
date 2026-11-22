import { useState } from 'react';
import Decimal from 'decimal.js';
import Button from 'antd/es/button';
import Form from 'antd/es/form';
import Input from 'antd/es/input';
import InputNumber from 'antd/es/input-number';
import Segmented from 'antd/es/segmented';
import type { ColDef, ColGroupDef } from 'ag-grid-community';
import { BusinessGrid } from './business-grid';
import { equipmentApi as api, exportEquipment } from './equipment-api';
import type { InventoryCategory, InventoryItem, InventoryValues } from './equipment-api';
import {
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
              <InputNumber stringMode precision={4} {...(key === 'unit_price' ? { min: '0' } : {})} />
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
const columns: (ColDef<Row> | ColGroupDef<Row>)[] = [
  {
    colId: 'sequence',
    headerName: '序号',
    valueGetter: (p) => (p.node?.rowPinned ? '' : (p.node?.rowIndex ?? 0) + 1),
  },
  { field: 'name', headerName: '名称' },
  { field: 'spec', headerName: '规格' },
  { field: 'unit', headerName: '单位' },
  { field: 'unit_price', headerName: '单价' },
  {
    headerName: '帐面数',
    children: [
      { field: 'book_qty', headerName: '数量' },
      { field: 'book_amount', headerName: '金额' },
    ],
  },
  {
    headerName: '盘点数',
    children: [
      { field: 'count_qty', headerName: '数量' },
      { field: 'count_amount', headerName: '金额' },
    ],
  },
  { field: 'diff_qty', headerName: '盈亏数量' },
  { field: 'diff_amount', headerName: '盈亏金额' },
  { field: 'diff_reason', headerName: '盈亏原因' },
];
export function Inventory() {
  const [category, setCategory] = useState<InventoryCategory>('tool'),
    [edit, setEdit] = useState<InventoryItem | null | undefined>(),
    [selected, setSelected] = useState<number | null>(null);
  const query = useLedgerQuery(['inventory', category], () => api.inventory(category)),
    action = useLedgerAction(),
    { writable } = useAccess(),
    data = query.data;
  const item = data?.items.find((i) => i.id === selected);
  return (
    <>
      <Segmented
        value={category}
        options={options(categories)}
        onChange={(v) => {
          setCategory(v as InventoryCategory);
          setSelected(null);
        }}
      />
      <div data-page-chrome className="equipment-toolbar">
        <Button type="primary" disabled={!writable} onClick={() => setEdit(null)}>
          新增盘点行
        </Button>
        <Button disabled={!writable || !item} onClick={() => item && setEdit(item)}>
          编辑所选行
        </Button>
        <Button
          disabled={action.busy}
          onClick={() => void action.run(() => exportEquipment('inventory'), false)}
        >
          导出盘点 Excel
        </Button>
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
          style={{ height: '62vh' }}
          grid={{
            rowSelection: { mode: 'singleRow', checkboxes: false, enableClickSelection: true },
            onSelectionChanged: (e) => setSelected(e.api.getSelectedRows()[0]?.id ?? null),
          }}
          totals={[
            {
              id: -1,
              name: '合计',
              book_amount: data.book_amount,
              count_amount: data.count_amount,
              diff_amount: differenceTotal(data.items),
            },
          ]}
        />
      )}
      {edit !== undefined && (
        <InventoryForm category={category} item={edit} close={() => setEdit(undefined)} />
      )}
    </>
  );
}
