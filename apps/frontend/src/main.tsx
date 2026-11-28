import './styles.css';
import { prepareAppearance, loadTextFonts } from './appearance-ready';
import { PageSurface } from './page-surface';
import { NoticeEntry } from './notice-entry';
import { PageErrorBoundary, WorkspaceReloadButton } from './page-error';
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
import { resetBrowserRelay } from './i8-browser-relay';
import { I8SessionProvider } from './i8-session';
import { NoticeFetchJobs } from './notice-fetch-jobs';
import { DialogPresence, MotionAccess, WorkspaceMarker } from './workspace-motion';
import { resolveSidebarCollapsed, sidebarNarrowWidth, toggleSidebarPreference } from './sidebar-state';
import type { SidebarPreference } from './sidebar-state';

type WorkspacePageProps = {
  me: Identity | null; blocked: boolean; active: boolean;
  project: number; setProject: (project: number) => void;
  onExportGuard: (guard: string) => void; exportGuard: string;
  onHistoryGuard: (guard: string) => void;
};

let readyHome: ComponentType<WorkspacePageProps> | undefined;
let homeModule: Promise<{ default: ComponentType<WorkspacePageProps> }> | undefined;
const loadHome = () => homeModule ??= import('./home').then(({ HomePage }) => {
  readyHome = HomePage;
  return { default: HomePage };
});
const LazyHome = lazy(loadHome);
function HomeEntry(props: WorkspacePageProps) {
  const [Page] = useState<ComponentType<WorkspacePageProps>>(() => readyHome ?? LazyHome);
  return <Page {...props} />;
}

const groups = [
  { id: 'home', title: '工作台' },
  { id: 'base', title: '主数据 / 基础' }, { id: 'payment', title: '付款域' },
  { id: 'contracts', title: '集采域' }, { id: 'materials', title: '材料与报表' },
  { id: 'global', title: '全局' },
];
const pages: { path: string; title: string; icon: string; group: string; loading?: string; component: ComponentType<WorkspacePageProps> }[] = [
  { path: '/', title: '首页', icon: 'M3 10 12 3l9 7v10H3z M9 20v-7h6v7', group: 'home', loading: '正在读取首页…', component: HomeEntry },
  { path: '/projects', title: '项目档案', icon: 'M3 6h7l2 2h9v12H3z M3 12h18', group: 'base', loading: '正在读取项目档案…', component: lazy(() => import('./projects').then(module => ({ default: module.Projects }))) },
  { path: '/i8', title: 'i8 接入层', icon: 'M8 3v5m8-5v5M6 8h12v3a6 6 0 0 1-12 0zm6 9v4', group: 'base', loading: '正在读取 i8 接入层…', component: lazy(() => import('./i8').then(module => ({ default: module.I8Page }))) },
  { path: '/notices', title: '付款通知书', icon: 'M5 3h10l4 4v14H5z M14 3v5h5M8 12h8m-8 4h6', group: 'payment', loading: '正在读取付款通知书…', component: NoticeEntry },
  { path: '/debt', title: '欠款台账', icon: 'M4 4h16v16H4z M9 4v16M12 9h5m-5 5h5', group: 'payment', loading: '正在读取欠款台账…', component: lazy(() => import('./flow').then(module => ({ default: module.DebtPage }))) },
  { path: '/ledger', title: '付款流水', icon: 'M3 8h17l-4-4m4 12H3l4 4M20 8l-4 4M3 16l4-4', group: 'payment', loading: '正在读取付款流水…', component: lazy(() => import('./flow').then(module => ({ default: module.FlowPage }))) },
  { path: '/contracts', title: '集采台账', icon: 'M4 6h16v15H4z M9 6V3h6v3M8 11h8m-8 5h8', group: 'contracts', loading: '正在读取集采合同…', component: lazy(() => import('./contracts').then(module => ({ default: module.ContractsPage }))) },
  { path: '/process', title: '过程资料', icon: 'M3 7h5v5H3zm13 7h5v5h-5zM8 9.5h4v7h4M12 5v4.5h5', group: 'materials', loading: '正在读取过程资料…', component: lazy(() => import('./process').then(module => ({ default: module.ProcessPage }))) },
  { path: '/settlement', title: '收发结存与提取', icon: 'm3 8 9-5 9 5-9 5zm0 0v9l9 4 9-4V8m-9 5v8', group: 'materials', loading: '正在读取收发结存…', component: lazy(() => import('./settlement').then(module => ({ default: module.SettlementPage }))) },
  { path: '/big', title: '月度会大表', icon: 'M3 5h18v14H3zm0 5h18M9 10v9m6-9v9', group: 'materials', loading: '正在读取月度会大表…', component: lazy(() => import('./big').then(module => ({ default: module.BigPage }))) },
  { path: '/inventory', title: '库存单据与调整单', icon: 'M4 3h16v5H4zm1 5v13h14V8m-9 4h4m-5 4h6', group: 'materials', loading: '正在读取库存单据…', component: lazy(() => import('./inventory').then(module => ({ default: module.InventoryPage }))) },
  { path: '/fees', title: '特殊费用', icon: 'M5 3h14v18l-3.5-2-3.5 2-3.5-2L5 21zm4 5h6m-6 4h6', group: 'materials', loading: '正在读取费用…', component: lazy(() => import('./fees').then(module => ({ default: module.FeesPage }))) },
  { path: '/mechanical', title: '机械费', icon: 'M14 6a5 5 0 0 0-6 6l-5 5 4 4 5-5a5 5 0 0 0 6-6l-3 3-4-4z', group: 'materials', loading: '正在读取机械费…', component: lazy(() => import('./mechanical').then(module => ({ default: module.MechanicalPage }))) },
  { path: '/equipment', title: '设备台账', icon: 'M3 5h18v12H3zm5 16h8m-4-4v4m-5-8 3-4 3 2 4-2', group: 'materials', loading: '正在读取设备分布…', component: lazy(() => import('./equipment').then(module => ({ default: module.EquipmentPage }))) },
  { path: '/oilcard', title: '油卡管理', icon: 'M3 6h18v12H3zm0 4h18m-14 4h4', group: 'materials', loading: '正在读取油卡档案…', component: lazy(() => import('./oilcard').then(module => ({ default: module.OilCardPage }))) },
  { path: '/rules', title: '规则配置', icon: 'M4 6h6m4 0h6M4 12h10m4 0h2M4 18h2m4 0h10M10 4v4m4 2v4m-8 2v4', group: 'global', loading: '正在读取规则配置…', component: lazy(() => import('./rules').then(module => ({ default: module.RulesPage }))) },
  { path: '/users', title: '用户管理', icon: 'M15 8a3 3 0 1 1-6 0 3 3 0 0 1 6 0z M5 20v-2a4 4 0 0 1 4-4h6a4 4 0 0 1 4 4v2z', group: 'global', loading: '正在读取用户管理…', component: lazy(() => import('./users').then(module => ({ default: module.UsersPage }))) },
];

for (const entry of pages) entry.component = memo(entry.component);

const appBase = import.meta.env.BASE_URL.replace(/\/$/, '');
function loginUrl() { return '/login?next=' + encodeURIComponent(window.location.pathname + window.location.search + window.location.hash); }

function Notice({ message, retry }: { message: string; retry?: () => void }) {
  return <div className="notice" role="alert"><span>{message}</span>{retry && <Button onClick={retry}>重试</Button>}</div>;
}

function AccountMenu({ me, busy, logout, appearance }: { me: Identity; busy: boolean; logout: () => void; appearance: () => void }) {
  return <Dropdown trigger={['click']} menu={{ items: [{ key: 'appearance', label: '外观与字号', disabled: busy }, { key: 'logout', label: busy ? '正在退出…' : '退出登录', disabled: busy }], onClick: ({ key }) => key === 'appearance' ? appearance() : logout() }}>
    <Button className="account-pill" disabled={busy}><span className="account-dot" aria-hidden="true" />{me.name || me.account}（{me.role === 'admin' ? '管理员' : '普通用户'}）</Button>
  </Dropdown>;
}

function NavigationIcon({ path }: { path: string }) {
  return <svg className="navigation-icon" viewBox="0 0 24 24" aria-hidden="true"><path d={path} /></svg>;
}

function Sidebar({ collapsed, inert, toggle }: { collapsed: boolean; inert: boolean; toggle: () => void }) {
  const toggleLabel = collapsed ? '展开侧栏' : '收起侧栏';
  return <aside className="sidebar" inert={inert}>
    <div className="sidebar-heading">
      <div className="sidebar-identity">
        <div className="brand">材料工作台</div>
        {appBase === '/preview' && <p className="preview-label">独立预览</p>}
      </div>
      <button className="sidebar-toggle" type="button" data-testid="sidebar-toggle" aria-controls="workspace-navigation"
        aria-expanded={!collapsed} aria-label={toggleLabel} title={toggleLabel} onClick={toggle}>
        <NavigationIcon path={collapsed ? 'M3 5h18v14H3z M9 5v14 M14 9l3 3-3 3' : 'M3 5h18v14H3z M9 5v14 M17 9l-3 3 3 3'} />
      </button>
    </div>
    <nav id="workspace-navigation" aria-label="主导航">
      {groups.map(group => <div key={group.id} className="nav-group" role="group" aria-labelledby={'nav-' + group.id}>
        <p id={'nav-' + group.id} className="nav-group-label">{group.title}</p>
        {pages.filter(entry => entry.group === group.id).map(entry => <NavLink key={entry.path} to={entry.path} end={entry.path === '/'} title={collapsed ? entry.title : undefined}>
          {({ isActive }) => <>
            {isActive && <WorkspaceMarker className="navigation-marker" layoutId="workspace-navigation" />}
            <NavigationIcon path={entry.icon} />
            <span className="navigation-label">{entry.title}</span>
          </>}
        </NavLink>)}
      </div>)}
    </nav>
  </aside>;
}

function AccountWorkspace({ me, blocked, obscured, preparing, fontError, onLogout, onPreferencesSaved }: { me: Identity | null; blocked: boolean; obscured: boolean; preparing: boolean; fontError: boolean; onLogout: () => void; onPreferencesSaved: () => Promise<void> }) {
  const [client] = useState(() => new QueryClient({ defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false }, mutations: { retry: false } } }));
  const [logoutError, setLogoutError] = useState('');
  const [appearanceOpen, setAppearanceOpen] = useState(false);
  const [sidebarPreference, setSidebarPreference] = useState<SidebarPreference>('auto');
  const [sidebarViewportWidth, setSidebarViewportWidth] = useState(() => window.innerWidth);
  const sidebarCollapsed = resolveSidebarCollapsed(sidebarPreference, sidebarViewportWidth);
  const [compactAppearance, setCompactAppearance] = useState(() => window.matchMedia('(max-width:900px)').matches);
  useEffect(() => {
    const query = window.matchMedia(`(max-width:${sidebarNarrowWidth}px)`);
    const update = () => setSidebarViewportWidth(window.innerWidth);
    query.addEventListener('change', update);
    update();
    return () => query.removeEventListener('change', update);
  }, []);
  useEffect(() => {
    const query = window.matchMedia('(max-width:900px)');
    const update = () => setCompactAppearance(query.matches);
    query.addEventListener('change', update);
    return () => query.removeEventListener('change', update);
  }, []);
  const [ledgerExportGuard, setLedgerExportGuard] = useState('');
  const [mechanicalHistoryGuard, setMechanicalHistoryGuard] = useState('');
  const historyGuard = ledgerExportGuard || mechanicalHistoryGuard;
  const [ledgerProject, setLedgerProject] = useState(0);
  const page = useLocation().pathname;
  const [navigation, setNavigation] = useState({ page, direction: 1 });
  if (navigation.page !== page) setNavigation({ page, direction: pages.findIndex(entry => entry.path === page) >= pages.findIndex(entry => entry.path === navigation.page) ? 1 : -1 });
  const title = pages.find(entry => entry.path === page)?.title ?? '材料工作台';
  useEffect(() => { document.title = `${title} · 材料工作台${appBase === '/preview' ? ' · 独立预览' : ''}`; }, [title]);
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
  return <MotionAccess.Provider value={!blocked && !obscured}><QueryClientProvider client={client}><GridWidthOwner value={me ? `${me.id}:${me.account}` : 'anonymous'}><HistoryScope workspaceGuard={historyGuard}><I8SessionProvider blocked={blocked} owner={me ? `${me.id}:${me.account}` : 'anonymous'}><NoticeFetchJobs account={me?.account ?? ''} paused={blocked}>
    {fontError && !obscured && <div className="session-notice" role="alert"><span>部分字体未能加载，已用系统字体显示。</span><WorkspaceReloadButton>重试字体加载</WorkspaceReloadButton></div>}
    <div className="workspace shell" data-sidebar={sidebarCollapsed ? 'collapsed' : 'expanded'} hidden={obscured} inert={blocked || preparing} style={{ visibility: preparing ? 'hidden' : undefined }}>
    <a className="skip" href="#content" inert={appearanceOpen && compactAppearance}>跳到内容</a>
    <Sidebar collapsed={sidebarCollapsed} inert={appearanceOpen && compactAppearance}
      toggle={() => setSidebarPreference(preference => toggleSidebarPreference(preference, sidebarViewportWidth))} />
    <div className="main" inert={appearanceOpen && compactAppearance}>
      <header>
        <div className="page-heading">
          <h1 id="page-title" key={page}>{title}</h1>
          {appBase === '/preview' && sidebarCollapsed && <span className="topbar-preview-label">独立预览</span>}
          <div id="ledger-status" />
        </div>
        <div className="account-area"><HistoryControls me={me} blocked={blocked || busy} guard={historyGuard} /><span hidden={Boolean(me)}>未登录，只读</span>{me ? <AccountMenu me={me} busy={busy} logout={() => void logout()} appearance={() => setAppearanceOpen(true)} /> : <a href={loginUrl()}>登录</a>}</div>
      </header>
      <main id="content" tabIndex={-1}><HistoryGate>{logoutError && <Notice message={logoutError} />}<Routes>{pages.map(entry => <Route key={entry.path} path={entry.path} element={null} />)}<Route path="*" element={<div className="page-view"><section className="wb-surface page-shell page-shell--flow" data-page-layout="flow" aria-labelledby="not-found-title"><h2 id="not-found-title">没有找到这个页面</h2><NavLink to="/">返回首页</NavLink></section></div>} /></Routes>
        {pages.map(entry => {
          const active = page === entry.path;
          if (!active && !visited.has(entry.path)) return null;
          const Page = entry.component;
          return <PageErrorBoundary key={entry.path} active={active} title={entry.title}><PageSurface active={active} direction={navigation.direction} position={Math.sign(pages.indexOf(entry) - pages.findIndex(item => item.path === page))} title={entry.title}><Suspense fallback={<p role="status" data-page-loading>{entry.loading}</p>}><Page me={me} blocked={blocked || !active} active={active} project={entry.path === '/debt' ? ledgerProject : 0} setProject={setLedgerProject} onExportGuard={setLedgerExportGuard} exportGuard={ledgerExportGuard} onHistoryGuard={setMechanicalHistoryGuard} /></Suspense></PageSurface></PageErrorBoundary>;
        })}</HistoryGate></main>
    </div>
    <DialogPresence>{appearanceOpen && me && !blocked && <AppearancePreferences compact={compactAppearance} close={() => setAppearanceOpen(false)} saved={onPreferencesSaved} />}</DialogPresence>
  </div></NoticeFetchJobs></I8SessionProvider></HistoryScope></GridWidthOwner></QueryClientProvider></MotionAccess.Provider>;
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
  const [fontError, setFontError] = useState(false);
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
      finishVerification();
      await loadTextFonts(pages.map(entry => entry.title).join('') + groups.map(group => group.title).join('') + '材料工作台独立预览管理员外观与字号撤销重做退出登录' + (next?.name ?? next?.account ?? ''));
      if (!controller.signal.aborted) setFontsReady(true);
    } catch (failure) {
      if (!controller.signal.aborted) {
        verificationError = '账号暂时无法核实，请重试后再操作。';
        setError(failure instanceof Error ? failure.message : '账号读取失败，请重试。'); setChecking(false);
        if (!pause && !background) throw failure;
      }
    } finally { finishVerification(verificationError); if (request.current === controller) identityPending.current = false; }
  }
  useEffect(() => {
    function reportFontFailure() {
      if ([...document.fonts].some(face => face.family === 'MiSans' && face.status === 'error')) setFontError(true);
    }
    document.fonts.addEventListener('loadingerror', reportFontFailure);
    reportFontFailure();
    void check();
    if (window.location.pathname === appBase || window.location.pathname === appBase + '/') {
      void loadHome().catch(() => {});
    }
    const focus = () => { if (document.visibilityState === 'visible' && !identityPending.current) void check(false, true); };
    const lost = () => { resetBrowserRelay(); setRequestIdentity('anonymous'); request.current?.abort(); knownIdentity.current = null; setMe(null); setExpired(true); setError(''); setChecking(false); };
    window.addEventListener('focus', focus); window.addEventListener('session-lost', lost);
    return () => { request.current?.abort(); window.removeEventListener('focus', focus); window.removeEventListener('session-lost', lost); document.fonts.removeEventListener('loadingerror', reportFontFailure); };
  }, []);
  if (me === undefined) return <main className="startup">{error ? <Notice message={error} retry={() => void check()} /> : <p role="status">正在识别账号…</p>}</main>;
  return <UiProvider appearanceKey={`${me?.account}:${me?.theme}:${me?.ui_scale_css}`}>
    {!fontsReady && !error && <p className="page-loading" role="status">正在准备界面…</p>}
    {expired && <div className="session-notice" role="alert">登录已失效，当前只读。<a href={loginUrl()}>重新登录</a></div>}
    {error ? <main className="startup"><Notice message={`账号暂时无法核实，已暂停操作。${error}`} retry={() => void check()} /></main> : null}
    <AccountWorkspace key={me ? `${me.id}:${me.account}` : 'anonymous'} me={me} blocked={checking || Boolean(error)} obscured={Boolean(error)} preparing={!fontsReady} fontError={fontError} onPreferencesSaved={() => check(false)} onLogout={() => { resetBrowserRelay(); setRequestIdentity('anonymous'); request.current?.abort(); knownIdentity.current = null; setMe(null); setExpired(false); setError(''); setChecking(false); }} />
  </UiProvider>;
}

createRoot(document.getElementById('root')!).render(<StrictMode><BrowserRouter basename={appBase} useTransitions={false}><App /></BrowserRouter></StrictMode>);
