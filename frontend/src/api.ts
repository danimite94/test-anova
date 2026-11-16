// Typed client for the backend API (SPEC §6). All requests go through /api, same origin.

export const API_BASE = '/api/v1';

export interface Health {
  status: 'ok' | 'degraded';
  database: 'ok' | 'unavailable';
  dataset_loaded: boolean;
}

export async function fetchHealth(signal?: AbortSignal): Promise<Health> {
  const response = await fetch(`${API_BASE}/health`, { signal: signal ?? null });
  if (!response.ok) {
    throw new Error(`Health check failed with HTTP ${String(response.status)}`);
  }
  return (await response.json()) as Health;
}
