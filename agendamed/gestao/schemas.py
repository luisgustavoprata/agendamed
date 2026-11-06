"""Esquemas de entrada da gestão: o formato e os limites dos dados que a API recebe.

Cada classe descreve o corpo (JSON) de uma requisição. O Pydantic confere os tipos e os
limites e devolve erro 422 com a mensagem do campo quando algo não confere.
Valores em dinheiro são inteiros em centavos (R$ 12,34 = 1234).
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from pydantic import Field, model_validator

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
