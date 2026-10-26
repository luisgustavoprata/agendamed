"""Esquemas Pydantic que validam os dados recebidos pela API."""

from datetime import date, time
from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    NaiveDatetime,
    PositiveInt,
    field_validator,
    model_validator,
)

from agendamed.validators import EMAIL_PATTERN, is_valid_cpf, only_digits

Name = Annotated[str, Field(min_length=3, max_length=120)]


class InputSchema(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")


class EmailMixin(InputSchema):
    email: str = Field(max_length=255)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        if not EMAIL_PATTERN.match(value):
            raise ValueError("E-mail inválido.")
        return value.lower()


class UserCreate(EmailMixin):
    full_name: Name
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(InputSchema):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.lower()


class DoctorCreate(InputSchema):
    name: Name
    specialty: str = Field(min_length=3, max_length=80)
    crm: str = Field(pattern=r"^\d{4,7}/[A-Z]{2}$", examples=["123456/SP"])
    slot_minutes: int = Field(default=30, ge=10, le=240)
    work_start: time = time(8, 0)
    work_end: time = time(18, 0)

    @model_validator(mode="after")
    def validate_working_hours(self) -> "DoctorCreate":
        start = self.work_start.hour * 60 + self.work_start.minute
        end = self.work_end.hour * 60 + self.work_end.minute
        if end <= start:
            raise ValueError("O fim do expediente deve ser depois do início.")
        if end - start < self.slot_minutes:
            raise ValueError("O expediente precisa comportar ao menos uma consulta.")
        return self


class PatientCreate(EmailMixin):
    name: Name
    cpf: str
    phone: str | None = Field(default=None, pattern=r"^\+?[\d\s()-]{10,20}$")
    birth_date: date

    @field_validator("cpf")
    @classmethod
    def validate_cpf(cls, value: str) -> str:
        if not is_valid_cpf(value):
            raise ValueError("CPF inválido.")
        return only_digits(value)

    @field_validator("birth_date")
    @classmethod
    def validate_birth_date(cls, value: date) -> date:
        if value > date.today():
            raise ValueError("A data de nascimento não pode estar no futuro.")
        return value


class AppointmentCreate(InputSchema):
    doctor_id: PositiveInt
    patient_id: PositiveInt
    start_at: NaiveDatetime = Field(description="Horário local da clínica, sem fuso.")
    notes: str | None = Field(default=None, max_length=500)
