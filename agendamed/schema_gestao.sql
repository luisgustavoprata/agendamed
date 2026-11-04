-- Prontuário, prescrições, procedimentos e convênios, financeiro, repasse e estoque.
-- Valores em dinheiro ficam em centavos (inteiros): nada de arredondamento de ponto flutuante.

-- Ficha clínica fixa do paciente (alergias, doenças, remédios de uso contínuo).
CREATE TABLE IF NOT EXISTS patient_clinical (
    patient_id  INTEGER PRIMARY KEY REFERENCES patients (id),
    clinic_id   INTEGER NOT NULL DEFAULT 1,
    allergies   TEXT,
    conditions  TEXT,
    medications TEXT,
    blood_type  TEXT,
    notes       TEXT,
    updated_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now')),
    updated_by  INTEGER REFERENCES users (id)
);

-- Registros do prontuário. Não são apagados nem editados (exigência do CFM): uma correção
-- é um registro novo.
CREATE TABLE IF NOT EXISTS record_entries (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    clinic_id      INTEGER NOT NULL DEFAULT 1,
    patient_id     INTEGER NOT NULL REFERENCES patients (id),
    doctor_id      INTEGER REFERENCES doctors (id),
    appointment_id INTEGER REFERENCES appointments (id),
    kind           TEXT    NOT NULL
                   CHECK (kind IN ('anamnese', 'evolucao', 'exame_fisico', 'diagnostico',
                                   'conduta', 'exame', 'anotacao')),
    content        TEXT    NOT NULL,
    created_by     INTEGER NOT NULL REFERENCES users (id),
    created_at     TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now'))
);
CREATE INDEX IF NOT EXISTS idx_record_entries_patient ON record_entries (clinic_id, patient_id, created_at);

-- Receitas, atestados, pedidos de exame. `items` guarda a lista de medicamentos em JSON.
CREATE TABLE IF NOT EXISTS prescriptions (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    clinic_id  INTEGER NOT NULL DEFAULT 1,
    patient_id INTEGER NOT NULL REFERENCES patients (id),
    doctor_id  INTEGER NOT NULL REFERENCES doctors (id),
    kind       TEXT    NOT NULL
               CHECK (kind IN ('simples', 'controle_especial', 'atestado', 'exames')),
    items      TEXT    NOT NULL DEFAULT '[]',
    text       TEXT,
    created_by INTEGER NOT NULL REFERENCES users (id),
    created_at TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now'))
);
CREATE INDEX IF NOT EXISTS idx_prescriptions_patient ON prescriptions (clinic_id, patient_id, created_at);

-- Catálogo de procedimentos (consulta, retorno, exames...) com preço particular.
CREATE TABLE IF NOT EXISTS procedures (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    clinic_id   INTEGER NOT NULL DEFAULT 1,
    name        TEXT    NOT NULL,
    tuss_code   TEXT,
    price_cents INTEGER NOT NULL CHECK (price_cents >= 0),
    active      INTEGER NOT NULL DEFAULT 1,
    UNIQUE (clinic_id, name)
);

-- Convênios atendidos (com o registro ANS da operadora, usado nas guias TISS).
CREATE TABLE IF NOT EXISTS health_plans (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    clinic_id INTEGER NOT NULL DEFAULT 1,
    name      TEXT    NOT NULL,
    ans_code  TEXT,
    active    INTEGER NOT NULL DEFAULT 1,
    UNIQUE (clinic_id, name)
);

-- Contas onde o dinheiro entra e sai (caixa, banco, maquininha...).
CREATE TABLE IF NOT EXISTS finance_accounts (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    clinic_id INTEGER NOT NULL DEFAULT 1,
    name      TEXT    NOT NULL,
    active    INTEGER NOT NULL DEFAULT 1,
    UNIQUE (clinic_id, name)
);

-- Lançamentos: contas a receber/receitas (income) e contas a pagar/despesas (expense).
-- paid_on vazio = em aberto.
CREATE TABLE IF NOT EXISTS finance_transactions (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    clinic_id      INTEGER NOT NULL DEFAULT 1,
    kind           TEXT    NOT NULL CHECK (kind IN ('income', 'expense')),
    description    TEXT    NOT NULL,
    category       TEXT    NOT NULL,
    amount_cents   INTEGER NOT NULL CHECK (amount_cents > 0),
    due_date       TEXT    NOT NULL,
    paid_on        TEXT,
    payment_method TEXT,
    account_id     INTEGER REFERENCES finance_accounts (id),
    doctor_id      INTEGER REFERENCES doctors (id),
    patient_id     INTEGER REFERENCES patients (id),
    appointment_id INTEGER UNIQUE REFERENCES appointments (id),
    procedure_id   INTEGER REFERENCES procedures (id),
    health_plan_id INTEGER REFERENCES health_plans (id),
    plan_card      TEXT,
    plan_guide     TEXT,
    created_at     TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now'))
);
CREATE INDEX IF NOT EXISTS idx_finance_due ON finance_transactions (clinic_id, due_date);
CREATE INDEX IF NOT EXISTS idx_finance_paid ON finance_transactions (clinic_id, paid_on);

-- Repasse: porcentagem do valor recebido que vai para o médico. Regra por procedimento
-- (procedure_id) vence a regra geral do médico (procedure_id vazio).
CREATE TABLE IF NOT EXISTS payout_rules (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    clinic_id    INTEGER NOT NULL DEFAULT 1,
    doctor_id    INTEGER NOT NULL REFERENCES doctors (id),
    procedure_id INTEGER REFERENCES procedures (id),
    percent      INTEGER NOT NULL CHECK (percent BETWEEN 0 AND 100)
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_payout_rules ON payout_rules (doctor_id, COALESCE(procedure_id, 0));

-- Estoque de materiais e medicamentos.
CREATE TABLE IF NOT EXISTS stock_items (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    clinic_id    INTEGER NOT NULL DEFAULT 1,
    name         TEXT    NOT NULL,
    unit         TEXT    NOT NULL DEFAULT 'un',
    quantity     INTEGER NOT NULL DEFAULT 0 CHECK (quantity >= 0),
    min_quantity INTEGER NOT NULL DEFAULT 0 CHECK (min_quantity >= 0),
    active       INTEGER NOT NULL DEFAULT 1,
    UNIQUE (clinic_id, name)
);

CREATE TABLE IF NOT EXISTS stock_movements (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    clinic_id  INTEGER NOT NULL DEFAULT 1,
    item_id    INTEGER NOT NULL REFERENCES stock_items (id),
    delta      INTEGER NOT NULL CHECK (delta <> 0),
    reason     TEXT,
    created_by INTEGER NOT NULL REFERENCES users (id),
    created_at TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now'))
);
CREATE INDEX IF NOT EXISTS idx_stock_movements_item ON stock_movements (item_id, created_at);
