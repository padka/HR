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

    const copilotHeading = page.getByRole('heading', { name: 'AI Copilot', exact: false }).first()
    await expect(copilotHeading).toBeVisible({ timeout: 10000 })

    const generateButton = page.getByRole('button', { name: /Сгенерировать/i }).first()
    await generateButton.click()

    await expect(
      page.getByText('Кандидат в процессе. Следующий шаг: назначить/подтвердить время.', { exact: false }).first(),
    ).toBeVisible({ timeout: 10000 })

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

    const chatTextarea = page.locator('.candidate-chat-drawer__footer textarea').first()
    await expect(chatTextarea).toHaveValue(/Здравствуйте!/i, { timeout: 10000 })
  })
})
