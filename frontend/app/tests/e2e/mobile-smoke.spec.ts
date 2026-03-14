import { expect, test } from '@playwright/test'

test.use({
  viewport: { width: 375, height: 812 },
  isMobile: true,
  hasTouch: true,
  deviceScaleFactor: 3,
  userAgent:
    'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1',
})

test('mobile shell navigation and layout smoke', async ({ page }) => {
  await page.goto('/app/slots')
  await page.waitForLoadState('domcontentloaded')

  const mobileTabBar = page.locator('.mobile-tab-bar')
  await expect(mobileTabBar).toBeVisible()

  const desktopNav = page.locator('.vision-nav-pill').first()
  await expect(desktopNav).toBeHidden()

  const sceneVisible = await page.evaluate(() => {
    const node = document.querySelector<HTMLElement>('.background-scene')
    if (!node) return false
    const style = window.getComputedStyle(node)
    return style.display !== 'none'
  })
  expect(sceneVisible).toBe(false)

  const slotsCards = page.locator('[data-testid="slots-mobile-cards"]')
  const slotsEmpty = page.locator('[data-testid="slots-empty-state"]')
  await expect(slotsCards.or(slotsEmpty)).toBeVisible()
  await expect(page.locator('#mobile-more-sheet')).toHaveCount(0)
  await expect(page.getByRole('dialog', { name: 'Ещё разделы' })).toHaveCount(0)

  await page.getByRole('link', { name: 'Кандидаты' }).click()
  await expect(page.getByRole('heading', { name: 'Кандидаты' })).toBeVisible()

  const candidateCards = page.locator('[data-testid="candidates-mobile-list"]')
  const candidatesEmpty = page.locator('[data-testid="candidates-empty-state"]')
  await expect(candidateCards.or(candidatesEmpty)).toBeVisible()

  await page.getByRole('link', { name: 'Чаты' }).click()
  await expect(page.getByRole('complementary', { name: 'Чаты кандидатов' })).toBeVisible()
  await expect(page.getByRole('searchbox', { name: 'Поиск по чатам' })).toBeVisible()

  await page.getByRole('button', { name: 'Ещё' }).click()
  await expect(page.getByRole('dialog', { name: 'Ещё разделы' })).toBeVisible()
  await expect(page.locator('#mobile-more-sheet .mobile-sheet__body')).toBeVisible()
})
