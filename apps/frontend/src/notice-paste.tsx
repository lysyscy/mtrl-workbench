import Button from 'antd/es/button';
import { BusinessModal } from './business-modal';
import { useEffect, useRef, useState } from 'react';
import { archiveLabel, money, matchNoticeCodes } from './notices-api';
import type { NoticeRow } from './notices-api';
import { DialogContents, useDialogClose } from './dialog-close';

export function NoticePaste({ blocked, close, read, apply, process }: { blocked: boolean; close: () => void; read: () => Promise<NoticeRow[]>; apply: (ids: number[]) => void; process: (ids: number[]) => void }) {
  const [raw,setRaw] = useState(''), [report,setReport] = useState<ReturnType<typeof matchNoticeCodes> | null>(null), [busy,setBusy] = useState(false), [error,setError] = useState('');
  const lock = useRef(false), alive = useRef(true), paused = useRef(blocked);
  paused.current = blocked;
  useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  const closing = useDialogClose({ active: !blocked, busy, dirty: !report && raw !== '', close });
  async function match() {
    if (blocked || lock.current) return;
    if (!raw.trim()) { setError('请先粘贴单据号。'); return; }
    lock.current = true; setBusy(true); setError('');
    try {
      const rows = await read();
      if (!alive.current || paused.current) return;
      const result = matchNoticeCodes(raw,rows); if (result.ids.length) apply(result.ids); setReport(result);
    } catch (failure) { if (alive.current) setError(failure instanceof Error ? failure.message : '通知书读取失败，请重试。'); }
    finally { lock.current = false; if (alive.current) setBusy(false); }
  }
  const groups: [string,string[]][] = report ? [['未识别为单据号的文本',report.invalid],['未找到的单据号',report.missing],['系统重号，未勾选',report.ambiguous],['重复输入，已合并',report.duplicates],['已付清，仍可打印',report.paid]] : [];
  return <BusinessModal open={!blocked} layout="scroll-body" className="project-dialog notice-dialog notice-paste-dialog" titleId="notice-paste-title" requestClose={closing.requestClose}><DialogContents titleId="notice-paste-title" title={report ? '单据号勾选结果' : '粘贴单据号勾选'} closing={closing}>
    {!report ? <form className="dialog-form" onSubmit={event => { event.preventDefault(); void match(); }}>
      <div className="dialog-body">
        <label>单据号<textarea aria-label="单据号" autoFocus rows={7} value={raw} disabled={busy} placeholder="从 Excel 复制单据号列，粘贴到这里" onChange={event => setRaw(event.target.value)} /></label>
        <p className="muted">格式为 FKTZS＋六位年月＋四位序号。可用换行、空格、逗号、分号、顿号、斜线或竖线分隔。</p>
        <p>命中后将<strong>替换当前勾选并清空筛选</strong>，匹配项置顶。</p>
        {error && <p role="alert" className="notice">{error}</p>}
      </div>
      <div className="dialog-actions">
        <Button htmlType="button" disabled={busy} onClick={closing.requestClose}>取消</Button>
        <Button htmlType="submit" type="primary" loading={busy} disabled={blocked}>匹配并勾选</Button>
      </div>
    </form> : <>
      <div className="dialog-body">
      <p>输入 {report.total} 段文本。{report.ids.length ? `已勾选 ${report.ids.length} 条，集中在表格顶部。` : '没有可勾选的单据，原勾选保持不变。'}</p>
      {groups.filter(([,items]) => items.length).map(([name,items]) => <div key={name}><h3>{name}（{items.length} 条）</h3><p>{items.join('、')}</p></div>)}
      {report.blocked.length > 0 && <div><h3>已剔除或撤单的未勾选单据（{report.blocked.length} 条）</h3><Button htmlType="button" disabled={blocked} onClick={() => { process(report.blocked.map(row => row.notice_id)); close(); }}>去处理</Button>{report.blocked.map(row => <div key={row.notice_id}><b>{row.bill_no}</b> <span className={`notice-tag ${row.is_excluded ? row.exclude_source : 'revoked'}`} title={row.exclude_rule_hint}>{archiveLabel(row)}</span>{row.is_excluded && row.is_revoked && '，i8 已撤单'}<p>{row.bill_name}，{row.project_display}，{row.doc_date}，{row.payee}，审批金额 {money(row.amount_approved)} 元</p></div>)}</div>}
      </div>
      <div className="dialog-actions"><Button htmlType="button" onClick={() => setReport(null)}>修改清单</Button><Button htmlType="button" type="primary" onClick={closing.requestClose}>完成</Button></div>
    </>}
  </DialogContents></BusinessModal>;
}
