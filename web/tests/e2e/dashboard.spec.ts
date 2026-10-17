import { expect, test, type Page } from '@playwright/test'

test.setTimeout(60_000)

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

const forecasts = [7, 14, 30].map((horizon) => ({
  market_id: 'dambulla', market_name: 'Dambulla', commodity: 'Tomato', category: 'Vegetable',
  generated_at: '2026-01-01T00:00:00Z', origin_date: '2025-12-31',
  training_cutoff: '2025-12-31', forecast_date: `2026-01-${horizon === 7 ? '07' : horizon}`,
  horizon_days: horizon, point_forecast_lkr: 300 + horizon, lower_80_lkr: 280,
  upper_80_lkr: 340, lower_95_lkr: 260, upper_95_lkr: 360,
  model_version: 'forecast-v1-test', feature_version: 'price-features-v1',
  model_type: 'test', experimental: true,
}))

const forecastQuality = {
  model_version: 'forecast-v1-test', evaluated_at: '2026-01-01T00:00:00Z',
  horizons: [7, 14, 30].map((horizon) => ({
    horizon_days: horizon, samples: 100, folds: 3,
    model_metrics: { mae: 24 }, baseline_metrics: { seasonal_naive: { mae: 30 } },
    interval_coverage_80: 0.8, interval_coverage_95: 0.95,
    interval_radius_80_lkr: 30, interval_radius_95_lkr: 60,
    beats_seasonal_baseline: true,
    beats_strongest_baseline: false,
  })),
}

const modelHealth = {
  status: 'warning', model_version: 'forecast-v1-test', checked_at: '2026-01-01T00:00:00Z',
  training_cutoff: '2025-12-31', training_data_age_days: 1,
  strongest_baseline_wins: [7], undercovered_horizons: [30],
  signals: [
    { source: 'nasa_power', latest_effective_date: '2025-12-31', observation_count: 1000, age_days: 1, stale: false },
    { source: 'cbsl', latest_effective_date: null, observation_count: 0, age_days: null, stale: true },
  ],
  messages: ['The strongest baseline still wins at 7d.'],
}

const stressSignals = [{
  market_id: 'dambulla', market_name: 'Dambulla', district: 'Matale', province: 'Central',
  latitude: 7.8742, longitude: 80.6511, commodity: 'Tomato', observation_date: '2025-12-31',
  price_midpoint_lkr: 300, score: 78, severity: 'warning', confidence: 0.9,
  components: { anomaly: 90, momentum: 80, forecast_surprise: 70, spatial_pressure: 60 },
  evidence_observations: 30, stale: false, methodology_version: 'economic-stress-v1',
}]

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
  await page.route('**/v1/forecasts/quality', (route) => route.fulfill({ json: forecastQuality }))
  await page.route('**/v1/forecasts?**', (route) => route.fulfill({ json: forecasts }))
  await page.route('**/v1/models/health', (route) => route.fulfill({ json: modelHealth }))
  await page.route('**/v1/stress/current**', (route) => route.fulfill({ json: stressSignals }))
  await page.route('**/v1/alerts**', (route) => route.fulfill({ json: [] }))
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

test('experimental forecasts show intervals and model provenance', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByText('Experimental outlook')).toBeVisible()
  await expect(page.getByText(/Nominal 80% interval/).first()).toBeVisible()
  await expect(page.getByText(/forecast-v1-test/).last()).toBeVisible()
})

test('model health exposes baseline and signal warnings', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByLabel('Forecast model health')).toContainText('Forecast caution active')
  await expect(page.getByLabel('Forecast model health')).toContainText('CBSL exchange rate · stale')
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

test('economic-stress mode explains a market warning and remains in the URL', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: 'Economic stress' }).click()
  await expect(page).toHaveURL(/mode=stress/)
  await expect(page.getByRole('button', { name: /Dambulla, warning pressure, score 78/ })).toBeVisible()
  await expect(page.getByLabel('Economic pressure explanation')).toContainText('not a shortage prediction')
})
