import { DialogPresence } from './workspace-motion';
import Button from 'antd/es/button';
import { useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import type { UseQueryResult } from '@tanstack/react-query';
import { ApiError, confirmWrite, record, requestJson, uncertainWrite } from './api';
import type { Identity } from './api';
import { body } from './notices-api';
import { BusinessModal } from './business-modal';
import { ReadGrid } from './business-grid';
import { DialogContents, useDialogClose } from './dialog-close';
import { useHistoryGuard } from './history';
import { FirstReadRegion, ReadFailure, ReadPlaceholder, ReadStatusLane, readPhase } from './read-region';
import { countNewRuleMatches } from './rule-add-recovery';
import { JcRules } from './jc-rules';
import { jcCondition, jcRuleKinds, jcRulesPath, readJcRules } from './jc-rule-data';
import { PageActivity } from './page-activity';

const NO_RECOMPUTE = '规则用于后续首次抓入的新单据；已有单据的剔除状态保持不变，再次抓取也不重算。';
const plain = (value: string) => value.replace(/\*\*/g, '').replace(/（§[^）]*）/g, '').replace(/，§[\d.]+/g, '').replace(/\s*[—-]+\s*§[\d.]+(\s*\/\s*§[\d.]+)*/g, '');
const splitValues = (raw: string) => raw.split(/[｜|]/).map(part => part.trim()).filter(Boolean);

function readMessage(value: unknown, fallback: string): string {
  return record(value) && typeof value.message === 'string' && value.message
    ? plain(value.message).replace(`（${NO_RECOMPUTE}）`, '') : fallback;
}

export interface RuleRow { id: number; kind: string; kindLabel: string; values: string; meaning: string }
export interface RuleKind { kind: string; label: string }
export interface RulesData { sourceLabel: string; rules: RuleRow[]; kinds: RuleKind[] }
type RuleDraft = { id: number | null; kind: string; values: string; meaning: string };
type AdditionRecovery =
  | { state: 'unknown'; draft: RuleDraft; kindLabel: string; beforeIds: ReadonlySet<number>; matches: number | null; readFailed: boolean; reviewing: boolean }
  | { state: 'confirmed-read-failed' };

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

function Feedback({ receipt, error }: { receipt: string; error: string }) {
  if (error) return <p className="notice" role="alert">{error}</p>;
  if (receipt) return <p className="rules-receipt" role="status">{receipt}</p>;
  return null;
}

type RulePage = 'notice' | 'procurement';
type RuleLocation = { page: RulePage; id: number };
const ruleTabs: Record<RulePage, string> = { notice: '付款通知书', procurement: '集采台账' };
const headings: Record<RulePage, string> = { notice: '付款通知书抓取剔除', procurement: '集采合同抓取剔除' };

function revealRule({ page, id }: RuleLocation) {
  requestAnimationFrame(() => {
    document.getElementById(`rule-${page}-${id}`)?.scrollIntoView({ block: 'nearest', inline: 'nearest' });
  });
}

export function RulesPage({ me, blocked, active }: { me: Identity | null; blocked: boolean; active: boolean }) {
  const enabled = active && !blocked;
  const writable = enabled && Boolean(me);
  const [page, setPage] = useState<RulePage>('notice');
  const [search, setSearch] = useState('');
  const [searchOpen, setSearchOpen] = useState(false);
  const [location, setLocation] = useState<RuleLocation | null>(null);
  const keyword = search.trim().toLowerCase();
  const notice = useQuery({
    queryKey: ['rules', 'exclusions'], enabled: enabled && (page === 'notice' || searchOpen),
    queryFn: async ({ signal }) => readRules(await requestJson('/api/m14/rules', { signal })),
  });
  const procurement = useQuery({
    queryKey: ['rules', 'jc-ignore'], enabled: enabled && (page === 'procurement' || searchOpen),
    queryFn: async ({ signal }) => readJcRules(await requestJson(jcRulesPath, { signal })),
  });
  const matches = keyword ? [
    ...(notice.data?.rules ?? []).map(row => ({
      page: 'notice' as const, id: row.id, condition: `${row.kindLabel} · ${row.values}`, meaning: row.meaning,
    })),
    ...(procurement.data ?? []).map(row => ({
      page: 'procurement' as const, id: row.id,
      condition: `${jcRuleKinds[row.kind]} · ${jcCondition(row)}`, meaning: row.reason,
    })),
  ].filter(row => `${ruleTabs[row.page]} ${headings[row.page]} ${row.condition} ${row.meaning}`.toLowerCase().includes(keyword)) : [];
  const searchClose = useDialogClose({ busy: false, dirty: false, close: () => setSearchOpen(false) });

  function selectTab(next: RulePage) {
    setLocation(null);
    setPage(next);
  }

  function locate(next: RuleLocation) {
    setSearchOpen(false);
    setLocation(next);
    setPage(next.page);
    revealRule(next);
  }

  return <section className="rules-page" aria-label="规则配置" data-page-chrome>
    <div className="rules-navigation">
      <nav className="rules-tabs" aria-label="规则所属业务">
        {(Object.keys(ruleTabs) as RulePage[]).map(tab =>
          <Button key={tab} aria-current={page === tab ? 'page' : undefined} onClick={() => selectTab(tab)}>{ruleTabs[tab]}</Button>)}
      </nav>
      <form className="rules-search" onSubmit={event => { event.preventDefault(); if (keyword) setSearchOpen(true); }}>
        <input type="search" aria-label="搜索全部规则" placeholder="项目、合同编号或关键词" value={search} onChange={event => setSearch(event.target.value)} />
        <Button htmlType="submit" disabled={!enabled || !keyword}>搜索全部规则</Button>
      </form>
    </div>
    <div hidden={page !== 'notice'}>
      <PageActivity.Provider value={enabled && page === 'notice'}>
        <ExclusionRules query={notice} writable={writable && page === 'notice'} blocked={!enabled || page !== 'notice'}
          selected={location?.page === 'notice' ? location.id : null}
          onPublished={() => { if (location?.page === 'notice') revealRule(location); }} />
      </PageActivity.Provider>
    </div>
    <div hidden={page !== 'procurement'}>
      <PageActivity.Provider value={enabled && page === 'procurement'}>
        <JcRules query={procurement} writable={writable && page === 'procurement'} active={enabled && page === 'procurement'}
          selected={location?.page === 'procurement' ? location.id : null} clearSelection={() => setLocation(null)}
          onPublished={() => { if (location?.page === 'procurement') revealRule(location); }} />
      </PageActivity.Provider>
    </div>
    <DialogPresence>{searchOpen && <BusinessModal open={enabled} className="rules-dialog rules-search-dialog" titleId="rules-search-title" requestClose={searchClose.requestClose}>
      <DialogContents title="搜索全部规则" titleId="rules-search-title" closing={searchClose}>
        <input type="search" aria-label="搜索规则关键词" value={search} onChange={event => setSearch(event.target.value)} />
        {notice.isError && <ReadFailure read={notice} retained="付款通知书规则更新失败，保留上次结果。" />}
        {procurement.isError && <ReadFailure read={procurement} retained="集采台账规则更新失败，保留上次结果。" />}
        {(notice.isFetching || procurement.isFetching) && <p role="status">正在读取规则…</p>}
        {keyword && !notice.isFetching && !procurement.isFetching && !notice.isError && !procurement.isError && matches.length === 0 && <p className="state">没有匹配的规则</p>}
        {matches.length > 0 && <ul className="rules-search-results">{matches.map(row => <li key={`${row.page}-${row.id}`}>
          <button type="button" onClick={() => locate(row)}>
            <span className="muted">{ruleTabs[row.page]} › {headings[row.page]}</span>
            <strong>{row.condition}</strong>
            {row.meaning && <span>{row.meaning}</span>}
          </button>
        </li>)}</ul>}
      </DialogContents>
    </BusinessModal>}</DialogPresence>
  </section>;
}

function ExclusionRules({ query, writable, blocked, selected, onPublished }: {
  query: UseQueryResult<RulesData, Error>; writable: boolean; blocked: boolean;
  selected: number | null; onPublished: () => void;
}) {
  const [form, setForm] = useState<RuleDraft | null>(null);
  const [formError, setFormError] = useState('');
  const [busy, setBusy] = useState(false);
  const [deleting, setDeleting] = useState<RuleRow | null>(null);
  const [deleteBusy, setDeleteBusy] = useState(false);
  const [receipt, setReceipt] = useState('');
  const [error, setError] = useState('');
  const lock = useRef(false);
  const recoveryRef = useRef<AdditionRecovery | null>(null);
  const [addition, setAddition] = useState<AdditionRecovery | null>(null);
  function changeAddition(next: AdditionRecovery | null) {
    recoveryRef.current = next;
    setAddition(next);
  }
  const recovery = addition?.state === 'unknown' ? addition : null;
  const confirmedReadFailed = addition?.state === 'confirmed-read-failed';
  const draft = recovery?.reviewing ? recovery.draft : form;
  const data = query.data;
  const original = form && form.id !== null ? data?.rules.find(rule => rule.id === form.id) ?? null : null;
  const empty = data?.kinds[0]?.kind ?? '';
  const dirty = Boolean(form) && (original ? original.kind !== form!.kind || original.values !== form!.values || original.meaning !== form!.meaning : form!.kind !== empty || form!.values !== '' || form!.meaning !== '');
  const closing = useDialogClose({ busy, dirty, close: () => {
    if (lock.current) return;
    const current = recoveryRef.current;
    if (current?.state === 'unknown') changeAddition({ ...current, reviewing: false });
    else setForm(null);
  } });
  const deleteClosing = useDialogClose({ busy: deleteBusy, dirty: false, close: () => setDeleting(null) });
  useHistoryGuard('exclusion-rules', () => lock.current ? '剔除规则正在处理，请稍候。'
    : recoveryRef.current?.state === 'unknown' ? '剔除规则新增结果待核对，请返回规则配置处理。'
    : recoveryRef.current ? '剔除规则已新增，请返回规则配置重新读取。' : '');
  const readState = readPhase(query, data !== undefined && data.rules.length === 0);
  const placeheld = data === undefined;
  const writeDisabled = !writable || busy || deleteBusy || addition !== null;
  const canStartWrite = () => writable && !lock.current && recoveryRef.current === null;
  function openForm(next: RuleDraft) {
    if (!canStartWrite()) return;
    setForm(next);
    setFormError('');
  }
  async function readCurrentRules() {
    const result = await query.refetch({ throwOnError: true });
    if (!result.isSuccess) throw new ApiError('规则列表读取未完成。');
    return result.data;
  }
  async function save() {
    if (!form || !data || !canStartWrite()) return;
    if (!form.values.trim()) { setFormError('命中值不能为空，请填写后保存。'); return; }
    const snapshot = form;
    const adding = snapshot.id === null;
    const beforeIds = adding ? new Set(data.rules.map(rule => rule.id)) : null;
    const kindLabel = data.kinds.find(kind => kind.kind === snapshot.kind)?.label ?? snapshot.kind;
    lock.current = true;
    setBusy(true); setFormError(''); setError(''); setReceipt('');
    try {
      const result = await requestJson(adding ? '/api/m14/rules' : `/api/m14/rules/${snapshot.id}`,
        { method: adding ? 'POST' : 'PUT', ...body({ kind: snapshot.kind, values: snapshot.values.trim(), meaning: snapshot.meaning.trim() }) });
      confirmWrite(record(result) && result.ok === true, '规则保存回执不完整。');
      setForm(null); setReceipt(readMessage(result, adding ? '已新增剔除规则。' : '已保存。'));
      if (adding) {
        try { await readCurrentRules(); }
        catch { changeAddition({ state: 'confirmed-read-failed' }); }
      } else await query.refetch();
    } catch (failure) {
      if (beforeIds && uncertainWrite(failure)) {
        changeAddition({ state: 'unknown', draft: snapshot, kindLabel, beforeIds, matches: null, readFailed: false, reviewing: true });
        setForm(null);
      } else setFormError(failure instanceof Error ? plain(failure.message) : '没能保存，请核对后重试。');
    } finally {
      lock.current = false;
      setBusy(false);
    }
  }
  async function rereadAddition() {
    const current = recoveryRef.current;
    if (!writable || lock.current || !current) return;
    lock.current = true;
    setBusy(true);
    if (current.state === 'unknown') changeAddition({ ...current, matches: null, readFailed: false });
    try {
      const latest = await readCurrentRules();
      changeAddition(current.state === 'unknown'
        ? { ...current, matches: countNewRuleMatches(current.draft, current.beforeIds, latest.rules), readFailed: false }
        : null);
    } catch {
      if (current.state === 'unknown') changeAddition({ ...current, matches: null, readFailed: true });
    } finally {
      lock.current = false;
      setBusy(false);
    }
  }
  function finishAddition() {
    const current = recoveryRef.current;
    if (!writable || lock.current || current?.state !== 'unknown' || current.matches === null) return;
    changeAddition(null);
  }
  async function remove() {
    if (!deleting || !canStartWrite()) return;
    lock.current = true;
    setDeleteBusy(true);
    try {
      const result = await requestJson(`/api/m14/rules/${deleting.id}`, { method: 'DELETE' });
      setDeleting(null); setError(''); setReceipt(readMessage(result, '已删除。'));
    } catch (failure) {
      setDeleting(null); setReceipt(''); setError(failure instanceof Error ? failure.message : '没能删除，请重试。');
    } finally {
      await query.refetch();
      lock.current = false;
      setDeleteBusy(false);
    }
  }
  return <div className="rules-block">
    <div className="rules-head"><h2>{headings.notice}{data && <span className="rules-count">（{data.rules.length} 条）</span>}</h2>
      <div className="rules-head-tools">{data?.sourceLabel.startsWith('出厂默认') && <span className="muted">出厂默认</span>}
        <Button htmlType="button" className="primary" disabled={writeDisabled || !empty}
          onClick={() => openForm({ id: null, kind: empty, values: '', meaning: '' })}>＋ 增加规则</Button></div></div>
    <ReadStatusLane phase={readState} announce="正在读取剔除规则…" className="rules-read-status">
      {!addition && (readState === 'error' || readState === 'stale') && <ReadFailure read={query} retained="规则更新失败，保留上次结果。" />}
      {recovery && <p className="notice" role="alert"><span className="read-failure-text">新增结果待核对。请先处理本次新增，再更改规则。</span>
        <Button htmlType="button" disabled={!writable || busy} onClick={() => {
          const current = recoveryRef.current;
          if (!lock.current && current?.state === 'unknown') changeAddition({ ...current, reviewing: true });
        }}>核对新增结果</Button>
      </p>}
      {confirmedReadFailed && <p className="notice" role="alert"><span className="read-failure-text">已新增剔除规则。列表更新失败，保留上次结果。</span>
        <Button htmlType="button" disabled={!writable || busy} onClick={() => void rereadAddition()}>{busy ? '正在读取…' : '重新读取'}</Button>
      </p>}
    </ReadStatusLane>
    <FirstReadRegion phase={placeheld ? readState === 'error' ? 'error' : 'pending' : 'content'} onPublished={onPublished}
      placeholder={<div className="rules-table rules-read-reserve read-reserve" aria-hidden="true"><ReadPlaceholder rows={4} quiet={readState === 'error'} /></div>}>
    {data && <>
      <Feedback receipt={confirmedReadFailed ? '' : receipt} error={error} />
      <ReadGrid table="exclusion-rules" className="rules-table" label="剔除规则列表" domLayout="autoHeight" rows={data.rules} rowId={rule=>String(rule.id)} columns={[
        {field:'kindLabel',headerName:'规则类别',cellRenderer:({data:rule}:{data:RuleRow})=><div id={`rule-notice-${rule.id}`} className={selected === rule.id ? 'rules-located' : undefined}>
          {rule.kindLabel}<span className="rules-match-kind">{rule.kind === 'bill_name' ? '包含' : '精确'}</span>
        </div>},
        {field:'values',headerName:'命中值',cellRenderer:({data:rule}:{data:RuleRow})=><div className="rules-values">{splitValues(rule.values).map(value=><span key={value}>{value}</span>)}</div>},
        {field:'meaning',headerName:'剔除的业务含义',valueFormatter:p=>p.value||'—'},
        {colId:'actions',headerName:'操作',minWidth:140,cellRenderer:({data:rule}:{data:RuleRow})=><div className="rules-actions"><Button disabled={writeDisabled} onClick={()=>openForm(rule)}>编辑</Button><Button danger disabled={writeDisabled} onClick={()=>{if(canStartWrite())setDeleting(rule);}}>删除</Button></div>},
      ]}/>
    </>}</FirstReadRegion>
    <DialogPresence>{draft && <BusinessModal open={!blocked} className="rules-dialog" titleId="rules-form-title" requestClose={closing.requestClose}><DialogContents title={recovery ? '核对剔除规则新增结果' : draft.id === null ? '新增剔除规则' : `编辑剔除规则，${original?.kindLabel ?? ''}`} titleId="rules-form-title" closing={closing}>
      {recovery && <p className="rules-warning" role="alert">提交结果待核对。请重新读取列表核对本次提交的内容。</p>}
      <label>规则类别 ＊<select value={draft.kind} disabled={busy || Boolean(recovery)} onChange={event => { if (form && !lock.current) setForm({ ...form, kind: event.target.value }); }}>{recovery ? <option value={draft.kind}>{recovery.kindLabel}</option> : (data?.kinds ?? []).map(kind => <option key={kind.kind} value={kind.kind}>{kind.label}</option>)}</select></label>
      <label>命中值 ＊（多个用 ｜ 分隔）<input value={draft.values} readOnly={Boolean(recovery)} disabled={busy} placeholder="例：水电｜水费｜电费" onChange={event => { if (form && !lock.current) setForm({ ...form, values: event.target.value }); }} /></label>
      <label>剔除的业务含义<input value={draft.meaning} readOnly={Boolean(recovery)} disabled={busy} placeholder="例：期间费用，非材料/机械" onChange={event => { if (form && !lock.current) setForm({ ...form, meaning: event.target.value }); }} /></label>
      {recovery ? <>
        {recovery.readFailed && <p className="notice" role="alert">列表读取失败，新增结果仍待核对。请重新读取。</p>}
        {recovery.matches !== null && <p role="status">{recovery.matches === 0 ? '这次读取未见同内容的新规则，原提交仍可能稍后写入。' : `这次读取发现 ${recovery.matches} 条此前未见的同内容规则，无法确认是否来自本次提交。`}</p>}
        <div className="dialog-actions">
          <Button htmlType="button" disabled={busy} onClick={closing.requestClose}>先返回列表</Button>
          <Button htmlType="button" className={recovery.matches === null ? 'primary' : ''} disabled={!writable || busy} onClick={() => void rereadAddition()}>{busy ? '正在读取…' : '重新读取'}</Button>
          {recovery.matches !== null && <Button htmlType="button" className="primary" disabled={!writable || busy} onClick={finishAddition}>结束本次新增，不再提交</Button>}
        </div>
      </> : <>
        {formError && <p className="notice" role="alert">{formError}</p>}
        <div className="dialog-actions"><Button htmlType="button" disabled={busy} onClick={closing.requestClose}>取消</Button>
          <Button htmlType="button" className="primary" disabled={!writable || busy} onClick={() => void save()}>{busy ? '正在保存…' : draft.id === null ? '新增' : '保存修改'}</Button></div>
      </>}
    </DialogContents></BusinessModal>}</DialogPresence>
    <DialogPresence>{deleting && <BusinessModal open={!blocked} className="rules-dialog" titleId="rules-delete-title" requestClose={deleteClosing.requestClose}><DialogContents title="删除剔除规则" titleId="rules-delete-title" closing={deleteClosing}>
      <p>确定删除「{deleting.kindLabel}」这条规则？命中值：{splitValues(deleting.values).join('、')}。</p>
      <p className="rules-warning">{data?.rules.length === 1 ? '删除最后一条规则后，抓取将使用出厂默认规则。' : NO_RECOMPUTE}</p>
      <div className="dialog-actions"><Button htmlType="submit" disabled={deleteBusy} onClick={deleteClosing.requestClose}>取消</Button>
        <Button htmlType="submit" className="danger" disabled={deleteBusy} onClick={() => void remove()}>{deleteBusy ? '正在删除…' : '删除'}</Button></div>
    </DialogContents></BusinessModal>}</DialogPresence>
  </div>;
}
