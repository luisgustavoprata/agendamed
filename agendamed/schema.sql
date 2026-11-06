-- Tabelas da agenda da Clínica Vida (SQLite). Roda a cada início do sistema: o
-- "IF NOT EXISTS" faz criar só o que falta. Para mudar uma tabela que já existe, use também
-- um ALTER TABLE em _upgrade (agendamed/db.py), porque bancos antigos não são recriados.
-- As tabelas da gestão (prontuário, financeiro, estoque...) ficam em schema_gestao.sql.
--
-- Datas são gravadas em ISO 8601 (YYYY-MM-DDTHH:MM:SS), o que permite
-- comparar e ordenar horários diretamente como texto no SQLite.

-- Acessos da equipe (login). A senha nunca é guardada: só o hash dela.
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    email         TEXT    NOT NULL UNIQUE,
    full_name     TEXT    NOT NULL,
    password_hash TEXT    NOT NULL,
    created_at    TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now'))
);

-- Médicos: duração da consulta (em minutos) e horário de atendimento dos dias úteis.
CREATE TABLE IF NOT EXISTS doctors (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT    NOT NULL,
    specialty    TEXT    NOT NULL,
    crm          TEXT    NOT NULL UNIQUE,
    slot_minutes INTEGER NOT NULL DEFAULT 30 CHECK (slot_minutes BETWEEN 10 AND 240),
    work_start   TEXT    NOT NULL DEFAULT '08:00',
    work_end     TEXT    NOT NULL DEFAULT '18:00',
    -- 0 = removido: some das listas e da agenda, mas o histórico de consultas continua.
    active       INTEGER NOT NULL DEFAULT 1
);

-- Pacientes. O CPF fica só com os números e não se repete.
CREATE TABLE IF NOT EXISTS patients (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL,
    cpf        TEXT NOT NULL UNIQUE,
    email      TEXT NOT NULL,
    phone      TEXT,
    birth_date TEXT NOT NULL
);

-- Consultas: médico, paciente, início e fim, e a situação (agendada, cancelada ou
-- concluída). O banco recusa uma consulta que termina antes de começar.
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

-- Índices: deixam rápidas as buscas da agenda de um médico e das consultas de um paciente.
CREATE INDEX IF NOT EXISTS idx_appointments_doctor_start
    ON appointments (doctor_id, start_at);
CREATE INDEX IF NOT EXISTS idx_appointments_patient_start
    ON appointments (patient_id, start_at);
