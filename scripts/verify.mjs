import { loadConfig, verify } from '../core.mjs';
try {
  const result = await verify(loadConfig());
  console.log(result.output);
  process.exitCode = result.ok ? 0 : 1;
} catch (error) {
  console.error(error.message);
  process.exitCode = 1;
}
