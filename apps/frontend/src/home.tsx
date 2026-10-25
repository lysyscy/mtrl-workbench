import Button from 'antd/es/button';
import { Link } from 'react-router';
import { useQuery } from '@tanstack/react-query';
import { requestJson } from './api';
import { live, readNotices } from './notices-api';
import './home.css';

// The three home todos are the same backend truth the notices page renders:
// counts come from /api/m03/notice-list with the shared ['notices'] query, so a
// tile count always equals the row set its deep link lands on (TAIL-421).
export function HomePage({ blocked, active }: { blocked: boolean; active: boolean }) {
  const query = useQuery({ queryKey: ['notices'], enabled: !blocked && active, queryFn: async ({ signal }) => readNotices(await requestJson('/api/m03/notice-list?period=', { signal })), refetchOnMount: 'always' });
  const rows = query.data ?? [];
  const todos = [
    { key: 'ownership', label: '归属待指定', detail: '尚未确定所属项目的通知书', action: '去指定归属', tone: 'wn', count: rows.filter(r => live(r) && !r.ownership_id).length },
    { key: 'jc', label: '集采未关联合同', detail: '未关联合同且未付清的集采通知书', action: '去关联合同', tone: 'wn', count: rows.filter(r => live(r) && r.category === 'jc' && !r.has_link && r.pay_status === '未付清').length },
    { key: 'void', label: '撤单但有牵涉', detail: 'i8 已撤单，仍有付款或合同关联', action: '去处理', tone: 'dg', count: rows.filter(r => live(r) && r.is_revoked).length },
  ];
  const total = todos.reduce((sum, todo) => sum + todo.count, 0);
  return <section className="home-page" aria-labelledby="page-title">
    <div className="home-block">
      <h2>待办{query.data && <span className="home-summary">{total ? `共 ${total} 项需处理` : '当前没有需要处理的事'}</span>}</h2>
      {query.isPending ? <p role="status">正在读取待办…</p> : query.isError ? <div className="notice" role="alert"><span>{query.error.message}</span><Button htmlType="submit" onClick={() => void query.refetch()}>重读待办</Button></div> : <>
        <div className="home-todos">
          {todos.map(todo => <div key={todo.key} className={`home-tile home-${todo.tone}${todo.count ? '' : ' home-clear'}`}>
            <p className="home-tile-label">{todo.label}</p>
            <p className="home-tile-count">{todo.count}</p>
            <p className="home-tile-detail">{todo.detail}</p>
            <Link className="home-tile-link" to={`/notices?todo=${todo.key}`}>{todo.action}</Link>
          </div>)}
        </div>
        {query.isFetching && <p role="status" className="home-updating">正在更新待办…</p>}
      </>}
    </div>
  </section>;
}
