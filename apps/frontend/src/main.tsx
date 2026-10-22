import { lazy, StrictMode, Suspense, useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter, NavLink, Navigate, Route, Routes, useLocation } from 'react-router';
import { QueryClient, QueryClientProvider, useQuery } from '@tanstack/react-query';
import { readIdentity, readProjects, requestJson } from './api';
import type { Identity } from './api';
const MechanicalPage = lazy(() => import('./mechanical').then(module => ({ default: module.MechanicalPage })));
const LedgerPage = lazy(() => import('./ledger').then(module => ({ default: module.LedgerPage })));
import { I8ExecutionProvider } from './i8-execution';
const I8Page = lazy(() => import('./i8').then(module => ({ default: module.I8Page })));
import './style.css';

const loginUrl = '/login?next=%2Fpreview%2Fprojects';

function Notice({ message, retry }: { message: string; retry?: () => void }) {
  return <div className="notice" role="alert"><span>{message}</span>{retry && <button onClick={retry}>重试</button>}</div>;
}

function Projects({ blocked }: { blocked: boolean }) {
  const [status, setStatus] = useState('active');
  const [keyword, setKeyword] = useState('');
  const [search, setSearch] = useState('');
  const [composing, setComposing] = useState(false);
  useEffect(() => {
    if (blocked || composing) return;
    const timer = window.setTimeout(() => setSearch(keyword.trim()), 250);
    return () => window.clearTimeout(timer);
  }, [keyword, composing, blocked]);
  const query = useQuery({
    queryKey: ['projects', status, search],
    enabled: !blocked,
    queryFn: async ({ signal }) => readProjects(await requestJson(`/api/m01/projects?${new URLSearchParams({ status, keyword: search })}`, { signal })),
  });
  return <section aria-labelledby="projects-title">
    <div className="card-head"><h1 id="projects-title">项目档案</h1></div>
    <form className="filters" onSubmit={event => event.preventDefault()}>
      <div className="filter-field"><label htmlFor="project-status">状态</label><select id="project-status" value={status} onChange={event => setStatus(event.target.value)}><option value="active">在建</option><option value="archived">归档</option><option value="all">全部</option></select></div>
      <label className="search">项目<input type="search" value={keyword} onChange={event => setKeyword(event.target.value)} onCompositionStart={() => setComposing(true)} onCompositionEnd={event => { setKeyword(event.currentTarget.value); setComposing(false); }} placeholder="全名、仓库名或展示名" /></label>
    </form>
    {query.isPending ? <p role="status" className="state">正在读取项目…</p> : query.isError ? <Notice message={query.error.message} retry={() => void query.refetch()} /> : query.data.length === 0 ? <p role="status" className="state">没有符合条件的项目。可调整状态或关键词。</p> : <>
      <p className="result" role="status">共 {query.data.length} 个项目{query.isFetching ? ' · 正在刷新…' : ''}</p>
      <div className="table-scroll" tabIndex={0} role="region" aria-label="项目列表"><table><thead><tr><th>序号</th><th>项目类型</th><th>展示名</th><th>仓库名</th><th>项目全名</th><th>信息化编号</th><th>状态</th></tr></thead><tbody>{query.data.map(project => <tr key={project.id}>
        <td>{project.ord}</td><td><span className={`project-type project-type-${project.project_type}`}>{{ normal: '普通项目', shell: '小微壳', small: '具体小微' }[project.project_type]}</span></td><td>{project.disp || '—'}</td><td>{project.warehouse_name ?? '—'}</td><td>{project.name_full}</td><td>{project.phid || '—'}</td><td>{project.status === 'active' ? '在建' : '归档'}</td>
      </tr>)}</tbody></table></div>
    </>}
  </section>;
}

function AccountWorkspace({ me, blocked, onLogout }: { me: Identity | null; blocked: boolean; onLogout: () => void }) {
  // A new account gets a new cache and component tree, including future page drafts/history.
  const [client] = useState(() => new QueryClient({ defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false }, mutations: { retry: false } } }));
  const [logoutError, setLogoutError] = useState('');
  const [ledgerExportGuard, setLedgerExportGuard] = useState('');
  const [ledgerProject, setLedgerProject] = useState(0);
  const ledgerActive = useLocation().pathname === '/ledger';
  const [ledgerVisited, setLedgerVisited] = useState(ledgerActive);
  useEffect(() => { if (ledgerActive) setLedgerVisited(true); }, [ledgerActive]);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    document.documentElement.style.setProperty('--fscale', me?.ui_scale_css ?? '1');
    const theme = document.querySelector<HTMLLinkElement>('#user-theme');
    if (theme) theme.href = `/static/theme.css?identity=${encodeURIComponent(me?.account ?? '')}`;
  }, [me?.account, me?.ui_scale_css]);
  useEffect(() => () => { void client.cancelQueries(); client.clear(); }, [client]);
  useEffect(() => { if (blocked) void client.cancelQueries(); }, [blocked, client]);
  async function logout() {
    setBusy(true); setLogoutError('');
    try {
      await requestJson('/api/m15/logout', { method: 'POST' });
      await client.cancelQueries(); client.clear(); onLogout();
      window.location.assign(loginUrl);
    } catch (error) { setLogoutError(error instanceof Error ? error.message : '退出失败，请重试。'); setBusy(false); }
  }
  return <QueryClientProvider client={client}><div className="workspace" hidden={blocked} inert={blocked}>
    <a className="skip" href="#content">跳到内容</a>
    <aside className="sidebar"><div className="brand">材料工作台</div><p className="preview-label">独立预览</p><nav aria-label="主导航"><NavLink to="/projects">MOD-01 项目档案</NavLink><NavLink to="/i8">MOD-02 i8 接入层</NavLink><NavLink to="/ledger" title="当前预览提供逐月台账，综合页面其余区域尚未接入">MOD-05 付款流水与欠款统计</NavLink><NavLink to="/mechanical">MOD-10 机械费</NavLink></nav><a className="old-app" href="/app">打开旧版预览</a></aside>
    <div className="main"><header><div id="ledger-status" /><div className="account-area"><div id="history-controls" /><span>{me ? `${me.name || me.account} · ${me.role === 'admin' ? '管理员' : '普通用户'}` : '未登录 · 只读'}</span>{me ? <button onClick={() => void logout()} disabled={busy}>{busy ? '正在退出…' : '切换账号'}</button> : <a href={loginUrl}>登录</a>}</div></header>
      <main id="content" tabIndex={-1}><I8ExecutionProvider me={me} blocked={blocked}>{logoutError && <Notice message={logoutError} />}<Routes><Route path="/projects" element={<Projects blocked={blocked} />} /><Route path="/i8" element={<Suspense fallback={<p role="status">正在读取 i8 接入层…</p>}><I8Page me={me} blocked={blocked} /></Suspense>} /><Route path="/ledger" element={null} /><Route path="/mechanical" element={<Suspense fallback={<p role="status">正在读取机械费…</p>}><MechanicalPage me={me} blocked={blocked} exportGuard={ledgerExportGuard} /></Suspense>} /><Route path="/" element={<Navigate to="/projects" replace />} /><Route path="*" element={<section><h1>页面尚未接入</h1><NavLink to="/projects">返回项目档案</NavLink></section>} /></Routes>{(ledgerVisited || ledgerActive) && <div hidden={!ledgerActive} inert={!ledgerActive}><Suspense fallback={<p role="status">正在读取台账…</p>}><LedgerPage me={me} blocked={blocked || !ledgerActive} active={ledgerActive} project={ledgerProject} setProject={setLedgerProject} onExportGuard={setLedgerExportGuard} /></Suspense></div>}</I8ExecutionProvider></main>
    </div>
  </div></QueryClientProvider>;
}

function App() {
  const [me, setMe] = useState<Identity | null | undefined>(undefined);
  const [error, setError] = useState('');
  const [expired, setExpired] = useState(false);
  const [checking, setChecking] = useState(true);
  const request = useRef<AbortController | null>(null);
  const knownIdentity = useRef<Identity | null>(null);
  async function check() {
    request.current?.abort();
    const controller = new AbortController(); request.current = controller;
    setChecking(true); setError('');
    try {
      const next = readIdentity(await requestJson('/api/m15/users', { signal: controller.signal }));
      if (controller.signal.aborted) return;
      if (next) setExpired(false);
      else if (knownIdentity.current) setExpired(true);
      knownIdentity.current = next; setMe(next); setChecking(false);
    } catch (failure) {
      if (!controller.signal.aborted) {
        // A failed check cannot establish an account change; keep local state while access is paused.
        setError(failure instanceof Error ? failure.message : '账号读取失败，请重试。'); setChecking(false);
      }
    }
  }
  useEffect(() => {
    void check();
    const focus = () => void check();
    const lost = () => { request.current?.abort(); knownIdentity.current = null; setMe(null); setExpired(true); setError(''); setChecking(false); };
    window.addEventListener('focus', focus); window.addEventListener('session-lost', lost);
    return () => { request.current?.abort(); window.removeEventListener('focus', focus); window.removeEventListener('session-lost', lost); };
  }, []);
  if (me === undefined) return <main className="startup">{error ? <Notice message={error} retry={() => void check()} /> : <p role="status">正在识别账号…</p>}</main>;
  return <>
    {expired && <div className="session-notice" role="alert">登录已失效，当前只读。<a href={loginUrl}>重新登录</a></div>}
    {error ? <main className="startup"><Notice message={`账号暂时无法核实，已暂停操作。${error}`} retry={() => void check()} /></main> : checking && <p className="startup" role="status">正在核实账号…</p>}
    <AccountWorkspace key={me ? `${me.id}:${me.account}` : 'anonymous'} me={me} blocked={checking || Boolean(error)} onLogout={() => { request.current?.abort(); knownIdentity.current = null; setMe(null); setExpired(false); setError(''); setChecking(false); }} />
  </>;
}

createRoot(document.getElementById('root')!).render(<StrictMode><BrowserRouter basename="/preview"><App /></BrowserRouter></StrictMode>);
