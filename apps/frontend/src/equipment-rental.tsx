import { useState } from 'react';
import Button from 'antd/es/button';
import Checkbox from 'antd/es/checkbox';
import Input from 'antd/es/input';
import Select from 'antd/es/select';
import dayjs from 'dayjs';
import type { ColDef, ICellRendererParams } from 'ag-grid-community';
import { BusinessGrid } from './business-grid';
import { rowsInOrder, useGridRowDrag } from './use-grid-row-drag';
import { equipmentApi as api, exportEquipment } from './equipment-api';
import type { Billing, Choice, Pending, RentGroup, RentalLine } from './equipment-api';
import {
  DateField,
  LedgerModal,
  LoadState,
  options,
  rowId,
  useAccess,
  useLedgerAction,
  useLedgerQuery,
} from './equipment-ui';
import { useIsMutating, useMutation, useQueryClient } from '@tanstack/react-query';

const billing = { normal: '正常计租', skip_month: '仅本月不收', stopped: '从本月起停收', blank: '留空' };
const choices: Record<Exclude<Pending, 'none'>, [Choice, string][]> = {
  transfer_attribution: [
    ['from_project', '归调出'],
    ['to_project', '归调入'],
  ],
  new_purchase_start: [
    ['this_month', '当月起收'],
    ['next_month', '次月起收'],
  ],
  scrap_stop: [
    ['stop_this_month', '本月停收'],
    ['charge_this_month', '本月照收'],
  ],
};
type Editable = 'quantity' | 'custom_unit_price' | 'distribution_note';
type RentalContext = { locked: boolean; act: (fn: () => Promise<unknown>) => Promise<void> };
type Cell = ICellRendererParams<RentalLine, unknown, RentalContext>;
function EditCell({ data, context, field }: { field: Editable } & Cell) {
  const [draft, setDraft] = useState<string | null>(null),
    [error, setError] = useState('');
  const client = useQueryClient();
  const write = useMutation({
    mutationKey: ['equipment-rental-edit', data?.month],
    mutationFn: async (input: { id: number; value: string }) => {
      await api.patchLine(input.id, { [field]: input.value || null });
      try {
        await client.invalidateQueries(
          { queryKey: ['equipment-ledger', 'rental', data?.month] },
          { throwOnError: true }
        );
      } catch {
        throw new Error('修改已保存，月租表重读失败。请重新读取后核对。');
      }
    },
  });
  const busy = write.isPending;
  if (!data) return null;
  const row = data,
    current = row[field] ?? '',
    shown = field === 'custom_unit_price' ? row.unit_price : current;
  const label = { quantity: '数量', custom_unit_price: '租赁单价', distribution_note: '分布' }[field];
  async function save() {
    if (busy || draft === null || context.locked) return;
    const value = draft.trim();
    if (value === current) {
      setDraft(null);
      return;
    }
    if (
      field !== 'distribution_note' &&
      ((field === 'quantity' && Number(value) <= 0) || (value !== '' && !/^\d+(\.\d{1,4})?$/.test(value)))
    ) {
      setError('请输入有效数值（最多四位小数）');
      return;
    }
    setError('');
    try {
      await write.mutateAsync({ id: row.id, value });
      setDraft(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : '保存失败，请核对后重试');
    }
  }
  return (
    <div>
      <Input
        size="small"
        aria-label={row.name + ' ' + label}
        value={draft ?? shown ?? ''}
        title={field === 'custom_unit_price' ? '清空自定单价后按原值的 5% 计价' : label}
        disabled={context.locked || busy}
        onFocus={() => {
          if (draft === null) setDraft(current);
        }}
        placeholder={field === 'custom_unit_price' ? (row.unit_price ?? '原值 × 5%') : ''}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={() => void save()}
        onPressEnter={(e) => e.currentTarget.blur()}
      />
      {error && (
        <span role="alert">
          {error}{' '}
          <Button
            size="small"
            onClick={() => {
              setDraft(null);
              setError('');
            }}
          >
            取消修改
          </Button>
        </span>
      )}
    </div>
  );
}
function Quantity(p: Cell) {
  return <EditCell {...p} field="quantity" />;
}
function Price(p: Cell) {
  return <EditCell {...p} field="custom_unit_price" />;
}
function Note(p: Cell) {
  return <EditCell {...p} field="distribution_note" />;
}
function Decision({ data: r, context }: Cell) {
  if (!r) return null;
  const meta = JSON.parse(r.pending_meta_json || '{}');
  return (
    <div className="equipment-billing">
      {r.pending_action_type === 'transfer_attribution' && (
        <span>
          {meta.from_project} → {meta.to_project} · {meta.transfer_date}（25 日起建议归调出，此前归调入）
        </span>
      )}
      {r.pending_action_type !== 'none' && (
        <div className="equipment-actions">
          {choices[r.pending_action_type].map(([value, label]) => (
            <Button
              key={value}
              size="small"
              disabled={context.locked}
              onClick={() => void context.act(() => api.resolve(r.id, value))}
            >
              {label}
            </Button>
          ))}
        </div>
      )}
      <Select
        size="small"
        aria-label={r.name + ' 本月计租'}
        value={r.billing_status}
        disabled={context.locked}
        options={options(billing)}
        onChange={(v: Billing) => void context.act(() => api.patchLine(r.id, { billing_status: v }))}
      />
    </div>
  );
}
const columns: ColDef<RentalLine>[] = [
  {
    colId: 'sequence',
    headerName: '序号',
    minWidth: 78,
    rowDrag: true,
    valueGetter: (p) => (p.node?.rowIndex ?? 0) + 1,
  },
  {
    field: 'name',
    headerName: '名称',
    tooltipValueGetter: (p) => (p.data?.source_row ? '租赁底稿行 ' + p.data.source_row : p.value),
  },
  { field: 'spec', headerName: '规格型号' },
  { field: 'unit', headerName: '单位' },
  { field: 'quantity', headerName: '数量', cellRenderer: Quantity },
  { field: 'unit_price', headerName: '租赁单价(元)', cellRenderer: Price },
  { field: 'amount', headerName: '金额(元)' },
  { field: 'category_label', headerName: '类别' },
  { field: 'distribution_note', headerName: '分布', cellRenderer: Note },
  { colId: 'billing', headerName: '本月计租', minWidth: 220, autoHeight: true, cellRenderer: Decision },
];
function ProjectGrid({
  group,
  month,
  only,
  context,
}: {
  group: RentGroup;
  month: string;
  only: boolean;
  context: RentalContext;
}) {
  const drag = useGridRowDrag<RentalLine>({
    disabled: context.locked || only,
    sourceId: (r) => r.id,
    targetId: (s, t) => (s.project_name === t.project_name ? t.id : null),
    orderFor: () => group.lines.map((r) => r.id),
    save: (_, __, ids) => context.act(() => api.reorder(month, group.project_name, ids)),
  });
  const rows = rowsInOrder(group.lines, drag.preview?.order, (r) => r.id).filter(
    (r) => !only || r.pending_action_type !== 'none'
  );
  if (!rows.length) return null;
  return (
    <section className="equipment-project">
      <h3>
        {group.project_name}
        <span>项目小计　{group.subtotal ?? '—'} 元</span>
      </h3>
      <BusinessGrid
        table="equipment-rental"
        scope={month + group.project_name}
        rows={rows}
        columns={columns}
        rowId={rowId}
        label={group.project_name + '租赁明细'}
        domLayout="autoHeight"
        grid={drag.grid}
        context={context}
      />
    </section>
  );
}
export function Rental() {
  const [month, setMonth] = useState(dayjs().format('YYYY-MM')),
    [project, setProject] = useState(''),
    [only, setOnly] = useState(false),
    [confirm, setConfirm] = useState(false);
  const query = useLedgerQuery(['rental', month], () => api.rental(month)),
    action = useLedgerAction(),
    { writable } = useAccess(),
    data = query.data;
  const savingCells = useIsMutating({ mutationKey: ['equipment-rental-edit', month] }) > 0;
  const locked = !writable || query.isError || data?.status !== 'draft' || action.busy;
  const context: RentalContext = {
    locked,
    act: (fn) =>
      action.run(async () => {
        await fn();
      }),
  };
  return (
    <>
      <div data-page-chrome className="equipment-toolbar">
        <DateField
          month
          label="租赁月份"
          value={month}
          onChange={(v) => {
            if (v) {
              setMonth(v);
              setProject('');
            }
          }}
        />
        <Select
          aria-label="租赁项目"
          value={project}
          options={[
            { value: '', label: '全部项目' },
            ...(data?.projects ?? []).map((g) => ({ value: g.project_name, label: g.project_name })),
          ]}
          onChange={setProject}
        />
        <Checkbox checked={only} onChange={(e) => setOnly(e.target.checked)}>
          仅看待定项 ({data?.pending_count ?? '…'})
        </Checkbox>
        <Button
          type="primary"
          disabled={locked || savingCells || !!data?.pending_count}
          title={data?.pending_count ? '请先处理全部待定项' : undefined}
          onClick={() => setConfirm(true)}
        >
          {data?.status === 'confirmed' ? '本月租赁已确认' : '确认本月租赁'}
        </Button>
        <Button
          disabled={!data || action.busy || savingCells}
          onClick={() => void action.run(() => exportEquipment('rental', month), false)}
        >
          导出租赁 Excel
        </Button>
      </div>
      <LoadState query={query} />
      {action.error && <p role="alert">{action.error}</p>}
      {data && (
        <>
          {data.projects
            .filter((g) => !project || g.project_name === project)
            .map((g) => (
              <ProjectGrid
                key={month + g.project_name}
                group={g}
                month={month}
                only={only}
                context={context}
              />
            ))}
          <div className="equipment-total">
            本月总计　{data.grand_total ?? '—'} 元 <small>零合计项目保留在列表，打印导出时跳过。</small>
          </div>
        </>
      )}
      {confirm && (
        <LedgerModal
          title={'确认 ' + month + ' 全部项目租赁？'}
          busy={action.busy}
          close={() => setConfirm(false)}
        >
          <p>确认后本月明细及计租归属将锁定。</p>
          <Button
            type="primary"
            disabled={locked || savingCells}
            onClick={() =>
              void action.run(async () => {
                await api.confirm(month);
                setConfirm(false);
              })
            }
          >
            确认本月租赁
          </Button>
          {action.error && <p role="alert">{action.error}</p>}
        </LedgerModal>
      )}
    </>
  );
}
