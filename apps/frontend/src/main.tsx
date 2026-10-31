import './styles.css';
import { prepareAppearance, loadTextFonts } from './appearance-ready';
import { PageSurface } from './page-surface';
import { PageErrorBoundary } from './page-error';
import Button from 'antd/es/button';
import Dropdown from 'antd/es/dropdown';
import { UiProvider } from './ui-provider';
import { AppearancePreferences } from './appearance-preferences';
import { HistoryControls, HistoryScope, HistoryGate } from './history';
import { lazy, memo, StrictMode, Suspense, useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter, NavLink, Route, Routes, useLocation } from 'react-router';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { readIdentity, setRequestIdentity, requestJson, beginIdentityVerification } from './api';
import type { Identity } from './api';
import type { ComponentType } from 'react';
import { GridWidthOwner } from './grid-width-owner';

type WorkspacePageProps = {
  me: Identity | null; blocked: boolean; active: boolean;
  project: number; setProject: (project: number) => void;
  onExportGuard: (guard: string) => void; exportGuard: string;
};

const groups = [
  { id: 'home', title: '工作台' },
  { id: 'base', title: '主数据 / 基础' }, { id: 'payment', title: '付款域' },
  { id: 'contracts', title: '集采域' }, { id: 'materials', title: '材料与报表' },
  { id: 'global', title: '全局' },
];
const pages: { path: string; title: string; mod: string; group: string; loading?: string; component: ComponentType<WorkspacePageProps> }[] = [
  { path: '/', title: '首页', mod: '', group: 'home', loading: '正在读取首页…', component: lazy(() => import('./home').then(module => ({ default: module.HomePage }))) },
  { path: '/projects', title: '项目档案', mod: '01', group: 'base', loading: '正在读取项目档案…', component: lazy(() => import('./projects').then(module => ({ default: module.Projects }))) },
  { path: '/i8', title: 'i8 接入层', mod: '02', group: 'base', loading: '正在读取 i8 接入层…', component: lazy(() => import('./i8').then(module => ({ default: module.I8Page }))) },
  { path: '/notices', title: '付款通知书', mod: '03', group: 'payment', loading: '正在读取付款通知书…', component: lazy(() => import('./notices').then(module => ({ default: module.NoticesPage }))) },
  { path: '/debt', title: '欠款台账', mod: '05', group: 'payment', loading: '正在读取欠款台账…', component: lazy(() => import('./flow').then(module => ({ default: module.DebtPage }))) },
  { path: '/ledger', title: '付款流水', mod: '05', group: 'payment', loading: '正在读取付款流水…', component: lazy(() => import('./flow').then(module => ({ default: module.FlowPage }))) },
  { path: '/contracts', title: '集采台账', mod: '11', group: 'contracts', loading: '正在读取集采合同…', component: lazy(() => import('./contracts').then(module => ({ default: module.ContractsPage }))) },
  { path: '/process', title: '过程资料', mod: '06', group: 'materials', loading: '正在读取过程资料…', component: lazy(() => import('./process').then(module => ({ default: module.ProcessPage }))) },
  { path: '/settlement', title: '收发结存与提取', mod: '07', group: 'materials', loading: '正在读取收发结存…', component: lazy(() => import('./settlement').then(module => ({ default: module.SettlementPage }))) },
  { path: '/big', title: '月度会大表', mod: '07', group: 'materials', loading: '正在读取月度会大表…', component: lazy(() => import('./big').then(module => ({ default: module.BigPage }))) },
  { path: '/inventory', title: '库存单据与调整单', mod: '08', group: 'materials', loading: '正在读取库存单据…', component: lazy(() => import('./inventory').then(module => ({ default: module.InventoryPage }))) },
  { path: '/fees', title: '特殊费用', mod: '09', group: 'materials', loading: '正在读取费用…', component: lazy(() => import('./fees').then(module => ({ default: module.FeesPage }))) },
  { path: '/mechanical', title: '机械费', mod: '10', group: 'materials', loading: '正在读取机械费…', component: lazy(() => import('./mechanical').then(module => ({ default: module.MechanicalPage }))) },
  { path: '/oilcard', title: '油卡管理', mod: '13', group: 'materials', loading: '正在读取油卡档案…', component: lazy(() => import('./oilcard').then(module => ({ default: module.OilCardPage }))) },
  { path: '/rules', title: '规则配置', mod: '14', group: 'global', loading: '正在读取规则配置…', component: lazy(() => import('./rules').then(module => ({ default: module.RulesPage }))) },
  { path: '/users', title: '用户管理', mod: '15', group: 'global', loading: '正在读取用户管理…', component: lazy(() => import('./users').then(module => ({ default: module.UsersPage }))) },
];

// Skip parent-only updates for unrelated retained pages; context updates still propagate.
for (const entry of pages) entry.component = memo(entry.component);

const appBase = import.meta.env.BASE_URL.replace(/\/$/, '');
function loginUrl() { return '/login?next=' + encodeURIComponent(window.location.pathname + window.location.search + window.location.hash); }

function Notice({ message, retry }: { message: string; retry?: () => void }) {
  return <div className="notice" role="alert"><span>{message}</span>{retry && <Button htmlType="submit" onClick={message.includes('字体加载失败') ? () => window.location.reload() : retry}>{message.includes('字体加载失败') ? '重试字体加载' : '重试'}</Button>}</div>;
}

function AccountMenu({ me, busy, logout, appearance }: { me: Identity; busy: boolean; logout: () => void; appearance: () => void }) {
  return <Dropdown trigger={['click']} menu={{ items: [{ key: 'appearance', label: '外观与字号', disabled: busy }, { key: 'logout', label: busy ? '正在退出…' : '退出登录', disabled: busy }], onClick: ({ key }) => key === 'appearance' ? appearance() : logout() }}>
    <Button className="account-pill" disabled={busy}><span className="account-dot" aria-hidden="true" />{me.name || me.account}（{me.role === 'admin' ? '管理员' : '普通用户'}）</Button>
  </Dropdown>;
}

function AccountWorkspace({ me, blocked, obscured, preparing, onLogout, onPreferencesSaved }: { me: Identity | null; blocked: boolean; obscured: boolean; preparing: boolean; onLogout: () => void; onPreferencesSaved: () => Promise<void> }) {
  // A new account gets a new cache and component tree, including future page drafts/history.
  const [client] = useState(() => new QueryClient({ defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false }, mutations: { retry: false } } }));
  const [logoutError, setLogoutError] = useState('');
  const [appearanceOpen, setAppearanceOpen] = useState(false);
  const [compactAppearance, setCompactAppearance] = useState(() => window.matchMedia('(max-width:900px)').matches);
  useEffect(() => {
    const query = window.matchMedia('(max-width:900px)');
    const update = () => setCompactAppearance(query.matches);
    query.addEventListener('change', update);
    return () => query.removeEventListener('change', update);
  }, []);
  const [ledgerExportGuard, setLedgerExportGuard] = useState('');
  const [ledgerProject, setLedgerProject] = useState(0);
  const page = useLocation().pathname;
  const title = pages.find(entry => entry.path === page)?.title ?? '材料工作台';
  const [visited, setVisited] = useState(() => new Set([page]));
  useEffect(() => { setVisited(old => old.has(page) ? old : new Set([...old, page])); }, [page]);
  const [busy, setBusy] = useState(false);
  useEffect(() => () => { void client.cancelQueries(); client.clear(); }, [client]);
  useEffect(() => { if (blocked) void client.cancelQueries(); }, [blocked, client]);
  async function logout() {
    setBusy(true); setLogoutError('');
    try {
      await requestJson('/api/m15/logout', { method: 'POST' });
      await client.cancelQueries(); client.clear(); onLogout();
      window.location.assign(loginUrl());
    } catch (error) { setLogoutError(error instanceof Error ? error.message : '退出失败，请重试。'); setBusy(false); }
  }
  return <QueryClientProvider client={client}><GridWidthOwner value={me ? `${me.id}:${me.account}` : 'anonymous'}><HistoryScope><div className="workspace" hidden={obscured} inert={blocked || preparing} style={{ visibility: preparing ? 'hidden' : undefined }}>
    <a className="skip" href="#content" inert={appearanceOpen && compactAppearance}>跳到内容</a>
    <aside className="sidebar" inert={appearanceOpen && compactAppearance}><div className="brand">材料工作台</div>{appBase === '/preview' && <p className="preview-label">独立预览</p>}<nav aria-label="主导航">
      {groups.map(group => <div key={group.id} className="nav-group" role="group" aria-labelledby={`nav-${group.id}`}><h2 id={`nav-${group.id}`}>{group.title}</h2>{pages.filter(entry => entry.group === group.id).map(entry => <NavLink key={entry.path} to={entry.path} end={entry.path === '/'}><span>{entry.title}</span></NavLink>)}</div>)}
    </nav></aside>
    <div className="main" inert={appearanceOpen && compactAppearance}><header><div className="page-heading"><h1 id="page-title" key={page}>{title}</h1><div id="ledger-status" /></div><div className="account-area"><HistoryControls me={me} blocked={blocked || busy} guard={ledgerExportGuard} /><span hidden={Boolean(me)}>未登录，只读</span>{me ? <AccountMenu me={me} busy={busy} logout={() => void logout()} appearance={() => setAppearanceOpen(true)} /> : <a href={loginUrl()}>登录</a>}</div></header>
      <main id="content" tabIndex={-1}><HistoryGate>{logoutError && <Notice message={logoutError} />}<Routes>{pages.map(entry => <Route key={entry.path} path={entry.path} element={null} />)}<Route path="*" element={<section aria-labelledby="not-found-title"><h2 id="not-found-title">没有找到这个页面</h2><NavLink to="/">返回首页</NavLink></section>} /></Routes>
        {pages.map(entry => {
          const active = page === entry.path;
          if (!active && !visited.has(entry.path)) return null;
          const Page = entry.component;
          return <PageErrorBoundary key={entry.path} active={active} title={entry.title}><PageSurface active={active} title={entry.title}><Suspense fallback={<p role="status" data-page-loading>{entry.loading}</p>}><Page me={me} blocked={blocked || !active} active={active} project={entry.path === '/debt' ? ledgerProject : 0} setProject={setLedgerProject} onExportGuard={setLedgerExportGuard} exportGuard={ledgerExportGuard} /></Suspense></PageSurface></PageErrorBoundary>;
        })}</HistoryGate></main>
    </div>
    {appearanceOpen && me && !blocked && <AppearancePreferences compact={compactAppearance} close={() => setAppearanceOpen(false)} saved={onPreferencesSaved} />}
  </div></HistoryScope></GridWidthOwner></QueryClientProvider>;
}

function preserveIdentity(current: Identity | null, incoming: Identity | null) {
  if (!current || !incoming) return incoming;
  const keys = Object.keys(incoming) as (keyof Identity)[];
  return keys.length === Object.keys(current).length && keys.every(key => current[key] === incoming[key]) ? current : incoming;
}

function App() {
  const [me, setMe] = useState<Identity | null | undefined>(undefined);
  const [error, setError] = useState('');
  const [expired, setExpired] = useState(false);
  const [checking, setChecking] = useState(true);
  const [fontsReady, setFontsReady] = useState(false);
  const request = useRef<AbortController | null>(null);
  const knownIdentity = useRef<Identity | null>(null), identityPending = useRef(false);
  async function check(pause = true, background = false) {
    request.current?.abort(); identityPending.current = true;
    const controller = new AbortController(); request.current = controller;
    const finishVerification = beginIdentityVerification();
    let verificationError = '';
    if (pause) setChecking(true); setError('');
    try {
      const next = preserveIdentity(knownIdentity.current, readIdentity(await requestJson('/api/m15/users', { signal: controller.signal })));
      if (controller.signal.aborted) return;
      await prepareAppearance(next, controller.signal);
      if (controller.signal.aborted) return;
      if (next) setExpired(false);
      else if (knownIdentity.current) setExpired(true);
      setRequestIdentity(next ? `${next.id}:${next.account}` : 'anonymous');
      knownIdentity.current = next; setMe(next); setChecking(false);
      // Identity and appearance are verified; font I/O must not hold API intents.
      finishVerification();
      // Mount read queries while shell glyphs load; only first paint waits for those glyphs.
      await loadTextFonts(pages.map(entry => entry.title).join('') + groups.map(group => group.title).join('') + '材料工作台独立预览管理员外观与字号撤销重做退出登录' + (next?.name ?? next?.account ?? ''));
      if (!controller.signal.aborted) setFontsReady(true);
    } catch (failure) {
      if (!controller.signal.aborted) {
        verificationError = '账号暂时无法核实，请重试后再操作。';
        // A failed check cannot establish an account change; keep local state while access is paused.
        setError(failure instanceof Error ? failure.message : '账号读取失败，请重试。'); setChecking(false);
        if (!pause && !background) throw failure;
      }
    } finally { finishVerification(verificationError); if (request.current === controller) identityPending.current = false; }
  }
  useEffect(() => {
    void check();
    // Keep local navigation/input responsive; API intents wait at the identity gate.
    const focus = () => { if (document.visibilityState === 'visible' && !identityPending.current) void check(false, true); };
    const lost = () => { setRequestIdentity('anonymous'); request.current?.abort(); knownIdentity.current = null; setMe(null); setExpired(true); setError(''); setChecking(false); };
    window.addEventListener('focus', focus); window.addEventListener('session-lost', lost);
    return () => { request.current?.abort(); window.removeEventListener('focus', focus); window.removeEventListener('session-lost', lost); };
  }, []);
  if (me === undefined) return <main className="startup">{error ? <Notice message={error} retry={() => void check()} /> : <p role="status">正在识别账号…</p>}</main>;
  return <UiProvider appearanceKey={`${me?.account}:${me?.theme}:${me?.ui_scale_css}`}>
    {!fontsReady && !error && <p className="page-loading" role="status">正在准备界面…</p>}
    {expired && <div className="session-notice" role="alert">登录已失效，当前只读。<a href={loginUrl()}>重新登录</a></div>}
    {error ? <main className="startup"><Notice message={`账号暂时无法核实，已暂停操作。${error}`} retry={() => void check()} /></main> : null}
    <AccountWorkspace key={me ? `${me.id}:${me.account}` : 'anonymous'} me={me} blocked={checking || Boolean(error)} obscured={Boolean(error)} preparing={!fontsReady} onPreferencesSaved={() => check(false)} onLogout={() => { setRequestIdentity('anonymous'); request.current?.abort(); knownIdentity.current = null; setMe(null); setExpired(false); setError(''); setChecking(false); }} />
  </UiProvider>;
}

createRoot(document.getElementById('root')!).render(<StrictMode><BrowserRouter basename={appBase} useTransitions={false}><App /></BrowserRouter></StrictMode>);
