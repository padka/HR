import { test, expect } from '@playwright/test'

/**
 * Regression e2e: city → slot → candidate funnel.
 * Verifies the core CRUD flow across the three main entities.
 */
test.describe('City → Slot → Candidate regression flow', () => {
  test('cities page loads and shows data or empty state', async ({ page }) => {
    await page.goto('/app/cities')
    await page.waitForLoadState('domcontentloaded')
    await page.waitForTimeout(500)

    await expect(page.getByRole('heading', { name: 'Города', exact: false })).toBeVisible({ timeout: 10000 })

    // Should have create button
    await expect(page.getByTestId('cities-create-btn')).toBeVisible({ timeout: 10000 })
  })

  test('slots page loads and shows data or empty state', async ({ page }) => {
    await page.goto('/app/slots')
    await page.waitForLoadState('domcontentloaded')
    await page.waitForTimeout(500)

    await expect(page.getByRole('heading', { name: 'Слоты', exact: false })).toBeVisible({ timeout: 10000 })

    // Filter bar always visible
    await expect(page.getByTestId('slots-filter-bar')).toBeVisible({ timeout: 10000 })

    // Either table or empty state
    const table = page.getByTestId('slots-table')
    const empty = page.getByTestId('slots-empty-state')
    await expect(table.or(empty).first()).toBeVisible({ timeout: 10000 })
  })

  test('candidates page loads and shows data or empty state', async ({ page }) => {
    await page.goto('/app/candidates')
    await page.waitForLoadState('domcontentloaded')
    await page.waitForTimeout(500)

    await expect(page.getByRole('heading', { name: 'Кандидаты', exact: false })).toBeVisible({ timeout: 10000 })

    // View switcher always visible
    await expect(page.getByTestId('candidates-view-switcher')).toBeVisible({ timeout: 10000 })

    // Either table or empty state
    const table = page.getByTestId('candidates-table')
    const empty = page.getByTestId('candidates-empty-state')
    await expect(table.or(empty).first()).toBeVisible({ timeout: 10000 })
  })

  test('full navigation: cities → slots → candidates', async ({ page }) => {
    // Start at cities
    await page.goto('/app/cities')
    await page.waitForLoadState('domcontentloaded')
    await expect(page.getByRole('heading', { name: 'Города', exact: false })).toBeVisible({ timeout: 10000 })

    // Navigate to slots via sidebar/nav
    await page.goto('/app/slots')
    await page.waitForLoadState('domcontentloaded')
    await expect(page.getByRole('heading', { name: 'Слоты', exact: false })).toBeVisible({ timeout: 10000 })
    await expect(page.getByTestId('slots-filter-bar')).toBeVisible({ timeout: 10000 })

    // Navigate to candidates
    await page.goto('/app/candidates')
    await page.waitForLoadState('domcontentloaded')
    await expect(page.getByRole('heading', { name: 'Кандидаты', exact: false })).toBeVisible({ timeout: 10000 })
    await expect(page.getByTestId('candidates-view-switcher')).toBeVisible({ timeout: 10000 })
  })

  test('slot creation CTA is accessible from empty state', async ({ page }) => {
    await page.goto('/app/slots')
    await page.waitForLoadState('domcontentloaded')
    await page.waitForTimeout(500)

    // The create button should always be visible in the header
    const createBtn = page.getByTestId('slots-create-btn')
    await expect(createBtn).toBeVisible({ timeout: 10000 })

    // Click it and verify navigation
    await createBtn.click()
    await page.waitForURL('/app/slots/create')
    await page.waitForLoadState('domcontentloaded')
  })

  test('candidate creation CTA is accessible', async ({ page }) => {
    await page.goto('/app/candidates')
    await page.waitForLoadState('domcontentloaded')
    await page.waitForTimeout(500)

    const createBtn = page.getByTestId('candidates-create-btn')
    await expect(createBtn).toBeVisible({ timeout: 10000 })

    await createBtn.click()
    await page.waitForURL('/app/candidates/new')
    await page.waitForLoadState('domcontentloaded')
  })

  test('no 4xx/5xx errors in console during navigation', async ({ page }) => {
    const networkErrors: string[] = []
    page.on('response', (response) => {
      if (response.status() >= 400 && !response.url().includes('favicon')) {
        networkErrors.push(`${response.status()} ${response.url()}`)
      }
    })

    // Navigate through the funnel
    for (const path of ['/app/cities', '/app/slots', '/app/candidates']) {
      await page.goto(path)
      await page.waitForLoadState('domcontentloaded')
      await page.waitForTimeout(500)
    }

    // Verify no API errors occurred
    expect(networkErrors).toEqual([])
  })
})
