import Button from 'antd/es/button';
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { ApiError, record, requestJson } from './api';
import type { Identity } from './api';
import { body } from './notices-api';
import { BusinessModal } from './business-modal';
import { DialogContents, useDialogClose } from './dialog-close';

const plain = (value: string) => value.replace(/\*\*/g, '').replace(/（§[^）]*）/g, '');

function readMessage(value: unknown, fallback: string): string {
  return record(value) && typeof value.message === 'string' && value.message ? plain(value.message) : fallback;
}

export interface UserRow { id: number; account: string; name: string; role: string; state: string; i8User: string; lastLogin: string }
export interface UsersData { me: UserRow | null; users: UserRow[]; counts: { active: number; disabled: number; deleted: number } }
export function readUsers(value: unknown): UsersData {
  if (!record(value) || !Array.isArray(value.users) || !record(value.counts)) throw new ApiError('账号列表读取不完整，请重试；仍失败请联系维护人员。');
  const row = (item: unknown): UserRow => {
    if (!record(item) || typeof item.id !== 'number' || !Number.isInteger(item.id) || typeof item.account !== 'string' || typeof item.name !== 'string' || typeof item.role !== 'string' || typeof item.state !== 'string' || typeof item.i8_user !== 'string' || typeof item.last_login_at !== 'string') throw new ApiError('账号列表读取不完整，请重试；仍失败请联系维护人员。');
    return { id: item.id, account: item.account, name: item.name, role: item.role, state: item.state, i8User: item.i8_user, lastLogin: item.last_login_at };
  };
  const me = value.me === null ? null : row(value.me);
  const counts = value.counts as { active: number; disabled: number; deleted: number };
  if (typeof counts.active !== 'number' || typeof counts.disabled !== 'number' || typeof counts.deleted !== 'number') throw new ApiError('账号计数读取不完整，请重试。');
  return { me, users: value.users.map(row), counts };
}

type Dialog =
  | { kind: 'add' }
  | { kind: 'password'; row: UserRow }
  | { kind: 'view'; row: UserRow; data: { account: string; name: string; password: string; i8User: string; i8Password: string } }
  | { kind: 'transfer' }
  | { kind: 'delete'; row: UserRow };

export function UsersPage({ me, blocked, active }: { me: Identity | null; blocked: boolean; active: boolean }) {
  const query = useQuery({ queryKey: ['m15-users'], enabled: active && !blocked, queryFn: async ({ signal }) => readUsers(await requestJson('/api/m15/users', { signal })), refetchOnMount: 'always' });
  const [dialog, setDialog] = useState<Dialog | null>(null);
  const [receipt, setReceipt] = useState('');
  const [error, setError] = useState('');
  const data = query.data;
  const current = data?.me ?? null;
  const isAdmin = current?.role === 'admin';
  const admins = data?.users.filter(user => user.role === 'admin' && user.state === '在用') ?? [];
  const lockAdmin = (user: UserRow) => user.role === 'admin' && user.state === '在用' && admins.length <= 1;
  const writable = active && !blocked && Boolean(me);

  async function run(action: () => Promise<unknown>, fallback: string) {
    setError('');
    try {
      const result = await action();
      setReceipt(readMessage(result, fallback));
      await query.refetch();
      return true;
    } catch (failure) {
      setReceipt('');
      setError(failure instanceof Error ? failure.message : `${fallback}失败，请重试。`);
      return false;
    }
  }

  return <section className="users-page" aria-label="用户管理">
    <div className="users-block">
      <div className="users-head"><h2>账号列表{data && <span className="users-count">（在用 {data.counts.active}，停用 {data.counts.disabled}，已删除 {data.counts.deleted}）</span>}</h2>
        <div className="users-head-tools">
          <Button htmlType="submit" disabled={!isAdmin} onClick={() => { setDialog({ kind: 'transfer' }); setError(''); }}>转让管理员</Button>
          <Button htmlType="submit" className="primary" disabled={!isAdmin} onClick={() => { setDialog({ kind: 'add' }); setError(''); }}>＋ 新增账号</Button>
        </div></div>
      {current && <p className="muted users-note">当前登录 {current.name || current.account}（{isAdmin ? '管理员' : '普通用户'}）{isAdmin ? '' : '，只有管理员可以新增、启停或删除账号；自己的密码和 i8 绑定可在本人行修改。'}</p>}
      {query.isError && !data && <div className="notice" role="alert"><span>{query.error instanceof Error ? query.error.message : '账号列表读取失败，请重试。'}</span><Button htmlType="submit" onClick={() => void query.refetch()}>重读</Button></div>}
      {query.isPending ? <p role="status">正在读取账号列表…</p> : data && <>
        <Feedback receipt={receipt} error={error} />
        <div className="table-scroll users-table" role="region" aria-label="账号列表" tabIndex={0}><table>
          <thead><tr><th>登录账号</th><th>姓名</th><th>角色</th><th>状态</th><th>最近登录</th><th>i8 绑定</th><th>操作</th></tr></thead>
          <tbody>{data.users.map(user => {
            const self = current?.id === user.id;
            const deleted = user.state === '已删除';
            return <tr key={user.id} className={user.state === '在用' ? '' : 'users-inactive'}>
              <td>{user.account}</td>
              <td>{user.name}{self && <span className="muted">（当前登录）</span>}</td>
              <td>{user.role === 'admin' ? <span className="status-tag status-info">管理员</span> : <span className="status-tag status-neutral">普通用户</span>}</td>
              <td>{user.state === '在用' ? <span className="status-tag status-positive">在用</span> : user.state === '已停用' ? <span className="status-tag status-pending">已停用</span> : <span className="status-tag status-negative">已删除</span>}</td>
              <td>{user.lastLogin || <span className="muted">从未登录</span>}</td>
              <td>{user.i8User || <span className="muted">未绑定</span>}</td>
              <td className="users-actions">{deleted
                ? <Button htmlType="submit" disabled={!isAdmin} title={isAdmin ? '恢复软删的账号；恢复不改停用状态' : '只有管理员能恢复账号'} onClick={() => void run(() => requestJson('/api/m15/actions/restore', { method: 'POST', ...body({ id: user.id }) }), '已恢复')}>恢复</Button>
                : <>
                  <Button htmlType="submit" disabled={!writable || !(isAdmin || self)} title={self ? '改自己的密码和 i8 绑定（不用找管理员）' : isAdmin ? '' : '改别人的密码要管理员；自己的密码在自己那一行'} onClick={() => { setDialog({ kind: 'password', row: user }); setError(''); }}>改密</Button>
                  <Button htmlType="submit" disabled={!isAdmin} title={isAdmin ? '' : '查看明文密码要管理员'} onClick={() => void viewPassword(user)}>看密码</Button>
                  <Button htmlType="submit" disabled={!isAdmin || lockAdmin(user)} title={!isAdmin ? '只有管理员可启停账号' : lockAdmin(user) ? '不能停用最后一个管理员（请先转让）' : ''} onClick={() => void run(() => requestJson('/api/m15/actions/status', { method: 'POST', ...body({ id: user.id, status: user.state === '在用' ? '已停用' : '在用' }) }), '已切换状态')}>{user.state === '在用' ? '停用' : '启用'}</Button>
                  {!self && <Button htmlType="submit" className="danger" disabled={!isAdmin || lockAdmin(user)} title={!isAdmin ? '只有管理员可删除账号' : lockAdmin(user) ? '不能删除最后一个管理员（防锁死）' : ''} onClick={() => { setDialog({ kind: 'delete', row: user }); setError(''); }}>删除</Button>}
                </>}</td>
            </tr>;
          })}</tbody>
        </table></div>
        <p className="muted users-note">停用 = 暂不可登录，可再启用；删除为软删，账号名与已有留痕保留、可恢复。密码与 i8 绑定按账号各存一份。</p>
      </>}
    </div>
    {dialog?.kind === 'add' && <AddDialog blocked={blocked} close={() => setDialog(null)} done={text => { setDialog(null); setReceipt(text); void query.refetch(); }} />}
    {dialog?.kind === 'password' && <PasswordDialog row={dialog.row} blocked={blocked} close={() => setDialog(null)} done={text => { setDialog(null); setReceipt(text); void query.refetch(); }} />}
    {dialog?.kind === 'view' && <ViewDialog data={dialog.data} close={() => setDialog(null)} />}
    {dialog?.kind === 'transfer' && <TransferDialog users={data?.users ?? []} current={current} blocked={blocked} close={() => setDialog(null)} done={text => { setDialog(null); setReceipt(text); void query.refetch(); }} />}
    {dialog?.kind === 'delete' && <DeleteDialog row={dialog.row} blocked={blocked} close={() => setDialog(null)} done={text => { setDialog(null); setReceipt(text); void query.refetch(); }} />}
  </section>;

  async function viewPassword(user: UserRow) {
    setError('');
    try {
      const value = await requestJson(`/api/m15/password?id=${user.id}`);
      if (!record(value) || typeof value.password !== 'string' || typeof value.i8_user !== 'string' || typeof value.i8_password !== 'string' || typeof value.account !== 'string' || typeof value.name !== 'string') throw new ApiError('密码读取不完整，请重试。');
      setDialog({ kind: 'view', row: user, data: { account: value.account, name: value.name, password: value.password, i8User: value.i8_user, i8Password: value.i8_password } });
    } catch (failure) {
      setReceipt(''); setError(failure instanceof Error ? failure.message : '看不到密码，请重试。');
    }
  }
}

function Feedback({ receipt, error }: { receipt: string; error: string }) {
  if (error) return <p className="notice" role="alert">{error}</p>;
  if (receipt) return <p className="users-receipt" role="status">{receipt}</p>;
  return null;
}

function useSaving(busy: boolean, dirty: boolean, close: () => void) {
  return useDialogClose({ busy, dirty, close });
}

function AddDialog({ blocked, close, done }: { blocked: boolean; close: () => void; done: (text: string) => void }) {
  const [account, setAccount] = useState(''), [name, setName] = useState(''), [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false), [error, setError] = useState('');
  const closing = useSaving(busy, Boolean(account || name || password), close);
  async function save() {
    if (busy) return;
    if (!account.trim() || !name.trim()) { setError('登录账号与姓名都要填（账号非空即可，不限格式与长度）。'); return; }
    setBusy(true); setError('');
    try {
      const result = await requestJson('/api/m15/actions/create', { method: 'POST', ...body({ account: account.trim(), name: name.trim(), password }) });
      done(readMessage(result, '已创建。'));
    } catch (failure) { setError(failure instanceof Error ? failure.message : '没能创建，请重试。'); }
    finally { setBusy(false); }
  }
  return <BusinessModal open={!blocked} className="users-dialog" titleId="users-add-title" requestClose={closing.requestClose}><DialogContents title="新增账号" titleId="users-add-title" closing={closing}>
    <p className="users-note muted">新增账号为普通用户；管理员只能靠转让产生。</p>
    <label>登录账号 ＊（非空、不重复即可）<input value={account} disabled={busy} placeholder="如 wanglijia" onChange={event => setAccount(event.target.value)} /></label>
    <label>姓名 ＊<input value={name} disabled={busy} placeholder="如 王丽佳" onChange={event => setName(event.target.value)} /></label>
    <label>初始密码（可为空）<input value={password} disabled={busy} placeholder="留空即可；无格式要求" onChange={event => setPassword(event.target.value)} /></label>
    {error && <p className="notice" role="alert">{error}</p>}
    <div className="dialog-actions"><Button htmlType="submit" disabled={busy} onClick={closing.requestClose}>取消</Button><Button htmlType="submit" className="primary" disabled={busy} onClick={() => void save()}>{busy ? '正在创建…' : '创建'}</Button></div>
  </DialogContents></BusinessModal>;
}

function PasswordDialog({ row, blocked, close, done }: { row: UserRow; blocked: boolean; close: () => void; done: (text: string) => void }) {
  const [password, setPassword] = useState(''), [i8User, setI8User] = useState(row.i8User), [i8Password, setI8Password] = useState('');
  const [busy, setBusy] = useState(false), [error, setError] = useState('');
  const dirty = password !== '' || i8User !== row.i8User || i8Password !== '';
  const closing = useSaving(busy, dirty, close);
  async function save() {
    if (busy) return;
    setBusy(true); setError('');
    let savedPassword = false;
    try {
      const first = await requestJson('/api/m15/actions/password', { method: 'POST', ...body({ id: row.id, password }) });
      savedPassword = true;
      const second = await requestJson('/api/m15/actions/i8', { method: 'POST', ...body({ id: row.id, i8_user: i8User.trim(), ...(i8Password === '' ? {} : { i8_password: i8Password }) }) });
      done(`${readMessage(first, '密码已更新。')} ${readMessage(second, 'i8 绑定已保存。')}`);
    } catch (failure) {
      setError(`${savedPassword ? '系统密码已改，但 i8 绑定没存上 —— 重开本弹窗再存一次 i8 绑定即可。' : ''}${failure instanceof Error ? failure.message : '没能保存，请重试。'}`);
    } finally { setBusy(false); }
  }
  return <BusinessModal open={!blocked} className="users-dialog" titleId="users-pwd-title" requestClose={closing.requestClose}><DialogContents title={`密码与 i8 绑定，${row.name || row.account}`} titleId="users-pwd-title" closing={closing}>
    <p className="users-note muted">新密码留空会清空该账号密码，空密码即可登录。</p>
    <label>新密码（可为空）<input value={password} disabled={busy} placeholder="留空即清空该账号密码" onChange={event => setPassword(event.target.value)} /></label>
    <label>i8 账号（绑定到本系统账号、每人一份）<input value={i8User} disabled={busy} placeholder="留空 = 解绑（解绑后抓取会被拦下，提示你先填）" onChange={event => setI8User(event.target.value)} /></label>
    <label>i8 密码<input value={i8Password} disabled={busy} placeholder="留空 = 不改（要清空就把上面的账号也清掉）" onChange={event => setI8Password(event.target.value)} /></label>
    <p className="muted users-note">i8 密码留空保持原值；清空 i8 账号会解绑。</p>
    {error && <p className="notice" role="alert">{error}</p>}
    <div className="dialog-actions"><Button htmlType="submit" disabled={busy} onClick={closing.requestClose}>取消</Button><Button htmlType="submit" className="primary" disabled={busy} onClick={() => void save()}>{busy ? '正在保存…' : '保存'}</Button></div>
  </DialogContents></BusinessModal>;
}

function ViewDialog({ data, close }: { data: { account: string; name: string; password: string; i8User: string; i8Password: string }; close: () => void }) {
  const closing = useSaving(false, false, close);
  return <BusinessModal open className="users-dialog" titleId="users-view-title" requestClose={closing.requestClose}><DialogContents title={`查看密码与 i8 绑定，${data.name || data.account}`} titleId="users-view-title" closing={closing}>
    <label>登录账号<input value={data.account} readOnly /></label>
    <label>当前密码<input value={data.password} readOnly />{!data.password && <span className="muted users-note">该账号没有设密码（空密码即可登录）。</span>}</label>
    {data.i8User
      ? <><label>i8 账号<input value={data.i8User} readOnly /></label><label>i8 密码<input value={data.i8Password} readOnly />{!data.i8Password && <span className="muted users-note">该账号的 i8 密码为空 —— 抓取会拿空密码去登录（会失败）。</span>}</label></>
      : <label>i8 账号<input value="（未绑定）" readOnly /><span className="muted users-note">该账号还没绑 i8 ⇒ 抓取会被拦下并提示先填（不会改用共享账号顶掉别人的会话）。在「改密」里填上即可。</span></label>}
    <div className="dialog-actions"><Button htmlType="submit" onClick={closing.requestClose}>关闭</Button></div>
  </DialogContents></BusinessModal>;
}

function TransferDialog({ users, current, blocked, close, done }: { users: UserRow[]; current: UserRow | null; blocked: boolean; close: () => void; done: (text: string) => void }) {
  const candidates = users.filter(user => current?.id !== user.id && user.state === '在用');
  const [target, setTarget] = useState<number | null>(candidates[0]?.id ?? null);
  const [busy, setBusy] = useState(false), [error, setError] = useState('');
  const closing = useSaving(busy, false, close);
  async function save() {
    if (busy || target === null) return;
    setBusy(true); setError('');
    try {
      const result = await requestJson('/api/m15/actions/transfer', { method: 'POST', ...body({ id: target }) });
      done(readMessage(result, '管理员已转让。'));
    } catch (failure) { setError(failure instanceof Error ? failure.message : '没能转让，请重试。'); }
    finally { setBusy(false); }
  }
  return <BusinessModal open={!blocked} className="users-dialog" titleId="users-transfer-title" requestClose={closing.requestClose}><DialogContents title="转让管理员（授权转让）" titleId="users-transfer-title" closing={closing}>
    {candidates.length === 0 ? <p className="notice" role="alert">没有可转让的在用账号（先新增或启用一个）。</p> : <>
      <p className="users-warning">转让后对方为管理员，你转为普通用户，不再能管理账号。</p>
      <label>转让给（限在用账号）<select value={target ?? ''} disabled={busy} onChange={event => setTarget(Number(event.target.value))}>{candidates.map(user => <option key={user.id} value={user.id}>{user.name}（{user.account}）</option>)}</select></label>
      {error && <p className="notice" role="alert">{error}</p>}
      <div className="dialog-actions"><Button htmlType="submit" disabled={busy} onClick={closing.requestClose}>取消</Button><Button htmlType="submit" className="primary" disabled={busy || target === null} onClick={() => void save()}>{busy ? '正在转让…' : '确认转让'}</Button></div></>}
  </DialogContents></BusinessModal>;
}

function DeleteDialog({ row, blocked, close, done }: { row: UserRow; blocked: boolean; close: () => void; done: (text: string) => void }) {
  const [busy, setBusy] = useState(false), [error, setError] = useState('');
  const closing = useSaving(busy, false, close);
  async function remove() {
    if (busy) return;
    setBusy(true); setError('');
    try {
      const result = await requestJson('/api/m15/actions/delete', { method: 'POST', ...body({ id: row.id }) });
      done(readMessage(result, '已删除（软删）。'));
    } catch (failure) { setError(failure instanceof Error ? failure.message : '没能删除，请重试。'); }
    finally { setBusy(false); }
  }
  return <BusinessModal open={!blocked} className="users-dialog" titleId="users-delete-title" requestClose={closing.requestClose}><DialogContents title="删除账号确认" titleId="users-delete-title" closing={closing}>
    <p>删除 {row.name || row.account}（{row.account}，{row.role === 'admin' ? '管理员' : '普通用户'}）？</p>
    <p className="users-warning">删除后不能登录；账号姓名与已有留痕记录保留，必要时可恢复。</p>
    {error && <p className="notice" role="alert">{error}</p>}
    <div className="dialog-actions"><Button htmlType="submit" disabled={busy} onClick={closing.requestClose}>取消</Button><Button htmlType="submit" className="danger" disabled={busy} onClick={() => void remove()}>{busy ? '正在删除…' : '确认删除'}</Button></div>
  </DialogContents></BusinessModal>;
}
