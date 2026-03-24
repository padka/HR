import { test, expect } from '@playwright/test'

test.describe('AI Copilot', () => {
  test('can generate summary and insert reply draft', async ({ page }) => {
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

    const copilotHeading = insightsDrawer.getByRole('heading', { name: 'AI-помощник', exact: false }).first()
    await expect(copilotHeading).toBeVisible({ timeout: 10000 })

    const newButton = insightsDrawer.getByRole('button', { name: 'Новый', exact: true })
    if (await newButton.count()) {
      await newButton.click()
    } else {
      await insightsDrawer.getByRole('button', { name: 'Обновить', exact: true }).click()
    }

    await expect(
      insightsDrawer.getByText('Кандидат в процессе. Следующий шаг: назначить/подтвердить время.', { exact: false }).first(),
    ).toBeVisible({ timeout: 10000 })
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
