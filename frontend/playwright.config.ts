import { defineConfig } from '@playwright/test'
const suites = ['workflow', 'ux-recovery', 'transcript']
export default defineConfig({
  testDir: './e2e', fullyParallel: false, workers: 1, timeout: 30000,
  use: { baseURL: process.env.CLAIMFLOW_E2E_URL || 'http://127.0.0.1:8001', viewport: { width:1440,height:1000 }, trace:'retain-on-failure', screenshot:'only-on-failure' },
  projects: suites.map((suite, n) => ({ name:suite, testMatch:`**/${suite}.spec.ts`, use:{baseURL:process.env.CLAIMFLOW_E2E_URL || `http://127.0.0.1:${8001+n}`} })),
  // Each suite gets the real 12-session budget on an isolated local server.
  webServer: process.env.CLAIMFLOW_E2E_URL ? undefined : suites.map((_, n) => ({
    command:`../.venv/bin/python -m uvicorn backend.main:create_app --factory --app-dir .. --host 127.0.0.1 --port ${8001+n}`,
    url:`http://127.0.0.1:${8001+n}/api/health`, reuseExistingServer:false,
    env: { MODEL_MODE:'scripted', DATA_DIR:`/private/tmp/claimflow-e2e-${process.pid}-${n}`, ALLOWED_ORIGINS:`http://127.0.0.1:${8001+n}` },
  })),
})
