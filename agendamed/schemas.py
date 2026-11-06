"""Esquemas Pydantic que validam os dados recebidos pela API."""

from datetime import date, datetime, time
from typing import Annotated

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    NaiveDatetime,
    field_validator,
    model_validator,
)

from agendamed.validators import EMAIL_PATTERN, is_valid_cpf, only_digits

Name = Annotated[str, Field(min_length=3, max_length=120)]

# Identificadores: inteiros positivos que cabem no banco (e em números do JavaScript).
# Sem o limite, um id gigante derrubava a requisição com erro 500.
MAX_ID = 2**53 - 1
DbId = Annotated[int, Field(gt=0, le=MAX_ID)]

# Datas aceitas: de 1900 a 2100. Datas como 31/12/9999 estouravam as contas de "dia seguinte"
# (erro 500). As datas da gestão usam o mesmo intervalo (BoundedDate em gestao/schemas.py).
MIN_DATE, MAX_DATE = date(1900, 1, 1), date(2100, 12, 31)


def _check_datetime(value: datetime) -> datetime:
    """Validador de BoundedDatetime: recusa horários com data fora de 1900 a 2100."""
    if not MIN_DATE <= value.date() <= MAX_DATE:
        raise ValueError("Informe uma data entre 1900 e 2100.")
    return value


BoundedDatetime = Annotated[NaiveDatetime, AfterValidator(_check_datetime)]


class InputSchema(BaseModel):
    """Base de todos os esquemas de entrada.

    Tira espaços do começo e do fim dos textos e recusa campos que o esquema não conhece (assim um
    erro de digitação no nome do campo não passa em silêncio).
    """

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")


class EmailMixin(InputSchema):
    """Campo `email` validado e em minúsculas, para reaproveitar nos esquemas."""

    email: str = Field(max_length=255)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        """Confere o formato do e-mail e o guarda em minúsculas."""
        if not EMAIL_PATTERN.match(value):
            raise ValueError("E-mail inválido.")
        return value.lower()


class UserCreate(EmailMixin):
    """Criação de conta de acesso: e-mail, nome e senha."""

    full_name: Name
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(InputSchema):
    """Corpo do login: e-mail e senha."""

    email: str
    password: str

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        """Põe o e-mail em minúsculas (o cadastro também guarda assim)."""
        return value.lower()


class DoctorCreate(InputSchema):
    """Cadastro de um médico: dados, duração da consulta e o horário de atendimento (`work_start`
    a `work_end`).
    """

    name: Name
    specialty: str = Field(min_length=3, max_length=80)
    crm: str = Field(pattern=r"^\d{4,7}/[A-Z]{2}$", examples=["123456/SP"])
    slot_minutes: int = Field(default=30, ge=10, le=240)
    work_start: time = time(8, 0)
    work_end: time = time(18, 0)

    @model_validator(mode="after")
    def validate_working_hours(self) -> "DoctorCreate":
        """O fim do expediente vem depois do início, e cabe ao menos uma consulta nele."""
        start = self.work_start.hour * 60 + self.work_start.minute
        end = self.work_end.hour * 60 + self.work_end.minute
        if end <= start:
            raise ValueError("O fim do expediente deve ser depois do início.")
        if end - start < self.slot_minutes:
            raise ValueError("O expediente precisa comportar ao menos uma consulta.")
        return self


class PatientCreate(EmailMixin):
    """Cadastro de um paciente."""

    name: Name
    cpf: str
    phone: str | None = Field(default=None, pattern=r"^\+?[\d\s()-]{10,20}$")
    birth_date: date

    @field_validator("cpf")
    @classmethod
    def validate_cpf(cls, value: str) -> str:
        """Confere os dígitos do CPF e guarda só os números."""
        if not is_valid_cpf(value):
            raise ValueError("CPF inválido.")
        return only_digits(value)

    @field_validator("birth_date")
    @classmethod
    def validate_birth_date(cls, value: date) -> date:
        """A data de nascimento não pode estar no futuro."""
        if value > date.today():
            raise ValueError("A data de nascimento não pode estar no futuro.")
        return value


class PatientUpdate(InputSchema):
    """Edição parcial: só os campos enviados mudam. O telefone aceita null para ser apagado."""

    name: Name | None = None
    cpf: str | None = None
    email: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, pattern=r"^\+?[\d\s()-]{10,20}$")
    birth_date: date | None = None

    @field_validator("name", "cpf", "email", "birth_date", mode="before")
    @classmethod
    def required_if_sent(cls, value):
        """Campos obrigatórios podem ficar de fora, mas não podem ser enviados vazios (null)."""
        if value is None:
            raise ValueError("Este campo não pode ficar vazio.")
        return value

    @field_validator("cpf")
    @classmethod
    def validate_cpf(cls, value: str) -> str:
        """Confere os dígitos do CPF e guarda só os números."""
        if not is_valid_cpf(value):
            raise ValueError("CPF inválido.")
        return only_digits(value)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        """Confere o formato do e-mail e o guarda em minúsculas."""
        if not EMAIL_PATTERN.match(value):
            raise ValueError("E-mail inválido.")
        return value.lower()

    @field_validator("birth_date")
    @classmethod
    def validate_birth_date(cls, value: date) -> date:
        """A data de nascimento não pode estar no futuro."""
        if value > date.today():
            raise ValueError("A data de nascimento não pode estar no futuro.")
        return value

    @model_validator(mode="after")
    def require_some_change(self) -> "PatientUpdate":
        """Recusa um pedido de edição sem nenhum campo."""
        if not self.model_fields_set:
            raise ValueError("Envie ao menos um campo para alterar.")
        return self

    def changes(self) -> dict:
        """Só os campos que vieram no pedido, com os valores novos."""
        return {name: getattr(self, name) for name in self.model_fields_set}


class AppointmentCreate(InputSchema):
    """Marcação de consulta: médico, paciente e horário."""

    doctor_id: DbId
    patient_id: DbId
    start_at: BoundedDatetime = Field(description="Horário local da clínica, sem fuso.")
    notes: str | None = Field(default=None, max_length=500)
