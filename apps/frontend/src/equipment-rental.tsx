import { useEffect, useMemo, useRef, useState } from 'react';
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
import { equipmentFlashDuration, scrollToEquipmentTarget, whenEquipmentTargetReady } from './equipment-navigation';
import type { RentalTarget } from './equipment-navigation';
import { contentWidth } from './grid';
import {
  DateField,
  decimalInput,
  formatNum,
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
type RentalContext = {
  locked: boolean;
  act: (fn: () => Promise<unknown>) => Promise<void>;
  goToDistribution: (ids: readonly number[]) => void;
};
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
    numeric = field !== 'distribution_note',
    current = numeric ? decimalInput(row[field] ?? '') : row[field] ?? '',
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
        value={draft ?? (numeric && shown ? formatNum(shown) : shown ?? '')}
        title={field === 'custom_unit_price' ? '清空自定单价后按原值的 5% 计价' : label}
        disabled={context.locked || busy}
        onFocus={() => {
          if (draft === null) setDraft(current);
        }}
        placeholder={field === 'custom_unit_price' ? (row.unit_price === null ? '原值 × 5%' : formatNum(row.unit_price)) : ''}
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
function EquipmentName({ data, context }: Cell) {
  const id = data?.equipment_id;
  if (!data || id == null) return data?.name;
  return <button type="button" className="equipment-row-link" title="定位到设备分布"
    onClick={() => context.goToDistribution([id])}>{data.name}</button>;
}

function rentalColumns(scale: number): ColDef<RentalLine>[] {
  return [
    {
      colId: 'sequence', headerName: '序号', ...contentWidth(61, 68, scale), rowDrag: true,
      valueGetter: p => (p.node?.rowIndex ?? 0) + 1,
    },
    {
      field: 'name', headerName: '名称', ...contentWidth(84, 140, scale, 1), cellRenderer: EquipmentName,
      tooltipValueGetter: p => p.data?.source_row ? '租赁底稿行 ' + p.data.source_row : p.value,
    },
    { field: 'spec', headerName: '规格型号', ...contentWidth(70, 115, scale, 0.6) },
    { field: 'unit', headerName: '单位', ...contentWidth(42, 56, scale) },
    { field: 'quantity', headerName: '数量', ...contentWidth(55, 72, scale), cellRenderer: Quantity },
    { field: 'unit_price', headerName: '租赁单价(元)', ...contentWidth(81, 94, scale), cellRenderer: Price },
    { field: 'amount', headerName: '金额(元)', ...contentWidth(78, 106, scale),
      cellClass: 'ag-right-aligned-cell', valueFormatter: ({ value }) => formatNum(value) },
    { field: 'category_label', headerName: '类别', ...contentWidth(48, 66, scale) },
    { field: 'distribution_note', headerName: '分布', ...contentWidth(62, 102, scale, 0.7), cellRenderer: Note },
    { colId: 'billing', headerName: '本月计租', ...contentWidth(130, 154, scale), autoHeight: true, cellRenderer: Decision },
  ];
}
const groupKey = (group: RentGroup) => group.project_id === null ? 'name:' + group.project_name : 'id:' + group.project_id;
const projectAnchor = (group: RentGroup) => 'equipment-rental-' + encodeURIComponent(groupKey(group));

function ProjectGrid({
  group,
  month,
  only,
  context,
  columns,
  scale,
}: {
  group: RentGroup;
  month: string;
  only: boolean;
  context: RentalContext;
  columns: ColDef<RentalLine>[];
  scale: number;
}) {
  const drag = useGridRowDrag<RentalLine>({
    disabled: context.locked || only,
    sourceId: (r) => r.id,
    targetId: (_source, target) => target.id,
    orderFor: () => group.lines.map((r) => r.id),
    save: (_, __, ids) => context.act(() => api.reorder(month, group.project_id, group.project_name, ids)),
  });
  const order = drag.preview?.order;
  const rows = useMemo(() => {
    const ordered = rowsInOrder(group.lines, order, r => r.id);
    return only ? ordered.filter(r => r.pending_action_type !== 'none') : ordered;
  }, [group.lines, order, only]);
  return (
    <section className="equipment-project" id={projectAnchor(group)}>
      <h3>
        {group.project_name}
        <span>项目小计　{formatNum(group.subtotal)} 元</span>
      </h3>
      {rows.length ? <BusinessGrid
        table="equipment-rental"
        scope={month + groupKey(group)}
        rows={rows}
        columns={columns}
        rowId={rowId}
        label={group.project_name + '租赁明细'}
        domLayout="autoHeight"
        scale={scale}
        grid={drag.grid}
        context={context}
      /> : <p className="equipment-project-empty">{only ? '没有待定项' : '暂无租赁明细'}</p>}
    </section>
  );
}
export function Rental({ target, scale, goToDistribution }: {
  target: RentalTarget | null;
  scale: number;
  goToDistribution: (ids: readonly number[]) => void;
}) {
  const [month, setMonth] = useState(dayjs().format('YYYY-MM')),
    [only, setOnly] = useState(false),
    [confirm, setConfirm] = useState(false),
    [jumpNotice, setJumpNotice] = useState('');
  const scroll = useRef<HTMLDivElement>(null);
  const resolved = useRef<RentalTarget | null>(null);
  const columns = useMemo(() => rentalColumns(scale), [scale]);
  const query = useLedgerQuery(['rental', month], () => api.rental(month)),
    action = useLedgerAction(),
    { enabled, writable } = useAccess(),
    data = query.data;
  const savingCells = useIsMutating({ mutationKey: ['equipment-rental-edit', month] }) > 0;
  const locked = !writable || query.isError || data?.status !== 'draft' || action.busy;
  const context: RentalContext = {
    locked,
    goToDistribution,
    act: (fn) =>
      action.run(async () => {
        await fn();
      }),
  };

  useEffect(() => {
    const root = scroll.current;
    if (!enabled || !target || !data || !root || resolved.current === target) return;
    if (only) {
      setOnly(false);
      return;
    }
    const linked = data.projects.find(group => group.lines.some(line => line.equipment_id === target.equipmentId));
    const group = linked ?? data.projects.find(project => target.projectId !== null
      ? project.project_id === target.projectId
      : project.project_name === target.projectName);
    if (!group) {
      resolved.current = target;
      setJumpNotice('本月租赁表未找到对应设备或项目。');
      return;
    }
    setJumpNotice('');
    const line = group.lines.find(row => row.equipment_id === target.equipmentId);
    let flash: HTMLElement | null = null;
    let inView: IntersectionObserver | undefined;
    let flashTimer = 0;
    const stop = whenEquipmentTargetReady(root, () => {
      if (root.querySelector('.business-grid[data-layout-state="preparing"]')) return false;
      const card = document.getElementById(projectAnchor(group));
      const row = card?.querySelector<HTMLElement>(line
        ? `.ag-center-cols-container .ag-row[row-id="${line.id}"]`
        : 'h3');
      if (!row || (line && row.closest('[inert]'))) return false;
      resolved.current = target;
      inView = new IntersectionObserver(entries => {
        if (!entries.some(entry => entry.isIntersecting)) return;
        inView?.disconnect();
        flash = row;
        row.classList.add('equipment-flash-row');
        flashTimer = window.setTimeout(() => row.classList.remove('equipment-flash-row'), equipmentFlashDuration);
      }, { root, threshold: 0.5 });
      inView.observe(row);
      scrollToEquipmentTarget(row, line ? 'center' : 'start');
      return true;
    });
    return () => {
      stop();
      inView?.disconnect();
      window.clearTimeout(flashTimer);
      flash?.classList.remove('equipment-flash-row');
    };
  }, [data, enabled, only, target]);

  return (
    <div className="equipment-sheet">
      <div data-page-chrome className="equipment-toolbar">
        <DateField
          month
          label="租赁月份"
          value={month}
          onChange={v => {
            if (v) { setMonth(v); setJumpNotice(''); }
          }}
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
      {jumpNotice && <div className="equipment-receipt" role="status">{jumpNotice}</div>}
      {!!data?.projects.length && (
        <nav className="equipment-rental-nav" aria-label="项目快速导航">
          {data.projects.map(group => {
            const pending = group.lines.filter(line => line.pending_action_type !== 'none').length;
            const zeroTotal = group.subtotal !== null && Number(group.subtotal) === 0;
            return (
              <Button key={groupKey(group)} size="small" shape="round"
                className={zeroTotal ? 'equipment-project-zero' : ''}
                aria-controls={projectAnchor(group)}
                onClick={() => {
                  const card = document.getElementById(projectAnchor(group));
                  if (card) scrollToEquipmentTarget(card);
                }}>
                {group.project_name}
                {!!pending && <span className="equipment-nav-pending" aria-label={pending + ' 项待定'}>{pending}</span>}
              </Button>
            );
          })}
        </nav>
      )}
      {data && (
        <div className="equipment-rental-scroll" ref={scroll} tabIndex={0} role="region" aria-label="月租赁明细">
          <div className="equipment-rental-grid">
            {data.projects.map((g) => (
              <ProjectGrid
                key={month + groupKey(g)}
                group={g}
                month={month}
                only={only}
                context={context}
                columns={columns}
                scale={scale}
              />
            ))}
          </div>
          <div className="equipment-total">
            本月总计　{formatNum(data.grand_total)} 元 <small>零合计项目保留在列表，打印导出时跳过。</small>
          </div>
        </div>
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
    </div>
  );
}
