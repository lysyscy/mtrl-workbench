import { noticeTodosKey } from './notice-todos';
import { Link } from 'react-router';
import { useQuery } from '@tanstack/react-query';
import { ApiError, record, requestJson } from './api';
import { ReadFailure, ReadStatusLane, readPhase } from './read-region';

interface HomeTodos { notice_count: number; ownership: number; jc: number; void: number }

const todos = [
  { key: 'ownership', label: '归属待指定', detail: '尚未确定所属项目的通知书', action: '去指定归属', tone: 'pending', status: '待处理',
    icon: 'M3 6h7l2 2h9v12H3z M9 13h6m-3-3v6' },
  { key: 'jc', label: '集采未关联合同', detail: '未关联合同且未付清的集采通知书', action: '去关联合同', tone: 'pending', status: '待处理',
    icon: 'm9 15 6-6m-7 3-3 3a3 3 0 0 0 4 4l3-3m0-8 3-3a3 3 0 0 1 4 4l-3 3' },
  { key: 'void', label: '撤单但有牵涉', detail: 'i8 已撤单，仍有付款或合同关联', action: '去处理', tone: 'negative', status: '需核对',
    icon: 'M12 4 3 20h18z M12 9v5m0 3h.01' },
] satisfies ReadonlyArray<{ key: 'ownership' | 'jc' | 'void'; label: string; detail: string; action: string; tone: string; status: string; icon: string }>;

function readHomeTodos(value: unknown): HomeTodos {
  const validCount = (n: unknown): n is number => typeof n === 'number' && Number.isSafeInteger(n) && n >= 0;
  if (record(value) && validCount(value.notice_count) && validCount(value.ownership) && validCount(value.jc) && validCount(value.void)
      && Math.max(value.ownership, value.jc, value.void) <= value.notice_count) {
    return { notice_count: value.notice_count, ownership: value.ownership, jc: value.jc, void: value.void };
  }
  throw new ApiError('待办数量读取不完整，请重试。');
}

export function HomePage({ blocked, active }: { blocked: boolean; active: boolean }) {
  const query = useQuery({ queryKey: noticeTodosKey, enabled: !blocked && active, queryFn: async ({ signal }) => readHomeTodos(await requestJson('/api/m03/notice-todos', { signal })), refetchOnMount: 'always' });
  const readState = readPhase(query, query.data?.notice_count === 0);
  const counts = query.data;
  const reading = readState === 'idle' || readState === 'reading';
  const total = counts && todos.reduce((sum, todo) => sum + counts[todo.key], 0);
  return <section className="home-page page-shell page-shell--flow wb-flow-width" data-page-layout="flow" aria-labelledby="page-title">
    <div className="home-block">
      <div className="home-heading">
        <h2>待办</h2>
        {total !== undefined && <span className="home-summary">{total ? `共 ${total} 项需处理` : '当前没有需要处理的事'}</span>}
      </div>
      <div className="home-todos">
        {todos.map(todo => {
          const count = counts?.[todo.key];
          const tone = count ? todo.tone : 'neutral';
          return <div key={todo.key} className={`home-tile${count === 0 ? ' home-clear' : ''}`} data-tone={tone}>
            <span className="home-tile-icon"><svg viewBox="0 0 24 24" aria-hidden="true"><path d={todo.icon} /></svg></span>
            <div className="home-tile-copy">
              <h3 className="home-tile-label">{todo.label}</h3>
              <p className="home-tile-detail">{todo.detail}</p>
            </div>
            {count != null ? <p className="home-tile-count">{count}</p>
              : <p className="home-tile-count home-tile-count-reading" aria-hidden="true"><span /></p>}
            <div className="home-tile-action">
              <Link className="home-tile-link" to={`/notices?todo=${todo.key}`}>
                {todo.action}<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12h14m-6-6 6 6-6 6" /></svg>
              </Link>
              <span className={`home-tile-status status-tag status-${tone}`}>
                {count != null && <svg viewBox="0 0 24 24" aria-hidden="true"><path d={count ? 'M12 7v6m0 4h.01' : 'm6 12 4 4 8-8'} /></svg>}
                {count == null ? '待读取' : count ? todo.status : '无待办'}
              </span>
            </div>
          </div>;
        })}
      </div>
      <ReadStatusLane phase={readState} announce="正在读取待办…" className="home-read-lane">
        {(readState === 'error' || readState === 'stale') && <ReadFailure read={query} retained="待办更新失败，保留上次结果。" />}
        {query.isFetching && !reading && <p role="status" className="home-updating">正在更新待办…</p>}
      </ReadStatusLane>
    </div>
  </section>;
}
