import { expect, test, type Page } from '@playwright/test'

const catalog = {
  commodities: ['Tomato', 'Carrot'],
  markets: [],
  minimum_date: '2025-01-01',
  maximum_date: '2025-12-31',
}

const quality = {
  total_bulletins: 340,
  processed_bulletins: 340,
  quarantined_bulletins: 0,
  failed_bulletins: 0,
  pending_bulletins: 0,
  latest_error: null,
}

function prices(commodity = 'Tomato') {
  return [
    {
      market_id: 'dambulla', market_name: 'Dambulla', district: 'Matale', province: 'Central',
      latitude: 7.8742, longitude: 80.6511, commodity, category: 'Vegetable',
      minimum_price_lkr: 280, maximum_price_lkr: 320, midpoint_price_lkr: 300,
      previous_price_lkr: 280, change_percentage: 7.14, observation_date: '2025-12-31',
      source_url: 'https://example.test/dambulla.pdf',
    },
    {
      market_id: 'kandy', market_name: 'Kandy', district: 'Kandy', province: 'Central',
      latitude: 7.2906, longitude: 80.6337, commodity, category: 'Vegetable',
      minimum_price_lkr: 230, maximum_price_lkr: 270, midpoint_price_lkr: 250,
      previous_price_lkr: 270, change_percentage: -7.41, observation_date: '2025-12-31',
      source_url: 'https://example.test/kandy.pdf',
    },
  ]
}

const history = [
  {
    observation_date: '2025-12-30', market: 'Dambulla', commodity: 'Tomato',
    price_min_lkr: 260, price_max_lkr: 300, price_midpoint_lkr: 280,
    moving_average_7: 275, moving_average_30: 265,
    source_url: 'https://example.test/previous.pdf',
  },
  {
    observation_date: '2025-12-31', market: 'Dambulla', commodity: 'Tomato',
    price_min_lkr: 280, price_max_lkr: 320, price_midpoint_lkr: 300,
    moving_average_7: 282, moving_average_30: 270,
    source_url: 'https://example.test/latest.pdf',
  },
]

async function mockDashboard(page: Page) {
  await page.route('**/styles/bright', (route) => route.fulfill({
    contentType: 'application/json',
    body: JSON.stringify({
      version: 8,
      sources: {},
      layers: [{ id: 'background', type: 'background', paint: { 'background-color': '#e9ede7' } }],
    }),
  }))
  await page.route('**/v1/catalog', (route) => route.fulfill({ json: catalog }))
  await page.route('**/v1/data-quality/status', (route) => route.fulfill({ json: quality }))
  await page.route('**/v1/map/prices**', (route) => {
    const commodity = new URL(route.request().url()).searchParams.get('commodity') ?? 'Tomato'
    return route.fulfill({ json: prices(commodity) })
  })
  await page.route('**/v1/markets/*/prices**', (route) => route.fulfill({ json: history }))
}

test.beforeEach(async ({ page }) => {
  await mockDashboard(page)
})

test('dashboard loads', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'See the country’s food economy move.' })).toBeVisible()
  await expect(page.getByText('Source pipeline verified')).toBeVisible()
})

test('markets appear on the map', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('button', { name: /Dambulla, Rising/ })).toBeVisible()
  await expect(page.getByRole('button', { name: /Kandy, Falling/ })).toBeVisible()
})

test('a commodity can be selected', async ({ page }) => {
  await page.goto('/')
  await page.getByLabel('Commodity').selectOption('Carrot')
  await expect(page).toHaveURL(/commodity=Carrot/)
  await expect(page.getByRole('button', { name: /Dambulla, Rising/ })).toBeVisible()
})

test('a market popup opens', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: /Kandy, Falling/ }).click()
  const popup = page.locator('.maplibregl-popup')
  await expect(popup).toContainText('Kandy')
  await expect(popup).toContainText('Central')
})

test('the selected market displays a historical chart', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByLabel('Historical price chart for Dambulla')).toBeVisible()
  await expect(page.getByText('2 observations')).toBeVisible()
})

test('filter state remains in the URL after reload', async ({ page }) => {
  await page.goto('/')
  await page.getByLabel('Commodity').selectOption('Carrot')
  await page.getByLabel('Province').selectOption('Central')
  await page.reload()
  await expect(page.getByLabel('Commodity')).toHaveValue('Carrot')
  await expect(page.getByLabel('Province')).toHaveValue('Central')
  await expect(page).toHaveURL(/commodity=Carrot/)
  await expect(page).toHaveURL(/province=Central/)
})

test('an API failure displays an understandable message', async ({ page }) => {
  await page.unroute('**/v1/catalog')
  await page.route('**/v1/catalog', (route) => route.fulfill({
    status: 503,
    contentType: 'application/json',
    body: JSON.stringify({ detail: 'The catalog is temporarily unavailable.' }),
  }))
  await page.goto('/')
  await expect(page.getByRole('alert')).toContainText('We could not load the market data')
  await expect(page.getByRole('alert')).toContainText('The catalog is temporarily unavailable.')
})
