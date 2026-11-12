import Button from 'antd/es/button';
import { useRef, useState } from 'react';
import { queryOptions, useQuery, useQueryClient } from '@tanstack/react-query';
import type { QueryClient } from '@tanstack/react-query';
import { Link } from 'react-router';
import { ApiError, body, confirmWrite, record, requestJson, uncertainWrite } from './api';
import { BusinessModal } from './business-modal';
import { DialogContents, useDialogClose } from './dialog-close';
import { SESSION_MODE_BROWSER, sessionPayload } from './i8-browser-relay';
import { useI8Session } from './i8-session';

export type OwnershipDocument = {
  number: string;
  name: string;
  project: string;
} & ({ source: 'notice'; noticeId?: number } | { source: 'contract'; runId: number });

type NoticePending = { bill_no: string; doc_name: string; project_name: string; reason: string };
type WarehouseCheck = { name: string; found: boolean; degraded: boolean; owners: string[]; from_cache: boolean; cached_at: string; message: string };
const projectId = (value: unknown): value is number => typeof value === 'number' && Number.isSafeInteger(value) && value > 0;
const clean = (value: string) => value.replace(/<[^>]*>/g, '').replace(/\*\*/g, '');

function pendingOptions<T>(queryKey: readonly unknown[], path: string, isItem: (item: unknown) => item is T) {
  return queryOptions({ queryKey, queryFn: async ({ signal }): Promise<T[]> => {
    const response = await requestJson(path, { signal });
    if (!record(response) || !Array.isArray(response.items) || !response.items.every(isItem)) {
      throw new ApiError('归属待办读取不完整，请重读。');
    }
    return response.items;
  } });
}
const noticePending = pendingOptions(['notice-ownership-pending'], '/api/m03/notices/unresolved',
  (item): item is NoticePending => record(item) && typeof item.bill_no === 'string' &&
    typeof item.doc_name === 'string' && typeof item.project_name === 'string' && typeof item.reason === 'string');
const contractPending = (runId: number) => pendingOptions(['contract-ownership-pending', runId], `/api/m11/unsettled?run_id=${runId}`,
  (item): item is Record<string, unknown> => record(item) && typeof item.contract_no === 'string' &&
    typeof item.doc_name === 'string' && typeof item.project_name === 'string' && typeof item.kind === 'string');

export function useContractOwnershipPending(runId: number, enabled: boolean) {
  const client = useQueryClient();
  const options = contractPending(runId);
  const read = useQuery({ ...options, enabled: enabled && runId > 0 });
  return {
    read,
    omit: (matches: (item: Record<string, unknown>) => boolean) =>
      client.setQueryData(options.queryKey, rows => rows?.filter(item => !matches(item))),
  };
}

export async function refreshNoticeOwnershipPending(client: QueryClient) {
  await client.cancelQueries({ queryKey: noticePending.queryKey, exact: true });
  return client.fetchQuery({ ...noticePending, staleTime: 0 });
}

export function OwnershipPending({ blocked, disabled, open }: {
  blocked: boolean; disabled: boolean; open: (document: OwnershipDocument) => void;
}) {
  const query = useQuery({ ...noticePending, enabled: !blocked, refetchOnMount: 'always' });
  if (query.isError) return <p className="notice" role="alert">{query.error.message}<Button onClick={() => void query.refetch()}>重读归属待办</Button></p>;
  return query.data?.length ? <details className="notice-ownership" open>
    <summary>待指定归属，{query.data.length} 条（本次未写入）</summary>
    {query.data.map((row, i) => <p key={`${row.bill_no}:${i}`}>{row.bill_no}，{row.project_name}，{row.doc_name}，{row.reason}
      <Button disabled={disabled} onClick={() => open({ source: 'notice', number: row.bill_no, name: row.doc_name, project: row.project_name })}>指定归属</Button>
    </p>)}
  </details> : null;
}

export function OwnershipProjectLink({ document, showNumber = false }: { document: OwnershipDocument; showNumber?: boolean }) {
  const search = new URLSearchParams({ ownership: document.source, bill: document.number });
  if (document.source === 'notice' && projectId(document.noticeId)) search.set('notice', String(document.noticeId));
  return <Link to={{ pathname: '/projects', search: `?${search}` }}>到项目档案核对{showNumber && document.number ? ` ${document.number}` : ''}</Link>;
}

export function OwnershipReturn({ params }: { params: URLSearchParams }) {
  const bill = params.get('bill');
  const source = params.get('ownership');
  if (source !== 'contract' && source !== 'notice' && !bill) return null;
  if (source === 'contract') return <p><Link to="/contracts">返回集采台账{bill ? `核对合同 ${bill}` : ''}</Link></p>;
  const noticeId = Number(params.get('notice'));
  return <p><Link to={projectId(noticeId) ? `/notices?notice=${noticeId}` : '/notices'}>返回通知书{bill ? ` ${bill}` : ''}继续核对</Link></p>;
}

function candidate(item: unknown): item is { id: number; display: string; archived: boolean } {
  return record(item) && projectId(item.id) && typeof item.display === 'string' && typeof item.archived === 'boolean';
}

async function readCandidates(document: OwnershipDocument, signal: AbortSignal) {
  const response = await requestJson('/api/m01/ownership', {
    method: 'POST', signal, ...body({ name_full: document.project, doc_name: document.name }),
  });
  if (!record(response) || typeof response.reason !== 'string' ||
    (response.shell_id !== null && !projectId(response.shell_id)) ||
    !Array.isArray(response.candidates) || !response.candidates.every(candidate)) {
    throw new ApiError('归属候选读取不完整，请重读。');
  }
  return { reason: response.reason, shellId: response.shell_id, candidates: response.candidates };
}

export function OwnershipDialog({ document, blocked, close, refresh, announce }: {
  document: OwnershipDocument; blocked: boolean; close: () => void;
  refresh: () => Promise<unknown>; announce: (message: string) => void;
}) {
  const client = useQueryClient();
  const lock = useRef(false);
  const session = useI8Session();
  const [value, setValue] = useState(''), [keyword, setKeyword] = useState('');
  const [newName, setNewName] = useState(''), [forceWarehouse, setForceWarehouse] = useState(false);
  const [warehouse, setWarehouse] = useState<WarehouseCheck | null>(null);
  const [busy, setBusy] = useState(false), [error, setError] = useState('');
  const [readback, setReadback] = useState<'saved' | 'unknown' | null>(null);
  const query = useQuery({
    queryKey: ['ownership-candidates', document.project, document.name],
    enabled: !blocked, refetchOnMount: 'always',
    queryFn: ({ signal }) => readCandidates(document, signal),
  });
  const closing = useDialogClose({
    busy: busy || readback !== null, dirty: Boolean(value || newName || keyword), close, active: !blocked,
  });
  const disabled = blocked || busy || readback !== null;
  const browserBlocked = session.mode === SESSION_MODE_BROWSER && !session.connected;
  const name = newName.trim();
  const word = keyword.trim();
  const keywordMatches = Boolean(word) && document.name.includes(word);
  const data = query.data;
  const warehouseReady = warehouse?.name === name && (warehouse.found && !warehouse.degraded || forceWarehouse);
  const target = value === 'new'
    ? data?.shellId && name && warehouseReady ? { shell_id: data.shellId, new_small_name: name } : null
    : data?.candidates.some(item => String(item.id) === value) ? { small_id: Number(value) } : null;
  const canSave = !disabled && !query.isFetching && !query.isError && keywordMatches && target !== null;

  async function checkWarehouse() {
    if (disabled || browserBlocked || !name || lock.current) return;
    lock.current = true; setBusy(true); setError('');
    try {
      // Follow the account's fetch mode, including refusal when browser mode is disconnected.
      const payload = sessionPayload(session, { allow_kick: true }, { warehouse_name: name });
      const r = await requestJson('/api/m03/notices/warehouse-check', { method: 'POST', ...body(payload) });
      if (!record(r) || typeof r.found !== 'boolean' || typeof r.degraded !== 'boolean' ||
        typeof r.message !== 'string' || typeof r.from_cache !== 'boolean' || typeof r.cached_at !== 'string' ||
        !Array.isArray(r.owners) || !r.owners.every(owner => typeof owner === 'string')) {
        throw new ApiError('仓库名单回执不完整，请重新查询。');
      }
      setWarehouse({ name, found: r.found, degraded: r.degraded, owners: r.owners,
        from_cache: r.from_cache, cached_at: r.cached_at, message: clean(r.message) });
      setForceWarehouse(false);
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : '查询失败，请重试。');
    } finally { setBusy(false); lock.current = false; }
  }

  async function refreshSource() {
    await refresh();
    if (document.source === 'notice') {
      await refreshNoticeOwnershipPending(client);
    } else {
      const options = contractPending(document.runId);
      await client.cancelQueries({ queryKey: options.queryKey, exact: true });
      await client.fetchQuery({ ...options, staleTime: 0 });
    }
  }

  async function submit() {
    if (!canSave || !target || lock.current) return;
    lock.current = true; setBusy(true); setError('');
    let saved = false;
    try {
      const response = await requestJson('/api/m03/notices/ownership-assign', {
        method: 'POST', ...body({ doc_name: document.name, keyword: word, ...target }),
      });
      saved = record(response) && response.ok === true;
      const message = record(response) && typeof response.message === 'string' ? clean(response.message) : null;
      confirmWrite(saved && message !== null, '归属保存回执不完整。');
      await refreshSource();
      announce(message!); close();
    } catch (failure) {
      const detail = failure instanceof Error ? failure.message : '操作未完成。';
      const state = saved ? 'saved' : uncertainWrite(failure) ? 'unknown' : null;
      setReadback(state);
      setError(state === 'saved' ? `档案已保存，但重读失败。请重读核对。${detail}`
        : state === 'unknown' ? `档案保存结果待核实，请重读后核对。${detail}` : clean(detail));
    } finally { setBusy(false); lock.current = false; }
  }

  async function reread() {
    if (blocked || lock.current) return;
    lock.current = true; setBusy(true); setError('');
    try {
      await refreshSource();
      announce(readback === 'saved' ? '档案已保存，已重读待指定归属。请重新抓取。'
        : '已重读待指定归属，请核对档案和待办后再操作。');
      close();
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : '重读失败，请重试。');
    } finally { setBusy(false); lock.current = false; }
  }

  const titleId = 'ownership-dialog-title';
  return <BusinessModal open={!blocked} className="project-dialog notice-dialog" titleId={titleId} requestClose={closing.requestClose}>
    <DialogContents title="指定项目归属" titleId={titleId} closing={closing}>
      <form onSubmit={event => { event.preventDefault(); void submit(); }}>
        <p>{document.number}，{document.name}，{document.project}</p>
        {query.isPending && <p role="status">正在读取…</p>}
        {query.isError && <p className="notice" role="alert">{query.error.message}<Button disabled={disabled} onClick={() => void query.refetch()}>重读候选</Button></p>}
        {data && <>
          <p>{data.reason && `${data.reason}。`}关键词须出现在单据名称里；补完档案后须重新抓取，不改本条既有关系。</p>
          <label>归属小微<select value={value} disabled={disabled} onChange={event => setValue(event.target.value)}>
            <option value="">请选择</option>
            {data.candidates.map(item => <option key={item.id} value={item.id}>{item.display}{item.archived ? '（归档）' : ''}</option>)}
            {data.shellId && <option value="new">新建具体小微</option>}
          </select></label>
          {value === 'new' && <>
            <label>新小微仓库名<input value={newName} disabled={disabled} onChange={event => {
              setNewName(event.target.value); setWarehouse(null); setForceWarehouse(false);
            }} /></label>
            <p>{session.mode === SESSION_MODE_BROWSER
              ? '本次只查名单，不建档：查询由你浏览器里已登录的 i8 标签发出，不登录、不顶号；连接不在时会直接停下。'
              : '查询可能重新登录 i8，并使该账号其他会话下线；此次只查名单，不建档。'}</p>
            {browserBlocked && <p className="notice" role="alert">当前选的是「浏览器已有会话」，但浏览器连接不在。请到「i8 接入」页重新连接，或把取数方式切回「工作台直连」。<strong>本次不会改用登录方式。</strong></p>}
            <Button disabled={disabled || browserBlocked || !name} onClick={() => void checkWarehouse()}>查询 i8 仓库名单</Button>
            {warehouse && <div>
              <p>{warehouse.degraded ? '未取到名单，不等于名单里没有。' : warehouse.found
                ? `名单中有该仓库，所属项目：${warehouse.owners.join('、')}` : '名单中没有该仓库；将来同步可能重复建档。'}</p>
              {warehouse.from_cache && <p>使用上次名单：{warehouse.cached_at || '时间未知'}</p>}
              {warehouse.found && !warehouse.owners.includes(document.project) && <p className="danger">该仓库所属项目与本条壳全名不一致，请核对。</p>}
              <p>{warehouse.message}</p>
              {(!warehouse.found || warehouse.degraded) && <label className="notice-choice"><input type="checkbox" disabled={disabled} checked={forceWarehouse} onChange={event => setForceWarehouse(event.target.checked)} />已了解上述结果，仍按此名建档</label>}
            </div>}
          </>}
          <label>关键词<input value={keyword} disabled={disabled} onChange={event => setKeyword(event.target.value)} /></label>
          {word && !keywordMatches && <p className="danger">关键词必须出现在单据名称里。</p>}
        </>}
        {!disabled && <OwnershipProjectLink document={document} showNumber />}
        {error && <p className="notice" role="alert">{error}</p>}
        <div className="dialog-actions">
          {readback ? <Button className="primary" disabled={busy || blocked} onClick={() => void reread()}>重读核对</Button>
            : <><Button disabled={busy} onClick={closing.requestClose}>取消</Button>
              <Button htmlType="submit" className="primary" disabled={!canSave}>确认补充档案</Button></>}
        </div>
      </form>
    </DialogContents>
  </BusinessModal>;
}
