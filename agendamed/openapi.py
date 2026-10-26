"""Especificação OpenAPI 3.1 da API.

Os corpos de requisição vêm direto dos esquemas Pydantic (`model_json_schema`), então a
documentação nunca fica desatualizada em relação à validação real. Um teste garante que
toda rota registrada no Flask aparece aqui.
"""

from functools import cache

from agendamed.schemas import (
    AppointmentCreate,
    DoctorCreate,
    LoginRequest,
    PatientCreate,
    UserCreate,
)

REF = "#/components/schemas/{model}"


def _ref(name: str) -> dict:
    return {"$ref": REF.format(model=name)}


def _obj(properties: dict, required: list[str] | None = None) -> dict:
    return {"type": "object", "properties": properties, "required": required or list(properties)}


_INT = {"type": "integer"}
_STR = {"type": "string"}
_HHMM = {"type": "string", "pattern": r"^\d{2}:\d{2}$", "examples": ["08:00"]}
_LOCAL_DT = {
    "type": "string",
    "examples": ["2030-01-08T10:00"],
    "description": "Horário local, sem fuso.",
}
_STATUS = {"type": "string", "enum": ["scheduled", "cancelled", "completed"]}
_SUMMARY = _obj({"id": _INT, "name": _STR})


def _page(item: str) -> dict:
    items = {"type": "array", "items": _ref(item)}
    return _obj({"items": items, "total": _INT, "limit": _INT, "offset": _INT})


RESPONSE_SCHEMAS = {
    "User": _obj({"id": _INT, "email": _STR, "full_name": _STR}),
    "Token": _obj({
        "access_token": _STR,
        "token_type": {"type": "string", "const": "bearer"},
        "expires_in": {"type": "integer", "description": "Validade em segundos."},
    }),
    "Doctor": _obj({
        "id": _INT, "name": _STR, "specialty": _STR, "crm": _STR,
        "slot_minutes": _INT, "work_start": _HHMM, "work_end": _HHMM,
    }),
    "Patient": _obj({
        "id": _INT, "name": _STR,
        "cpf": {"type": "string", "examples": ["529.982.247-25"]},
        "email": _STR, "phone": {"type": ["string", "null"]},
        "birth_date": {"type": "string", "format": "date"},
    }),
    "Appointment": _obj({
        "id": _INT, "doctor": _SUMMARY, "patient": _SUMMARY,
        "start_at": _LOCAL_DT, "end_at": _LOCAL_DT,
        "status": _STATUS,
        "notes": {"type": ["string", "null"]},
    }),
    "Availability": _obj({
        "doctor_id": _INT,
        "date": {"type": "string", "format": "date"},
        "available_slots": {"type": "array", "items": _LOCAL_DT},
    }),
    "DoctorPage": _page("Doctor"),
    "PatientPage": _page("Patient"),
    "AppointmentPage": _page("Appointment"),
    "Error": _obj(
        {
            "detail": _STR,
            "errors": {"type": "array", "items": _obj({"field": _STR, "message": _STR})},
        },
        required=["detail"],
    ),
}

REQUEST_MODELS = {
    "UserCreate": UserCreate,
    "LoginRequest": LoginRequest,
    "DoctorCreate": DoctorCreate,
    "PatientCreate": PatientCreate,
    "AppointmentCreate": AppointmentCreate,
}

ERROR_DESCRIPTIONS = {
    400: "Parâmetro ou corpo da requisição malformado.",
    401: "Token ausente, inválido ou expirado.",
    404: "Recurso não encontrado.",
    409: "Conflito com o estado atual (ex.: horário já ocupado).",
    422: "Dados inválidos ou regra de negócio violada.",
    429: "Muitas tentativas. Aguarde o tempo indicado em Retry-After.",
}


def _param(name: str, where: str, schema: dict, description: str, required: bool = False):
    return {
        "name": name, "in": where, "required": required or where == "path",
        "schema": schema, "description": description,
    }


def _id(name: str, label: str) -> dict:
    return _param(name, "path", {"type": "integer", "minimum": 1}, f"Identificador {label}.")


PAGINATION = [
    _param("limit", "query", {"type": "integer", "minimum": 1, "maximum": 100, "default": 20},
           "Itens por página."),
    _param("offset", "query", {"type": "integer", "minimum": 0, "default": 0},
           "Quantos itens pular."),
]


def _op(summary, tag, *, ok, ok_schema=None, body=None, params=(), errors=(), auth=True,
        description=None):
    responses = {
        str(ok): {
            "description": "Sucesso.",
            **({"content": {"application/json": {"schema": _ref(ok_schema)}}} if ok_schema else {}),
        }
    }
    codes = set(errors) | ({401} if auth else set())
    for code in sorted(codes):
        responses[str(code)] = {
            "description": ERROR_DESCRIPTIONS[code],
            "content": {"application/json": {"schema": _ref("Error")}},
        }
    operation = {"summary": summary, "tags": [tag], "responses": responses}
    if description:
        operation["description"] = description
    if params:
        operation["parameters"] = list(params)
    if body:
        operation["requestBody"] = {
            "required": True,
            "content": {"application/json": {"schema": _ref(body)}},
        }
    operation["security"] = [{"bearerAuth": []}] if auth else []
    return operation


def _paths() -> dict:
    doctor_id = _id("doctor_id", "do médico")
    patient_id = _id("patient_id", "do paciente")
    appointment_id = _id("appointment_id", "da consulta")
    day = {"type": "string", "format": "date"}
    return {
        "/health": {"get": _op("Verifica se a aplicação está no ar", "Sistema", ok=200,
                               auth=False)},
        "/auth/register": {"post": _op(
            "Cria um usuário", "Autenticação", ok=201, ok_schema="User", body="UserCreate",
            errors=(400, 409, 422), auth=False)},
        "/auth/login": {"post": _op(
            "Faz login e retorna o token JWT", "Autenticação", ok=200, ok_schema="Token",
            body="LoginRequest", errors=(400, 401, 422, 429), auth=False,
            description="Após 5 tentativas erradas para o mesmo e-mail, novas tentativas "
                        "são bloqueadas por alguns minutos (proteção contra força bruta).")},
        "/auth/me": {"get": _op("Dados do usuário logado", "Autenticação", ok=200,
                                ok_schema="User")},
        "/doctors": {
            "get": _op("Lista médicos", "Médicos", ok=200, ok_schema="DoctorPage", errors=(400,),
                       params=[_param("specialty", "query", _STR, "Filtra pela especialidade."),
                               *PAGINATION]),
            "post": _op("Cadastra um médico", "Médicos", ok=201, ok_schema="Doctor",
                        body="DoctorCreate", errors=(400, 409, 422)),
        },
        "/doctors/{doctor_id}": {
            "get": _op("Detalhes de um médico", "Médicos", ok=200, ok_schema="Doctor",
                       params=[doctor_id], errors=(404,)),
            "delete": _op(
                "Remove um médico", "Médicos", ok=204, params=[doctor_id], errors=(404, 409),
                description="Some das listas e da agenda; as consultas antigas continuam no "
                            "histórico. Recusado (409) se houver consultas futuras marcadas."),
        },
        "/doctors/{doctor_id}/availability": {"get": _op(
            "Horários livres do médico em um dia", "Médicos", ok=200, ok_schema="Availability",
            params=[doctor_id, _param("date", "query", day, "Dia (AAAA-MM-DD).", required=True)],
            errors=(400, 404))},
        "/patients": {
            "get": _op("Lista pacientes", "Pacientes", ok=200, ok_schema="PatientPage",
                       errors=(400,),
                       params=[_param("q", "query", _STR, "Busca por nome ou CPF."), *PAGINATION]),
            "post": _op("Cadastra um paciente", "Pacientes", ok=201, ok_schema="Patient",
                        body="PatientCreate", errors=(400, 409, 422)),
        },
        "/patients/{patient_id}": {"get": _op(
            "Detalhes de um paciente", "Pacientes", ok=200, ok_schema="Patient",
            params=[patient_id], errors=(404,))},
        "/appointments": {
            "get": _op("Lista consultas", "Consultas", ok=200, ok_schema="AppointmentPage",
                       errors=(400,), params=[
                           _param("doctor_id", "query", _INT, "Filtra pelo médico."),
                           _param("patient_id", "query", _INT, "Filtra pelo paciente."),
                           _param("date", "query", day, "Filtra pelo dia (AAAA-MM-DD)."),
                           _param("status", "query", _STATUS, "Filtra pela situação."),
                           *PAGINATION]),
            "post": _op("Agenda uma consulta", "Consultas", ok=201, ok_schema="Appointment",
                        body="AppointmentCreate", errors=(400, 404, 409, 422),
                        description="Valida expediente, grade de horários, fins de semana e "
                                    "conflitos de médico e de paciente."),
        },
        "/appointments/{appointment_id}": {"get": _op(
            "Detalhes de uma consulta", "Consultas", ok=200, ok_schema="Appointment",
            params=[appointment_id], errors=(404,))},
        "/appointments/{appointment_id}/cancel": {"post": _op(
            "Cancela uma consulta", "Consultas", ok=200, ok_schema="Appointment",
            params=[appointment_id], errors=(404, 409))},
        "/appointments/{appointment_id}/complete": {"post": _op(
            "Conclui uma consulta", "Consultas", ok=200, ok_schema="Appointment",
            params=[appointment_id], errors=(404, 409))},
    }


@cache
def build_spec(version: str) -> dict:
    schemas = {
        name: model.model_json_schema(ref_template=REF) for name, model in REQUEST_MODELS.items()
    }
    schemas.update(RESPONSE_SCHEMAS)
    return {
        "openapi": "3.1.0",
        "info": {
            "title": "AgendaMed API",
            "version": version,
            "description": "API REST para agendamento de consultas médicas. Faça login em "
                           "`/auth/login`, copie o `access_token` e clique em **Authorize**.",
        },
        "tags": [
            {"name": "Autenticação"}, {"name": "Médicos"}, {"name": "Pacientes"},
            {"name": "Consultas"}, {"name": "Sistema"},
        ],
        "paths": _paths(),
        "components": {
            "schemas": schemas,
            "securitySchemes": {
                "bearerAuth": {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}
            },
        },
    }
