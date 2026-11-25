import { useState } from 'react';
import { ReadGrid } from './business-grid';
import Button from 'antd/es/button';
import Form from 'antd/es/form';
import Input from 'antd/es/input';
import InputNumber from 'antd/es/input-number';
import Select from 'antd/es/select';
import Checkbox from 'antd/es/checkbox';
import dayjs from 'dayjs';
import Decimal from 'decimal.js';
import { ApiError, uncertainWrite } from './api';
import type { Project } from './api';
import { ProjectPicker } from './ledger-controls';
import { equipmentApi as api } from './equipment-api';
import type { Create, EquipmentItem, EquipmentLocation, EquipmentPatch, ItemCategory, LocationValues, TransferRow } from './equipment-api';
import {
  DateField,
  decimalField,
  formatNum,
  flagLabels,
  issue,
  LedgerModal,
  LoadState,
  options,
  scopeLabels,
  statusLabels,
  SyncTag,
  syncReceipt,
  useAccess,
  useLedgerAction,
  useLedgerQuery,
} from './equipment-ui';

export type DialogState =
  | { kind: 'create'; category: ItemCategory }
  | { kind: 'transfer'; items: EquipmentItem[] }
  | { kind: 'edit' | 'scrap'; item: EquipmentItem }
  | { kind: 'delete-transfer'; transfer: TransferRow }
  | { kind: 'locations' }
  | { kind: 'sync'; id: number };
type Props = {
  state: DialogState;
  close: () => void;
  done: (receipt: string) => void;
};
const required = [{ required: true, message: '请填写此项' }];
const today = () => dayjs().format('YYYY-MM-DD');

type ProjectValue = { id: number | null; custom: string | null };
const emptyProject: ProjectValue = { id: null, custom: null };
const hasProject = (value?: ProjectValue) => value?.id != null || !!value?.custom?.trim();
const projectRequired = {
  validator: (_rule: unknown, value?: ProjectValue) =>
    hasProject(value) ? Promise.resolve() : Promise.reject(new Error('请选择系统项目或地点')),
};

function SystemProjectField({
  label, value, onChange, projects, disabled,
}: {
  label: string;
  value?: number | null;
  onChange?: (value: number | null) => void;
  projects: Project[];
  disabled: boolean;
}) {
  return <ProjectPicker projects={projects} selected={value == null ? [] : [value]}
    label={label} emptyLabel="选择系统项目" allowClear disabled={disabled}
    pick={ids => onChange?.(ids[0] ?? null)} />;
}

function ProjectDualField({
  id, label, value = emptyProject, onChange, busy,
}: {
  id?: string;
  label: string;
  value?: ProjectValue;
  onChange?: (value: ProjectValue) => void;
  busy: boolean;
}) {
  const projects = useLedgerQuery(['project-options'], api.projectOptions);
  const locations = useLedgerQuery(['locations', false], () => api.locations());
  const available = locations.data?.items ?? [];
  const choices = available.map(location => ({ value: location.name, label: location.name, disabled: false }));
  if (value.custom && !available.some(location => location.name === value.custom)) {
    choices.push({ value: value.custom, label: value.custom, disabled: true });
  }
  return (
    <>
      <div className="equipment-project-field">
        <SystemProjectField label={label + '系统项目'} value={value.id}
          projects={projects.data?.items ?? []} disabled={busy || projects.isPending}
          onChange={projectId => onChange?.({ ...value, id: projectId })} />
        <Select
          {...(id ? { id } : {})}
          aria-label={label + '地点'}
          value={value.custom || undefined}
          options={choices}
          allowClear
          showSearch={{ optionFilterProp: 'label' }}
          loading={locations.isPending}
          disabled={busy || locations.isPending}
          placeholder="选择地点"
          popupMatchSelectWidth={false}
          onChange={custom => {
            const location = available.find(option => option.name === custom);
            onChange?.({ id: value.id ?? location?.default_project_id ?? null, custom: custom ?? null });
          }}
        />
      </div>
      {projects.error && <LoadState query={projects} />}
      {locations.error && <LoadState query={locations} />}
    </>
  );
}

function LocationDialog({ close }: { close: () => void }) {
  const locations = useLedgerQuery(['locations', true], () => api.locations(true));
  const projects = useLedgerQuery(['project-options'], api.projectOptions);
  const action = useLedgerAction();
  const { writable } = useAccess();
  const [edit, setEdit] = useState<{ location: EquipmentLocation | null } | null>(null);
  const [dirty, setDirty] = useState(false);
  const disabled = !writable || action.busy;
  const stopEditing = () => { setEdit(null); setDirty(false); };
  return (
    <LedgerModal title="地点维护" compact busy={action.busy} dirty={dirty} close={close}>
      {edit ? (
        <Form<LocationValues> layout="vertical" disabled={disabled}
          initialValues={edit.location ?? { name: '', default_project_id: null, is_active: true }}
          onValuesChange={() => setDirty(true)}
          onFinish={values => void action.run(async () => {
            if (edit.location) await api.updateLocation(edit.location.id, values);
            else await api.createLocation(values);
            stopEditing();
          })}>
          <Form.Item name="name" label="地点名称" rules={[{ required: true, whitespace: true, message: '请输入地点名称' }]}>
            <Input autoFocus />
          </Form.Item>
          {edit.location && <p className="equipment-location-note">改名会同步更新已有设备、调拨和租赁记录。</p>}
          <Form.Item name="default_project_id" label="默认系统项目">
            <SystemProjectField label="默认系统项目" projects={projects.data?.items ?? []}
              disabled={disabled || projects.isPending} />
          </Form.Item>
          {projects.error && <LoadState query={projects} />}
          <Form.Item name="is_active" valuePropName="checked">
            <Checkbox>启用地点</Checkbox>
          </Form.Item>
          <div className="dialog-actions">
            <Button disabled={action.busy} onClick={stopEditing}>取消</Button>
            <Button type="primary" htmlType="submit" loading={action.busy}
              disabled={disabled || !dirty}>保存地点</Button>
          </div>
        </Form>
      ) : (
        <>
          <LoadState query={locations} />
          {locations.data && (
            <>
              <div className="equipment-location-toolbar">
                <Button size="small" type="primary" disabled={disabled} onClick={() => setEdit({ location: null })}>
                  新增地点
                </Button>
              </div>
              {locations.data.items.length ? (
                <ul className="equipment-location-list">
                  {locations.data.items.map(location => (
                    <li key={location.id}>
                      <div>
                        <strong>{location.name}</strong>
                        <span>{[location.default_project_disp, !location.is_active && '已停用'].filter(Boolean).join(' · ')}</span>
                      </div>
                      <Button size="small" disabled={disabled} aria-label={'编辑地点 ' + location.name}
                        onClick={() => setEdit({ location })}>编辑</Button>
                    </li>
                  ))}
                </ul>
              ) : <p>暂无地点。</p>}
            </>
          )}
        </>
      )}
      {action.error && <p role="alert">{action.error}</p>}
    </LedgerModal>
  );
}

type EquipmentFormValues = Omit<Create, 'expected_codes' | 'item_category'> & {
  purchase: ProjectValue;
};

function EquipmentForm({ state, close, done }: Props) {
  const item = state.kind === 'edit' ? state.item : null,
    category = state.kind === 'create' ? state.category : item!.item_category;
  const [form] = Form.useForm<EquipmentFormValues>();
  const initial = {
    name: item?.name,
    spec: item?.spec,
    unit: item ? item.unit : '台',
    quantity: '1',
    purchase_date: item ? item.purchase_date : today(),
    purchase: item ? {
      id: item.purchase_project_id,
      custom: item.purchase_project_custom ?? (item.purchase_project_id === null ? item.purchase_project : null),
    } : emptyProject,
    purchase_price: item?.purchase_price,
    asset_scope: item?.asset_scope ?? 'current_asset',
    in_rental: item?.in_rental ?? 'yes',
    status: item?.status ?? 'in_use',
    remark: item?.remark,
  };
  const [dirty, setDirty] = useState(false),
    action = useLedgerAction(),
    { writable } = useAccess();
  const name = Form.useWatch('name', form),
    date = Form.useWatch('purchase_date', form),
    qty = Form.useWatch('quantity', form);
  const preview = { name: name?.trim(), purchase_date: date, quantity: String(qty), item_category: category };
  const validPreview = !item && !!preview.name && !!date && Number(qty) > 0;
  const codes = useLedgerQuery(['codes', preview], () => api.preview(preview), validPreview);
  const [unknownCodes, setUnknownCodes] = useState<string[] | null>(null);
  async function save({ purchase, ...values }: EquipmentFormValues) {
    if (!writable) return;
    if (item) {
      const changes: EquipmentPatch = {};
      for (const [k, v] of Object.entries(values))
        if (v !== initial[k as keyof typeof initial]) Object.assign(changes, { [k]: v ?? null });
      if (purchase.id !== initial.purchase.id || purchase.custom?.trim() !== initial.purchase.custom?.trim()) {
        changes.purchase_project_id = purchase.id;
        changes.purchase_project_custom = purchase.custom?.trim() || null;
      }
      if (Object.keys(changes).length) await api.update(item.id, changes);
      done('设备资料已保存。');
    } else if (validPreview && codes.data && !unknownCodes) {
      try {
        const result = await api.create({
          ...values,
          purchase_project_id: purchase.id,
          purchase_project_custom: purchase.custom?.trim() || null,
          item_category: category,
          expected_codes: codes.data.codes,
        });
        done(
          '分布新增 ' +
            result.equipment.length +
            ' 条：' +
            result.codes.join('、') +
            '。盘点账面' +
            (result.inventory_item ? '已生成' : '未生成') +
            '；租赁带入待定 ' +
            result.rental_line_ids.length +
            ' 条；i8 ' +
            syncReceipt(result.i8_sync) +
            '。'
        );
      } catch (e) {
        if (e instanceof ApiError && e.status === 409 && e.detail === 'expected_codes') {
          await codes.refetch();
        } else if (uncertainWrite(e)) {
          setUnknownCodes(codes.data.codes);
          throw new Error(
            '未收到完整的新增回执。请关闭窗口，刷新分布台账并按本批编号核对是否已创建，再决定是否重新新增。'
          );
        }
        throw e;
      }
    }
  }
  return (
    <LedgerModal
      title={item ? '编辑设备资料' : category === 'equipment' ? '新增设备' : '新增周转材料'}
      busy={action.busy}
      dirty={dirty}
      close={close}
    >
      <Form
        layout="vertical"
        form={form}
        initialValues={initial}
        disabled={!writable || action.busy}
        onValuesChange={() => setDirty(true)}
        onFinish={(v) => void action.run(() => save(v))}
      >
        <div className="equipment-fields">
          <Form.Item name="name" label="名称" rules={required}>
            <Input />
          </Form.Item>
          <Form.Item name="spec" label="规格型号">
            <Input />
          </Form.Item>
          <Form.Item name="unit" label="单位">
            <Input />
          </Form.Item>
          {!item && (
            <Form.Item name="quantity" label="数量" rules={required}>
              <InputNumber
                stringMode
                {...decimalField}
                min={category === 'equipment' ? '1' : '0.0001'}
                precision={category === 'equipment' ? 0 : 4}
              />
            </Form.Item>
          )}
          <Form.Item name="purchase_date" label="购买日期" rules={item ? [] : required}>
            <DateField label="购买日期" />
          </Form.Item>
          <Form.Item className="equipment-project-form-item" name="purchase" label="购买项目" rules={[projectRequired]}>
            <ProjectDualField label="购买项目" busy={!writable || action.busy} />
          </Form.Item>
          <Form.Item name="purchase_price" label="购买价格">
            <InputNumber stringMode {...decimalField} min="0" precision={4} />
          </Form.Item>
          <Form.Item name="asset_scope" label="资产归属">
            <Select options={options(scopeLabels)} />
          </Form.Item>
          <Form.Item name="in_rental" label="列租赁表">
            <Select options={options(flagLabels)} />
          </Form.Item>
          <Form.Item name="status" label="当前状态">
            <Select options={options(statusLabels).filter((x) => x.value !== 'scrapped')} />
          </Form.Item>
          <Form.Item name="remark" label="备注">
            <Input.TextArea />
          </Form.Item>
        </div>
        {validPreview && (
          <div aria-live="polite" className="equipment-preview">
            <strong>编号预览</strong>
            <LoadState query={codes} />
            {(unknownCodes ?? codes.data?.codes)?.join('、')}
          </div>
        )}
        {action.error && <p role="alert">{action.error}</p>}
        <div className="dialog-actions">
          <Button
            type="primary"
            htmlType="submit"
            loading={action.busy}
            disabled={
              !writable ||
              !!unknownCodes ||
              (item ? !dirty : !validPreview || !codes.data || codes.isFetching || codes.isError)
            }
          >
            保存
          </Button>
        </div>
      </Form>
    </LedgerModal>
  );
}

function MovementForm({ state, close, done }: Props) {
  const transfer = state.kind === 'transfer',
    items = transfer ? state.items : state.kind === 'scrap' ? [state.item] : [];
  const [dirty, setDirty] = useState(false),
    action = useLedgerAction(),
    { writable } = useAccess();
  async function save(values: { project: ProjectValue; date: string; note: string }) {
    if (!writable) return;
    const ids = items.map((x) => x.id);
    if (transfer) {
      const r = await api.transfer({
        equipment_ids: ids,
        expected_from_projects: Object.fromEntries(items.map((item) => [item.id, item.current_project])),
        to_project_id: values.project.id,
        to_project_custom: values.project.custom?.trim() || null,
        transfer_date: values.date,
        remark: values.note,
      });
      done(
        '分布更新 ' +
          r.equipment_ids.length +
          ' 条，已写入调拨记录 ' +
          r.transfers.length +
          ' 条。租赁归属待定 ' +
          r.rental_line_ids.length +
          ' 条；i8 ' +
          syncReceipt(r.i8_sync) +
          '。'
      );
    } else {
      const r = await api.scrap({ equipment_ids: ids, scrap_date: values.date, reason: values.note });
      done('已登记报废 ' + r.scraps.length + ' 条，待确认停租 ' + r.rental_line_ids.length + ' 条。');
    }
  }
  return (
    <LedgerModal
      title={transfer ? (items.length > 1 ? '批量调拨' : '设备调拨') : '登记报废'}
      busy={action.busy}
      dirty={dirty}
      close={close}
    >
      <div className="equipment-selection" tabIndex={0} role="region" aria-label="已选设备">
        <ReadGrid<EquipmentItem>
          table="equipment-movement"
          label={transfer ? '调出设备' : '报废设备'}
          rows={items}
          columns={[
            { field: 'code', headerName: '编号' },
            { field: 'name', headerName: '名称' },
            { field: 'spec', headerName: '规格型号' },
            { field: 'current_project', headerName: transfer ? '调出项目' : '所在项目' },
          ]}
          rowId={(row) => String(row.id)}
          domLayout="normal"
          style={{ height: Math.min(15, 4 + items.length * 2.4) + 'em' }}
        />
      </div>
      {!transfer && items[0] && <ScrapImpact item={items[0]} />}
      <Form
        layout="vertical"
        initialValues={{ date: today() }}
        disabled={!writable || action.busy}
        onValuesChange={() => setDirty(true)}
        onFinish={(v) => void action.run(() => save(v))}
      >
        {transfer && (
          <Form.Item name="project" label="调入项目" rules={[projectRequired]}>
            <ProjectDualField label="调入项目" busy={!writable || action.busy} />
          </Form.Item>
        )}
        <Form.Item name="date" label={transfer ? '调拨日期' : '报废日期'} rules={required}>
          <DateField label={transfer ? '调拨日期' : '报废日期'} />
        </Form.Item>
        <Form.Item name="note" label={transfer ? '调拨备注' : '报废原因'}>
          <Input.TextArea />
        </Form.Item>
        {action.error && <p role="alert">{action.error}</p>}
        <div className="dialog-actions">
          <Button type="primary" htmlType="submit" danger={!transfer} loading={action.busy}>
            {transfer ? '确认调拨' : '确认报废'}
          </Button>
        </div>
      </Form>
    </LedgerModal>
  );
}

function ScrapImpact({ item }: { item: EquipmentItem }) {
  if (!item.inventory_name || item.inventory_book_qty === null || item.inventory_count_qty === null) return null;
  const Amount = Decimal.clone({ precision: 40 });
  const bookLeft = new Amount(item.inventory_book_qty).minus(item.quantity);
  const countLeft = new Amount(item.inventory_count_qty).minus(item.quantity);
  const removed = bookLeft.isZero() && countLeft.lte(0);
  return (
    <p className="equipment-receipt">
      将同步从盘点表《{item.inventory_name}》扣减 {formatNum(item.quantity)} {item.unit ?? '台'}
      （{removed ? '扣完后该行将从盘点表移出' : '扣后账面剩 ' + formatNum(bookLeft.toFixed()) + ' ' + (item.unit ?? '台')}）。
    </p>
  );
}

function SyncDetails({ id, close }: { id: number; close: () => void }) {
  const query = useLedgerQuery(['detail', id], () => api.detail(id));
  const action = useLedgerAction();
  const { writable } = useAccess();
  const [receipt, setReceipt] = useState('');
  const detail = query.data;
  const transfers = detail?.transfers.filter(row => issue(row.i8_sync_status)) ?? [];
  return (
    <LedgerModal title="i8 同步与来源" compact busy={action.busy} close={close}>
      <LoadState query={query} />
      {detail && <>
        <p><SyncTag status={detail.i8_sync.status} showNormal /></p>
        {issue(detail.i8_sync.status) && <>
          {detail.i8_sync.message && <p>{detail.i8_sync.message}</p>}
          {detail.i8_sync.snapshot_json && (
            <details><summary>i8 设备快照</summary><pre>{detail.i8_sync.snapshot_json}</pre></details>
          )}
          {transfers.map(row => row.i8_conflict_json && (
            <details key={row.id}>
              <summary>{row.transfer_date ?? '日期未登记'} 调拨冲突快照</summary>
              {row.i8_sync_message && <p>{row.i8_sync_message}</p>}
              <pre>{row.i8_conflict_json}</pre>
            </details>
          ))}
          <Button disabled={!writable || action.busy} onClick={() => void action.run(async () => {
            const result = await api.retry({
              equipment_ids: transfers.length ? [] : [id],
              transfer_ids: transfers.map(row => row.id),
            });
            setReceipt(syncReceipt([...result.equipment, ...result.transfers]));
          })}>补同步 i8</Button>
        </>}
        <details className="equipment-history-source">
          <summary>历史接续来源</summary>
          <dl>
            <dt>分布来源</dt><dd>{detail.equipment.source_info ?? '—'}</dd>
            <dt>盘点底稿行</dt><dd>{detail.equipment.inventory_source_row ?? '—'}</dd>
            <dt>租赁底稿行</dt><dd>{detail.equipment.rental_source_row ?? '—'}</dd>
          </dl>
        </details>
      </>}
      {receipt && <p role="status">{receipt}</p>}
      {action.error && <p role="alert">{action.error}</p>}
    </LedgerModal>
  );
}

function DeleteTransferDialog({ transfer, close, done }: { transfer: TransferRow } & Pick<Props, 'close' | 'done'>) {
  const { writable } = useAccess();
  const action = useLedgerAction();
  return (
    <LedgerModal compact title="删除调拨记录" busy={action.busy} close={close}>
      <p>{transfer.code} · {transfer.transfer_date ?? '日期未登记'} · {transfer.from_project} → {transfer.to_project}</p>
      <p>删除后，设备将回到上一次调入的项目；没有更早的调拨记录时，回到购买项目。系统会同时清理这笔调拨的草稿租赁归属。</p>
      {action.error && <p role="alert">{action.error}</p>}
      <div className="dialog-actions">
        <Button disabled={action.busy} onClick={close}>取消</Button>
        <Button type="primary" danger loading={action.busy} disabled={!writable} onClick={() => void action.run(async () => {
          const result = await api.deleteTransfer(transfer.id);
          done(`已删除调拨记录 #${result.deleted_transfer_id}，设备 ${transfer.code} 已回到 ${result.reverted_project}。`);
        })}>删除调拨记录</Button>
      </div>
    </LedgerModal>
  );
}

export function EquipmentDialog(props: Props) {
  const state = props.state;
  if (state.kind === 'locations') return <LocationDialog close={props.close} />;
  if (state.kind === 'sync') return <SyncDetails id={state.id} close={props.close} />;
  if (state.kind === 'delete-transfer') return <DeleteTransferDialog {...props} transfer={state.transfer} />;
  if (state.kind === 'edit' || state.kind === 'create') return <EquipmentForm {...props} />;
  return <MovementForm {...props} />;
}
