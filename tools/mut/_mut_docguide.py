"""历史原型导读边界的反向灵敏度：仅在子进程内存替换输入，交付面不写靶。"""
from pathlib import Path
import json
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools/audit'))
from audit_common import delivery_root


def main():
    root=delivery_root();assert root,'需配置真实交付面才能核对导读边界'
    checker=root/'demo/_doccheck.js';guide=root/'demo/原型导读.md'
    node=shutil.which('node');assert node,'需Node运行真实文档检查'
    # VM运行原检查器，只代理导读读取；其它输入仍只读，不复制素材或修改工作文件。
    harness=r'''
const fs=require('fs'),path=require('path'),vm=require('vm');
const cfg=JSON.parse(process.argv[1]);
const proxy=Object.create(fs);
proxy.readFileSync=(file,...args)=>{
  const value=fs.readFileSync(file,...args);
  return path.resolve(file)===path.resolve(cfg.guide)&&cfg.old ? value.replace(cfg.old,cfg.new) : value;
};
vm.runInNewContext(fs.readFileSync(cfg.checker,'utf8'),{
  require:name=>name==='fs'?proxy:require(name),__dirname:path.dirname(cfg.checker),console,process
},{filename:cfg.checker});
'''
    def probe(old='',new=''):
        payload=json.dumps(dict(checker=str(checker),guide=str(guide),old=old,new=new),ensure_ascii=False)
        return subprocess.run([node,'-e',harness,payload],capture_output=True,text=True,
                              encoding='utf-8',timeout=15)
    original=guide.read_bytes();text=original.decode('utf-8')
    normal=probe();assert normal.returncode==0,normal.stdout+normal.stderr
    for label,old,new in [
        ('去掉历史用途','已不决定当前运行界面','仍决定当前运行界面'),
        ('去掉现行主人','当前业务目标回说明书与PRD','当前业务目标回原型'),
        ('复活现行原型基准','历史交互留痕','现行交互基准'),
    ]:
        assert text.count(old)==1,(label,text.count(old))
        red=probe(old,new)
        assert red.returncode==1 and 'FAIL  demo/原型导读.md' in red.stdout and '历史用途与当前权威边界' in red.stdout,red.stdout+red.stderr
        print(label+'：正常绿/缺陷红',flush=True)
    assert guide.read_bytes()==original
    print('3/3 文档边界反向灵敏度通过；仓外文件未写靶')


if __name__=='__main__':
    main()
