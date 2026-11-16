import { useEffect, useState } from 'react';

import { fetchHealth, type Health } from './api';

type State = { kind: 'loading' } | { kind: 'ok'; health: Health } | { kind: 'unreachable' };

const POLL_MS = 5000;

export function HealthStatus() {
  const [state, setState] = useState<State>({ kind: 'loading' });

  useEffect(() => {
    const controller = new AbortController();
    const load = () => {
      fetchHealth(controller.signal)
        .then((health) => {
          setState({ kind: 'ok', health });
        })
        .catch(() => {
          if (!controller.signal.aborted) setState({ kind: 'unreachable' });
        });
    };
    load();
    const timer = setInterval(load, POLL_MS);
    return () => {
      controller.abort();
      clearInterval(timer);
    };
  }, []);

  if (state.kind === 'loading') return <p aria-busy="true">Checking system health…</p>;

  const backend = state.kind === 'ok' ? 'OK' : 'unreachable';
  const database = state.kind === 'ok' ? databaseLabel(state.health) : 'unknown';
  const dataset =
    state.kind === 'ok' ? (state.health.dataset_loaded ? 'loaded' : 'not loaded') : 'unknown';

  return (
    <ul className="health" aria-label="System health">
      <Item ok={state.kind === 'ok'} text={`Backend: ${backend}`} />
      <Item
        ok={state.kind === 'ok' && state.health.database === 'ok'}
        text={`Database: ${database}`}
      />
      <Item ok={state.kind === 'ok' && state.health.dataset_loaded} text={`Dataset: ${dataset}`} />
    </ul>
  );
}

function databaseLabel(health: Health): string {
  return health.database === 'ok' ? 'OK' : 'unavailable';
}

function Item({ ok, text }: { ok: boolean; text: string }) {
  // Colour is never the only signal (SPEC §7.2): the icon and text carry the state too.
  return (
    <li className={ok ? 'ok' : 'bad'}>
      <span aria-hidden="true">{ok ? '●' : '○'}</span> <span>{text}</span>
    </li>
  );
}
