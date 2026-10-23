import Button from 'antd/es/button';
import Dropdown from 'antd/es/dropdown';
import { UiProvider } from './ui-provider';
import { HistoryControls, HistoryScope, HistoryGate } from './history';
import { lazy, StrictMode, Suspense, useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter, NavLink, Navigate, Route, Routes, useLocation } from 'react-router';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { readIdentity, requestJson } from './api';
import type { Identity } from './api';
const MechanicalPage = lazy(() => import('./mechanical').then(module => ({ default: module.MechanicalPage })));
const LedgerPage = lazy(() => import('./flow').then(module => ({ default: module.FlowPage })));
const NoticesPage = lazy(() => import('./notices').then(module => ({ default: module.NoticesPage })));
const ContractsPage = lazy(() => import('./contracts').then(module => ({ default: module.ContractsPage })));
const I8Page = lazy(() => import('./i8').then(module => ({ default: module.I8Page })));
const SettlementPage = lazy(() => import('./settlement').then(module => ({ default: module.SettlementPage })));
const InventoryPage = lazy(() => import('./inventory').then(module => ({ default: module.InventoryPage })));
const FeesPage = lazy(() => import('./fees').then(module => ({ default: module.FeesPage })));
const ProcessPage = lazy(() => import('./process').then(module => ({ default: module.ProcessPage })));
const BigPage = lazy(() => import('./big').then(module => ({ default: module.BigPage })));
import './style.css';
import { Projects } from './projects';

const loginUrl = '/login?next=%2Fpreview%2Fprojects';

function Notice({ message, retry }: { message: string; retry?: () => void }) {
  return <div className="notice" role="alert"><span>{message}</span>{retry && <Button htmlType="submit" onClick={retry}>重试</Button>}</div>;
}

function AccountMenu({ me, busy, logout }: { me: Identity; busy: boolean; logout: () => void }) {
  return <Dropdown trigger={['click']} menu={{ items: [{ key: 'logout', label: busy ? '正在退出…' : '退出登录', disabled: busy }], onClick: logout }}>
    <Button className="account-pill" disabled={busy}><span className="account-dot" aria-hidden="true" />{me.name || me.account}（{me.role === 'admin' ? '管理员' : '普通用户'}）</Button>
  </Dropdown>;
}

function AccountWorkspace({ me, blocked, obscured, onLogout }: { me: Identity | null; blocked: boolean; obscured: boolean; onLogout: () => void }) {
  // A new account gets a new cache and component tree, including future page drafts/history.
  const [client] = useState(() => new QueryClient({ defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false }, mutations: { retry: false } } }));
  const [logoutError, setLogoutError] = useState('');
  const [ledgerExportGuard, setLedgerExportGuard] = useState('');
  const [ledgerProject, setLedgerProject] = useState(0);
  const page = useLocation().pathname;
  const title = ({ '/process': '过程资料', '/projects': '项目档案', '/i8': 'i8 接入层', '/notices': '付款通知书', '/ledger': '付款流水与欠款统计', '/mechanical': '机械费', '/contracts': '集采合同', '/big': '月度会大表', '/fees': '特殊费用', '/settlement': '收发结存与提取', '/inventory': '库存单据与调整单' } as Record<string, string>)[page] ?? '材料工作台';
  const projectsActive = page === '/projects', i8Active = page === '/i8', contractsActive = page === '/contracts';
  const [visited, setVisited] = useState(() => new Set([page]));
  useEffect(() => { setVisited(old => old.has(page) ? old : new Set([...old, page])); }, [page]);
  const noticeActive = page === '/notices';
  const [noticeVisited, setNoticeVisited] = useState(noticeActive);
  useEffect(() => { if (noticeActive) setNoticeVisited(true); }, [noticeActive]);
  const ledgerActive = page === '/ledger';
  const [ledgerVisited, setLedgerVisited] = useState(ledgerActive);
  useEffect(() => { if (ledgerActive) setLedgerVisited(true); }, [ledgerActive]);
  const processActive = page === '/process';
  const bigActive = page === '/big';
  const feesActive = page === '/fees';
  const settlementActive = page === '/settlement';
  const inventoryActive = page === '/inventory';
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
  return <QueryClientProvider client={client}><HistoryScope><div className="workspace" hidden={obscured} inert={blocked}>
    <a className="skip" href="#content">跳到内容</a>
    <aside className="sidebar"><div className="brand">材料工作台</div><p className="preview-label">独立预览</p><nav aria-label="主导航">
      <div className="nav-group" role="group" aria-labelledby="nav-base"><h2 id="nav-base">主数据 · 基础</h2><NavLink to="/projects"><span className="nav-code">MOD-01</span><span>项目档案</span></NavLink><NavLink to="/i8"><span className="nav-code">MOD-02</span><span>i8 接入层</span></NavLink></div>
      <div className="nav-group" role="group" aria-labelledby="nav-payment"><h2 id="nav-payment">付款域</h2><NavLink to="/notices"><span className="nav-code">MOD-03</span><span>付款通知书</span></NavLink><NavLink to="/ledger"><span className="nav-code">MOD-05</span><span>付款流水与欠款统计</span></NavLink></div>
      <div className="nav-group" role="group" aria-labelledby="nav-contracts"><h2 id="nav-contracts">集采域</h2><NavLink to="/contracts"><span className="nav-code">MOD-11</span><span>集采合同</span></NavLink></div>
      <div className="nav-group" role="group" aria-labelledby="nav-materials"><h2 id="nav-materials">材料与报表</h2><NavLink to="/process"><span className="nav-code">MOD-06</span><span>过程资料</span></NavLink><NavLink to="/settlement"><span className="nav-code">MOD-07</span><span>收发结存与提取</span></NavLink><NavLink to="/big"><span className="nav-code">MOD-07</span><span>月度会大表</span></NavLink><NavLink to="/inventory"><span className="nav-code">MOD-08</span><span>库存单据与调整单</span></NavLink><NavLink to="/fees"><span className="nav-code">MOD-09</span><span>特殊费用</span></NavLink></div>
    </nav><a className="old-app" href="/app">打开旧版预览</a></aside>
    <div className="main"><header><div className="page-heading"><h1 id="page-title">{title}</h1><div id="ledger-status" /></div><div className="account-area"><div hidden={mechanicalActive}><HistoryControls me={me} blocked={blocked || busy || mechanicalActive} guard={ledgerExportGuard} /></div>{mechanicalActive && <div id="history-controls" />}<span hidden={Boolean(me)}>未登录 · 只读</span>{me ? <AccountMenu me={me} busy={busy} logout={() => void logout()} /> : <a href={loginUrl}>登录</a>}</div></header>
      <main id="content" tabIndex={-1}><HistoryGate>{logoutError && <Notice message={logoutError} />}<Routes><Route path="/projects" element={null} /><Route path="/i8" element={null} /><Route path="/notices" element={null} /><Route path="/ledger" element={null} /><Route path="/mechanical" element={null} /><Route path="/contracts" element={null} /><Route path="/process" element={null} /><Route path="/big" element={null} /><Route path="/fees" element={null} /><Route path="/settlement" element={null} /><Route path="/inventory" element={null} /><Route path="/" element={<Navigate to="/projects" replace />} /><Route path="*" element={<section><h1>页面尚未接入</h1><NavLink to="/projects">返回项目档案</NavLink></section>} /></Routes>
        {(visited.has('/projects') || projectsActive) && <div className="page-view" hidden={!projectsActive} inert={!projectsActive}><Projects me={me} blocked={blocked || !projectsActive} /></div>}
        {(visited.has('/i8') || i8Active) && <div className="page-view" hidden={!i8Active} inert={!i8Active}><Suspense fallback={<p role="status">正在读取 i8 接入层…</p>}><I8Page blocked={blocked || !i8Active} /></Suspense></div>}
        {(noticeVisited || noticeActive) && <div className="page-view" hidden={!noticeActive} inert={!noticeActive}><Suspense fallback={<p role="status">正在读取付款通知书…</p>}><NoticesPage me={me} blocked={blocked || !noticeActive} active={noticeActive} /></Suspense></div>}
        {(ledgerVisited || ledgerActive) && <div className="page-view" hidden={!ledgerActive} inert={!ledgerActive}><Suspense fallback={<p role="status">正在读取台账…</p>}><LedgerPage me={me} blocked={blocked || !ledgerActive} active={ledgerActive} project={ledgerProject} setProject={setLedgerProject} onExportGuard={setLedgerExportGuard} /></Suspense></div>}
        {(visited.has('/contracts') || contractsActive) && <div className="page-view" hidden={!contractsActive} inert={!contractsActive}><Suspense fallback={<p role="status">正在读取集采合同…</p>}><ContractsPage me={me} blocked={blocked || !contractsActive} active={contractsActive} /></Suspense></div>}
        {(visited.has('/settlement') || settlementActive) && <div className="page-view" hidden={!settlementActive} inert={!settlementActive}><Suspense fallback={<p role="status">正在读取收发结存…</p>}><SettlementPage me={me} blocked={blocked || !settlementActive} active={settlementActive} /></Suspense></div>}
        {(visited.has('/inventory') || inventoryActive) && <div className="page-view" hidden={!inventoryActive} inert={!inventoryActive}><Suspense fallback={<p role="status">正在读取库存单据…</p>}><InventoryPage me={me} blocked={blocked || !inventoryActive} active={inventoryActive} /></Suspense></div>}
        {(visited.has('/process') || processActive) && <div className="page-view" hidden={!processActive} inert={!processActive}><Suspense fallback={<p role="status">正在读取过程资料…</p>}><ProcessPage me={me} blocked={blocked || !processActive} active={processActive} /></Suspense></div>}
        {(visited.has('/big') || bigActive) && <div className="page-view" hidden={!bigActive} inert={!bigActive}><Suspense fallback={<p role="status">正在读取月度会大表…</p>}><BigPage me={me} blocked={blocked || !bigActive} active={bigActive} /></Suspense></div>}
        {(visited.has('/fees') || feesActive) && <div className="page-view" hidden={!feesActive} inert={!feesActive}><Suspense fallback={<p role="status">正在读取费用…</p>}><FeesPage me={me} blocked={blocked || !feesActive} active={feesActive} /></Suspense></div>}
        {(mechanicalVisited || mechanicalActive) && <div className="page-view" hidden={!mechanicalActive} inert={!mechanicalActive}><Suspense fallback={<p role="status">正在读取机械费…</p>}><MechanicalPage me={me} blocked={blocked || !mechanicalActive} active={mechanicalActive} exportGuard={ledgerExportGuard} /></Suspense></div>}</HistoryGate></main>
    </div>
  </div></HistoryScope></QueryClientProvider>;
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
    {error ? <main className="startup"><Notice message={`账号暂时无法核实，已暂停操作。${error}`} retry={() => void check()} /></main> : null}
    <AccountWorkspace key={me ? `${me.id}:${me.account}` : 'anonymous'} me={me} blocked={checking || Boolean(error)} obscured={Boolean(error)} onLogout={() => { request.current?.abort(); knownIdentity.current = null; setMe(null); setExpired(false); setError(''); setChecking(false); }} />
  </>;
}

createRoot(document.getElementById('root')!).render(<StrictMode><BrowserRouter basename="/preview"><UiProvider><App /></UiProvider></BrowserRouter></StrictMode>);
