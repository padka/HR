import { expect, test, type APIRequestContext, type Locator, type Page } from '@playwright/test'

async function waitForRoute(page: Page, path: string) {
  await page.goto(path)
  await page.waitForLoadState('domcontentloaded')
  await page.waitForTimeout(500)
}

async function openSeededCandidateDetail(page: Page) {
  await waitForRoute(page, '/app/candidates')

  const seededCandidate = page.getByRole('link', { name: 'E2E Candidate', exact: false }).first()
  const fallbackCandidate = page.locator('a[href^="/app/candidates/"]:not([href="/app/candidates/new"])').first()
  const target = (await seededCandidate.count()) > 0 ? seededCandidate : fallbackCandidate

  await expect(target).toBeVisible({ timeout: 10000 })
  await target.click()
  await page.waitForURL(/\/app\/candidates\/\d+/)
  await expect(page.getByTestId('candidate-header')).toBeVisible({ timeout: 10000 })
}

async function selectFirstRealOption(select: Locator) {
  const currentValue = await select.inputValue()
  if (currentValue) return

  const firstOptionValue = await select.locator('option').evaluateAll((options) =>
    options
      .map((option) => (option as HTMLOptionElement).value)
      .find((value) => Boolean(value)),
  )

  expect(firstOptionValue).toBeTruthy()
  await select.selectOption(firstOptionValue!)
}

const SEEDED_CANDIDATE_ID = 1

async function ensureMessengerThread(request: APIRequestContext) {
  const csrfResponse = await request.get('/api/csrf')
  expect(csrfResponse.ok()).toBeTruthy()

  const { token } = (await csrfResponse.json()) as { token?: string }
  expect(token).toBeTruthy()

  const seedMessage = `Seed messenger thread ${Date.now()}`
  const response = await request.post(`/api/candidates/${SEEDED_CANDIDATE_ID}/chat`, {
    headers: {
      'x-csrf-token': token!,
    },
    data: {
      text: seedMessage,
      client_request_id: `seed-${Date.now()}`,
    },
  })
  expect(response.ok()).toBeTruthy()
  return seedMessage
}

test.describe('Critical User Flows', () => {
  test('candidate detail shows pipeline stages', async ({ page }) => {
    await openSeededCandidateDetail(page)

    const pipeline = page.getByTestId('candidate-pipeline')
    await expect(pipeline).toBeVisible({ timeout: 10000 })
    await expect(pipeline.locator('.candidate-pipeline-stage')).toHaveCount(6)
    await expect(pipeline.locator('.candidate-pipeline-stage--current')).toBeVisible()
  })

  test('candidate details drawer scrolls through insights', async ({ page }) => {
    await openSeededCandidateDetail(page)

    await page.getByTestId('candidate-insights-trigger').click()

    const drawer = page.getByTestId('candidate-insights-drawer')
    await expect(drawer).toBeVisible({ timeout: 10000 })

    const drawerBody = drawer.locator('.candidate-drawer__body')
    const scrollState = await drawerBody.evaluate((node) => {
      const element = node as HTMLElement
      return {
        overflowY: window.getComputedStyle(element).overflowY,
        scrollTop: element.scrollTop,
        clientHeight: element.clientHeight,
        scrollHeight: element.scrollHeight,
        maxScrollTop: Math.max(0, element.scrollHeight - element.clientHeight),
      }
    })

    expect(['auto', 'scroll']).toContain(scrollState.overflowY)
    expect(scrollState.clientHeight).toBeGreaterThan(0)
    expect(scrollState.scrollHeight).toBeGreaterThanOrEqual(scrollState.clientHeight)
    if (scrollState.maxScrollTop > 0) {
      const nextScrollTop = await drawerBody.evaluate((node) => {
        const element = node as HTMLElement
        element.scrollTo(0, element.scrollHeight)
        return element.scrollTop
      })
      expect(nextScrollTop).toBeGreaterThan(0)
    } else {
      expect(scrollState.scrollTop).toBe(0)
    }
    await expect(drawer.getByRole('heading', { name: 'Заметки по кандидату', exact: true })).toBeVisible()
    await expect(drawer.getByTestId('candidate-quick-notes')).toBeVisible()
    await expect(drawer.getByText('HeadHunter')).toBeVisible()
  })

  test('messenger keeps composer pinned and sends a message', async ({ page, request }) => {
    const seededMessage = await ensureMessengerThread(request)
    await waitForRoute(page, '/app/messenger')

    await expect(page.getByRole('complementary', { name: 'Чаты кандидатов' })).toBeVisible({ timeout: 10000 })
    await expect(page.getByRole('searchbox', { name: 'Поиск по чатам' })).toBeVisible()

    const composer = page.getByTestId('messenger-composer')
    if (!(await composer.isVisible().catch(() => false))) {
      const seededThreadButton = page.locator('button.messenger-thread-card', { hasText: 'E2E Candidate' }).first()
      await expect(seededThreadButton).toBeVisible({ timeout: 10000 })
      await seededThreadButton.click()
    }

    await expect(composer).toBeVisible({ timeout: 10000 })
    await expect(page.getByTestId('messenger-messages')).toBeVisible({ timeout: 10000 })
    await expect(page.getByText(seededMessage).last()).toBeVisible({ timeout: 10000 })

    const composerBox = await composer.boundingBox()
    const viewport = page.viewportSize()
    expect(composerBox).not.toBeNull()
    expect(viewport).not.toBeNull()
    expect((composerBox?.y || 0) + (composerBox?.height || 0)).toBeGreaterThan((viewport?.height || 0) * 0.7)

    const uniqueMessage = `Playwright critical flow ${Date.now()}`
    const messageInput = page.locator('textarea.message-input')
    await messageInput.fill(uniqueMessage)

    const sendResponse = page.waitForResponse((response) => {
      const pathname = new URL(response.url()).pathname
      return response.request().method() === 'POST' && /\/api\/candidates\/\d+\/chat$/.test(pathname)
    })

    await page.getByRole('button', { name: 'Отправить сообщение' }).click()

    const response = await sendResponse
    expect(response.ok()).toBeTruthy()
    await expect(messageInput).toHaveValue('')
    await expect(page.getByText(uniqueMessage).last()).toBeVisible({ timeout: 10000 })
  })

  test('dashboard shows KPI metrics', async ({ page }) => {
    await waitForRoute(page, '/app/dashboard')

    await expect(page.locator('.kpi-card').first()).toBeVisible({ timeout: 10000 })
    await expect(page.locator('.kpi-value').first()).toBeVisible({ timeout: 10000 })

    const kpiCount = await page.locator('.kpi-card').count()
    expect(kpiCount).toBeGreaterThan(0)
  })

  test('candidate creation validates required fields and creates a candidate', async ({ page }) => {
    await waitForRoute(page, '/app/candidates/new')

    await expect(page.getByRole('heading', { name: 'Новый кандидат', exact: false })).toBeVisible({ timeout: 10000 })

    const submitButton = page.getByRole('button', { name: 'Создать кандидата' })
    await expect(submitButton).toBeDisabled()

    await page.getByLabel(/^ФИО/).fill(`Playwright Candidate ${Date.now()}`)
    await selectFirstRealOption(page.getByLabel(/^Город/))
    await selectFirstRealOption(page.getByLabel(/^Ответственный рекрутёр/))
    await page.getByRole('checkbox', { name: 'Назначить собеседование сразу' }).uncheck()

    await expect(submitButton).toBeEnabled()
    await submitButton.click()

    await page.waitForURL(/\/app\/candidates\/\d+/)
    await expect(page.getByTestId('candidate-header')).toBeVisible({ timeout: 10000 })
  })

  test('slots page renders data surface without API errors', async ({ page }) => {
    const networkErrors: string[] = []
    page.on('response', (response) => {
      const pathname = new URL(response.url()).pathname
      if (response.status() >= 400 && !pathname.includes('favicon')) {
        networkErrors.push(`${response.status()} ${pathname}`)
      }
    })

    await waitForRoute(page, '/app/slots')

    await expect(page.getByTestId('slots-filter-bar')).toBeVisible({ timeout: 10000 })
    await expect(page.getByTestId('slots-table').or(page.getByTestId('slots-empty-state')).first()).toBeVisible({
      timeout: 10000,
    })

    expect(networkErrors).toEqual([])
  })
})

test.describe('Critical User Flows Mobile', () => {
  test.use({
    viewport: { width: 390, height: 844 },
    isMobile: true,
    hasTouch: true,
    deviceScaleFactor: 3,
    userAgent:
      'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1',
  })

  test('candidate detail mobile tabs switch between profile, tests, and chat', async ({ page }) => {
    await openSeededCandidateDetail(page)

    const mobileTabs = page.locator('.cd-mobile-tabs')
    const profileTab = mobileTabs.getByRole('button', { name: 'Профиль' })
    const testsTab = mobileTabs.getByRole('button', { name: 'Тесты' })
    const chatTab = mobileTabs.getByRole('button', { name: 'Чат' })

    await expect(profileTab).toBeVisible({ timeout: 10000 })
    await expect(testsTab).toBeVisible()
    await expect(chatTab).toBeVisible()

    await testsTab.click()
    await expect(page.getByTestId('candidate-tests-section')).toBeVisible({ timeout: 10000 })
    await page.locator('.modal-overlay').getByRole('button', { name: 'Закрыть', exact: true }).click()
    await expect(page.locator('.modal-overlay')).toHaveCount(0)

    await chatTab.click()
    await expect(page.getByTestId('candidate-chat-drawer')).toBeVisible({ timeout: 10000 })
  })
})
