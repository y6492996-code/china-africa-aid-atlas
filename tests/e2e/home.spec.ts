import { expect, test } from '@playwright/test'

test('map home loads real country data and switches countries', async ({ page }) => {
  await page.goto('/#/')
  await expect(page.getByRole('heading', { level: 1 })).toContainText('中非援助')
  await expect(page.getByRole('heading', { name: '埃塞俄比亚' }).first()).toBeVisible()
  await page.getByRole('button', { name: /安哥拉:/ }).click()
  await expect(page.getByRole('heading', { name: '安哥拉' }).first()).toBeVisible()
  await page.getByRole('button', { name: '记录密度' }).click()
  await page.getByRole('button', { name: /English/i }).click()
  await expect(page.getByRole('heading', { level: 1 })).toContainText('China–Africa Aid')
})

test('database catalogue keeps its filter interaction', async ({ page }) => {
  await page.goto('/#/databases')
  await expect(page.getByRole('heading', { level: 1 })).toContainText('先比较')
  await page.getByRole('button', { name: '卫生' }).click()
  await expect(page.getByRole('heading', { name: 'CHAPO' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'IHME DAH' })).toBeVisible()
})

test('trend and country panels use the integrated country data', async ({ page }) => {
  await page.goto('/#/trends')
  await expect(page.getByRole('heading', { name: '沿着记录看趋势。' })).toBeVisible()
  await page.getByLabel('地理范围').selectOption('AGO')
  await expect(page.getByText('峰值年份').locator('..').locator('strong')).not.toHaveText('—')

  await page.goto('/#/countries')
  await page.getByRole('textbox', { name: '搜索国家或ISO代码' }).fill('Ethiopia')
  await expect(page.getByRole('heading', { name: '埃塞俄比亚' })).toBeVisible()
  await page.getByRole('link', { name: /打开地图/ }).click()
  await expect(page).toHaveURL(/country=ETH/)
  await expect(page.getByRole('heading', { name: '埃塞俄比亚' }).first()).toBeVisible()
})
