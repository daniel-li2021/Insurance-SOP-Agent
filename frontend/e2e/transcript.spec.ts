import { test, expect, type Page } from '@playwright/test'

const identity = 'My name is Margaret Chen, policy POL-9921. My DOB is 1985-03-15, and my SSN last four is 4472.'
const values = ['Margaret Chen', 'POL-9921', '1985-03-15', '4472']

async function message(page: Page, text: string) {
  const input = page.getByRole('textbox', { name: 'Message ClaimFlow' })
  await expect(input).toBeEnabled()
  await input.fill(text)
  await page.getByRole('button', { name: 'Send message', exact: true }).click()
  await expect(input).toBeEnabled()
}

async function safeHistory(page: Page, rawValues = values) {
  const response = await page.request.get('/api/session')
  expect(response.ok()).toBe(true)
  const saved = await response.json()
  for (const value of rawValues) {
    expect(JSON.stringify(saved)).not.toContain(value)
    await expect(page.locator('.inspector-panel')).not.toContainText(value)
    expect(await page.evaluate(() => JSON.stringify({ local: localStorage, session: sessionStorage }))).not.toContain(value)
  }
}

test('manual submitted identity is visible only after matching confirmation; refresh and other tabs stay redacted', async ({ page, context }) => {
  await page.goto('/')
  let release!: () => void
  const gate = new Promise<void>(resolve => { release = resolve })
  await page.route('**/api/turn', async route => {
    const response = await route.fetch()
    const confirmed = await response.json()
    expect(confirmed.messages.find((m: { id: string }) => m.id === route.request().postDataJSON().request_id).text).toContain('[name provided]')
    for (const value of values) expect(JSON.stringify(confirmed)).not.toContain(value)
    await gate
    await route.fulfill({ response })
  })
  await page.getByRole('textbox', { name: 'Message ClaimFlow' }).fill(identity)
  await page.getByRole('button', { name: 'Send message', exact: true }).click()
  await expect(page.locator('.pending-message')).toContainText('personal details hidden')
  await expect(page.locator('.pending-message')).not.toContainText('Margaret Chen')
  release()
  await expect(page.locator('.user-message .message-text')).toHaveText(identity)
  await safeHistory(page)
  const other = await context.newPage()
  await other.goto('/')
  await expect(other.locator('.user-message')).toContainText('[name provided]')
  await expect(other.locator('.user-message')).not.toContainText('Margaret Chen')
  await page.locator('.user-message').scrollIntoViewIfNeeded()
  await expect(page.locator('.user-message .message-text')).toBeInViewport()
  await page.screenshot({ path: '../data/transcript-manual.png', fullPage: true })
  await page.reload()
  await expect(page.locator('.user-message')).toContainText('[name provided]')
  for (const value of values) await expect(page.locator('.user-message')).not.toContainText(value)
  await expect(page.getByRole('button', { name: 'Hide submitted details', exact: true })).toHaveCount(0)
})

test('unmatched identity needs no verification; unconfirmed IDs never reveal text; Hide forgets originals', async ({ page }) => {
  await page.goto('/')
  await page.route('**/api/turn', async route => {
    const response = await route.fetch()
    const data = await response.json()
    const id = route.request().postDataJSON().request_id
    data.messages = data.messages.map((m: { id: string }) => m.id === id ? { ...m, id: 'different-confirmation' } : m)
    await route.fulfill({ response, json: data })
    await page.unroute('**/api/turn')
  })
  await message(page, 'My name is Avery Rivers.')
  await expect(page.locator('.user-message')).toContainText('[name provided]')
  await expect(page.locator('.user-message')).not.toContainText('Avery Rivers')
  const unknown = 'My name is Jordan Avery. My DOB is 1990-07-09, SSN last four 1234.'
  await message(page, unknown)
  await expect(page.locator('.user-message .message-text').last()).toHaveText(unknown)
  await expect(page.locator('.inspector-panel')).toContainText('Locked until verified')
  await expect(page.locator('.user-message').first()).not.toContainText('Avery Rivers')
  await safeHistory(page, ['Avery Rivers', 'Jordan Avery', '1990-07-09', '1234'])
  await page.getByRole('button', { name: 'Hide submitted details', exact: true }).click()
  await expect(page.locator('.user-message').last()).toContainText('[name provided]')
  await expect(page.locator('.user-message').last()).not.toContainText('Jordan Avery')
  await message(page, 'What is the status?')
  await expect(page.locator('.user-message').nth(1)).not.toContainText('Jordan Avery')
})

test('guided scenario keeps original opening, Sources and Summary work, Hide works on mobile', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: /Try a guided scenario/ }).click()
  const opening = await page.locator('.demo-opening').innerText()
  await page.getByRole('button', { name: 'Use this opening message', exact: true }).click()
  await expect(page.getByRole('textbox', { name: 'Message ClaimFlow' })).toHaveValue(opening)
  await page.getByRole('button', { name: 'Send message', exact: true }).click()
  await expect(page.locator('.user-message .message-text')).toHaveText(opening)
  await page.locator('.message-grounding').last().locator('summary').click()
  await expect(page.locator('.message-grounding').last()).toContainText('Claim CL-2048 record')
  await safeHistory(page)
  await page.getByRole('button', { name: 'Review summary', exact: true }).click()
  await expect(page.locator('.summary-content')).toContainText('CL-2048')
  await page.getByRole('button', { name: 'Skip', exact: true }).click()
  await expect(page.locator('.summary-result')).toContainText('Skipped')
  await page.setViewportSize({ width: 390, height: 844 })
  const hide = page.getByRole('button', { name: 'Hide submitted details', exact: true })
  await expect(hide).toBeInViewport()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.locator('.user-message').scrollIntoViewIfNeeded()
  await expect(page.locator('.user-message .message-text')).toBeInViewport()
  await page.screenshot({ path: '../data/transcript-mobile.png', fullPage: true })
  await hide.click()
  await expect(page.locator('.user-message')).toContainText('[name provided]')
  await expect(page.locator('.user-message')).not.toContainText('Margaret Chen')
})

test('Optional Form displays only submitted values even on mismatch, synthetic autofill stays editable', async ({ page }) => {
  await page.goto('/')
  await page.locator('.verification-form>summary').click()
  await page.getByRole('textbox', { name: 'Full name', exact: true }).fill('Avery Rivers')
  await page.getByRole('textbox', { name: 'Date of birth', exact: true }).fill('1990-07-09')
  await page.getByRole('textbox', { name: 'Phone', exact: true }).fill('2025550100')
  await page.getByRole('button', { name: 'Verify details', exact: true }).click()
  await expect(page.locator('.user-message .message-text')).toHaveText('Full name: Avery Rivers\nDate of birth: 1990-07-09\nPhone: 2025550100')
  await expect(page.locator('.inspector-panel')).toContainText('Locked until verified')
  await safeHistory(page, ['Avery Rivers', '1990-07-09', '2025550100'])
  await expect(page.locator('.verification-form')).not.toHaveAttribute('open')
  await page.locator('.verification-form>summary').click()
  await page.getByRole('button', { name: 'Use synthetic verification details', exact: true }).click()
  await page.getByRole('textbox', { name: 'Phone', exact: true }).fill('(650) 521-2836')
  await page.getByRole('button', { name: 'Verify details', exact: true }).click()
  await expect(page.locator('.user-message .message-text').last()).toHaveText('Full name: Margaret Chen\nDate of birth: 1985-03-15\nPhone: (650) 521-2836')
  await expect(page.locator('.inspector-panel')).toContainText('3 of 3')
  await safeHistory(page, ['Margaret Chen', '1985-03-15', '(650) 521-2836'])
  await page.reload()
  await expect(page.locator('.user-message').last()).not.toContainText('1985-03-15')
})

test('identity recheck, New Session and model reset discard earlier local originals', async ({ page }) => {
  await page.goto('/')
  await message(page, identity)
  await message(page, 'Actually my name is Avery Rivers.')
  await expect(page.locator('.inspector-panel')).toContainText('Locked until verified')
  await expect(page.getByRole('button', { name: 'Hide submitted details', exact: true })).toHaveCount(0)
  await expect(page.locator('.user-message').first()).toContainText('[name provided]')
  await expect(page.locator('.user-message').first()).not.toContainText('1985-03-15')
  await page.getByRole('button', { name: 'New session', exact: true }).click()
  await page.getByRole('button', { name: 'Start new session', exact: true }).click()
  await expect(page.locator('.user-message')).toHaveCount(0)
  await message(page, identity)
  await expect(page.locator('.user-message .message-text')).toHaveText(identity)
  await page.getByRole('button', { name: 'Model settings', exact: true }).click()
  await page.getByLabel('Clear this conversation and summary when applying').check()
  await page.getByRole('button', { name: 'Apply offline mode', exact: true }).click()
  await expect(page.getByRole('dialog')).toContainText('Connection validated')
  await page.getByRole('button', { name: 'Close model settings', exact: true }).click()
  await expect(page.locator('.user-message')).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Hide submitted details', exact: true })).toHaveCount(0)
})

test('lost response retries reveal the same local text once after confirmation', async ({ page }) => {
  await page.goto('/')
  let requestId = ''
  await page.route('**/api/turn', async route => {
    requestId = route.request().postDataJSON().request_id
    await route.fetch()
    await route.abort()
    await page.unroute('**/api/turn')
  })
  await message(page, identity)
  await expect(page.getByRole('alert')).toBeVisible()
  await expect(page.locator('.pending-message')).not.toContainText('Margaret Chen')
  await page.route('**/api/turn', async route => {
    expect(route.request().postDataJSON().request_id).toBe(requestId)
    await route.continue()
  })
  await page.getByRole('button', { name: 'Retry', exact: true }).click()
  await expect(page.locator('.pending-message')).toHaveCount(0)
  await expect(page.locator('.user-message .message-text')).toHaveText(identity)
  await safeHistory(page)
})
