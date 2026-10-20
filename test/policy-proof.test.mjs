import test from 'node:test';
import assert from 'node:assert/strict';
import * as fs from 'node:fs/promises';
import * as path from 'node:path';
import * as os from 'node:os';
import { loadConfig, verify } from '../core.mjs';

test('actual verifier subprocess must match every published artifact and TLS pin', async () => {
  const temp=await fs.mkdtemp(path.join(os.tmpdir(),'kit policy '));
  try {
    const folder=path.join(temp,'plugins/adverserial-verify/bin');await fs.mkdir(folder,{recursive:true});
    await fs.writeFile(path.join(folder,'adverserial-verify.mjs'), `if(process.env.ADVERSERIAL_API_KEY||process.env.ADVERSERIAL_UPSTREAM_API_KEY||process.env.ADVERSERIAL_LOCAL_GATEWAY_TOKEN)process.exit(9);console.log(JSON.stringify({status:'verified',trust:'pinned',verifiedAt:Date.now(),config:{modelId:'lordx64/cyberglm',baseURL:'https://api.adverserial.ai/v1',hardwareVerifierConfigured:true,trustEvidenceKey:false},proof:{status:'verified',modelId:'lordx64/cyberglm',endpoint:'https://api.adverserial.ai',hardwareVerifier:'FIXTURE ONLY',devMode:false,expiresEpoch:Date.now()/1000+60,modelDigest:'sha256:model',runtimeDigest:'sha256:runtime',composeDigest:'sha256:compose',tlsSpkiSha256:'sha256:tls'}}));`);
    const policy={status:'active',model_id:'lordx64/cyberglm',model_artifact_digest:'sha256:model',runtime_image_digest:'sha256:runtime',deployment_configuration_digest:'sha256:compose',tls_spki_sha256:'sha256:tls'};
    const file=path.join(temp,'policy.json');await fs.writeFile(file,JSON.stringify(policy));
    const config=loadConfig({ADVERSERIAL_SDK_DIR:temp,ADVERSERIAL_NODE_BINARY:process.execPath,ADVERSERIAL_POLICY_FILE:file,ADVERSERIAL_API_KEY:'do-not-forward',ADVERSERIAL_UPSTREAM_API_KEY:'do-not-forward',ADVERSERIAL_LOCAL_GATEWAY_TOKEN:'do-not-forward'});
    assert.equal((await verify(config)).ok,true);
    for(const field of ['model_artifact_digest','runtime_image_digest','deployment_configuration_digest','tls_spki_sha256']) {
      await fs.writeFile(file,JSON.stringify({...policy,[field]:'sha256:wrong'}));
      assert.equal((await verify(config)).ok,false,field);
    }
    await fs.writeFile(file,JSON.stringify({...policy,status:'inactive'}));assert.equal((await verify(config)).ok,false);
  } finally {await fs.rm(temp,{recursive:true,force:true});}
});
