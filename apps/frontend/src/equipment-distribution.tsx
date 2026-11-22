import { useState } from 'react';
import Button from 'antd/es/button';
import Checkbox from 'antd/es/checkbox';
import Input from 'antd/es/input';
import Select from 'antd/es/select';
import Segmented from 'antd/es/segmented';
import type { ColDef, ICellRendererParams } from 'ag-grid-community';
import { BusinessGrid, ReadGrid } from './business-grid';
import { equipmentApi as api, exportEquipment } from './equipment-api';
import type { EquipmentItem, ItemCategory, ScrapRow, TransferRow, Scope, RentalFlag } from './equipment-api';
import { EquipmentDialog } from './equipment-dialogs';
import type { DialogState } from './equipment-dialogs';
import {
  flagLabels,
  issue,
  LoadState,
  options,
  rowId,
  scopeLabels,
  statusLabels,
  syncReceipt,
  SyncTag,
  useAccess,
  useLedgerAction,
  useLedgerQuery,
} from './equipment-ui';

const tabs = { equipment: '工机具分布', transfers: '调拨记录', scraps: '报废记录', turnover: '周转材料' };
export function Distribution() {
  const [tab, setTab] = useState<keyof typeof tabs>('equipment'),
    [project, setProject] = useState(''),
    [keyword, setKeyword] = useState('');
  const [scope, setScope] = useState<Scope>(),
    [flag, setFlag] = useState<RentalFlag>(),
    [only, setOnly] = useState(false);
  const [historyCategory, setHistoryCategory] = useState<ItemCategory | ''>('');
  const [ids, setIds] = useState<number[]>([]),
    [dialog, setDialog] = useState<DialogState | null>(null),
    [receipt, setReceipt] = useState('');
  const { writable } = useAccess(),
    action = useLedgerAction();
  const listTab = tab === 'equipment' || tab === 'turnover',
    category = tab === 'turnover' ? 'turnover' : 'equipment';
  const list = useLedgerQuery(
    ['list', category],
    () => api.list({ item_category: category, include_scrapped: false }),
    listTab
  );
  const transfers = useLedgerQuery(
    ['transfers', project, keyword, historyCategory],
    () => api.transfers({ project, keyword, item_category: historyCategory || undefined }),
    tab === 'transfers'
  );
  const scraps = useLedgerQuery(
    ['scraps', project, keyword, historyCategory],
    () => api.scraps({ project, keyword, item_category: historyCategory || undefined }),
    tab === 'scraps'
  );
  const problems = useLedgerQuery(['sync-issues'], api.issues);
  const all = list.data?.items ?? [],
    filtered = all.filter(
      (i) =>
        (!project || i.current_project === project) &&
        (!scope || i.asset_scope === scope) &&
        (!flag || i.in_rental === flag) &&
        [i.code, i.name, i.spec, i.current_project].some((v) =>
          v?.toLowerCase().includes(keyword.trim().toLowerCase())
        )
    );
  const count = filtered.filter((i) => issue(i.i8_sync_status)).length,
    rows = filtered.filter((i) => !only || issue(i.i8_sync_status));
  const selected = rows.filter((i) => ids.includes(i.id));
  const historyDetail = (id: number) =>
    void action.run(async () => {
      setDialog({ kind: 'detail', item: (await api.detail(id)).equipment });
    }, false);
  const tCols: ColDef<TransferRow>[] = [
    {
      field: 'item_category',
      headerName: '类别',
      valueFormatter: ({ value }) => (value === 'turnover' ? '周转材料' : '工机具'),
    },
    { field: 'code', headerName: '编号' },
    { field: 'name', headerName: '名称' },
    { field: 'spec', headerName: '规格型号' },
    { field: 'from_project', headerName: '调出项目' },
    { field: 'to_project', headerName: '调入项目' },
    { field: 'transfer_date', headerName: '调拨日期' },
    { field: 'quantity', headerName: '数量' },
    { field: 'remark', headerName: '调拨备注' },
    {
      colId: 'sync',
      headerName: '同步状态',
      cellRenderer: ({ data }: ICellRendererParams<TransferRow>) =>
        data && <SyncTag status={data.i8_sync_status} />,
    },
    {
      colId: 'actions',
      headerName: '操作',
      cellRenderer: ({ data }: ICellRendererParams<TransferRow>) =>
        data && <Button onClick={() => historyDetail(data.equipment_id)}>详情</Button>,
    },
  ];
  const sCols: ColDef<ScrapRow>[] = [
    {
      field: 'item_category',
      headerName: '类别',
      valueFormatter: ({ value }) => (value === 'turnover' ? '周转材料' : '工机具'),
    },
    { field: 'code', headerName: '编号' },
    { field: 'name', headerName: '名称' },
    { field: 'spec', headerName: '规格型号' },
    { field: 'quantity', headerName: '数量' },
    { field: 'original_project', headerName: '原所在项目' },
    { field: 'scrap_date', headerName: '报废日期' },
    { field: 'reason', headerName: '报废原因' },
    {
      colId: 'actions',
      headerName: '操作',
      cellRenderer: ({ data }: ICellRendererParams<ScrapRow>) =>
        data && <Button onClick={() => historyDetail(data.equipment_id)}>详情</Button>,
    },
  ];
  const columns: ColDef<EquipmentItem>[] = [
    { field: 'code', headerName: '工机具编号', minWidth: 185 },
    { field: 'name', headerName: '名称' },
    { field: 'spec', headerName: '规格型号' },
    { field: 'unit', headerName: '单位' },
    { field: 'quantity', headerName: '数量' },
    {
      field: 'purchase_date',
      headerName: '购买日期',
      valueGetter: (p) => p.data?.purchase_date ?? p.data?.purchase_date_text,
    },
    { field: 'purchase_project', headerName: '购买项目' },
    { field: 'purchase_price', headerName: '购买价格' },
    { field: 'current_project', headerName: '当前所在项目' },
    { field: 'status', headerName: '当前状态', valueGetter: (p) => p.data && statusLabels[p.data.status] },
    {
      field: 'asset_scope',
      headerName: '资产归属',
      valueGetter: (p) => p.data && scopeLabels[p.data.asset_scope],
    },
    {
      field: 'in_rental',
      headerName: '列租赁表',
      valueGetter: (p) => p.data && flagLabels[p.data.in_rental],
    },
    {
      colId: 'sync',
      headerName: '同步/待办',
      cellRenderer: ({ data }: ICellRendererParams<EquipmentItem>) =>
        data && <SyncTag status={data.i8_sync_status} />,
    },
    { field: 'remark', headerName: '备注' },
    {
      colId: 'actions',
      headerName: '操作',
      minWidth: 145,
      cellRenderer: ({ data }: ICellRendererParams<EquipmentItem>) =>
        data && (
          <div className="equipment-actions">
            <Button
              size="small"
              disabled={!writable}
              onClick={() => setDialog({ kind: 'transfer', items: [data] })}
            >
              调拨
            </Button>
            <Button size="small" onClick={() => setDialog({ kind: 'detail', item: data })}>
              详情
            </Button>
          </div>
        ),
    },
  ];
  const pending = problems.data,
    retryable = pending && pending.equipment.length + pending.transfers.length > 0;
  return (
    <>
      <Segmented
        value={tab}
        options={options(tabs)}
        onChange={(v) => {
          setTab(v as keyof typeof tabs);
          setIds([]);
          setProject('');
        }}
      />
      <div data-page-chrome className="equipment-toolbar">
        {listTab ? (
          <Select
            aria-label="项目筛选"
            value={project}
            options={[
              { value: '', label: '全部项目' },
              ...Array.from(new Set(all.map((i) => i.current_project))).map((value) => ({
                value,
                label: value,
              })),
            ]}
            onChange={setProject}
          />
        ) : (
          <Input
            aria-label="项目筛选"
            placeholder="项目名称"
            value={project}
            onChange={(e) => setProject(e.target.value)}
          />
        )}
        {listTab && (
          <>
            <Select
              aria-label="资产归属"
              allowClear
              placeholder="全部资产归属"
              value={scope}
              options={options(scopeLabels)}
              onChange={setScope}
            />
            <Select
              aria-label="列租赁表"
              allowClear
              placeholder="列租赁表"
              value={flag}
              options={options(flagLabels)}
              onChange={setFlag}
            />
          </>
        )}
        {!listTab && (
          <Select
            aria-label="类别筛选"
            value={historyCategory}
            onChange={setHistoryCategory}
            options={options({ '': '全部', equipment: '工机具', turnover: '周转材料' })}
          />
        )}
        <Input.Search
          allowClear
          aria-label="搜索设备"
          placeholder="编号、名称或规格"
          value={keyword}
          onChange={(e) => setKeyword(e.target.value)}
        />
        {listTab && (
          <Checkbox checked={only} onChange={(e) => setOnly(e.target.checked)}>
            仅看异常/待同步{count ? ' (' + count + ')' : ''}
          </Checkbox>
        )}
        {listTab && (
          <>
            <Button
              type="primary"
              disabled={!writable}
              onClick={() => setDialog({ kind: 'create', category })}
            >
              {category === 'equipment' ? '新增设备' : '新增周转材料'}
            </Button>
            <Button
              disabled={!writable || !selected.length}
              onClick={() => setDialog({ kind: 'transfer', items: selected })}
            >
              批量调拨{selected.length ? ' (' + selected.length + ')' : ''}
            </Button>
          </>
        )}
        {retryable && (
          <Button
            disabled={!writable || action.busy}
            onClick={() =>
              void action.run(async () => {
                const linked = new Set(pending.transfers.map((t) => t.equipment_id));
                const r = await api.retry({
                  equipment_ids: pending.equipment.filter((i) => !linked.has(i.id)).map((i) => i.id),
                  transfer_ids: pending.transfers.map((t) => t.id),
                });
                setReceipt('i8 补同步结果：' + syncReceipt([...r.equipment, ...r.transfers]));
              })
            }
          >
            一键补同步 i8
          </Button>
        )}
        <Button
          disabled={action.busy}
          onClick={() => void action.run(() => exportEquipment('distribution'), false)}
        >
          导出分布 Excel
        </Button>
      </div>
      {receipt && (
        <div className="equipment-receipt" role="status">
          {receipt}{' '}
          <Button type="text" onClick={() => setReceipt('')}>
            收起
          </Button>
        </div>
      )}
      {action.error && <p role="alert">{action.error}</p>}
      {problems.error && <LoadState query={problems} />}
      {listTab && (
        <>
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
              style={{ height: '62vh' }}
              grid={{
                rowSelection: { mode: 'multiRow', enableClickSelection: false },
                onSelectionChanged: (e) => setIds(e.api.getSelectedRows().map((i) => i.id)),
              }}
            />
          )}
        </>
      )}
      {tab === 'transfers' && (
        <>
          <LoadState query={transfers} />
          {transfers.data && (
            <ReadGrid
              table="equipment-transfers"
              label="调拨记录"
              rows={transfers.data.items}
              columns={tCols}
              rowId={rowId}
              domLayout="normal"
              style={{ height: '62vh' }}
            />
          )}
        </>
      )}
      {tab === 'scraps' && (
        <>
          <LoadState query={scraps} />
          {scraps.data && (
            <ReadGrid
              table="equipment-scraps"
              label="报废记录"
              rows={scraps.data.items}
              columns={sCols}
              rowId={rowId}
              domLayout="normal"
              style={{ height: '62vh' }}
            />
          )}
        </>
      )}
      {dialog && (
        <EquipmentDialog
          key={dialog.kind}
          state={dialog}
          change={setDialog}
          close={() => setDialog(null)}
          done={(msg) => {
            setReceipt(msg);
            setDialog(null);
          }}
        />
      )}
    </>
  );
}
