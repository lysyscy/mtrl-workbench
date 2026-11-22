import { useState } from 'react';
import { ReadGrid } from './business-grid';
import Button from 'antd/es/button';
import Form from 'antd/es/form';
import Input from 'antd/es/input';
import InputNumber from 'antd/es/input-number';
import Select from 'antd/es/select';
import dayjs from 'dayjs';
import { ApiError, uncertainWrite } from './api';
import { equipmentApi as api } from './equipment-api';
import type { Create, EquipmentItem, EquipmentPatch, ItemCategory } from './equipment-api';
import {
  DateField,
  flagLabels,
  issue,
  LedgerModal,
  LoadState,
  options,
  scopeLabels,
  statusLabels,
  syncLabels,
  syncReceipt,
  useAccess,
  useLedgerAction,
  useLedgerQuery,
} from './equipment-ui';

export type DialogState =
  | { kind: 'create'; category: ItemCategory }
  | { kind: 'transfer'; items: EquipmentItem[] }
  | { kind: 'detail' | 'edit' | 'scrap'; item: EquipmentItem };
type Props = {
  state: DialogState;
  close: () => void;
  change: (v: DialogState) => void;
  done: (receipt: string) => void;
};
const required = [{ required: true, message: '请填写此项' }];
const today = () => dayjs().format('YYYY-MM-DD');

function EquipmentForm({ state, close, done }: Props) {
  const item = state.kind === 'edit' ? state.item : null,
    category = state.kind === 'create' ? state.category : item!.item_category;
  const [form] = Form.useForm<Create>();
  const initial = {
    name: item?.name,
    spec: item?.spec,
    unit: item ? item.unit : '台',
    quantity: '1',
    purchase_date: item ? item.purchase_date : today(),
    purchase_project: item?.purchase_project,
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
  async function save(values: Create) {
    if (!writable) return;
    if (item) {
      const changes: EquipmentPatch = {};
      for (const [k, v] of Object.entries(values))
        if (v !== initial[k as keyof typeof initial]) Object.assign(changes, { [k]: v ?? null });
      await api.update(item.id, changes);
      done('设备资料已保存，i8 状态可在详情核对。');
    } else if (validPreview && codes.data && !unknownCodes) {
      try {
        const result = await api.create({
          ...values,
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
                min={category === 'equipment' ? '1' : '0.0001'}
                precision={category === 'equipment' ? 0 : 4}
              />
            </Form.Item>
          )}
          <Form.Item name="purchase_date" label="购买日期" rules={item ? [] : required}>
            <DateField label="购买日期" />
          </Form.Item>
          <Form.Item name="purchase_project" label="购买项目" rules={required}>
            <Input />
          </Form.Item>
          {!item && (
            <Form.Item name="current_project" label="当前所在项目">
              <Input placeholder="默认同购买项目" />
            </Form.Item>
          )}
          <Form.Item name="purchase_price" label="购买价格">
            <InputNumber stringMode min="0" precision={4} />
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
  async function save(values: { project: string; date: string; note: string }) {
    if (!writable) return;
    const ids = items.map((x) => x.id);
    if (transfer) {
      const r = await api.transfer({
        equipment_ids: ids,
        expected_from_projects: Object.fromEntries(items.map((item) => [item.id, item.current_project])),
        to_project: values.project,
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
      <Form
        layout="vertical"
        initialValues={{ date: today() }}
        disabled={!writable || action.busy}
        onValuesChange={() => setDirty(true)}
        onFinish={(v) => void action.run(() => save(v))}
      >
        {transfer && (
          <Form.Item
            name="project"
            label="调入项目"
            rules={[
              ...required,
              {
                validator: (_, v) =>
                  items.some((i) => i.current_project === v?.trim())
                    ? Promise.reject(new Error('调入项目与所选设备当前项目相同'))
                    : Promise.resolve(),
              },
            ]}
          >
            <Input />
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

function Detail({
  item,
  close,
  change,
}: {
  item: EquipmentItem;
  close: () => void;
  change: Props['change'];
}) {
  const [month, setMonth] = useState(dayjs().format('YYYY-MM')),
    data = useLedgerQuery(['detail', item.id, month], () => api.detail(item.id, month));
  const action = useLedgerAction(),
    { writable } = useAccess(),
    [receipt, setReceipt] = useState('');
  const d = data.data,
    i = d?.equipment,
    transfers = d?.transfers.filter((t) => issue(t.i8_sync_status)) ?? [];
  return (
    <LedgerModal title={'设备详情 · ' + item.code} busy={action.busy} close={close}>
      <LoadState query={data} />
      {d && i && (
        <>
          <h3>
            {i.name}　{i.spec}
          </h3>
          <p>
            {i.quantity} {i.unit} · {i.current_project} · {statusLabels[i.status]} ·{' '}
            {scopeLabels[i.asset_scope]}
          </p>
          <p>
            购买日期 {i.purchase_date ?? i.purchase_date_text ?? '未登记'}　购买项目 {i.purchase_project}
            　购买价格 {i.purchase_price ?? '未登记'}
          </p>
          {i.remark && <p>备注　{i.remark}</p>}
          <h3>调拨与报废记录</h3>
          {d.transfers.length ? (
            d.transfers.map((t) => (
              <p key={t.id}>
                {t.transfer_date}　{t.from_project} → {t.to_project}　{t.remark}　
                {syncLabels[t.i8_sync_status]} {t.i8_conflict_json}
              </p>
            ))
          ) : (
            <p>暂无调拨</p>
          )}
          {d.scrap && (
            <p>
              {d.scrap.scrap_date} 报废　{d.scrap.reason}
            </p>
          )}
          <h3>关联盘点与租赁</h3>
          <p>
            {d.inventory_item
              ? '盘点行 ' +
                d.inventory_item.id +
                ' · ' +
                d.inventory_item.name +
                '　帐面数 ' +
                d.inventory_item.book_qty +
                '　盘点数 ' +
                d.inventory_item.count_qty
              : '无关联盘点行'}
          </p>
          <DateField label="关联租赁月份" month value={month} onChange={(v) => v && setMonth(v)} />
          {d.rental_lines.length ? (
            d.rental_lines.map((l) => (
              <p key={l.id}>
                租赁行 {l.id} · {l.project_name}　{l.name}　金额 {l.amount ?? '—'}　底稿行{' '}
                {l.source_row ?? '—'}
              </p>
            ))
          ) : (
            <p>本月无关联租赁行</p>
          )}
          <h3>来源与 i8 同步</h3>
          <p>
            {i.source_info ?? '来源未登记'}　盘点底稿 {i.inventory_source_row ?? '—'}　租赁底稿{' '}
            {i.rental_source_row ?? '—'}
          </p>
          <p>
            {syncLabels[d.i8_sync.status]}　{d.i8_sync.message}
          </p>
          {d.i8_sync.snapshot_json && (
            <details>
              <summary>i8 记录快照</summary>
              <pre>{d.i8_sync.snapshot_json}</pre>
            </details>
          )}
          {(issue(i.i8_sync_status) || transfers.length > 0) && (
            <Button
              disabled={!writable || action.busy}
              onClick={() =>
                void action.run(async () => {
                  const r = await api.retry({
                    equipment_ids: transfers.length ? [] : [i.id],
                    transfer_ids: transfers.map((t) => t.id),
                  });
                  setReceipt(syncReceipt([...r.equipment, ...r.transfers]));
                })
              }
            >
              补同步 i8
            </Button>
          )}
          {receipt && <p role="status">{receipt}</p>}
          {action.error && <p role="alert">{action.error}</p>}
          {i.status !== 'scrapped' && (
            <div className="dialog-actions">
              <Button
                disabled={!writable || action.busy}
                danger
                onClick={() => change({ kind: 'scrap', item: i })}
              >
                登记报废
              </Button>
              <Button disabled={!writable || action.busy} onClick={() => change({ kind: 'edit', item: i })}>
                编辑资料
              </Button>
            </div>
          )}
        </>
      )}
    </LedgerModal>
  );
}
export function EquipmentDialog(props: Props) {
  const s = props.state;
  if (s.kind === 'detail') return <Detail item={s.item} close={props.close} change={props.change} />;
  if (s.kind === 'edit' || s.kind === 'create') return <EquipmentForm {...props} />;
  return <MovementForm {...props} />;
}
