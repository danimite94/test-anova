import { expect, test } from '@playwright/test';

// Runs against `docker compose up` on a clean machine (CI) — the walking skeleton end to end.
test('[NFR-007] [NFR-011] the stack starts and the UI shows backend and database health', async ({
  page,
}) => {
  await page.goto('/');

  await expect(page.getByRole('heading', { name: 'Pump Skid Telemetry Explorer' })).toBeVisible();
  await expect(page.getByText('Backend: OK')).toBeVisible();
  await expect(page.getByText('Database: OK')).toBeVisible();
});
