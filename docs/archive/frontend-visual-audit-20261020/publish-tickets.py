"""Publish only the thirteen user-approved frontend slices through the local tracker."""
from pathlib import Path
import json,re,subprocess,sys

repo=Path(__file__).resolve().parents[2]
proposal=(repo/'.scratch/frontend-visual-audit/ticket-plan.md').read_text(encoding='utf-8')
art=repo/'.artifacts/frontend-audit-20261018/ticket-publication-20261019'
art.mkdir(parents=True,exist_ok=True)
manifest=art/'publication.json'
if manifest.exists():
    state=json.loads(manifest.read_text(encoding='utf-8'))
else:
    highest=max(int(re.match(r'TAIL-(\d+)',p.name).group(1)) for p in (repo/'.scratch/tails/issues').glob('TAIL-*.md'))
    state={'authorization':'User approved thirteen frontend tickets with implement-solo-spec execution binding; ticket publication only','mapping':{f'{i:02}':highest+i for i in range(1,14)},'published':[]}
    manifest.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
shorts=[x['short'] for x in json.loads((repo/'.scratch/frontend-visual-audit/ticket-publication-input.json').read_text(encoding='utf-8'))]
for i in range(1,14):
    key=f'{i:02}';number=state['mapping'][key]
    section=re.search(r'^## '+key+r' (.+?)\n([\s\S]*?)(?=^## |\Z)',proposal,re.M)
    title,body=section.groups()
    what=re.search(r'\*\*What to build:\*\* (.+)',body).group(1)
    blocker=re.search(r'\*\*Blocked by:\*\* (.+)',body).group(1)
    blocker=re.sub(r'\b(\d{2})\b',lambda m:'TAIL-'+str(state['mapping'][m.group(1)]),blocker)
    blocker=blocker.replace('None (can start immediately after implementation authorization).','None (can start immediately)')
    criteria=[line for line in body.splitlines() if line.startswith('- [ ]')]
    tpath=repo/f'.scratch/tails/issues/TAIL-{number}-{shorts[i-1]}.md'
    if number not in state['published']:
        if tpath.exists():raise RuntimeError(f'Ticket already exists outside this publication: {tpath}')
        args=[sys.executable,'-X','utf8','tools/oneoff/_tail_open.py','--id',str(number),'--what',title,
              '--short',shorts[i-1],'--src','用户批准逐页审计后的13项精修拆分；要求个人工作流可接续',
              '--not-doing',what,'--where','全站界面审计对应页面与个人工作流接续',
              '--when','随时','--why','①逐页审计及拆分已获批准②现有可读性或状态缺陷尚存③保留现有风格和业务契约④按页面行为与累计影响隔离验收',
              '--pre',blocker]
        for apply in [False,True]:
            r=subprocess.run(args+(['--apply'] if apply else []),cwd=repo,text=True,encoding='utf-8',capture_output=True)
            (art/f'ticket-{number}-{"apply" if apply else "dry-run"}.txt').write_text(r.stdout+'\n'+r.stderr,encoding='utf-8')
            if r.returncode:raise RuntimeError(r.stdout+'\n'+r.stderr)
        created=tpath.read_text(encoding='utf-8')
        comments=created[created.index('## Comments'):]
        text=f'# TAIL-{number}: {title}\n\n**What to build:** {what}\n\n**Blocked by:** {blocker}\n\n**Status:** ready-for-agent\n\n'+'\n'.join(criteria)+'\n\n---\n\n'+comments
        text+='\n**2026-10-19 · 个人工作流与授权。** 来源为全站界面审计及已批准拆分第'+key+'项。正式接续调用 implement-solo-spec，按项目 workflow 绑定读取 execution.md，核实际授权、依赖、受影响入口及必要隔离验证，按本票记录与销号；累计整合需要时才按条件读取 coordination.md，不自动派子Agent。当前仅批准拆票，未开始正式开发，不改真实业务数据、不部署或重启。\n'
        tpath.write_text(text,encoding='utf-8',newline='\r\n')
        state['published'].append(number)
        manifest.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
        print(f'Published TAIL-{number}: {title}',flush=True)
print('Thirteen frontend tickets published; no product implementation.',flush=True)
