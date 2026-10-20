"""Publish only the six user-approved machinery slices through the local tracker."""
from pathlib import Path
import json,re,subprocess,sys

repo=Path(__file__).resolve().parents[2]
proposal=(repo/'.scratch/machinery-fee-workflow/ticket-plan.md').read_text(encoding='utf-8')
art=repo/'.artifacts/machinery-fee-workflow/prototype-20261017'
manifest=art/'business-ticket-publication.json'
if manifest.exists():
    state=json.loads(manifest.read_text(encoding='utf-8'))
else:
    highest=max(int(re.match(r'TAIL-(\d+)',p.name).group(1)) for p in (repo/'.scratch/tails/issues').glob('TAIL-*.md'))
    state={'authorization':'User approved six machinery tickets; visual tickets deferred pending page audit; no implementation','mapping':{f'{i:02}':highest+i for i in range(1,7)},'published':[]}
    manifest.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
shorts=['零租明细确认与汇总','包月与内租维护','原报录入与历史接续','机械费i8累计核对','机械费忽略与事项','机械费原四页导出']
for i in range(1,7):
    key=f'{i:02}';number=state['mapping'][key]
    section=re.search(r'^## '+key+r' (.+?)\n([\s\S]*?)(?=^## |\Z)',proposal,re.M)
    title,body=section.groups()
    what=re.search(r'\*\*What to build:\*\* (.+)',body).group(1)
    blocker=re.search(r'\*\*Blocked by:\*\* (.+)',body).group(1)
    blocker=re.sub(r'\b(0[1-6])\b',lambda m:'TAIL-'+str(state['mapping'][m.group(1)]),blocker)
    blocker=blocker.replace('None (can start immediately after implementation authorization).','None (can start immediately)')
    criteria=[line for line in body.splitlines() if line.startswith('- [ ]')]
    tpath=repo/f'.scratch/tails/issues/TAIL-{number}-{shorts[i-1]}.md'
    if number not in state['published']:
        if tpath.exists():raise RuntimeError(f'Ticket already exists outside this publication: {tpath}')
        args=[sys.executable,'-X','utf8','tools/oneoff/_tail_open.py','--id',str(number),'--what',title,
              '--short',shorts[i-1],'--src','用户确认机械费原型定稿并批准6张业务票；精修票另行审计',
              '--not-doing',what,'--where','机械费定稿方案对应切片；保留现有有效金额出口',
              '--when','随时','--why','①原型已获验收②正式能力尚未实现③复用既有模块与共享出口④按本票隔离验收与真实数据边界验证',
              '--pre',blocker]
        for apply in [False,True]:
            r=subprocess.run(args+(['--apply'] if apply else []),cwd=repo,text=True,encoding='utf-8',capture_output=True)
            (art/f'ticket-{number}-{"apply" if apply else "dry-run"}.txt').write_text(r.stdout+'\n'+r.stderr,encoding='utf-8')
            if r.returncode:raise RuntimeError(r.stdout+'\n'+r.stderr)
        created=tpath.read_text(encoding='utf-8')
        comments=created[created.index('## Comments'):]
        text=f'# TAIL-{number}: {title}\n\n**What to build:** {what}\n\n**Blocked by:** {blocker}\n\n**Status:** ready-for-agent\n\n'+'\n'.join(criteria)+'\n\n---\n\n'+comments
        text+='\n**2026-10-18 · 方案与授权边界。** 最终业务依据为机械费定稿方案一至十一节；本票对应经用户批准的业务切片'+key+'。发布不代表开工授权，当前不开发正式功能、不迁移生产、不导入真实业务、不重启服务或写i8。原型及本机证据不等同正式能力已验收。\n'
        tpath.write_text(text,encoding='utf-8',newline='\r\n')
        state['published'].append(number)
        manifest.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
        print(f'Published TAIL-{number}: {title}',flush=True)
print('Six machinery tickets published; no visual tickets or product implementation.',flush=True)
