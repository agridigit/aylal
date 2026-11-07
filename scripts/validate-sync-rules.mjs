// Validates a PowerSync sync-rules file with the same parser as the service (run inside its image).
import { readFileSync } from 'node:fs';
import { SqlSyncRules, DEFAULT_TAG } from '/app/packages/sync-rules/dist/index.js';

const file = process.argv[2];
const { errors } = SqlSyncRules.fromYaml(readFileSync(file, 'utf8'), {
  defaultSchema: 'public',
  throwOnError: false
});
const fatal = errors.filter((e) => e.type === 'fatal');
for (const e of errors) console.error(`${e.type}: ${e.message}`);
process.exit(fatal.length ? 1 : 0);
