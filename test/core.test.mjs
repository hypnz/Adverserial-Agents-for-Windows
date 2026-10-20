import test from 'node:test';
import assert from 'node:assert/strict';
import { loadConfig, validateVerdict, verifierInvocation, runProcess, verify } from '../core.mjs';
const env = { PATH: process.env.PATH };
const config = loadConfig(env);
const valid = () => ({ status: 'verified', trust: 'pinned', verifiedAt: Date.now(),
 config: { modelId: config.model, baseURL: config.remote, hardwareVerifierConfigured: true, trustEvidenceKey: false },
 proof: { status: 'verified', modelId: config.model, endpoint: 'https://api.adverserial.ai', hardwareVerifier: 'fixture-only', devMode: false, expiresEpoch: Date.now()/1000 + 60 } });

test('accepts literal loopback and both canonical models', () => {
 assert.equal(loadConfig({...env, ADVERSERIAL_MODEL:'lordx64/cyberkimi'}).model, 'lordx64/cyberkimi');
 assert.equal(loadConfig({...env, ADVERSERIAL_GATEWAY_URL:'http://[::1]:8787/v1'}).gateway, 'http://[::1]:8787/v1');
});
for (const url of ['https://remote.example/v1','http://localhost:8787/v1','http://127.0.0.1:8787/v1?x=y','http://user@127.0.0.1/v1','http://127.0.0.1:8787/wrong']) {
 test(`rejects unsafe gateway ${url}`, () => assert.throws(() => loadConfig({...env, ADVERSERIAL_GATEWAY_URL:url})));
}
test('rejects endpoint mismatch, TLS bypass, TOFU, invalid model', () => {
 for (const bad of [{ADVERSERIAL_API_URL:'https://other/v1',ADVERSERIAL_CC_API_URL:'https://api.adverserial.ai/v1'}, {NODE_TLS_REJECT_UNAUTHORIZED:'0'}, {ADVERSERIAL_TRUST_EVIDENCE_KEY:'true'}, {ADVERSERIAL_MODEL:'other'}]) assert.throws(()=>loadConfig({...env,...bad}));
});
test('accepts fresh production proof',()=>assert.equal(validateVerdict(valid(),config).ok,true));
for (const [name, change] of [
 ['TOFU', v=>v.trust='tofu'],['dev evidence',v=>v.proof.devMode=true],['wrong model',v=>v.proof.modelId='other'],
 ['wrong endpoint',v=>v.proof.endpoint='https://other'],['missing hardware',v=>delete v.proof.hardwareVerifier],
 ['expired',v=>v.proof.expiresEpoch=1],['stale',v=>v.verifiedAt=1],['future',v=>v.verifiedAt=Date.now()+120000],
 ['wrong config',v=>v.config.baseURL='https://other/v1'],['failure',v=>v.status='failed'],
]) test(`rejects ${name}`,()=>{const v=valid();change(v);assert.throws(()=>validateVerdict(v,config));});
test('rejects relative verifier command',()=>assert.throws(()=>verifierInvocation({ADVERSERIAL_VERIFY_COMMAND:'./fake'})));
test('captures JSON from an actual subprocess',async()=>{
 const r=await runProcess({command:process.execPath,args:['-e','process.stdout.write(JSON.stringify({ok:true}))']},{env,timeoutMs:2000});
 assert.equal(r.ok,true);assert.deepEqual(JSON.parse(r.stdout),{ok:true});
});
test('timeout stops verifier',async()=>assert.equal((await runProcess({command:process.execPath,args:['-e','setInterval(()=>{},1000)']},{env,timeoutMs:50})).ok,false));
test('output cap stops verifier',async()=>assert.equal((await runProcess({command:process.execPath,args:['-e','process.stdout.write("x".repeat(10000))']},{env,timeoutMs:2000,maxBytes:64})).ok,false));
test('cancellation stops verifier',async()=>{
 const ac=new AbortController();const result=runProcess({command:process.execPath,args:['-e','setInterval(()=>{},1000)']},{env,timeoutMs:2000,signal:ac.signal});ac.abort();assert.equal((await result).ok,false);
});
test('spawn error fails closed',async()=>assert.equal((await runProcess({command:'/not/a/real/executable',args:[]},{env,timeoutMs:2000})).ok,false));
test('missing verifier fails closed',async()=>assert.equal((await verify(config)).ok,false));
