import { useCallback, useMemo, useState } from 'react';
import Button from 'antd/es/button';
import Checkbox from 'antd/es/checkbox';
import Dropdown from 'antd/es/dropdown';
import Input from 'antd/es/input';
import Segmented from 'antd/es/segmented';
import type { ColDef, GridApi, ICellRendererParams } from 'ag-grid-community';
import { BusinessGrid, ReadGrid } from './business-grid';
import { equipmentApi as api, exportEquipment } from './equipment-api';
import type { EquipmentItem, ItemCategory, ScrapRow, TransferRow } from './equipment-api';
import { EquipmentDialog } from './equipment-dialogs';
import type { DialogState } from './equipment-dialogs';
import {
  flagLabels,
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

function useHistoryColumns(openSync: (id: number) => void) {
  const transferColumns = useMemo<ColDef<TransferRow>[]>(() => [
    ledgerColumn({ colId: 'item_category', headerName: '类别' }, r => categoryLabels[r.item_category]),
    ledgerColumn({ field: 'code', headerName: '编号' }, r => r.code),
    ledgerColumn({ field: 'name', headerName: '名称' }, r => r.name),
    ledgerColumn({ field: 'spec', headerName: '规格型号' }, r => r.spec),
    ledgerColumn({
      field: 'from_project', headerName: '调出项目',
      tooltipValueGetter: ({ data }) => data && projectTitle(data.from_project_disp, data.from_project_custom, data.from_project),
    }, r => r.from_project),
    ledgerColumn({
      field: 'to_project', headerName: '调入项目',
      tooltipValueGetter: ({ data }) => data && projectTitle(data.to_project_disp, data.to_project_custom, data.to_project),
    }, r => r.to_project),
    ledgerColumn({ field: 'transfer_date', headerName: '调拨日期' }, r => r.transfer_date, 'date'),
    ledgerColumn({ field: 'quantity', headerName: '数量' }, r => r.quantity, 'number'),
    ledgerColumn({ field: 'remark', headerName: '调拨备注' }, r => r.remark),
    ledgerColumn({
      colId: 'sync', headerName: '同步状态',
      cellRenderer: ({ data }: ICellRendererParams<TransferRow>) => data && <SyncTag status={data.i8_sync_status} />,
    }, r => issue(r.i8_sync_status) ? syncLabels[r.i8_sync_status] : null),
    {
      colId: 'actions', headerName: '操作',
      cellRenderer: ({ data }: ICellRendererParams<TransferRow>) =>
        data && <Button size="small" onClick={() => openSync(data.equipment_id)}>i8 同步与来源</Button>,
    },
  ], [openSync]);
  const scrapColumns = useMemo<ColDef<ScrapRow>[]>(() => [
    ledgerColumn({ colId: 'item_category', headerName: '类别' }, r => categoryLabels[r.item_category]),
    ledgerColumn({ field: 'code', headerName: '编号' }, r => r.code),
    ledgerColumn({ field: 'name', headerName: '名称' }, r => r.name),
    ledgerColumn({ field: 'spec', headerName: '规格型号' }, r => r.spec),
    ledgerColumn({ field: 'quantity', headerName: '数量' }, r => r.quantity, 'number'),
    ledgerColumn({
      field: 'original_project', headerName: '原所在项目',
      tooltipValueGetter: ({ data }) => data && projectTitle(data.original_project_disp, data.original_project_custom, data.original_project),
    }, r => r.original_project),
    ledgerColumn({ field: 'scrap_date', headerName: '报废日期' }, r => r.scrap_date, 'date'),
    ledgerColumn({ field: 'reason', headerName: '报废原因' }, r => r.reason),
    {
      colId: 'actions', headerName: '操作',
      cellRenderer: ({ data }: ICellRendererParams<ScrapRow>) =>
        data && <Button size="small" onClick={() => openSync(data.equipment_id)}>i8 同步与来源</Button>,
    },
  ], [openSync]);
  return { transferColumns, scrapColumns };
}

export function Distribution({ goToRental }: { goToRental: () => void }) {
  const [tab, setTab] = useState<keyof typeof tabs>('equipment');
  const [keyword, setKeyword] = useState('');
  const [historyKeyword, setHistoryKeyword] = useState('');
  const [historyCode, setHistoryCode] = useState('');
  const [only, setOnly] = useState(false);
  const [selected, setSelected] = useState<EquipmentItem[]>([]);
  const [dialog, setDialog] = useState<DialogState | null>(null);
  const [receipt, setReceipt] = useState('');
  const { writable } = useAccess();
  const action = useLedgerAction();
  const listTab = tab === 'equipment' || tab === 'turnover';
  const category: ItemCategory = tab === 'turnover' ? 'turnover' : 'equipment';
  const list = useLedgerQuery(['list', category], () => api.list({ item_category: category, include_scrapped: false }), listTab);
  const transfers = useLedgerQuery(['transfers'], () => api.transfers({}), tab === 'transfers');
  const scraps = useLedgerQuery(['scraps'], () => api.scraps({}), tab === 'scraps');
  const problems = useLedgerQuery(['sync-issues'], api.issues);
  const items = list.data?.items ?? emptyItems;

  const matches = useMemo(() => {
    const term = keyword.trim().toLowerCase();
    return term ? items.filter(r => [r.code, r.name, r.spec, r.current_project, r.current_project_disp]
      .some(value => value?.toLowerCase().includes(term))) : items;
  }, [items, keyword]);
  const issues = useMemo(() => matches.filter(r => issue(r.i8_sync_status)), [matches]);
  const rows = only ? issues : matches;
  const selectedIds = useMemo(() => new Set(selected.map(r => r.id)), [selected]);
  const selectedRows = useMemo(() => rows.filter(r => selectedIds.has(r.id)), [rows, selectedIds]);
  const transferRows = useMemo(() => transfers.data?.items.filter(row =>
    historyCode ? row.code === historyCode : matchesHistory(row, historyKeyword)
  ) ?? [], [transfers.data, historyCode, historyKeyword]);
  const scrapRows = useMemo(() => scraps.data?.items.filter(row =>
    matchesHistory(row, historyKeyword)
  ) ?? [], [scraps.data, historyKeyword]);

  const openSync = useCallback((id: number) => setDialog({ kind: 'sync', id }), []);
  const { transferColumns, scrapColumns } = useHistoryColumns(openSync);
  function updateSelection(grid: GridApi<EquipmentItem>) {
    const visible: EquipmentItem[] = [];
    grid.forEachNodeAfterFilter(node => {
      if (node.isSelected() && node.data) visible.push(node.data);
    });
    setSelected(visible);
  }

  const columns = useMemo<ColDef<EquipmentItem>[]>(() => [
    ledgerColumn({ field: 'code', headerName: '编号', minWidth: 185 }, r => r.code),
    ledgerColumn({ field: 'name', headerName: '名称' }, r => r.name),
    ledgerColumn({ field: 'spec', headerName: '规格型号' }, r => r.spec),
    ledgerColumn({ field: 'unit', headerName: '单位' }, r => r.unit),
    ledgerColumn({ field: 'quantity', headerName: '数量' }, r => r.quantity, 'number'),
    ledgerColumn({ field: 'purchase_date', headerName: '购买日期' }, r => r.purchase_date ?? r.purchase_date_text, 'date'),
    ledgerColumn({
      field: 'purchase_project', headerName: '购买项目',
      tooltipValueGetter: ({ data }) => data && projectTitle(data.purchase_project_disp, data.purchase_project_custom, data.purchase_project),
    }, r => r.purchase_project),
    ledgerColumn({ field: 'purchase_price', headerName: '购买价格' }, r => r.purchase_price, 'number'),
    ledgerColumn({
      field: 'current_project', headerName: '当前所在项目',
      tooltipValueGetter: ({ data }) => data && projectTitle(data.current_project_disp, data.current_project_custom, data.current_project),
    }, r => r.current_project),
    ledgerColumn({ field: 'status', headerName: '当前状态' }, r => statusLabels[r.status]),
    ledgerColumn({ field: 'asset_scope', headerName: '资产归属' }, r => scopeLabels[r.asset_scope]),
    ledgerColumn({ field: 'in_rental', headerName: '列租赁表' }, r => flagLabels[r.in_rental]),
    ledgerColumn({
      colId: 'sync', headerName: '同步/待办',
      cellRenderer: ({ data }: ICellRendererParams<EquipmentItem>) => data && <SyncTag status={data.i8_sync_status} />,
    }, r => issue(r.i8_sync_status) ? syncLabels[r.i8_sync_status] : null),
    ledgerColumn({ field: 'remark', headerName: '备注' }, r => r.remark),
    {
      colId: 'actions', headerName: '操作', minWidth: 228, pinned: 'right',
      cellRenderer: ({ data }: ICellRendererParams<EquipmentItem>) => data && (
        <div className="equipment-row-actions">
          <Button size="small" disabled={!writable} onClick={() => setDialog({ kind: 'transfer', items: [data] })}>调拨</Button>
          <Button size="small" disabled={!writable} onClick={() => setDialog({ kind: 'edit', item: data })}>编辑</Button>
          <Button size="small" danger disabled={!writable} onClick={() => setDialog({ kind: 'scrap', item: data })}>报废</Button>
          <Dropdown trigger={['click']} menu={{
            items: moreActions,
            onClick: ({ key }) => {
              if (key === 'rental') goToRental();
              if (key === 'sync') openSync(data.id);
              if (key === 'transfers') {
                setTab('transfers');
                setHistoryKeyword('');
                setHistoryCode(data.code);
                setSelected([]);
              }
            },
          }}>
            <Button size="small" aria-haspopup="menu">更多</Button>
          </Dropdown>
        </div>
      ),
    },
  ], [writable, goToRental, openSync]);

  const pending = problems.data;
  const retryable = pending && pending.equipment.length + pending.transfers.length > 0;
  return (
    <div className="equipment-sheet">
      <Segmented value={tab} options={options(tabs)} onChange={value => {
        setTab(value as keyof typeof tabs);
        setSelected([]);
        setHistoryCode('');
      }} />
      <div data-page-chrome className="equipment-toolbar">
        <Input.Search
          allowClear
          aria-label="搜索设备"
          placeholder="编号、名称或规格"
          value={listTab ? keyword : historyCode || historyKeyword}
          onChange={event => {
            if (listTab) setKeyword(event.target.value);
            else {
              setHistoryCode('');
              setHistoryKeyword(event.target.value);
            }
          }}
        />
        {listTab && <>
          <Checkbox checked={only} onChange={event => setOnly(event.target.checked)}>
            仅看异常/待同步{issues.length ? ' (' + issues.length + ')' : ''}
          </Checkbox>
          <Button type="primary" disabled={!writable} onClick={() => setDialog({ kind: 'create', category })}>
            {category === 'equipment' ? '新增设备' : '新增周转材料'}
          </Button>
          <Button disabled={!writable || !selectedRows.length} onClick={() => setDialog({ kind: 'transfer', items: selectedRows })}>
            批量调拨{selectedRows.length ? ' (' + selectedRows.length + ')' : ''}
          </Button>
        </>}
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
        <Button disabled={action.busy} onClick={() => void action.run(() => exportEquipment('distribution'), false)}>
          导出分布 Excel
        </Button>
      </div>
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
            className="equipment-grid-slot"
            grid={{
              ...headerFilters,
              rowSelection: { mode: 'multiRow', enableClickSelection: false, selectAll: 'filtered' },
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
            rowId={rowId} domLayout="normal" className="equipment-grid-slot" grid={headerFilters} />
        )}
      </>}
      {tab === 'scraps' && <>
        <LoadState query={scraps} />
        {scraps.data && (
          <ReadGrid table="equipment-scraps" label="报废记录" rows={scrapRows} columns={scrapColumns}
            rowId={rowId} domLayout="normal" className="equipment-grid-slot" grid={headerFilters} />
        )}
      </>}
      {dialog && (
        <EquipmentDialog key={dialog.kind} state={dialog} close={() => setDialog(null)}
          done={msg => { setReceipt(msg); setDialog(null); }} />
      )}
    </div>
  );
}

function matchesHistory(row: TransferRow | ScrapRow, keyword: string) {
  const term = keyword.trim().toLowerCase();
  return !term || [row.code, row.name, row.spec].some(value => value?.toLowerCase().includes(term));
}
