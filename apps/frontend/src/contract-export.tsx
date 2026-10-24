import Button from 'antd/es/button';
import { useEffect, useRef, useState } from 'react';
import type { Project } from './api';
import { ProjectExport } from './ledger-controls';
import { loadContractExport } from './contract-export-api';

// getIds reads every filtered grid row in its current sort order, including virtual rows.
export function ContractExports({ owner, projects, project, getIds, scope, unavailable, paused }: {
  owner: string; projects: Project[]; project: number; getIds: () => number[];
  scope: string; unavailable: string; paused: boolean;
}) {
  const [busy, setBusy] = useState(false), [feedback, setFeedback] = useState('');
  const request = useRef<AbortController | null>(null), lock = useRef(false);
  const current = useRef({ owner, scope, unavailable, paused }); current.current = { owner, scope, unavailable, paused };
  useEffect(() => {
    request.current?.abort(); setFeedback('');
    return () => { request.current?.abort(); };
  }, [owner, scope, unavailable, paused]);
  const valid = () => current.current.owner === owner && current.current.scope === scope && !current.current.unavailable && !current.current.paused && !request.current?.signal.aborted;
  async function run(action: () => Promise<void>): Promise<string | null> {
    if (current.current.owner !== owner || current.current.scope !== scope || current.current.unavailable || current.current.paused || lock.current) return null;
    lock.current = true; request.current = new AbortController(); setBusy(true); setFeedback('');
    try { await action(); return null; }
    catch (error) { return valid() ? error instanceof Error ? error.message : '导出失败，请重试。' : null; }
    finally { lock.current = false; setBusy(false); }
  }
  async function ordinary() {
    const failure = await run(async () => {
      const result = await loadContractExport('ordinary', getIds(), request.current!.signal);
      if (!valid()) return;
      const url = URL.createObjectURL(result.blob), link = document.createElement('a');
      link.href = url; link.download = result.filename; link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000); setFeedback('集采台账已导出。');
    });
    if (failure) setFeedback(failure);
  }
  const reason = unavailable || (paused ? '当前页面暂不可操作。' : busy ? '正在生成文件，请稍候。' : '');
  return <>
    <Button type="primary" disabled={Boolean(reason)} title={reason || '导出当前筛选及排序的全部合同，包含隐藏贸易列'} onClick={() => void ordinary()}>导出 Excel</Button>
    <ProjectExport kind="contracts-print" owner={owner} projects={projects} project={project}
      unavailable={reason} paused={paused} run={run} valid={valid} signal={undefined} message={setFeedback}
      title="导出打印版" description="按所选项目的全部纳入合同生成，各项目独立工作表。" summary={count => `已选 ${count} 个项目，按以下顺序导出。`}
      success="集采打印台账已导出。" exportFile={chosen => loadContractExport('print', chosen.map(item => item.warehouse_name!), request.current!.signal)} />
    {feedback && <span role="status">{feedback}</span>}
  </>;
}
