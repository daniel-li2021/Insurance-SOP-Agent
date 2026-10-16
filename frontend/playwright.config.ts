import { defineConfig } from '@playwright/test'
export default defineConfig({
  testDir: './e2e', fullyParallel: false, workers: 1, timeout: 30000,
  use: { baseURL: process.env.CLAIMFLOW_E2E_URL || 'http://127.0.0.1:8001', viewport: { width:1440,height:1000 }, trace:'retain-on-failure', screenshot:'only-on-failure' },
  webServer: process.env.CLAIMFLOW_E2E_URL ? undefined : {
    command:'../.venv/bin/python -m uvicorn backend.main:create_app --factory --app-dir .. --host 127.0.0.1 --port 8001',
    url:'http://127.0.0.1:8001/api/health', reuseExistingServer:false,
    env: { MODEL_MODE:'scripted', DATA_DIR:`/private/tmp/claimflow-e2e-${process.pid}`, ALLOWED_ORIGINS:'http://127.0.0.1:8001' },
  },
})
