"""Network intents wait for focus verification without freezing local UI."""
from pathlib import Path
import shutil
import subprocess


def test_identity_gate_blocks_stale_and_unverified_intents():
    code = r"""
import assert from 'node:assert/strict';
import {createServer} from 'vite';
const server = await createServer({server:{middlewareMode:true,hmr:false,watch:null},appType:'custom'});
try {
  const {beginIdentityVerification,requestJson,setRequestIdentity,uncertainWrite} = await server.ssrLoadModule('/src/api.ts');
  const sent=[];
  globalThis.fetch=async(path,init)=>{sent.push({path,method:init.method});return new Response('{}',{headers:{'Content-Type':'application/json'}})};
  setRequestIdentity('same');
  let finish=beginIdentityVerification();
  const write=requestJson('/write',{method:'POST'});
  await Promise.resolve(); assert.equal(sent.length,0);
  await requestJson('/api/m15/users'); assert.equal(sent.length,1);
  finish(); await write; assert.equal(sent.length,2);

  finish=beginIdentityVerification();
  const stale=assert.rejects(requestJson('/old-account',{method:'POST'}),{name:'AbortError'});
  setRequestIdentity('different'); finish(); await stale;
  assert.equal(sent.length,2,'An old intent must never reach a new account');

  finish=beginIdentityVerification();
  const rejected=assert.rejects(requestJson('/unverified',{method:'POST'}),error=>error.code==='identity_unverified'&&!uncertainWrite(error));
  finish('verification failed'); await rejected;
  assert.equal(sent.length,2);
  await assert.rejects(requestJson('/still-blocked'),error=>error.code==='identity_unverified');

  finish=beginIdentityVerification();
  const controller=new AbortController();
  const cancelled=assert.rejects(requestJson('/cancelled',{signal:controller.signal}),{name:'AbortError'});
  controller.abort();await cancelled;finish();assert.equal(sent.length,2);

  const old=beginIdentityVerification(), newer=beginIdentityVerification();
  const waiting=requestJson('/after-newer'); old(); await Promise.resolve();await Promise.resolve();
  assert.equal(sent.length,2,'Superseded checks must not release a newer gate');
  newer();await waiting;assert.equal(sent.length,3);
  console.log('Identity verification preserves same-account intents and blocks stale/unverified requests');
} finally {await server.close()}
"""
    node = shutil.which('node')
    assert node
    result = subprocess.run([node, '--input-type=module', '-e', code], cwd=Path(__file__).resolve().parents[1], capture_output=True, encoding='utf-8')
    assert result.returncode == 0, result.stdout + result.stderr
