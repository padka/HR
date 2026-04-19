import { test, expect } from '@playwright/test'

test.describe('Candidate Notes And Drafts', () => {
  test('opens notes drawer and inserts reply draft from chat', async ({ page }) => {
    await page.goto('/app/candidates')
    await page.waitForLoadState('domcontentloaded')
    await page.waitForTimeout(500)

    const candidateLink = page.getByRole('link', { name: 'E2E Candidate', exact: false }).first()
    await expect(candidateLink).toBeVisible({ timeout: 10000 })
    await candidateLink.click()

    await page.waitForURL(/\/app\/candidates\/\d+/)
    await page.waitForLoadState('domcontentloaded')

    await page.getByTestId('candidate-insights-trigger').click()
    const insightsDrawer = page.getByTestId('candidate-insights-drawer')
    await expect(insightsDrawer).toBeVisible({ timeout: 10000 })
    await expect(
      insightsDrawer.getByRole('heading', { name: 'Заметки по кандидату', exact: true }),
    ).toBeVisible({ timeout: 10000 })
    await expect(insightsDrawer.getByTestId('candidate-quick-notes')).toBeVisible({ timeout: 10000 })
    await expect(insightsDrawer.getByText('HeadHunter')).toBeVisible({ timeout: 10000 })
    const hhLink = insightsDrawer.getByRole('link', { name: 'Открыть в HH', exact: true })
    if (await hhLink.count()) {
      await expect(hhLink).toBeVisible({ timeout: 10000 })
    }
    await insightsDrawer.getByRole('button', { name: 'Закрыть', exact: true }).click()

    const chatButton = page.getByRole('button', { name: /Чат/i }).first()
    await expect(chatButton).toBeEnabled({ timeout: 10000 })
    await chatButton.click()

    await expect(page.getByRole('heading', { name: 'Чат с кандидатом', exact: false }).first()).toBeVisible({
      timeout: 10000,
    })

    const draftsButton = page.getByRole('button', { name: /Черновики ответа/i }).first()
    await draftsButton.click()

    await expect(page.getByText(/Здравствуйте!/i).first()).toBeVisible({ timeout: 10000 })

    const insertButton = page.getByRole('button', { name: 'Вставить', exact: true }).first()
    await insertButton.click()

    const chatTextarea = page.getByTestId('chat-textarea')
    await expect(chatTextarea).toHaveValue(/Здравствуйте!/i, { timeout: 10000 })
  })
})
