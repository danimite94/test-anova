import { render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { HealthStatus } from '../../src/HealthStatus';

function stubHealth(response: Response | Error) {
  const fetchMock = vi.fn(() =>
    response instanceof Error ? Promise.reject(response) : Promise.resolve(response),
  );
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('HealthStatus', () => {
  it('[NFR-011] shows backend and database OK when the API reports ok', async () => {
    const fetchMock = stubHealth(json({ status: 'ok', database: 'ok', dataset_loaded: false }));

    render(<HealthStatus />);

    expect(await screen.findByText('Backend: OK')).toBeInTheDocument();
    expect(screen.getByText('Database: OK')).toBeInTheDocument();
    expect(screen.getByText('Dataset: not loaded')).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/health', expect.anything());
  });

  it('[NFR-011] shows database unavailable when the API is degraded', async () => {
    stubHealth(json({ status: 'degraded', database: 'unavailable', dataset_loaded: false }));

    render(<HealthStatus />);

    expect(await screen.findByText('Backend: OK')).toBeInTheDocument();
    expect(screen.getByText('Database: unavailable')).toBeInTheDocument();
  });

  it('[NFR-011] shows backend unreachable when the request fails', async () => {
    stubHealth(new TypeError('Failed to fetch'));

    render(<HealthStatus />);

    expect(await screen.findByText('Backend: unreachable')).toBeInTheDocument();
    expect(screen.getByText('Database: unknown')).toBeInTheDocument();
  });

  it('[NFR-011] treats a non-2xx response as unreachable', async () => {
    stubHealth(json({ title: 'Bad gateway' }, 502));

    render(<HealthStatus />);

    expect(await screen.findByText('Backend: unreachable')).toBeInTheDocument();
  });
});
