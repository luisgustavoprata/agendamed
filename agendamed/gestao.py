"""Prontuário, prescrições, procedimentos, convênios, financeiro, repasse, estoque e relatórios.

Todo o SQL destes módulos fica aqui. Como nos outros repositórios, cada consulta inclui o
`clinic_id`: um id de outra clínica simplesmente não é encontrado (404).
Valores em dinheiro são inteiros em centavos.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import date
from typing import Annotated, Literal

from pydantic import Field, model_validator

from agendamed.errors import BusinessRuleError, ConflictError, NotFoundError
from agendamed.schemas import InputSchema

DbId = Annotated[int, Field(gt=0, le=2**53 - 1)]
BoundedDate = Annotated[date, Field(ge=date(1900, 1, 1), le=date(2100, 12, 31))]

ShortText = Annotated[str, Field(min_length=1, max_length=200)]
LongText = Annotated[str, Field(min_length=1, max_length=20_000)]
Cents = Annotated[int, Field(ge=0, le=100_000_000_00)]
PositiveCents = Annotated[int, Field(gt=0, le=100_000_000_00)]

RECORD_KINDS = {
    "anamnese": "Anamnese",
    "evolucao": "Evolução",
    "exame_fisico": "Exame físico",
    "diagnostico": "Hipótese diagnóstica",
    "conduta": "Conduta",
    "exame": "Resultado de exame",
    "anotacao": "Anotação",
}
PRESCRIPTION_KINDS = {
    "simples": "Receituário simples",
    "controle_especial": "Receituário de controle especial",
    "atestado": "Atestado médico",
    "exames": "Solicitação de exames",
    "relatorio": "Relatório médico",
}
PAYMENT_METHODS = (
    "dinheiro",
    "pix",
    "cartao_credito",
    "cartao_debito",
    "boleto",
    "transferencia",
    "convenio",
)


# ---------------------------------------------------------------- esquemas de entrada


class ClinicalSummaryUpdate(InputSchema):
    allergies: str | None = Field(default=None, max_length=2000)
    conditions: str | None = Field(default=None, max_length=2000)
    medications: str | None = Field(default=None, max_length=2000)
    blood_type: Literal["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"] | None = None
    notes: str | None = Field(default=None, max_length=5000)


class RecordEntryCreate(InputSchema):
    kind: Literal[
        "anamnese", "evolucao", "exame_fisico", "diagnostico", "conduta", "exame", "anotacao"
    ]
    content: LongText
    doctor_id: DbId | None = None
    appointment_id: DbId | None = None


class PrescriptionItem(InputSchema):
    name: ShortText = Field(description="Medicamento ou exame.")
    dosage: str | None = Field(default=None, max_length=200, description="Ex.: 500 mg, 1 caixa")
    instructions: str | None = Field(
        default=None, max_length=1000, description="Posologia. Ex.: 1 comprimido de 8/8h por 7 dias"
    )


class PrescriptionCreate(InputSchema):
    kind: Literal["simples", "controle_especial", "atestado", "exames", "relatorio"]
    doctor_id: DbId | None = None
    items: list[PrescriptionItem] = Field(default=[], max_length=30)
    text: str | None = Field(
        default=None, max_length=5000, description="Texto livre (atestado ou observações)."
    )

    @model_validator(mode="after")
    def needs_content(self) -> PrescriptionCreate:
        if not self.items and not self.text:
            raise ValueError("Inclua ao menos um item ou um texto.")
        return self


class ProcedureCreate(InputSchema):
    name: ShortText
    tuss_code: str | None = Field(
        default=None, pattern=r"^\d{8}$", description="Código TUSS (8 dígitos)"
    )
    price_cents: Cents
    active: bool = True


class HealthPlanCreate(InputSchema):
    name: ShortText
    ans_code: str | None = Field(
        default=None, pattern=r"^\d{6}$", description="Registro ANS da operadora (6 dígitos)"
    )
    active: bool = True


class FinanceAccountCreate(InputSchema):
    name: ShortText


class TransactionCreate(InputSchema):
    kind: Literal["income", "expense"]
    description: ShortText
    category: ShortText
    amount_cents: PositiveCents
    due_date: BoundedDate
    paid_on: BoundedDate | None = None
    payment_method: Literal[PAYMENT_METHODS] | None = None  # type: ignore[valid-type]
    account_id: DbId | None = None
    doctor_id: DbId | None = None
    patient_id: DbId | None = None


class TransactionUpdate(InputSchema):
    description: ShortText | None = None
    category: ShortText | None = None
    amount_cents: PositiveCents | None = None
    due_date: BoundedDate | None = None


class TransactionPay(InputSchema):
    paid_on: BoundedDate
    account_id: DbId | None = None
    payment_method: Literal[PAYMENT_METHODS] | None = None  # type: ignore[valid-type]


class AppointmentCharge(InputSchema):
    """Fatura uma consulta: particular (com preço) ou convênio (com carteirinha)."""

    procedure_id: DbId
    health_plan_id: DbId | None = None
    amount_cents: Cents | None = Field(
        default=None, description="Se vazio, usa o preço do procedimento."
    )
    plan_card: str | None = Field(
        default=None, max_length=40, description="Número da carteirinha do convênio"
    )
    plan_guide: str | None = Field(
        default=None, max_length=40, description="Número da guia / senha de autorização"
    )
    paid_on: BoundedDate | None = None
    account_id: DbId | None = None
    payment_method: Literal[PAYMENT_METHODS] | None = None  # type: ignore[valid-type]


class PayoutRuleSet(InputSchema):
    doctor_id: DbId
    procedure_id: DbId | None = None
    percent: int = Field(ge=0, le=100)


class StockItemCreate(InputSchema):
    name: ShortText
    unit: str = Field(default="un", min_length=1, max_length=20)
    min_quantity: int = Field(default=0, ge=0, le=1_000_000)


class StockItemUpdate(InputSchema):
    name: ShortText | None = None
    unit: str | None = Field(default=None, min_length=1, max_length=20)
    min_quantity: int | None = Field(default=None, ge=0, le=1_000_000)
    active: bool | None = None


class StockMovementCreate(InputSchema):
    delta: int = Field(
        ge=-1_000_000, le=1_000_000, description="Positivo = entrada, negativo = saída."
    )
    reason: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def not_zero(self) -> StockMovementCreate:
        if self.delta == 0:
            raise ValueError("A quantidade não pode ser zero.")
        return self


REQUEST_MODELS = {
    "ClinicalSummaryUpdate": ClinicalSummaryUpdate,
    "RecordEntryCreate": RecordEntryCreate,
    "PrescriptionCreate": PrescriptionCreate,
    "ProcedureCreate": ProcedureCreate,
    "HealthPlanCreate": HealthPlanCreate,
    "FinanceAccountCreate": FinanceAccountCreate,
    "TransactionCreate": TransactionCreate,
    "TransactionUpdate": TransactionUpdate,
    "TransactionPay": TransactionPay,
    "AppointmentCharge": AppointmentCharge,
    "PayoutRuleSet": PayoutRuleSet,
    "StockItemCreate": StockItemCreate,
    "StockItemUpdate": StockItemUpdate,
    "StockMovementCreate": StockMovementCreate,
}


# ---------------------------------------------------------------- utilitários


def _row(row) -> dict | None:
    return dict(row) if row is not None else None


def _bools(item: dict, *names: str) -> dict:
    for name in names:
        if name in item:
            item[name] = bool(item[name])
    return item


def _iso(value: date | None) -> str | None:
    return value.isoformat() if value else None


# ---------------------------------------------------------------- banco

# Nesta versão há uma clínica só. As tabelas de gestão (e pacientes, médicos e consultas)
# têm a coluna clinic_id sempre igual a 1, o que mantém o SQL igual ao da versão para
# várias clínicas.
CLINIC_ID = 1


class GestaoDb:
    """Adapta a conexão sqlite3 desta versão à interface usada pelo repositório."""

    integrity_errors = (sqlite3.IntegrityError,)

    def __init__(self, conn: sqlite3.Connection):
        self.raw = conn

    def execute(self, sql: str, params=()):
        return self.raw.execute(sql, tuple(params))

    def one(self, sql: str, params=()):
        return self.execute(sql, params).fetchone()

    def all(self, sql: str, params=()) -> list:
        return self.execute(sql, params).fetchall()

    def insert(self, sql: str, params=()) -> int:
        return self.execute(sql, params).lastrowid

    @contextmanager
    def transaction(self, *, lock_keys=()):
        self.raw.execute("BEGIN IMMEDIATE" if lock_keys else "BEGIN")
        try:
            yield
        except BaseException:
            self.raw.execute("ROLLBACK")
            raise
        self.raw.execute("COMMIT")


# ---------------------------------------------------------------- repositório


class Gestao:
    """Acesso aos dados de gestão de uma clínica."""

    def __init__(self, db, clinic_id: int):
        self.db = db
        self.clinic_id = clinic_id

    def _insert(self, sql: str, params: tuple, conflict: str) -> int:
        try:
            return self.db.insert(sql, params)
        except self.db.integrity_errors as exc:
            raise ConflictError(conflict) from exc

    # --- conferências de pertencimento à clínica

    def require_patient(self, patient_id: int) -> dict:
        row = self.db.one(
            "SELECT id, name, cpf, birth_date FROM patients " "WHERE id = ? AND clinic_id = ?",
            (patient_id, self.clinic_id),
        )
        if row is None:
            raise NotFoundError("Paciente não encontrado.")
        return dict(row)

    def require_doctor(self, doctor_id: int) -> dict:
        row = self.db.one(
            "SELECT id, name, specialty, crm FROM doctors " "WHERE id = ? AND clinic_id = ?",
            (doctor_id, self.clinic_id),
        )
        if row is None:
            raise NotFoundError("Médico não encontrado.")
        return dict(row)

    def require_appointment(self, appointment_id: int) -> dict:
        row = self.db.one(
            """SELECT a.id, a.doctor_id, a.patient_id, a.start_at, a.status,
                      d.name AS doctor_name, p.name AS patient_name
               FROM appointments a JOIN doctors d ON d.id = a.doctor_id
               JOIN patients p ON p.id = a.patient_id
               WHERE a.id = ? AND a.clinic_id = ?""",
            (appointment_id, self.clinic_id),
        )
        if row is None:
            raise NotFoundError("Consulta não encontrada.")
        return dict(row)

    def _require_in_clinic(self, table: str, item_id: int | None, message: str) -> None:
        if item_id is None:
            return
        if (
            self.db.one(
                f"SELECT id FROM {table} WHERE id = ? AND clinic_id = ?", (item_id, self.clinic_id)
            )
            is None
        ):
            raise NotFoundError(message)

    # --- prontuário

    def clinical_summary(self, patient_id: int) -> dict:
        row = self.db.one(
            """SELECT c.allergies, c.conditions, c.medications, c.blood_type, c.notes,
                      c.updated_at, u.full_name AS updated_by
               FROM patient_clinical c LEFT JOIN users u ON u.id = c.updated_by
               WHERE c.patient_id = ? AND c.clinic_id = ?""",
            (patient_id, self.clinic_id),
        )
        empty = dict.fromkeys(
            (
                "allergies",
                "conditions",
                "medications",
                "blood_type",
                "notes",
                "updated_at",
                "updated_by",
            )
        )
        return _row(row) or empty

    def save_clinical_summary(
        self, patient_id: int, data: ClinicalSummaryUpdate, user_id: int, now: str
    ) -> dict:
        values = (
            data.allergies,
            data.conditions,
            data.medications,
            data.blood_type,
            data.notes,
            now,
            user_id,
        )
        exists = self.db.one(
            "SELECT patient_id FROM patient_clinical WHERE patient_id = ? " "AND clinic_id = ?",
            (patient_id, self.clinic_id),
        )
        if exists:
            self.db.execute(
                """UPDATE patient_clinical SET allergies = ?, conditions = ?, medications = ?,
                   blood_type = ?, notes = ?, updated_at = ?, updated_by = ?
                   WHERE patient_id = ? AND clinic_id = ?""",
                (*values, patient_id, self.clinic_id),
            )
        else:
            self.db.execute(
                """INSERT INTO patient_clinical (allergies, conditions, medications, blood_type,
                   notes, updated_at, updated_by, patient_id, clinic_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (*values, patient_id, self.clinic_id),
            )
        return self.clinical_summary(patient_id)

    def record_entries(self, patient_id: int) -> list[dict]:
        rows = self.db.all(
            """SELECT r.id, r.kind, r.content, r.created_at, r.appointment_id, r.doctor_id,
                      d.name AS doctor_name, u.full_name AS author
               FROM record_entries r LEFT JOIN doctors d ON d.id = r.doctor_id
               JOIN users u ON u.id = r.created_by
               WHERE r.patient_id = ? AND r.clinic_id = ?
               ORDER BY r.created_at DESC, r.id DESC""",
            (patient_id, self.clinic_id),
        )
        return [{**dict(r), "kind_label": RECORD_KINDS[r["kind"]]} for r in rows]

    def add_record_entry(
        self,
        patient_id: int,
        data: RecordEntryCreate,
        doctor_id: int | None,
        user_id: int,
        now: str,
    ) -> dict:
        if data.appointment_id is not None:
            appointment = self.require_appointment(data.appointment_id)
            if appointment["patient_id"] != patient_id:
                raise BusinessRuleError("A consulta informada é de outro paciente.")
        entry_id = self.db.insert(
            """INSERT INTO record_entries (clinic_id, patient_id, doctor_id, appointment_id, kind,
                                           content, created_by, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                self.clinic_id,
                patient_id,
                doctor_id,
                data.appointment_id,
                data.kind,
                data.content,
                user_id,
                now,
            ),
        )
        return next(e for e in self.record_entries(patient_id) if e["id"] == entry_id)

    # --- prescrições

    def _prescription(self, row) -> dict:
        item = dict(row)
        item["items"] = json.loads(item["items"] or "[]")
        item["kind_label"] = PRESCRIPTION_KINDS[item["kind"]]
        return item

    _PRESCRIPTION_SELECT = """
        SELECT pr.id, pr.kind, pr.items, pr.text, pr.created_at, pr.patient_id, pr.doctor_id,
               d.name AS doctor_name, d.crm AS doctor_crm, d.specialty AS doctor_specialty,
               p.name AS patient_name, p.cpf AS patient_cpf, p.birth_date AS patient_birth_date
        FROM prescriptions pr JOIN doctors d ON d.id = pr.doctor_id
        JOIN patients p ON p.id = pr.patient_id
    """

    def prescriptions(self, patient_id: int) -> list[dict]:
        rows = self.db.all(
            f"{self._PRESCRIPTION_SELECT} WHERE pr.patient_id = ? AND pr.clinic_id = ? "
            "ORDER BY pr.created_at DESC, pr.id DESC",
            (patient_id, self.clinic_id),
        )
        return [self._prescription(r) for r in rows]

    def prescription(self, prescription_id: int) -> dict:
        row = self.db.one(
            f"{self._PRESCRIPTION_SELECT} WHERE pr.id = ? AND pr.clinic_id = ?",
            (prescription_id, self.clinic_id),
        )
        if row is None:
            raise NotFoundError("Prescrição não encontrada.")
        return self._prescription(row)

    def add_prescription(
        self, patient_id: int, data: PrescriptionCreate, doctor_id: int, user_id: int, now: str
    ) -> dict:
        items = json.dumps([i.model_dump() for i in data.items], ensure_ascii=False)
        new_id = self.db.insert(
            """INSERT INTO prescriptions (clinic_id, patient_id, doctor_id, kind, items, text,
                                          created_by, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (self.clinic_id, patient_id, doctor_id, data.kind, items, data.text, user_id, now),
        )
        return self.prescription(new_id)

    # --- catálogos: procedimentos, convênios e contas

    def _list(self, table: str, columns: str, *, only_active: bool) -> list[dict]:
        where = "clinic_id = ?" + (" AND active = 1" if only_active else "")
        rows = self.db.all(
            f"SELECT {columns} FROM {table} WHERE {where} ORDER BY name", (self.clinic_id,)
        )
        return [_bools(dict(r), "active") for r in rows]

    def procedures(self, only_active=False) -> list[dict]:
        return self._list(
            "procedures", "id, name, tuss_code, price_cents, active", only_active=only_active
        )

    def health_plans(self, only_active=False) -> list[dict]:
        return self._list("health_plans", "id, name, ans_code, active", only_active=only_active)

    def accounts(self) -> list[dict]:
        rows = self.db.all(
            """SELECT a.id, a.name, a.active,
                      COALESCE(SUM(CASE WHEN t.kind = 'income' THEN t.amount_cents
                                        ELSE -t.amount_cents END), 0) AS balance_cents
               FROM finance_accounts a
               LEFT JOIN finance_transactions t
                      ON t.account_id = a.id AND t.paid_on IS NOT NULL
               WHERE a.clinic_id = ? GROUP BY a.id, a.name, a.active ORDER BY a.name""",
            (self.clinic_id,),
        )
        return [_bools(dict(r), "active") for r in rows]

    def _get(self, table: str, columns: str, item_id: int, message: str) -> dict:
        row = self.db.one(
            f"SELECT {columns} FROM {table} WHERE id = ? AND clinic_id = ?",
            (item_id, self.clinic_id),
        )
        if row is None:
            raise NotFoundError(message)
        return _bools(dict(row), "active")

    def procedure(self, procedure_id: int) -> dict:
        return self._get(
            "procedures",
            "id, name, tuss_code, price_cents, active",
            procedure_id,
            "Procedimento não encontrado.",
        )

    def health_plan(self, plan_id: int) -> dict:
        return self._get(
            "health_plans", "id, name, ans_code, active", plan_id, "Convênio não encontrado."
        )

    def save_procedure(self, data: ProcedureCreate, procedure_id: int | None = None) -> dict:
        values = (data.name, data.tuss_code, data.price_cents, int(data.active))
        conflict = "Já existe um procedimento com este nome."
        if procedure_id is None:
            procedure_id = self._insert(
                "INSERT INTO procedures (name, tuss_code, price_cents, active, clinic_id) "
                "VALUES (?, ?, ?, ?, ?)",
                (*values, self.clinic_id),
                conflict,
            )
        else:
            self.procedure(procedure_id)
            try:
                self.db.execute(
                    "UPDATE procedures SET name = ?, tuss_code = ?, price_cents = ?, active = ? "
                    "WHERE id = ? AND clinic_id = ?",
                    (*values, procedure_id, self.clinic_id),
                )
            except self.db.integrity_errors as exc:
                raise ConflictError(conflict) from exc
        return self.procedure(procedure_id)

    def save_health_plan(self, data: HealthPlanCreate, plan_id: int | None = None) -> dict:
        values = (data.name, data.ans_code, int(data.active))
        conflict = "Já existe um convênio com este nome."
        if plan_id is None:
            plan_id = self._insert(
                "INSERT INTO health_plans (name, ans_code, active, clinic_id) VALUES (?, ?, ?, ?)",
                (*values, self.clinic_id),
                conflict,
            )
        else:
            self.health_plan(plan_id)
            try:
                self.db.execute(
                    "UPDATE health_plans SET name = ?, ans_code = ?, active = ? "
                    "WHERE id = ? AND clinic_id = ?",
                    (*values, plan_id, self.clinic_id),
                )
            except self.db.integrity_errors as exc:
                raise ConflictError(conflict) from exc
        return self.health_plan(plan_id)

    def add_account(self, data: FinanceAccountCreate) -> dict:
        new_id = self._insert(
            "INSERT INTO finance_accounts (name, clinic_id) VALUES (?, ?)",
            (data.name, self.clinic_id),
            "Já existe uma conta com este nome.",
        )
        return next(a for a in self.accounts() if a["id"] == new_id)

    # --- lançamentos financeiros

    _TX_SELECT = """
        SELECT t.id, t.kind, t.description, t.category, t.amount_cents, t.due_date, t.paid_on,
               t.payment_method, t.account_id, fa.name AS account_name,
               t.doctor_id, d.name AS doctor_name, t.patient_id, p.name AS patient_name,
               t.appointment_id, t.procedure_id, pc.name AS procedure_name,
               pc.tuss_code AS procedure_tuss, t.health_plan_id, hp.name AS health_plan_name,
               t.plan_card, t.plan_guide
        FROM finance_transactions t
        LEFT JOIN finance_accounts fa ON fa.id = t.account_id
        LEFT JOIN doctors d ON d.id = t.doctor_id
        LEFT JOIN patients p ON p.id = t.patient_id
        LEFT JOIN procedures pc ON pc.id = t.procedure_id
        LEFT JOIN health_plans hp ON hp.id = t.health_plan_id
    """

    @staticmethod
    def _tx(row, today: str) -> dict:
        item = dict(row)
        if item["paid_on"]:
            item["status"] = "paid"
        else:
            item["status"] = "overdue" if item["due_date"] < today else "open"
        return item

    def transaction(self, tx_id: int, today: str) -> dict:
        row = self.db.one(
            f"{self._TX_SELECT} WHERE t.id = ? AND t.clinic_id = ?", (tx_id, self.clinic_id)
        )
        if row is None:
            raise NotFoundError("Lançamento não encontrado.")
        return self._tx(row, today)

    def transactions(
        self,
        *,
        start: date,
        end: date,
        today: str,
        kind: str | None = None,
        status: str | None = None,
        account_id: int | None = None,
        health_plan_id: int | None = None,
    ) -> list[dict]:
        # Pago: entra pela data do pagamento. Em aberto: pela data de vencimento.
        where = ["t.clinic_id = ?", "COALESCE(t.paid_on, t.due_date) BETWEEN ? AND ?"]
        params: list = [self.clinic_id, start.isoformat(), end.isoformat()]
        if kind:
            where.append("t.kind = ?")
            params.append(kind)
        if status == "paid":
            where.append("t.paid_on IS NOT NULL")
        elif status == "open":
            where.append("t.paid_on IS NULL")
        if account_id:
            where.append("t.account_id = ?")
            params.append(account_id)
        if health_plan_id:
            where.append("t.health_plan_id = ?")
            params.append(health_plan_id)
        rows = self.db.all(
            f"{self._TX_SELECT} WHERE {' AND '.join(where)} "
            "ORDER BY COALESCE(t.paid_on, t.due_date), t.id",
            params,
        )
        return [self._tx(r, today) for r in rows]

    def _check_links(self, *, account_id=None, doctor_id=None, patient_id=None) -> None:
        self._require_in_clinic("finance_accounts", account_id, "Conta não encontrada.")
        self._require_in_clinic("doctors", doctor_id, "Médico não encontrado.")
        self._require_in_clinic("patients", patient_id, "Paciente não encontrado.")

    def add_transaction(self, data: TransactionCreate, today: str) -> dict:
        self._check_links(
            account_id=data.account_id, doctor_id=data.doctor_id, patient_id=data.patient_id
        )
        tx_id = self.db.insert(
            """INSERT INTO finance_transactions (clinic_id, kind, description, category,
                   amount_cents, due_date, paid_on, payment_method, account_id, doctor_id,
                   patient_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                self.clinic_id,
                data.kind,
                data.description,
                data.category,
                data.amount_cents,
                data.due_date.isoformat(),
                _iso(data.paid_on),
                data.payment_method,
                data.account_id,
                data.doctor_id,
                data.patient_id,
            ),
        )
        return self.transaction(tx_id, today)

    def update_transaction(self, tx_id: int, data: TransactionUpdate, today: str) -> dict:
        self.transaction(tx_id, today)
        changes = data.model_dump(exclude_unset=True, exclude_none=True)
        if changes:
            if "due_date" in changes:
                changes["due_date"] = changes["due_date"].isoformat()
            sets = ", ".join(f"{name} = ?" for name in changes)
            self.db.execute(
                f"UPDATE finance_transactions SET {sets} WHERE id = ? AND clinic_id = ?",
                (*changes.values(), tx_id, self.clinic_id),
            )
        return self.transaction(tx_id, today)

    def pay_transaction(self, tx_id: int, data: TransactionPay, today: str) -> dict:
        tx = self.transaction(tx_id, today)
        if tx["paid_on"]:
            raise ConflictError("Este lançamento já foi pago.")
        self._check_links(account_id=data.account_id)
        self.db.execute(
            """UPDATE finance_transactions SET paid_on = ?, account_id = COALESCE(?, account_id),
               payment_method = COALESCE(?, payment_method) WHERE id = ? AND clinic_id = ?""",
            (data.paid_on.isoformat(), data.account_id, data.payment_method, tx_id, self.clinic_id),
        )
        return self.transaction(tx_id, today)

    def unpay_transaction(self, tx_id: int, today: str) -> dict:
        self.transaction(tx_id, today)
        self.db.execute(
            "UPDATE finance_transactions SET paid_on = NULL " "WHERE id = ? AND clinic_id = ?",
            (tx_id, self.clinic_id),
        )
        return self.transaction(tx_id, today)

    def delete_transaction(self, tx_id: int, today: str) -> None:
        tx = self.transaction(tx_id, today)
        if tx["paid_on"]:
            raise ConflictError("Desfaça o pagamento antes de excluir o lançamento.")
        self.db.execute(
            "DELETE FROM finance_transactions WHERE id = ? AND clinic_id = ?",
            (tx_id, self.clinic_id),
        )

    def charge_appointment(self, appointment_id: int, data: AppointmentCharge, today: str) -> dict:
        """Cria a conta a receber de uma consulta (uma por consulta)."""
        appointment = self.require_appointment(appointment_id)
        if appointment["status"] == "cancelled":
            raise ConflictError("Consulta cancelada não pode ser faturada.")
        procedure = self.procedure(data.procedure_id)
        plan = self.health_plan(data.health_plan_id) if data.health_plan_id else None
        amount = data.amount_cents if data.amount_cents is not None else procedure["price_cents"]
        if amount <= 0:
            raise BusinessRuleError("Informe o valor da consulta.")
        self._check_links(account_id=data.account_id)
        description = f"{procedure['name']} — {appointment['patient_name']}"
        method = data.payment_method or ("convenio" if plan else None)
        tx_id = self._insert(
            """INSERT INTO finance_transactions (clinic_id, kind, description, category,
                   amount_cents, due_date, paid_on, payment_method, account_id, doctor_id,
                   patient_id, appointment_id, procedure_id, health_plan_id, plan_card,
                   plan_guide)
               VALUES (?, 'income', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                self.clinic_id,
                description,
                "Convênio" if plan else "Consultas particulares",
                amount,
                appointment["start_at"][:10],
                _iso(data.paid_on),
                method,
                data.account_id,
                appointment["doctor_id"],
                appointment["patient_id"],
                appointment_id,
                procedure["id"],
                plan["id"] if plan else None,
                data.plan_card,
                data.plan_guide,
            ),
            "Esta consulta já foi faturada.",
        )
        return self.transaction(tx_id, today)

    def release_appointment_charge(self, appointment_id: int) -> None:
        """Consulta cancelada: a cobrança em aberto sai do financeiro.

        Se já foi paga, fica (o dinheiro entrou; devolução é um lançamento à parte).
        """
        self.db.execute(
            """DELETE FROM finance_transactions
               WHERE appointment_id = ? AND clinic_id = ? AND paid_on IS NULL""",
            (appointment_id, self.clinic_id),
        )

    def appointment_charge(self, appointment_id: int, today: str) -> dict | None:
        row = self.db.one(
            f"{self._TX_SELECT} WHERE t.appointment_id = ? AND t.clinic_id = ?",
            (appointment_id, self.clinic_id),
        )
        return self._tx(row, today) if row else None

    def cashflow(self, start: date, end: date, today: str) -> dict:
        """Fluxo de caixa: realizado (pago) e previsto (em aberto), por dia e por categoria."""
        txs = self.transactions(start=start, end=end, today=today)
        days: dict[str, dict] = {}
        categories: dict[tuple[str, str], int] = {}
        totals = {
            "income_paid": 0,
            "expense_paid": 0,
            "income_open": 0,
            "expense_open": 0,
            "overdue_income": 0,
            "overdue_expense": 0,
        }
        for tx in txs:
            paid = tx["status"] == "paid"
            key = f"{tx['kind']}_{'paid' if paid else 'open'}"
            totals[key] += tx["amount_cents"]
            if tx["status"] == "overdue":
                totals[f"overdue_{tx['kind']}"] += tx["amount_cents"]
            day = days.setdefault(
                tx["paid_on"] or tx["due_date"], {"income_cents": 0, "expense_cents": 0}
            )
            day[f"{tx['kind']}_cents"] += tx["amount_cents"]
            if paid:
                cat = (tx["kind"], tx["category"])
                categories[cat] = categories.get(cat, 0) + tx["amount_cents"]
        totals["balance_paid"] = totals["income_paid"] - totals["expense_paid"]
        totals["balance_forecast"] = (
            totals["balance_paid"] + totals["income_open"] - totals["expense_open"]
        )
        return {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "totals": totals,
            "days": [{"date": d, **v} for d, v in sorted(days.items())],
            "categories": [
                {"kind": k, "category": c, "amount_cents": v}
                for (k, c), v in sorted(categories.items(), key=lambda i: -i[1])
            ],
            "accounts": self.accounts(),
        }

    # --- repasse

    def payout_rules(self) -> list[dict]:
        rows = self.db.all(
            """SELECT r.id, r.doctor_id, d.name AS doctor_name, r.procedure_id,
                      p.name AS procedure_name, r.percent
               FROM payout_rules r JOIN doctors d ON d.id = r.doctor_id
               LEFT JOIN procedures p ON p.id = r.procedure_id
               WHERE r.clinic_id = ? ORDER BY d.name, p.name""",
            (self.clinic_id,),
        )
        return [dict(r) for r in rows]

    def set_payout_rule(self, data: PayoutRuleSet) -> list[dict]:
        self.require_doctor(data.doctor_id)
        if data.procedure_id is not None:
            self.procedure(data.procedure_id)
        proc_clause = "procedure_id = ?" if data.procedure_id else "procedure_id IS NULL"
        params = (data.doctor_id, data.procedure_id) if data.procedure_id else (data.doctor_id,)
        self.db.execute(
            f"DELETE FROM payout_rules WHERE clinic_id = ? AND doctor_id = ? AND {proc_clause}",
            (self.clinic_id, *params),
        )
        self.db.execute(
            "INSERT INTO payout_rules (clinic_id, doctor_id, procedure_id, percent) "
            "VALUES (?, ?, ?, ?)",
            (self.clinic_id, data.doctor_id, data.procedure_id, data.percent),
        )
        return self.payout_rules()

    def delete_payout_rule(self, rule_id: int) -> None:
        self.db.execute(
            "DELETE FROM payout_rules WHERE id = ? AND clinic_id = ?", (rule_id, self.clinic_id)
        )

    def payouts(self, start: date, end: date, today: str) -> list[dict]:
        """Repasse de cada médico sobre o que foi RECEBIDO no período."""
        rules = {(r["doctor_id"], r["procedure_id"]): r["percent"] for r in self.payout_rules()}
        report: dict[int, dict] = {}
        for tx in self.transactions(
            start=start, end=end, today=today, kind="income", status="paid"
        ):
            if not tx["doctor_id"]:
                continue
            percent = rules.get(
                (tx["doctor_id"], tx["procedure_id"]), rules.get((tx["doctor_id"], None), 0)
            )
            share = round(tx["amount_cents"] * percent / 100)
            doc = report.setdefault(
                tx["doctor_id"],
                {
                    "doctor_id": tx["doctor_id"],
                    "doctor_name": tx["doctor_name"],
                    "received_cents": 0,
                    "payout_cents": 0,
                    "items": [],
                },
            )
            doc["received_cents"] += tx["amount_cents"]
            doc["payout_cents"] += share
            doc["items"].append(
                {
                    "transaction_id": tx["id"],
                    "date": tx["paid_on"],
                    "description": tx["description"],
                    "amount_cents": tx["amount_cents"],
                    "percent": percent,
                    "payout_cents": share,
                }
            )
        return sorted(report.values(), key=lambda d: d["doctor_name"])

    # --- estoque

    def stock_items(self) -> list[dict]:
        rows = self.db.all(
            "SELECT id, name, unit, quantity, min_quantity, active FROM stock_items "
            "WHERE clinic_id = ? ORDER BY active DESC, name",
            (self.clinic_id,),
        )
        return [
            _bools({**dict(r), "low": r["quantity"] <= r["min_quantity"]}, "active") for r in rows
        ]

    def stock_item(self, item_id: int) -> dict:
        item = self._get(
            "stock_items",
            "id, name, unit, quantity, min_quantity, active",
            item_id,
            "Item de estoque não encontrado.",
        )
        item["low"] = item["quantity"] <= item["min_quantity"]
        return item

    def add_stock_item(self, data: StockItemCreate) -> dict:
        new_id = self._insert(
            "INSERT INTO stock_items (clinic_id, name, unit, min_quantity) VALUES (?, ?, ?, ?)",
            (self.clinic_id, data.name, data.unit, data.min_quantity),
            "Já existe um item com este nome.",
        )
        return self.stock_item(new_id)

    def update_stock_item(self, item_id: int, data: StockItemUpdate) -> dict:
        self.stock_item(item_id)
        changes = data.model_dump(exclude_unset=True, exclude_none=True)
        if "active" in changes:
            changes["active"] = int(changes["active"])
        if changes:
            sets = ", ".join(f"{name} = ?" for name in changes)
            try:
                self.db.execute(
                    f"UPDATE stock_items SET {sets} WHERE id = ? AND clinic_id = ?",
                    (*changes.values(), item_id, self.clinic_id),
                )
            except self.db.integrity_errors as exc:
                raise ConflictError("Já existe um item com este nome.") from exc
        return self.stock_item(item_id)

    def move_stock(self, item_id: int, data: StockMovementCreate, user_id: int, now: str) -> dict:
        with self.db.transaction(lock_keys=(f"stock:{item_id}",)):
            item = self.stock_item(item_id)
            if item["quantity"] + data.delta < 0:
                raise BusinessRuleError(
                    f"Estoque insuficiente: há {item['quantity']} {item['unit']} de "
                    f"{item['name']}."
                )
            self.db.execute(
                "UPDATE stock_items SET quantity = quantity + ? " "WHERE id = ? AND clinic_id = ?",
                (data.delta, item_id, self.clinic_id),
            )
            self.db.execute(
                "INSERT INTO stock_movements (clinic_id, item_id, delta, reason, created_by, "
                "created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (self.clinic_id, item_id, data.delta, data.reason, user_id, now),
            )
        return self.stock_item(item_id)

    def stock_movements(self, item_id: int) -> list[dict]:
        self.stock_item(item_id)
        rows = self.db.all(
            """SELECT m.id, m.delta, m.reason, m.created_at, u.full_name AS author
               FROM stock_movements m JOIN users u ON u.id = m.created_by
               WHERE m.item_id = ? AND m.clinic_id = ? ORDER BY m.created_at DESC, m.id DESC
               LIMIT 200""",
            (item_id, self.clinic_id),
        )
        return [dict(r) for r in rows]

    # --- relatórios de gestão

    def overview(self, start: date, end: date, today: str) -> dict:
        start_s, end_s = start.isoformat(), f"{end.isoformat()}T23:59:59"
        by_status = {
            r["status"]: r["total"]
            for r in self.db.all(
                "SELECT status, COUNT(*) AS total FROM appointments WHERE clinic_id = ? "
                "AND start_at BETWEEN ? AND ? GROUP BY status",
                (self.clinic_id, start_s, end_s),
            )
        }
        # Agendadas cujo horário já passou e ninguém concluiu: provável falta.
        missed = self.db.one(
            "SELECT COUNT(*) AS total FROM appointments WHERE clinic_id = ? AND status = "
            "'scheduled' AND start_at BETWEEN ? AND ? AND start_at < ?",
            (self.clinic_id, start_s, end_s, today),
        )["total"]
        doctors = self.db.all(
            """SELECT d.id, d.name,
                      SUM(CASE WHEN a.status = 'completed' THEN 1 ELSE 0 END) AS completed,
                      SUM(CASE WHEN a.status = 'cancelled' THEN 1 ELSE 0 END) AS cancelled,
                      COUNT(a.id) AS total
               FROM doctors d LEFT JOIN appointments a ON a.doctor_id = d.id
                    AND a.start_at BETWEEN ? AND ?
               WHERE d.clinic_id = ? AND d.active = 1 GROUP BY d.id, d.name ORDER BY d.name""",
            (start_s, end_s, self.clinic_id),
        )
        revenue = {}
        by_plan: dict[str, int] = {}
        for tx in self.transactions(
            start=start, end=end, today=today, kind="income", status="paid"
        ):
            if tx["doctor_id"]:
                revenue[tx["doctor_id"]] = revenue.get(tx["doctor_id"], 0) + tx["amount_cents"]
            plan = tx["health_plan_name"] or "Particular"
            by_plan[plan] = by_plan.get(plan, 0) + tx["amount_cents"]
        new_patients = self.db.one(
            """SELECT COUNT(*) AS total FROM (
                   SELECT patient_id, MIN(start_at) AS first FROM appointments
                   WHERE clinic_id = ? AND status <> 'cancelled' GROUP BY patient_id) f
               WHERE f.first BETWEEN ? AND ?""",
            (self.clinic_id, start_s, end_s),
        )["total"]
        total = sum(by_status.values())
        cash = self.cashflow(start, end, today)["totals"]
        low_stock = [i for i in self.stock_items() if i["active"] and i["low"]]
        return {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "appointments": {
                "total": total,
                "scheduled": by_status.get("scheduled", 0),
                "completed": by_status.get("completed", 0),
                "cancelled": by_status.get("cancelled", 0),
                "missed": missed,
                "cancel_rate": round(100 * by_status.get("cancelled", 0) / total, 1)
                if total
                else 0,
            },
            "new_patients": new_patients,
            "finance": cash,
            "doctors": [
                {
                    **dict(d),
                    "completed": d["completed"] or 0,
                    "cancelled": d["cancelled"] or 0,
                    "revenue_cents": revenue.get(d["id"], 0),
                }
                for d in doctors
            ],
            "revenue_by_plan": [
                {"name": k, "amount_cents": v}
                for k, v in sorted(by_plan.items(), key=lambda i: -i[1])
            ],
            "low_stock": low_stock,
        }

    def tiss_batch(self, plan_id: int, start: date, end: date, today: str) -> dict:
        """Guias de consulta de um convênio no período, prontas para imprimir em lote."""
        plan = self.health_plan(plan_id)
        rows = self.db.all(
            f"""{self._TX_SELECT.replace('SELECT t.id,', '''SELECT a.start_at,
                   d.crm AS doctor_crm, d.specialty AS doctor_specialty, p.cpf AS patient_cpf,
                   p.birth_date AS patient_birth_date, t.id,''')}
                JOIN appointments a ON a.id = t.appointment_id
                WHERE t.clinic_id = ? AND t.health_plan_id = ?
                  AND a.start_at BETWEEN ? AND ?
                ORDER BY a.start_at""",
            (self.clinic_id, plan_id, start.isoformat(), f"{end.isoformat()}T23:59:59"),
        )
        guides = [self._tx(r, today) for r in rows]
        return {
            "health_plan": plan,
            "start": start.isoformat(),
            "end": end.isoformat(),
            "total_cents": sum(g["amount_cents"] for g in guides),
            "guides": guides,
        }
