-- Datas são gravadas em ISO 8601 (YYYY-MM-DDTHH:MM:SS), o que permite
-- comparar e ordenar horários diretamente como texto no SQLite.

CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    email         TEXT    NOT NULL UNIQUE,
    full_name     TEXT    NOT NULL,
    password_hash TEXT    NOT NULL,
    created_at    TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now'))
);

CREATE TABLE IF NOT EXISTS doctors (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT    NOT NULL,
    specialty    TEXT    NOT NULL,
    crm          TEXT    NOT NULL UNIQUE,
    slot_minutes INTEGER NOT NULL DEFAULT 30 CHECK (slot_minutes BETWEEN 10 AND 240),
    work_start   TEXT    NOT NULL DEFAULT '08:00',
    work_end     TEXT    NOT NULL DEFAULT '18:00'
);

CREATE TABLE IF NOT EXISTS patients (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL,
    cpf        TEXT NOT NULL UNIQUE,
    email      TEXT NOT NULL,
    phone      TEXT,
    birth_date TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS appointments (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    doctor_id  INTEGER NOT NULL REFERENCES doctors (id),
    patient_id INTEGER NOT NULL REFERENCES patients (id),
    start_at   TEXT    NOT NULL,
    end_at     TEXT    NOT NULL,
    status     TEXT    NOT NULL DEFAULT 'scheduled'
               CHECK (status IN ('scheduled', 'cancelled', 'completed')),
    notes      TEXT,
    created_at TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now')),
    CHECK (end_at > start_at)
);

CREATE INDEX IF NOT EXISTS idx_appointments_doctor_start
    ON appointments (doctor_id, start_at);
CREATE INDEX IF NOT EXISTS idx_appointments_patient_start
    ON appointments (patient_id, start_at);
