import { spawn } from 'node:child_process';
import * as fs from 'node:fs';
import * as path from 'node:path';

export const PROVIDER = 'adverserial-confidential';
export const SDK_REVISION = '527b9f4942d2ea1a26fdfaeebb8bddbba404bdc9';
const MODELS = new Set(['lordx64/cyberglm', 'lordx64/cyberkimi']);

function positive(env, key, fallback, maximum) {
  const value = Number(env[key] ?? fallback);
  if (!Number.isSafeInteger(value) || value < 1 || value > maximum) throw new Error(`${key} must be an integer from 1 to ${maximum}.`);
  return value;
}

export function loadConfig(env = process.env) {
  const gateway = new URL(env.ADVERSERIAL_GATEWAY_URL || 'http://127.0.0.1:8787/v1');
  // Literal loopback avoids DNS resolving a hostname onto a remote interface.
  if (gateway.protocol !== 'http:' || !['127.0.0.1', '[::1]'].includes(gateway.hostname) ||
      gateway.username || gateway.password || gateway.search || gateway.hash || gateway.pathname.replace(/\/$/, '') !== '/v1') {
    throw new Error('ADVERSERIAL_GATEWAY_URL must be http://127.0.0.1:<port>/v1 or http://[::1]:<port>/v1 without credentials or query.');
  }
  const remote = new URL(env.ADVERSERIAL_CC_API_URL || env.ADVERSERIAL_API_URL || 'https://api.adverserial.ai/v1');
  if (remote.protocol !== 'https:' || remote.username || remote.password || remote.search || remote.hash) throw new Error('Remote endpoint must be a plain HTTPS URL.');
  if (env.ADVERSERIAL_CC_API_URL && env.ADVERSERIAL_API_URL && env.ADVERSERIAL_CC_API_URL.replace(/\/$/, '') !== env.ADVERSERIAL_API_URL.replace(/\/$/, '')) {
    throw new Error('ADVERSERIAL_CC_API_URL and ADVERSERIAL_API_URL must identify the same endpoint.');
  }
  const model = env.ADVERSERIAL_MODEL || 'lordx64/cyberglm';
  if (!MODELS.has(model)) throw new Error('ADVERSERIAL_MODEL must be lordx64/cyberglm or lordx64/cyberkimi.');
  if (env.ADVERSERIAL_TRUST_EVIDENCE_KEY && !['0', 'false'].includes(env.ADVERSERIAL_TRUST_EVIDENCE_KEY.toLowerCase())) throw new Error('TOFU/dev trust is not supported by this Hermes integration.');
  if (env.NODE_TLS_REJECT_UNAUTHORIZED === '0') throw new Error('TLS validation must remain enabled.');
  return Object.freeze({
    gateway: gateway.href.replace(/\/$/, ''), remote: remote.href.replace(/\/$/, ''), model,
    timeoutMs: positive(env, 'ADVERSERIAL_VERIFY_TIMEOUT_MS', 25000, 120000),
    env: { ...env, ADVERSERIAL_API_URL: remote.href.replace(/\/$/, ''), ADVERSERIAL_MODEL: model, ADVERSERIAL_TRUST_EVIDENCE_KEY: '0' },
  });
}

function executable(filename) {
  if (!path.isAbsolute(filename)) throw new Error('Verifier and runtime paths must be absolute.');
  const resolved = fs.realpathSync(filename);
  if (!fs.statSync(resolved).isFile()) throw new Error('Executable path must name a file.');
  fs.accessSync(resolved, fs.constants.X_OK);
  return resolved;
}

export function verifierInvocation(env = process.env) {
  if (env.ADVERSERIAL_VERIFY_COMMAND) return { command: executable(env.ADVERSERIAL_VERIFY_COMMAND), args: ['--json'] };
  if (!env.ADVERSERIAL_SDK_DIR || !path.isAbsolute(env.ADVERSERIAL_SDK_DIR)) throw new Error('Set ADVERSERIAL_SDK_DIR to the absolute kit resources directory, or set ADVERSERIAL_VERIFY_COMMAND to an absolute executable.');
  const script = fs.realpathSync(path.join(env.ADVERSERIAL_SDK_DIR, 'plugins/adverserial-verify/bin/adverserial-verify.mjs'));
  if (!fs.statSync(script).isFile()) throw new Error('SDK verifier bundle is missing.');
  fs.accessSync(script, fs.constants.R_OK);
  let node = env.ADVERSERIAL_NODE_BINARY;
  if (!node && process.release.name === 'node' && !process.versions.bun) node = process.execPath;
  if (!node) {
    for (const dir of (env.PATH || '').split(path.delimiter)) {
      if (!path.isAbsolute(dir)) continue;
      const candidate = path.join(dir, process.platform === 'win32' ? 'node.exe' : 'node');
      try { node = executable(candidate); break; } catch { /* try next absolute PATH entry */ }
    }
  }
  if (!node) throw new Error('Install Node.js or set ADVERSERIAL_NODE_BINARY to its absolute path. The SDK verifier must run through Node.js.');
  return { command: executable(node), args: [script, '--json'] };
}

export function runProcess(invocation, { env, timeoutMs, signal, maxBytes = 262144 }) {
  return new Promise((resolve) => {
    if (signal?.aborted) return resolve({ ok: false, output: 'Verification cancelled.' });
    const child = spawn(invocation.command, invocation.args, { env, shell: false, windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'] });
    let stdout = '', stderr = '', bytes = 0, settled = false;
    const finish = (result) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      signal?.removeEventListener('abort', abort);
      resolve(result);
    };
    const stop = (output) => { child.kill('SIGKILL'); finish({ ok: false, output }); };
    const abort = () => stop('Verification cancelled.');
    const timer = setTimeout(() => stop(`Verification timed out after ${timeoutMs} ms.`), timeoutMs);
    signal?.addEventListener('abort', abort, { once: true });
    if (signal?.aborted) abort();
    const collect = (which, chunk) => {
      bytes += chunk.length;
      if (bytes > maxBytes) return stop('Verifier output exceeded the size limit.');
      if (which === 'stdout') stdout += chunk.toString('utf8'); else stderr += chunk.toString('utf8');
    };
    child.stdout.on('data', chunk => collect('stdout', chunk));
    child.stderr.on('data', chunk => collect('stderr', chunk));
    child.once('error', error => finish({ ok: false, output: `Could not start verifier: ${error.message}` }));
    child.once('close', code => finish({ ok: code === 0, stdout, output: stderr.trim() || stdout.trim() || `Verifier exited ${code}.` }));
  });
}

export function validateVerdict(value, config, now = Date.now()) {
  const p = value?.proof, c = value?.config;
  if (value?.status !== 'verified' || value.trust !== 'pinned' || p?.status !== 'verified' || p.devMode !== false || !p.hardwareVerifier || !c?.hardwareVerifierConfigured || c.trustEvidenceKey !== false) throw new Error('Verifier did not return pinned, production hardware verification.');
  if (p.modelId !== config.model || c.modelId !== config.model || c.baseURL?.replace(/\/$/, '') !== config.remote) throw new Error('Verifier model or endpoint does not match the Hermes provider.');
  if (p.endpoint !== (config.env.ADVERSERIAL_EXPECTED_ENDPOINT || new URL(config.remote).origin)) throw new Error('Attested endpoint does not match the expected endpoint.');
  if (!Number.isFinite(value.verifiedAt) || value.verifiedAt > now + 5000 || now - value.verifiedAt > 60000 || !Number.isFinite(p.expiresEpoch) || p.expiresEpoch * 1000 <= now) throw new Error('Verifier proof is stale or expired.');
  return { ok: true, output: `Verified ${config.model}; pinned hardware proof accepted. Gateway validates each inference receipt.`, expiresAt: Math.min(p.expiresEpoch * 1000, value.verifiedAt + 300000) };
}

export async function verify(config, signal) {
  try {
    const invocation = verifierInvocation(config.env);
    // Verification never needs the billing credential.
    const env = { ...config.env };
    for (const name of ['ADVERSERIAL_API_KEY', 'ADVERSERIAL_UPSTREAM_API_KEY', 'ADVERSERIAL_LOCAL_GATEWAY_TOKEN', 'ADVERSERIAL_HERMES_SESSION_KEY', 'OPENAI_API_KEY']) delete env[name];
    const result = await runProcess(invocation, { env, timeoutMs: config.timeoutMs, signal });
    if (!result.ok) return { ok: false, output: 'Attestation failed. Run the SDK verifier directly for diagnostics.' };
    const verdict = JSON.parse(result.stdout);
    const accepted = validateVerdict(verdict, config);
    if (config.env.ADVERSERIAL_POLICY_FILE) {
      const policy = JSON.parse(fs.readFileSync(config.env.ADVERSERIAL_POLICY_FILE, 'utf8'));
      if (policy.status !== 'active' || policy.model_id !== config.model) throw new Error('Active policy does not match the selected model.');
      for (const [pin, field] of [['model_artifact_digest','modelDigest'], ['runtime_image_digest','runtimeDigest'], ['deployment_configuration_digest','composeDigest'], ['tls_spki_sha256','tlsSpkiSha256']]) {
        if (policy[pin] && policy[pin] !== verdict.proof[field]) throw new Error(`Attestation does not match the published ${pin}.`);
      }
    }
    return accepted;
  } catch (error) {
    return { ok: false, output: `Verification unavailable: ${error.message}` };
  }
}
