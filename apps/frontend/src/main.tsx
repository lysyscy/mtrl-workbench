import { lazy, StrictMode, Suspense, useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter, NavLink, Navigate, Route, Routes, useLocation } from 'react-router';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { readIdentity, requestJson } from './api';
import type { Identity } from './api';
const MechanicalPage = lazy(() => import('./mechanical').then(module => ({ default: module.MechanicalPage })));
const LedgerPage = lazy(() => import('./flow').then(module => ({ default: module.FlowPage })));
const NoticesPage = lazy(() => import('./notices').then(module => ({ default: module.NoticesPage })));
const I8Page = lazy(() => import('./i8').then(module => ({ default: module.I8Page })));
import './style.css';
import { Projects } from './projects';

const loginUrl = '/login?next=%2Fpreview%2Fprojects';

function Notice({ message, retry }: { message: string; retry?: () => void }) {
  return <div className="notice" role="alert"><span>{message}</span>{retry && <button onClick={retry}>重试</button>}</div>;
}

function AccountWorkspace({ me, blocked, onLogout }: { me: Identity | null; blocked: boolean; onLogout: () => void }) {
  // A new account gets a new cache and component tree, including future page drafts/history.
  const [client] = useState(() => new QueryClient({ defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false }, mutations: { retry: false } } }));
  const [logoutError, setLogoutError] = useState('');
  const [ledgerExportGuard, setLedgerExportGuard] = useState('');
  const [ledgerProject, setLedgerProject] = useState(0);
  const page = useLocation().pathname;
  const title = ({ '/projects': '项目档案', '/i8': 'i8 接入层', '/notices': '付款通知书', '/ledger': '付款流水与欠款统计', '/mechanical': '机械费' } as Record<string, string>)[page] ?? '材料工作台';
  const noticeActive = page === '/notices';
  const [noticeVisited, setNoticeVisited] = useState(noticeActive);
  useEffect(() => { if (noticeActive) setNoticeVisited(true); }, [noticeActive]);
  const ledgerActive = page === '/ledger';
  const [ledgerVisited, setLedgerVisited] = useState(ledgerActive);
  useEffect(() => { if (ledgerActive) setLedgerVisited(true); }, [ledgerActive]);
  const mechanicalActive=page==='/mechanical';
  const [mechanicalVisited,setMechanicalVisited]=useState(mechanicalActive);
  useEffect(()=>{if(mechanicalActive)setMechanicalVisited(true);},[mechanicalActive]);
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
    <aside className="sidebar"><div className="brand">材料工作台</div><p className="preview-label">独立预览</p><nav aria-label="主导航"><NavLink to="/projects">MOD-01 项目档案</NavLink><NavLink to="/i8">MOD-02 i8 接入层</NavLink><NavLink to="/notices">MOD-03 付款通知书</NavLink><NavLink to="/ledger">MOD-05 付款流水与欠款统计</NavLink><NavLink to="/mechanical">MOD-10 机械费</NavLink></nav><a className="old-app" href="/app">打开旧版预览</a></aside>
    <div className="main"><header><div className="page-heading"><h1 id="page-title">{title}</h1><div id="ledger-status" /></div><div className="account-area"><div className="history-slot"><div id="history-controls" /><div className="history-fallback ledger-tools"><button disabled title="当前页面没有可撤销的操作">撤销</button><button disabled title="当前页面没有可重做的操作">重做</button></div></div><span>{me ? `${me.name || me.account} · ${me.role === 'admin' ? '管理员' : '普通用户'}` : '未登录 · 只读'}</span>{me ? <button onClick={() => void logout()} disabled={busy}>{busy ? '正在退出…' : '切换账号'}</button> : <a href={loginUrl}>登录</a>}</div></header>
      <main id="content" tabIndex={-1}>{logoutError && <Notice message={logoutError} />}<Routes><Route path="/projects" element={<Projects me={me} blocked={blocked} />} /><Route path="/i8" element={<Suspense fallback={<p role="status">正在读取 i8 接入层…</p>}><I8Page blocked={blocked} /></Suspense>} /><Route path="/notices" element={null} /><Route path="/ledger" element={null} /><Route path="/mechanical" element={null} /><Route path="/" element={<Navigate to="/projects" replace />} /><Route path="*" element={<section><h1>页面尚未接入</h1><NavLink to="/projects">返回项目档案</NavLink></section>} /></Routes>{(noticeVisited || noticeActive) && <div hidden={!noticeActive} inert={!noticeActive}><Suspense fallback={<p role="status">正在读取付款通知书…</p>}><NoticesPage me={me} blocked={blocked || !noticeActive} active={noticeActive} /></Suspense></div>}{(ledgerVisited || ledgerActive) && <div hidden={!ledgerActive} inert={!ledgerActive}><Suspense fallback={<p role="status">正在读取台账…</p>}><LedgerPage me={me} blocked={blocked || !ledgerActive} active={ledgerActive} project={ledgerProject} setProject={setLedgerProject} onExportGuard={setLedgerExportGuard} /></Suspense></div>}{(mechanicalVisited||mechanicalActive)&&<div hidden={!mechanicalActive} inert={!mechanicalActive}><Suspense fallback={<p role="status">正在读取机械费…</p>}><MechanicalPage me={me} blocked={blocked||!mechanicalActive} active={mechanicalActive} exportGuard={ledgerExportGuard} /></Suspense></div>}</main>
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
