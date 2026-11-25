import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Button from 'antd/es/button';
import Checkbox from 'antd/es/checkbox';
import Dropdown from 'antd/es/dropdown';
import Segmented from 'antd/es/segmented';
import type { ColDef, GridApi, ICellRendererParams } from 'ag-grid-community';
import { BusinessGrid, ReadGrid } from './business-grid';
import { equipmentApi as api, exportEquipment } from './equipment-api';
import type { EquipmentItem, ItemCategory, ScrapRow, TransferRow } from './equipment-api';
import { EquipmentDialog } from './equipment-dialogs';
import type { DialogState } from './equipment-dialogs';
import { equipmentFlashDuration, whenEquipmentTargetReady } from './equipment-navigation';
import type { RentalTarget } from './equipment-navigation';
import { contentWidth, numberColumnWidth } from './grid';
import {
  flagLabels,
  formatNum,
  issue,
  ledgerColumn,
  LoadState,
  options,
  projectTitle,
  rowId,
  scopeLabels,
  statusLabels,
  syncLabels,
  syncReceipt,
  SyncTag,
  useAccess,
  useLedgerAction,
  useLedgerQuery,
} from './equipment-ui';

const tabs = { equipment: '工机具分布', transfers: '调拨记录', scraps: '报废记录', turnover: '周转材料' };
const categoryLabels = { equipment: '工机具', turnover: '周转材料' };
const emptyItems: EquipmentItem[] = [];
const moreActions = [
  { key: 'transfers', label: '查看调拨记录' },
  { key: 'rental', label: '去租赁表' },
  { key: 'sync', label: 'i8 同步与来源' },
];
const headerFilters = { enableFilterHandlers: true, popupParent: document.body, enableBrowserTooltips: true };

function TransferActions({ transfer, writable, openSync, remove }: {
  transfer: TransferRow;
  writable: boolean;
  openSync: (id: number) => void;
  remove: (row: TransferRow) => void;
}) {
  const reason = !transfer.is_latest_for_equipment ? '仅可删除该设备的最新一条调拨记录'
    : transfer.i8_sync_status === 'synced' ? '已同步 i8 的调拨不可直接删除'
    : !writable ? '当前没有删除权限' : undefined;
  return (
    <div className="equipment-row-actions">
      <Button size="small" onClick={() => openSync(transfer.equipment_id)}>i8 同步与来源</Button>
      <span title={reason}>
        <Button size="small" danger disabled={!!reason} onClick={() => remove(transfer)}>删除</Button>
      </span>
    </div>
  );
}

function useHistoryColumns(
  scale: number, writable: boolean, openSync: (id: number) => void, remove: (row: TransferRow) => void
) {
  const transferColumns = useMemo<ColDef<TransferRow>[]>(() => [
    ledgerColumn({ colId: 'item_category', headerName: '类别', ...contentWidth(72, 90, scale) }, r => categoryLabels[r.item_category]),
    ledgerColumn({ field: 'code', headerName: '编号', ...contentWidth(165, 225, scale) }, r => r.code),
    ledgerColumn({ field: 'name', headerName: '名称', ...contentWidth(108, 175, scale, 0.7) }, r => r.name),
    ledgerColumn({ field: 'spec', headerName: '规格型号', ...contentWidth(92, 165, scale, 0.5) }, r => r.spec),
    ledgerColumn({
      field: 'from_project', headerName: '调出项目', ...contentWidth(104, 150, scale),
      tooltipValueGetter: ({ data }) => data && projectTitle(data.from_project_disp, data.from_project_custom, data.from_project),
    }, r => r.from_project),
    ledgerColumn({
      field: 'to_project', headerName: '调入项目', ...contentWidth(104, 150, scale),
      tooltipValueGetter: ({ data }) => data && projectTitle(data.to_project_disp, data.to_project_custom, data.to_project),
    }, r => r.to_project),
    ledgerColumn({ field: 'transfer_date', headerName: '调拨日期', ...contentWidth(96, 110, scale) }, r => r.transfer_date, 'date'),
    ledgerColumn({ field: 'quantity', headerName: '数量', ...contentWidth(60, 76, scale) }, r => r.quantity, 'number'),
    ledgerColumn({ field: 'remark', headerName: '调拨备注', ...contentWidth(180, 440, scale, 2) }, r => r.remark),
    ledgerColumn({
      colId: 'sync', headerName: '同步状态', ...contentWidth(80, 98, scale),
      cellRenderer: ({ data }: ICellRendererParams<TransferRow>) => data && <SyncTag status={data.i8_sync_status} />,
    }, r => issue(r.i8_sync_status) ? syncLabels[r.i8_sync_status] : null),
    {
      colId: 'actions', headerName: '操作', ...contentWidth(156, 180, scale),
      cellRenderer: ({ data }: ICellRendererParams<TransferRow>) =>
        data && <TransferActions transfer={data} writable={writable} openSync={openSync} remove={remove} />,
    },
  ], [openSync, remove, scale, writable]);
  const scrapColumns = useMemo<ColDef<ScrapRow>[]>(() => [
    ledgerColumn({ colId: 'item_category', headerName: '类别', ...contentWidth(72, 90, scale) }, r => categoryLabels[r.item_category]),
    ledgerColumn({ field: 'code', headerName: '编号', ...contentWidth(165, 225, scale) }, r => r.code),
    ledgerColumn({ field: 'name', headerName: '名称', ...contentWidth(108, 175, scale, 0.7) }, r => r.name),
    ledgerColumn({ field: 'spec', headerName: '规格型号', ...contentWidth(92, 165, scale, 0.5) }, r => r.spec),
    ledgerColumn({ field: 'quantity', headerName: '数量', ...contentWidth(60, 76, scale) }, r => r.quantity, 'number'),
    ledgerColumn({
      field: 'original_project', headerName: '原所在项目', ...contentWidth(108, 155, scale),
      tooltipValueGetter: ({ data }) => data && projectTitle(data.original_project_disp, data.original_project_custom, data.original_project),
    }, r => r.original_project),
    ledgerColumn({ field: 'scrap_date', headerName: '报废日期', ...contentWidth(96, 110, scale) }, r => r.scrap_date, 'date'),
    ledgerColumn({ field: 'reason', headerName: '报废原因', ...contentWidth(180, 440, scale, 2) }, r => r.reason),
    {
      colId: 'actions', headerName: '操作', ...contentWidth(108, 126, scale),
      cellRenderer: ({ data }: ICellRendererParams<ScrapRow>) =>
        data && <Button size="small" onClick={() => openSync(data.equipment_id)}>i8 同步与来源</Button>,
    },
  ], [openSync, scale]);
  return { transferColumns, scrapColumns };
}

type DistributionTarget = { category: ItemCategory; ids: ReadonlySet<number> };

function PreviewText({ value }: ICellRendererParams<EquipmentItem, string | null>) {
  return <span className="grid-ellipsis" onMouseEnter={({ currentTarget }) => {
    currentTarget.title = currentTarget.scrollWidth > currentTarget.clientWidth ? value ?? '' : '';
  }}>{value}</span>;
}

export function Distribution({ goToRental, targetIds, scale }: {
  goToRental: (target: RentalTarget) => void;
  targetIds: readonly number[] | null;
  scale: number;
}) {
  const [tab, setTab] = useState<keyof typeof tabs>('equipment');
  const [historyItem, setHistoryItem] = useState<Pick<EquipmentItem, 'id' | 'code'> | null>(null);
  const [only, setOnly] = useState(false);
  const [selected, setSelected] = useState<EquipmentItem[]>([]);
  const [dialog, setDialog] = useState<DialogState | null>(null);
  const [receipt, setReceipt] = useState('');
  const [destination, setDestination] = useState<DistributionTarget | null>(null);
  const [readyGrid, setReadyGrid] = useState<{ category: ItemCategory; api: GridApi<EquipmentItem> } | null>(null);
  const sheet = useRef<HTMLDivElement>(null);
  const resolved = useRef<readonly number[] | null>(null);
  const highlighted = useRef<DistributionTarget | null>(null);
  const flashIds = useRef<ReadonlySet<number>>(new Set());
  const { enabled, writable } = useAccess();
  const action = useLedgerAction();
  const listTab = tab === 'equipment' || tab === 'turnover';
  const category: ItemCategory = tab === 'turnover' ? 'turnover' : 'equipment';
  const list = useLedgerQuery(['list'], () => api.list({ include_scrapped: true }), listTab || !!targetIds);
  const transfers = useLedgerQuery(['transfers'], () => api.transfers({}), tab === 'transfers');
  const scraps = useLedgerQuery(['scraps'], () => api.scraps({}), tab === 'scraps');
  const problems = useLedgerQuery(['sync-issues'], api.issues);
  const items = useMemo(() => (list.data?.items ?? emptyItems).filter(r =>
    r.item_category === category && (r.status !== 'scrapped' || destination?.ids.has(r.id))
  ), [list.data, category, destination]);
  const issues = useMemo(() => items.filter(r => issue(r.i8_sync_status)), [items]);
  const rows = only ? issues : items;
  const selectedIds = useMemo(() => new Set(selected.map(r => r.id)), [selected]);
  const selectedRows = useMemo(() => rows.filter(r => selectedIds.has(r.id)), [rows, selectedIds]);
  const transferRows = useMemo(() => {
    const records = transfers.data?.items ?? [];
    return historyItem ? records.filter(row => row.equipment_id === historyItem.id) : records;
  }, [transfers.data, historyItem]);

  useEffect(() => {
    if (!enabled || !targetIds || targetIds === resolved.current || !list.data) return;
    resolved.current = targetIds;
    const byId = new Map(list.data.items.map(item => [item.id, item]));
    const linked = targetIds.flatMap(id => {
      const item = byId.get(id);
      return item ? [item] : [];
    });
    const first = linked[0];
    if (!first) {
      setReceipt('在设备分布中找不到关联设备。');
      return;
    }
    const matches = linked.filter(item => item.item_category === first.item_category);
    setDestination({ category: first.item_category, ids: new Set(matches.map(item => item.id)) });
    setTab(first.item_category);
    setHistoryItem(null);
    if (tab !== first.item_category) setSelected([]);
    if (matches.some(item => !issue(item.i8_sync_status))) setOnly(false);
  }, [enabled, list.data, tab, targetIds]);

  useEffect(() => {
    const root = sheet.current;
    if (!enabled || !listTab || !root || !destination || destination === highlighted.current ||
        !readyGrid || readyGrid.category !== destination.category) return;
    const { api } = readyGrid;
    let highlightTimer = 0;
    function clearHighlight() {
      if (!flashIds.current.size) return;
      const ids = flashIds.current;
      flashIds.current = new Set();
      if (api.isDestroyed()) return;
      const rendered = api.getRenderedNodes().filter(node => node.data && ids.has(node.data.id));
      if (rendered.length) api.redrawRows({ rowNodes: rendered });
    }
    const stop = whenEquipmentTargetReady(root, () => {
      if (api.isDestroyed() || !root.querySelector('.equipment-grid-slot .business-grid[data-layout-state="ready"]:not([inert])')) return false;
      const nodes = [...destination.ids].flatMap(id => api.getRowNode(String(id)) ?? []);
      const first = nodes[0];
      if (nodes.length !== destination.ids.size || !first) return false;
      if (nodes.some(node => node.rowIndex === null)) api.setFilterModel(null);
      if (first.rowIndex === null) return false;
      highlighted.current = destination;
      flashIds.current = destination.ids;
      api.ensureNodeVisible(first, 'middle');
      api.redrawRows({ rowNodes: nodes });
      highlightTimer = window.setTimeout(clearHighlight, equipmentFlashDuration);
      return true;
    });
    return () => {
      stop();
      window.clearTimeout(highlightTimer);
      clearHighlight();
    };
  }, [destination, enabled, listTab, readyGrid]);

  const openSync = useCallback((id: number) => setDialog({ kind: 'sync', id }), []);
  const removeTransfer = useCallback((transfer: TransferRow) => setDialog({ kind: 'delete-transfer', transfer }), []);
  const { transferColumns, scrapColumns } = useHistoryColumns(scale, writable, openSync, removeTransfer);
  function updateSelection(grid: GridApi<EquipmentItem>) {
    const visible: EquipmentItem[] = [];
    grid.forEachNodeAfterFilter(node => {
      if (node.isSelected() && node.data) visible.push(node.data);
    });
    setSelected(visible);
  }

  const columns = useMemo<ColDef<EquipmentItem>[]>(() => [
    ledgerColumn({ field: 'code', headerName: '工机具编号', ...contentWidth(165, 225, scale), cellRenderer: PreviewText }, r => r.code),
    ledgerColumn({ field: 'name', headerName: '名称', ...contentWidth(108, 175, scale, 0.7), cellRenderer: PreviewText }, r => r.name),
    ledgerColumn({ field: 'spec', headerName: '规格型号', ...contentWidth(92, 165, scale, 0.5), cellRenderer: PreviewText }, r => r.spec),
    ledgerColumn({ field: 'unit', headerName: '单位', ...contentWidth(52, 66, scale) }, r => r.unit),
    ledgerColumn({ field: 'quantity', headerName: '数量', ...contentWidth(60, 76, scale) }, r => r.quantity, 'number'),
    ledgerColumn({ field: 'purchase_date', headerName: '购买日期', ...contentWidth(96, 110, scale) }, r => r.purchase_date ?? r.purchase_date_text, 'date'),
    ledgerColumn({
      field: 'purchase_project', headerName: '购买项目', ...contentWidth(104, 150, scale),
      tooltipValueGetter: ({ data }) => data && projectTitle(data.purchase_project_disp, data.purchase_project_custom, data.purchase_project),
    }, r => r.purchase_project),
    ledgerColumn({
      field: 'purchase_price', headerName: '购买价格', cellClass: 'ag-right-aligned-cell',
      ...numberColumnWidth(items.map(item => formatNum(item.purchase_price)), scale, false, 0),
    }, r => r.purchase_price, 'number'),
    ledgerColumn({
      field: 'current_project', headerName: '当前所在项目', ...contentWidth(108, 155, scale),
      tooltipValueGetter: ({ data }) => data && projectTitle(data.current_project_disp, data.current_project_custom, data.current_project),
    }, r => r.current_project),
    ledgerColumn({ field: 'status', headerName: '当前状态', ...contentWidth(70, 84, scale) }, r => statusLabels[r.status]),
    ledgerColumn({ field: 'asset_scope', headerName: '资产归属', ...contentWidth(80, 94, scale) }, r => scopeLabels[r.asset_scope]),
    ledgerColumn({ field: 'in_rental', headerName: '列租赁表', ...contentWidth(72, 86, scale) }, r => flagLabels[r.in_rental]),
    ledgerColumn({
      colId: 'sync', headerName: '同步/待办', ...contentWidth(80, 98, scale),
      cellRenderer: ({ data }: ICellRendererParams<EquipmentItem>) => data && <SyncTag status={data.i8_sync_status} />,
    }, r => issue(r.i8_sync_status) ? syncLabels[r.i8_sync_status] : null),
    ledgerColumn({ field: 'remark', headerName: '备注', ...contentWidth(180, 440, scale, 2), cellRenderer: PreviewText }, r => r.remark),
    {
      colId: 'actions', headerName: '操作', ...contentWidth(188, 210, scale), pinned: 'right',
      cellRenderer: ({ data }: ICellRendererParams<EquipmentItem>) => data && (
        <div className="equipment-row-actions">
          <Button size="small" disabled={!writable || data.status === 'scrapped'} onClick={() => setDialog({ kind: 'transfer', items: [data] })}>调拨</Button>
          <Button size="small" disabled={!writable || data.status === 'scrapped'} onClick={() => setDialog({ kind: 'edit', item: data })}>编辑</Button>
          <Button size="small" danger disabled={!writable || data.status === 'scrapped'} onClick={() => setDialog({ kind: 'scrap', item: data })}>报废</Button>
          <Dropdown trigger={['click']} menu={{
            items: moreActions,
            onClick: ({ key }) => {
              if (key === 'rental') goToRental({
                equipmentId: data.id, projectId: data.current_project_id, projectName: data.current_project,
              });
              if (key === 'sync') openSync(data.id);
              if (key === 'transfers') {
                setTab('transfers');
                setHistoryItem(data);
                setSelected([]);
              }
            },
          }}>
            <Button size="small" aria-haspopup="menu">更多</Button>
          </Dropdown>
        </div>
      ),
    },
  ], [writable, goToRental, openSync, items, scale]);

  const pending = problems.data;
  const retryable = pending && pending.equipment.length + pending.transfers.length > 0;
  return (
    <div className="equipment-sheet" ref={sheet}>
      <div data-page-chrome className="equipment-toolbar equipment-workspace-bar">
        <Segmented value={tab} options={options(tabs)} onChange={value => {
          setTab(value as keyof typeof tabs);
          setSelected([]);
          setDestination(null);
          setHistoryItem(null);
        }} />
        <div className="equipment-actions equipment-toolbar-actions">
          {listTab && <Checkbox checked={only} onChange={event => setOnly(event.target.checked)}>
            仅看异常/待同步{issues.length ? ' (' + issues.length + ')' : ''}
          </Checkbox>}
          {retryable && (
            <Button disabled={!writable || action.busy} onClick={() => void action.run(async () => {
              const linked = new Set(pending.transfers.map(t => t.equipment_id));
              const r = await api.retry({
                equipment_ids: pending.equipment.filter(i => !linked.has(i.id)).map(i => i.id),
                transfer_ids: pending.transfers.map(t => t.id),
              });
              setReceipt('i8 补同步结果：' + syncReceipt([...r.equipment, ...r.transfers]));
            })}>
              一键补同步 i8
            </Button>
          )}
          {listTab && <>
            <Button disabled={!writable || !selectedRows.length} onClick={() => setDialog({ kind: 'transfer', items: selectedRows })}>
              批量调拨{selectedRows.length ? ' (' + selectedRows.length + ')' : ''}
            </Button>
            <Button type="primary" disabled={!writable} onClick={() => setDialog({ kind: 'create', category })}>
              {category === 'equipment' ? '新增设备' : '新增周转材料'}
            </Button>
          </>}
          <Button size="small" onClick={() => setDialog({ kind: 'locations' })}>地点维护</Button>
          <Button disabled={action.busy} onClick={() => void action.run(() => exportEquipment('distribution'), false)}>
            导出分布 Excel
          </Button>
        </div>
      </div>
      {tab === 'transfers' && historyItem && (
        <div className="equipment-history-scope">
          {historyItem.code}
          <Button size="small" type="text" onClick={() => setHistoryItem(null)}>查看全部调拨</Button>
        </div>
      )}
      {receipt && (
        <div className="equipment-receipt" role="status">
          {receipt}{' '}<Button type="text" onClick={() => setReceipt('')}>收起</Button>
        </div>
      )}
      {action.error && <p role="alert">{action.error}</p>}
      {problems.error && <LoadState query={problems} />}
      {listTab && <>
        <LoadState query={list} />
        {list.data && (
          <BusinessGrid
            key={category}
            table={'equipment-' + category}
            label={tabs[tab]}
            rows={rows}
            columns={columns}
            rowId={rowId}
            domLayout="normal"
            scale={scale}
            singleLine
            className="equipment-grid-slot"
            grid={{
              ...headerFilters,
              rowSelection: {
                mode: 'multiRow', enableClickSelection: false, selectAll: 'filtered',
                isRowSelectable: ({ data }) => !!data && data.status !== 'scrapped',
              },
              rowClassRules: { 'equipment-flash-row': ({ data }) => !!data && flashIds.current.has(data.id) },
              onFirstDataRendered: ({ api }) => setReadyGrid({ category, api }),
              onSelectionChanged: event => updateSelection(event.api),
              onFilterChanged: event => updateSelection(event.api),
            }}
          />
        )}
      </>}
      {tab === 'transfers' && <>
        <LoadState query={transfers} />
        {transfers.data && (
          <ReadGrid table="equipment-transfers" label="调拨记录" rows={transferRows} columns={transferColumns}
            rowId={rowId} domLayout="normal" scale={scale} className="equipment-grid-slot" grid={headerFilters} />
        )}
      </>}
      {tab === 'scraps' && <>
        <LoadState query={scraps} />
        {scraps.data && (
          <ReadGrid table="equipment-scraps" label="报废记录" rows={scraps.data.items} columns={scrapColumns}
            rowId={rowId} domLayout="normal" scale={scale} className="equipment-grid-slot" grid={headerFilters} />
        )}
      </>}
      {dialog && (
        <EquipmentDialog key={dialog.kind} state={dialog} close={() => setDialog(null)}
          done={msg => { setReceipt(msg); setDialog(null); }} />
      )}
    </div>
  );
}
