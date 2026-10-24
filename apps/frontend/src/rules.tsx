import Button from 'antd/es/button';
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { ApiError, record, requestJson } from './api';
import type { Identity } from './api';
import { body } from './notices-api';
import { BusinessModal } from './business-modal';
import { DialogContents, useDialogClose } from './dialog-close';
import './rules.css';

const NO_RECOMPUTE = '规则用于后续首次抓入的新单据；已有单据的剔除状态保持不变，再次抓取也不重算。';
const plain = (value: string) => value.replace(/\*\*/g, '').replace(/（§[^）]*）/g, '').replace(/，§[\d.]+/g, '').replace(/\s*[—-]+\s*§[\d.]+(\s*\/\s*§[\d.]+)*/g, '');
const splitValues = (raw: string) => raw.split(/[｜|]/).map(part => part.trim()).filter(Boolean);

function readMessage(value: unknown, fallback: string): string {
  return record(value) && typeof value.message === 'string' && value.message ? plain(value.message) : fallback;
}

export interface RuleRow { id: number; kind: string; kindLabel: string; values: string; meaning: string }
export interface RuleKind { kind: string; label: string }
export interface RulesData { sourceLabel: string; rules: RuleRow[]; kinds: RuleKind[] }
export function readRules(value: unknown): RulesData {
  if (!record(value) || !Array.isArray(value.rules) || !Array.isArray(value.kinds) || typeof value.source_label !== 'string') throw new ApiError('剔除规则读取不完整，请重试；仍失败请联系维护人员。');
  const rules = value.rules.map((row: unknown) => {
    if (!record(row) || typeof row.id !== 'number' || !Number.isInteger(row.id) || typeof row.kind !== 'string' || typeof row.kind_label !== 'string' || typeof row.values !== 'string' || typeof row.meaning !== 'string') throw new ApiError('剔除规则读取不完整，请重试；仍失败请联系维护人员。');
    return { id: row.id, kind: row.kind, kindLabel: row.kind_label, values: row.values, meaning: row.meaning };
  });
  const kinds = value.kinds.map((row: unknown) => {
    if (!record(row) || typeof row.kind !== 'string' || typeof row.label !== 'string') throw new ApiError('规则类别读取不完整，请重试；仍失败请联系维护人员。');
    return { kind: row.kind, label: row.label };
  });
  return { sourceLabel: value.source_label, rules, kinds };
}

export interface JcIgnoreRow { id: number; nameFull: string; reason: string; operator: string; active: boolean; createdAt: string }
export function readJcIgnore(value: unknown): JcIgnoreRow[] {
  if (!record(value) || !Array.isArray(value.items)) throw new ApiError('集采项目剔除名单读取不完整，请重试；仍失败请联系维护人员。');
  return value.items.map((row: unknown) => {
    if (!record(row) || typeof row.id !== 'number' || !Number.isInteger(row.id) || typeof row.name_full !== 'string' || typeof row.reason !== 'string' || typeof row.operator !== 'string' || typeof row.active !== 'boolean' || typeof row.created_at !== 'string') throw new ApiError('集采项目剔除名单读取不完整，请重试；仍失败请联系维护人员。');
    return { id: row.id, nameFull: row.name_full, reason: row.reason, operator: row.operator, active: row.active, createdAt: row.created_at };
  });
}

export interface MechRuleRow { warehouse: string; display: string; aliases: string[] }
export function readMechRules(value: unknown): MechRuleRow[] {
  if (!record(value) || !Array.isArray(value.items)) throw new ApiError('机械报表项目匹配读取不完整，请重试；仍失败请联系维护人员。');
  return value.items.map((row: unknown) => {
    if (!record(row) || typeof row.warehouse !== 'string' || typeof row.display !== 'string' || !Array.isArray(row.aliases) || !row.aliases.every((alias: unknown) => typeof alias === 'string')) throw new ApiError('机械报表项目匹配读取不完整，请重试；仍失败请联系维护人员。');
    return { warehouse: row.warehouse, display: row.display, aliases: row.aliases as string[] };
  });
}

function ReadFailed({ message, retry }: { message: string; retry: () => void }) {
  return <div className="notice" role="alert"><span>{message}</span><Button htmlType="submit" onClick={retry}>重读</Button></div>;
}

function Feedback({ receipt, error }: { receipt: string; error: string }) {
  if (error) return <p className="notice" role="alert">{error}</p>;
  if (receipt) return <p className="rules-receipt" role="status">{receipt}</p>;
  return null;
}

export function RulesPage({ me, blocked, active }: { me: Identity | null; blocked: boolean; active: boolean }) {
  const enabled = active && !blocked;
  const writable = enabled && Boolean(me);
  return <section className="rules-page" aria-label="规则配置">
    <ExclusionRules enabled={enabled} writable={writable} blocked={blocked} />
    <JcIgnore enabled={enabled} writable={writable} />
    <MechMatch enabled={enabled} writable={writable} />
  </section>;
}

function ExclusionRules({ enabled, writable, blocked }: { enabled: boolean; writable: boolean; blocked: boolean }) {
  const query = useQuery({ queryKey: ['rules', 'exclusions'], enabled, queryFn: async ({ signal }) => readRules(await requestJson('/api/m14/rules', { signal })) });
  const [form, setForm] = useState<{ id: number | null; kind: string; values: string; meaning: string } | null>(null);
  const [formError, setFormError] = useState('');
  const [busy, setBusy] = useState(false);
  const [deleting, setDeleting] = useState<RuleRow | null>(null);
  const [deleteBusy, setDeleteBusy] = useState(false);
  const [receipt, setReceipt] = useState('');
  const [error, setError] = useState('');
  const data = query.data;
  const original = form && form.id !== null ? data?.rules.find(rule => rule.id === form.id) ?? null : null;
  const empty = data?.kinds[0]?.kind ?? '';
  const dirty = Boolean(form) && (original ? original.kind !== form!.kind || original.values !== form!.values || original.meaning !== form!.meaning : form!.kind !== empty || form!.values !== '' || form!.meaning !== '');
  const closing = useDialogClose({ busy, dirty, close: () => setForm(null) });
  const deleteClosing = useDialogClose({ busy: deleteBusy, dirty: false, close: () => setDeleting(null) });
  async function save() {
    if (!form || busy) return;
    if (!form.values.trim()) { setFormError('命中值不能为空，请填写后保存。'); return; }
    setBusy(true); setFormError('');
    try {
      const result = await requestJson(form.id === null ? '/api/m14/rules' : `/api/m14/rules/${form.id}`,
        { method: form.id === null ? 'POST' : 'PUT', ...body({ kind: form.kind, values: form.values.trim(), meaning: form.meaning.trim() }) });
      setForm(null); setError(''); setReceipt(readMessage(result, '已保存。'));
      await query.refetch();
    } catch (failure) {
      setFormError(failure instanceof Error ? failure.message : '没能保存，请核对后重试。');
    } finally { setBusy(false); }
  }
  async function remove() {
    if (!deleting || deleteBusy) return;
    setDeleteBusy(true);
    try {
      const result = await requestJson(`/api/m14/rules/${deleting.id}`, { method: 'DELETE' });
      setDeleting(null); setError(''); setReceipt(readMessage(result, '已删除。'));
    } catch (failure) {
      setDeleting(null); setReceipt(''); setError(failure instanceof Error ? failure.message : '没能删除，请重试。');
    } finally {
      setDeleteBusy(false);
      await query.refetch();
    }
  }
  return <div className="rules-block">
    <div className="rules-head"><h2>剔除规则{data && <span className="rules-count">（{data.rules.length} 条）</span>}</h2>
      <div className="rules-head-tools">{data && <span className="muted">来源：{data.sourceLabel}</span>}
        <Button htmlType="submit" className="primary" disabled={!writable || !data || data.kinds.length === 0}
          onClick={() => { setForm({ id: null, kind: data!.kinds[0]!.kind, values: '', meaning: '' }); setFormError(''); }}>＋ 增加规则</Button></div></div>
    {query.isError && !data && <ReadFailed message={query.error instanceof Error ? query.error.message : '剔除规则读取失败，请重试。'} retry={() => void query.refetch()} />}
    {query.isError && data && <ReadFailed message={`规则更新失败，保留上次结果。${query.error instanceof Error ? query.error.message : ''}`} retry={() => void query.refetch()} />}
    {query.isPending ? <p role="status">正在读取剔除规则…</p> : data && <>
      <Feedback receipt={receipt} error={error} />
      <div className="table-scroll rules-table" role="region" aria-label="剔除规则列表" tabIndex={0}><table>
        <thead><tr><th>规则类别</th><th>命中值（多个用 ｜ 分隔）</th><th>剔除的业务含义</th><th>操作</th></tr></thead>
        <tbody>{data.rules.map(rule => <tr key={rule.id}>
          <td className="rules-kind">{rule.kindLabel}</td>
          <td><div className="rules-values">{splitValues(rule.values).map(value => <span key={value}>{value}</span>)}</div></td>
          <td className="rules-meaning">{rule.meaning || '—'}</td>
          <td className="rules-actions">
            <Button htmlType="submit" disabled={!writable || busy || deleteBusy} onClick={() => { setForm({ id: rule.id, kind: rule.kind, values: rule.values, meaning: rule.meaning }); setFormError(''); }}>编辑</Button>
            <Button htmlType="submit" className="danger" disabled={!writable || busy || deleteBusy} onClick={() => setDeleting(rule)}>删除</Button>
          </td>
        </tr>)}</tbody>
      </table></div>
      <p className="rules-note muted">{NO_RECOMPUTE}</p>
      <p className="rules-warning">剔除规则中不得配置「收款单位 = 资产处集中采购」：集采不走剔除，而是参与分类。</p>
    </>}
    {form && <BusinessModal open={!blocked} className="rules-dialog" titleId="rules-form-title" requestClose={closing.requestClose}><DialogContents title={form.id === null ? '新增剔除规则' : `编辑剔除规则 · ${data?.rules.find(rule => rule.id === form.id)?.kindLabel ?? ''}`} titleId="rules-form-title" closing={closing}>
      <p className="rules-note muted">修改只影响后续抓取，已有剔除标记不重算。</p>
      <label>规则类别 ＊<select value={form.kind} disabled={busy} onChange={event => setForm({ ...form, kind: event.target.value })}>{(data?.kinds ?? []).map(kind => <option key={kind.kind} value={kind.kind}>{kind.label}</option>)}</select></label>
      <label>命中值 ＊（多个用 ｜ 分隔）<input value={form.values} disabled={busy} placeholder="例：水电｜水费｜电费" onChange={event => setForm({ ...form, values: event.target.value })} /></label>
      <label>剔除的业务含义<input value={form.meaning} disabled={busy} placeholder="例：期间费用，非材料/机械" onChange={event => setForm({ ...form, meaning: event.target.value })} /></label>
      {formError && <p className="notice" role="alert">{formError}</p>}
      <div className="dialog-actions"><Button htmlType="submit" disabled={busy} onClick={closing.requestClose}>取消</Button>
        <Button htmlType="submit" className="primary" disabled={busy} onClick={() => void save()}>{busy ? '正在保存…' : form.id === null ? '新增' : '保存修改'}</Button></div>
    </DialogContents></BusinessModal>}
    {deleting && <BusinessModal open={!blocked} className="rules-dialog" titleId="rules-delete-title" requestClose={deleteClosing.requestClose}><DialogContents title="删除剔除规则" titleId="rules-delete-title" closing={deleteClosing}>
      <p>确定删除「{deleting.kindLabel}」这条规则？命中值：{splitValues(deleting.values).join('、')}。</p>
      <p className="rules-warning">配置类数据为硬删、不留痕，删除后无法找回。{NO_RECOMPUTE}</p>
      <div className="dialog-actions"><Button htmlType="submit" disabled={deleteBusy} onClick={deleteClosing.requestClose}>取消</Button>
        <Button htmlType="submit" className="danger" disabled={deleteBusy} onClick={() => void remove()}>{deleteBusy ? '正在删除…' : '删除'}</Button></div>
    </DialogContents></BusinessModal>}
  </div>;
}

function JcIgnore({ enabled, writable }: { enabled: boolean; writable: boolean }) {
  const query = useQuery({ queryKey: ['rules', 'jc-ignore'], enabled, queryFn: async ({ signal }) => readJcIgnore(await requestJson('/api/m14/jc-ignore', { signal })) });
  const [name, setName] = useState('');
  const [reason, setReason] = useState('');
  const [busy, setBusy] = useState(false);
  const [receipt, setReceipt] = useState('');
  const [error, setError] = useState('');
  const rows = query.data;
  async function add() {
    if (busy) return;
    if (!name.trim()) { setReceipt(''); setError('项目全名不能为空，请粘贴项目全名（与档案里那个名字一致）。'); return; }
    setBusy(true); setError('');
    try {
      const result = await requestJson('/api/m14/jc-ignore', { method: 'POST', ...body({ name_full: name.trim(), reason: reason.trim() }) });
      setReceipt(readMessage(result, '已加入剔除名单。')); setError(''); setName(''); setReason('');
      await query.refetch();
    } catch (failure) {
      setReceipt(''); setError(failure instanceof Error ? failure.message : '没能加入，请核对后重试。');
    } finally { setBusy(false); }
  }
  async function setActive(row: JcIgnoreRow, active: boolean) {
    if (busy) return;
    setBusy(true); setError('');
    try {
      const result = await requestJson(`/api/m14/jc-ignore/${row.id}`, { method: 'PUT', ...body({ active }) });
      setReceipt(readMessage(result, '已更新。')); setError('');
    } catch (failure) {
      setReceipt(''); setError(failure instanceof Error ? failure.message : '没能修改，请重试。');
    } finally {
      setBusy(false);
      await query.refetch();
    }
  }
  return <div className="rules-block">
    <div className="rules-head"><h2>集采项目剔除名单{rows && <span className="rules-count">（{rows.filter(row => row.active).length} 项在用）</span>}</h2></div>
    {query.isError && !rows && <ReadFailed message={query.error instanceof Error ? query.error.message : '集采项目剔除名单读取失败，请重试。'} retry={() => void query.refetch()} />}
    {query.isError && rows && <ReadFailed message={`名单更新失败，保留上次结果。${query.error instanceof Error ? query.error.message : ''}`} retry={() => void query.refetch()} />}
    {query.isPending ? <p role="status">正在读取集采项目剔除名单…</p> : rows && <>
      <Feedback receipt={receipt} error={error} />
      {rows.length === 0 ? <p className="state">集采项目剔除名单为空；需要排除项目时，在下方加入项目全名。</p> : <div className="table-scroll rules-table" role="region" aria-label="集采项目剔除名单" tabIndex={0}><table>
        <thead><tr><th>项目全名</th><th>加入理由</th><th>操作人</th><th>加入时间</th><th>状态</th><th>操作</th></tr></thead>
        <tbody>{rows.map(row => <tr key={row.id} className={row.active ? '' : 'rules-inactive'}>
          <td>{row.nameFull}</td>
          <td className="rules-meaning">{row.reason || '—'}</td>
          <td className="rules-nowrap">{row.operator || '—'}</td>
          <td className="rules-nowrap">{row.createdAt || '—'}</td>
          <td className="rules-nowrap">{row.active ? <span className="status-tag status-neutral">在用</span> : '已停用'}</td>
          <td className="rules-actions">{row.active
            ? <Button htmlType="submit" className="danger" disabled={!writable || busy} onClick={() => void setActive(row, false)}>停用</Button>
            : <Button htmlType="submit" disabled={!writable || busy} onClick={() => void setActive(row, true)}>恢复</Button>}</td>
        </tr>)}</tbody>
      </table></div>}
      <div className="rules-form">
        <label>加入一项（粘贴项目全名）<input aria-label="项目全名" value={name} placeholder="例：某某项目安装工程" disabled={!writable || busy} onChange={event => setName(event.target.value)} /></label>
        <label>理由（可选）<input aria-label="加入理由" value={reason} placeholder="例：老项目，款已付清" disabled={!writable || busy} onChange={event => setReason(event.target.value)} /></label>
        <Button htmlType="submit" className="primary" disabled={!writable || busy} onClick={() => void add()}>加入剔除名单</Button>
      </div>
      <p className="rules-note muted">加入后：该项目从下次抓取起不再写入，也不再进「未写入」清单。停用只是不再参与过滤，记录留在册、可随时恢复。</p>
    </>}
  </div>;
}

function MechMatch({ enabled, writable }: { enabled: boolean; writable: boolean }) {
  const query = useQuery({ queryKey: ['rules', 'mech-match'], enabled, queryFn: async ({ signal }) => readMechRules(await requestJson('/api/m14/mech-match', { signal })) });
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [busyRow, setBusyRow] = useState('');
  const [receipt, setReceipt] = useState('');
  const [errors, setErrors] = useState<Record<string, string>>({});
  const rows = query.data;
  const text = (row: MechRuleRow) => drafts[row.warehouse] ?? row.aliases.join(' ｜ ');
  async function save(row: MechRuleRow) {
    if (busyRow) return;
    setBusyRow(row.warehouse);
    try {
      const result = await requestJson('/api/m14/mech-match', { method: 'PUT', ...body({ warehouse: row.warehouse, aliases: splitValues(text(row)) }) });
      setReceipt(readMessage(result, '已保存。')); setErrors(old => ({ ...old, [row.warehouse]: '' }));
      await query.refetch();
      setDrafts(old => { const next = { ...old }; delete next[row.warehouse]; return next; });
    } catch (failure) {
      setReceipt(''); setErrors(old => ({ ...old, [row.warehouse]: failure instanceof Error ? failure.message : '没能保存，请核对后重试。' }));
    } finally { setBusyRow(''); }
  }
  return <div className="rules-block">
    <div className="rules-head"><h2>机械报表项目匹配{rows && <span className="rules-count">（{rows.length} 项）</span>}</h2></div>
    {query.isError && !rows && <ReadFailed message={query.error instanceof Error ? query.error.message : '机械报表项目匹配读取失败，请重试。'} retry={() => void query.refetch()} />}
    {query.isError && rows && <ReadFailed message={`匹配规则更新失败，保留上次结果。${query.error instanceof Error ? query.error.message : ''}`} retry={() => void query.refetch()} />}
    {query.isPending ? <p role="status">正在读取机械报表项目匹配…</p> : rows && <>
      <Feedback receipt={receipt} error="" />
      {rows.length === 0 ? <p className="state">还没有机械报表项目匹配规则。</p> : <div className="table-scroll rules-table" role="region" aria-label="机械报表项目匹配" tabIndex={0}><table>
        <thead><tr><th>项目</th><th>报表项目名（多个用 ｜ 分隔）</th><th>操作</th></tr></thead>
        <tbody>{rows.map(row => <tr key={row.warehouse}>
          <td>{row.display}</td>
          <td><input className="rules-alias-input" aria-label={`${row.display}的报表项目名`} value={text(row)} disabled={!writable || busyRow !== ''} onChange={event => setDrafts(old => ({ ...old, [row.warehouse]: event.target.value }))} /></td>
          <td className="rules-actions">
            <Button htmlType="submit" disabled={!writable || busyRow !== ''} onClick={() => void save(row)}>保存</Button>
            {errors[row.warehouse] && <p className="notice" role="alert">{errors[row.warehouse]}</p>}
          </td>
        </tr>)}</tbody>
      </table></div>}
      <p className="rules-note muted">机械报表按这里的项目名对应到档案项目；两个项目用同一个名字会让报表混写，保存时后端会拒绝。</p>
    </>}
  </div>;
}
