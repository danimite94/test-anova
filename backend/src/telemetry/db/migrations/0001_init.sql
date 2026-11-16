-- 0001: initial schema (SPEC §5.1), sensor catalogue (SPEC §2.1), application role (GOV-005)

CREATE TABLE asset (
    id          text PRIMARY KEY,
    name        text NOT NULL
);

CREATE TABLE sensor (
    id          text PRIMARY KEY,
    asset_id    text NOT NULL REFERENCES asset(id),
    name        text NOT NULL,
    measurement text NOT NULL,
    unit        text NOT NULL,
    valid_min   double precision NOT NULL,
    valid_max   double precision NOT NULL,
    alarm_low   double precision,
    warn_low    double precision,
    warn_high   double precision,
    alarm_high  double precision
);

CREATE TABLE dataset (
    id                 serial PRIMARY KEY,
    readings_sha256    text NOT NULL UNIQUE,
    seed               integer NOT NULL,
    generator_version  text NOT NULL,
    period_start       timestamptz NOT NULL,
    period_end         timestamptz NOT NULL,
    loaded_at          timestamptz NOT NULL DEFAULT now(),
    load_mode          text NOT NULL CHECK (load_mode IN ('batch', 'replay')),
    flag_counts        jsonb NOT NULL
);

CREATE TABLE reading (
    id          bigserial PRIMARY KEY,
    dataset_id  integer NOT NULL REFERENCES dataset(id) ON DELETE CASCADE,
    seq         integer NOT NULL,
    sensor_id   text NOT NULL REFERENCES sensor(id),
    ts          timestamptz NOT NULL,
    value       double precision NOT NULL,
    quality     text NOT NULL CHECK (quality IN ('ok', 'late', 'outlier', 'duplicate')),
    UNIQUE (dataset_id, seq)
);

CREATE INDEX reading_sensor_ts ON reading (sensor_id, ts);

INSERT INTO asset (id, name) VALUES ('P-101', 'Pump skid P-101');

INSERT INTO sensor
    (id, asset_id, name, measurement, unit, valid_min, valid_max,
     alarm_low, warn_low, warn_high, alarm_high)
VALUES
    ('TT-101', 'P-101', 'Inlet temperature',      'temperature', '°C',   -40, 150,    0,    5,   40,   45),
    ('TT-102', 'P-101', 'Outlet temperature',     'temperature', '°C',   -40, 200,    5,   10,   55,   65),
    ('PT-101', 'P-101', 'Discharge pressure',     'pressure',    'bar',    0,  25,  3.0,  4.0,  8.5, 10.0),
    ('VT-101', 'P-101', 'Vibration velocity RMS', 'vibration',   'mm/s',   0,  50, NULL, NULL,  4.5,  7.1),
    ('FT-101', 'P-101', 'Flow rate',              'flow',        'm³/h',   0, 400,   30,   50,  180,  200);

-- Application role: read everything, append readings, never alter or delete them (GOV-005).
-- The password is set by the migration runner from APP_DB_PASSWORD.
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'telemetry_app') THEN
        CREATE ROLE telemetry_app LOGIN;
    END IF;
END
$$;

GRANT USAGE ON SCHEMA public TO telemetry_app;
GRANT SELECT ON asset, sensor, dataset, reading TO telemetry_app;
GRANT INSERT ON dataset, reading TO telemetry_app;
GRANT UPDATE (flag_counts) ON dataset TO telemetry_app;
GRANT USAGE ON SEQUENCE dataset_id_seq, reading_id_seq TO telemetry_app;
