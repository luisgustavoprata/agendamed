"""Especificação OpenAPI 3.1 da API.

Os corpos de requisição vêm direto dos esquemas Pydantic (`model_json_schema`), então a
documentação nunca fica desatualizada em relação à validação real. Um teste garante que
toda rota registrada no Flask aparece aqui.
"""

from functools import cache

from agendamed.gestao.schemas import REQUEST_MODELS as GESTAO_MODELS

from agendamed.schemas import (
    AppointmentCreate,
    DoctorCreate,
    LoginRequest,
    PatientCreate,
    PatientUpdate,
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
    "Token": _obj(
        {
            "access_token": _STR,
            "token_type": {"type": "string", "const": "bearer"},
            "expires_in": {"type": "integer", "description": "Validade em segundos."},
        }
    ),
    "Doctor": _obj(
        {
            "id": _INT,
            "name": _STR,
            "specialty": _STR,
            "crm": _STR,
            "slot_minutes": _INT,
            "work_start": _HHMM,
            "work_end": _HHMM,
        }
    ),
    "Patient": _obj(
        {
            "id": _INT,
            "name": _STR,
            "cpf": {"type": "string", "examples": ["529.982.247-25"]},
            "email": _STR,
            "phone": {"type": ["string", "null"]},
            "birth_date": {"type": "string", "format": "date"},
        }
    ),
    "Appointment": _obj(
        {
            "id": _INT,
            "doctor": _SUMMARY,
            "patient": _SUMMARY,
            "start_at": _LOCAL_DT,
            "end_at": _LOCAL_DT,
            "status": _STATUS,
            "notes": {"type": ["string", "null"]},
        }
    ),
    "Availability": _obj(
        {
            "doctor_id": _INT,
            "date": {"type": "string", "format": "date"},
            "available_slots": {"type": "array", "items": _LOCAL_DT},
        }
    ),
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
    "PatientUpdate": PatientUpdate,
    "AppointmentCreate": AppointmentCreate,
}

ERROR_DESCRIPTIONS = {
    400: "Parâmetro ou corpo da requisição malformado.",
    401: "Token ausente, inválido ou expirado.",
    403: "Ação não permitida.",
    404: "Recurso não encontrado.",
    409: "Conflito com o estado atual (ex.: horário já ocupado).",
    422: "Dados inválidos ou regra de negócio violada.",
    429: "Muitas tentativas. Aguarde o tempo indicado em Retry-After.",
}


def _param(name: str, where: str, schema: dict, description: str, required: bool = False):
    return {
        "name": name,
        "in": where,
        "required": required or where == "path",
        "schema": schema,
        "description": description,
    }


def _id(name: str, label: str) -> dict:
    return _param(name, "path", {"type": "integer", "minimum": 1}, f"Identificador {label}.")


PAGINATION = [
    _param(
        "limit",
        "query",
        {"type": "integer", "minimum": 1, "maximum": 100, "default": 20},
        "Itens por página.",
    ),
    _param(
        "offset", "query", {"type": "integer", "minimum": 0, "default": 0}, "Quantos itens pular."
    ),
]


def _op(
    summary,
    tag,
    *,
    ok,
    ok_schema=None,
    body=None,
    params=(),
    errors=(),
    auth=True,
    description=None,
):
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


def _gestao_paths() -> dict:
    patient_id = _id("patient_id", "do paciente")
    appointment_id = _id("appointment_id", "da consulta")
    period = [
        _param(
            "start",
            "query",
            {"type": "string", "format": "date"},
            "Início do período (padrão: dia 1 do mês atual).",
        ),
        _param(
            "end",
            "query",
            {"type": "string", "format": "date"},
            "Fim do período (padrão: último dia do mês).",
        ),
    ]

    def op(summary, tag, ok=200, body=None, params=(), errors=(403, 404)):
        return _op(
            summary,
            tag,
            ok=ok,
            ok_schema=None if ok == 204 else "Result",
            body=body,
            params=params,
            errors=(*errors, 422) if body else errors,
        )

    tx_id = _id("tx_id", "do lançamento")
    item_id = _id("item_id", "do item de estoque")
    return {
        "/patients/{patient_id}/record": {
            "get": op(
                "Prontuário do paciente (ficha clínica e registros)",
                "Prontuário",
                params=[patient_id],
            )
        },
        "/patients/{patient_id}/record/summary": {
            "put": op(
                "Salva a ficha clínica (alergias, doenças, medicamentos)",
                "Prontuário",
                body="ClinicalSummaryUpdate",
                params=[patient_id],
            )
        },
        "/patients/{patient_id}/record/entries": {
            "post": op(
                "Adiciona um registro ao prontuário",
                "Prontuário",
                ok=201,
                body="RecordEntryCreate",
                params=[patient_id],
            )
        },
        "/patients/{patient_id}/prescriptions": {
            "get": op(
                "Receitas, atestados e pedidos de exame do paciente",
                "Prescrições",
                params=[patient_id],
            ),
            "post": op(
                "Emite uma receita, atestado ou pedido de exame",
                "Prescrições",
                ok=201,
                body="PrescriptionCreate",
                params=[patient_id],
            ),
        },
        "/prescriptions/{prescription_id}": {
            "get": op(
                "Uma prescrição, com dados do médico e do paciente para impressão",
                "Prescrições",
                params=[_id("prescription_id", "da prescrição")],
            )
        },
        "/procedures": {
            "get": op("Lista procedimentos", "Cadastros", errors=()),
            "post": op(
                "Cadastra um procedimento",
                "Cadastros",
                ok=201,
                body="ProcedureCreate",
                errors=(403, 409),
            ),
        },
        "/procedures/{procedure_id}": {
            "put": op(
                "Altera um procedimento",
                "Cadastros",
                body="ProcedureCreate",
                params=[_id("procedure_id", "do procedimento")],
                errors=(403, 404, 409),
            )
        },
        "/health-plans": {
            "get": op("Lista convênios", "Cadastros", errors=()),
            "post": op(
                "Cadastra um convênio",
                "Cadastros",
                ok=201,
                body="HealthPlanCreate",
                errors=(403, 409),
            ),
        },
        "/health-plans/{plan_id}": {
            "put": op(
                "Altera um convênio",
                "Cadastros",
                body="HealthPlanCreate",
                params=[_id("plan_id", "do convênio")],
                errors=(403, 404, 409),
            )
        },
        "/finance/accounts": {
            "get": op("Contas (caixa, banco) com saldo", "Financeiro", errors=(403,)),
            "post": op(
                "Cria uma conta",
                "Financeiro",
                ok=201,
                body="FinanceAccountCreate",
                errors=(403, 409),
            ),
        },
        "/finance/transactions": {
            "get": op(
                "Lançamentos do período",
                "Financeiro",
                errors=(400, 403),
                params=[
                    *period,
                    _param(
                        "kind",
                        "query",
                        {"type": "string", "enum": ["income", "expense"]},
                        "Receitas ou despesas.",
                    ),
                    _param(
                        "status",
                        "query",
                        {"type": "string", "enum": ["paid", "open"]},
                        "Pagos ou em aberto.",
                    ),
                    _param("account_id", "query", {"type": "integer"}, "Só uma conta."),
                ],
            ),
            "post": op(
                "Lança uma receita ou despesa", "Financeiro", ok=201, body="TransactionCreate"
            ),
        },
        "/finance/transactions/{tx_id}": {
            "patch": op(
                "Altera um lançamento", "Financeiro", body="TransactionUpdate", params=[tx_id]
            ),
            "delete": op(
                "Exclui um lançamento em aberto",
                "Financeiro",
                ok=204,
                params=[tx_id],
                errors=(403, 404, 409),
            ),
        },
        "/finance/transactions/{tx_id}/pay": {
            "post": op(
                "Marca como pago/recebido",
                "Financeiro",
                body="TransactionPay",
                params=[tx_id],
                errors=(403, 404, 409),
            )
        },
        "/finance/transactions/{tx_id}/unpay": {
            "post": op("Desfaz o pagamento", "Financeiro", params=[tx_id])
        },
        "/finance/cashflow": {
            "get": op(
                "Fluxo de caixa: realizado e previsto, por dia, categoria e conta",
                "Financeiro",
                params=period,
                errors=(400, 403),
            )
        },
        "/appointments/{appointment_id}/charge": {
            "get": op("Faturamento de uma consulta", "Financeiro", params=[appointment_id]),
            "post": op(
                "Fatura uma consulta (particular ou convênio)",
                "Financeiro",
                ok=201,
                body="AppointmentCharge",
                params=[appointment_id],
                errors=(403, 404, 409),
            ),
        },
        "/finance/payout-rules": {
            "get": op("Regras de repasse aos médicos", "Financeiro", errors=(403,)),
            "put": op(
                "Define a porcentagem de repasse de um médico", "Financeiro", body="PayoutRuleSet"
            ),
        },
        "/finance/payout-rules/{rule_id}": {
            "delete": op(
                "Remove uma regra de repasse",
                "Financeiro",
                ok=204,
                params=[_id("rule_id", "da regra")],
                errors=(403,),
            )
        },
        "/finance/payouts": {
            "get": op(
                "Repasse calculado de cada médico sobre o recebido",
                "Financeiro",
                params=period,
                errors=(400, 403),
            )
        },
        "/finance/tiss": {
            "get": op(
                "Lote de guias de um convênio no período",
                "Financeiro",
                errors=(400, 403, 404),
                params=[
                    _param(
                        "health_plan_id", "query", {"type": "integer"}, "Convênio.", required=True
                    ),
                    *period,
                ],
            )
        },
        "/stock/items": {
            "get": op("Itens do estoque", "Estoque", errors=(403,)),
            "post": op(
                "Cadastra um item", "Estoque", ok=201, body="StockItemCreate", errors=(403, 409)
            ),
        },
        "/stock/items/{item_id}": {
            "patch": op(
                "Altera um item",
                "Estoque",
                body="StockItemUpdate",
                params=[item_id],
                errors=(403, 404, 409),
            )
        },
        "/stock/items/{item_id}/movements": {
            "get": op("Entradas e saídas de um item", "Estoque", params=[item_id]),
            "post": op(
                "Registra entrada (+) ou saída (-)",
                "Estoque",
                ok=201,
                body="StockMovementCreate",
                params=[item_id],
            ),
        },
        "/reports/overview": {
            "get": op(
                "Painel de gestão: consultas, faltas, faturamento, novos pacientes",
                "Gestão",
                params=period,
                errors=(400, 403),
            )
        },
    }


def _paths() -> dict:
    doctor_id = _id("doctor_id", "do médico")
    patient_id = _id("patient_id", "do paciente")
    appointment_id = _id("appointment_id", "da consulta")
    day = {"type": "string", "format": "date"}
    return {
        "/health": {
            "get": _op("Verifica se a aplicação está no ar", "Sistema", ok=200, auth=False)
        },
        "/auth/register": {
            "post": _op(
                "Cria um usuário",
                "Autenticação",
                ok=201,
                ok_schema="User",
                body="UserCreate",
                errors=(400, 409, 422),
                auth=False,
            )
        },
        "/auth/login": {
            "post": _op(
                "Faz login e retorna o token JWT",
                "Autenticação",
                ok=200,
                ok_schema="Token",
                body="LoginRequest",
                errors=(400, 401, 422, 429),
                auth=False,
                description="Após 5 tentativas erradas para o mesmo e-mail, novas tentativas "
                "são bloqueadas por alguns minutos (proteção contra força bruta).",
            )
        },
        "/auth/me": {
            "get": _op("Dados do usuário logado", "Autenticação", ok=200, ok_schema="User")
        },
        "/doctors": {
            "get": _op(
                "Lista médicos",
                "Médicos",
                ok=200,
                ok_schema="DoctorPage",
                errors=(400,),
                params=[
                    _param("specialty", "query", _STR, "Filtra pela especialidade."),
                    *PAGINATION,
                ],
            ),
            "post": _op(
                "Cadastra um médico",
                "Médicos",
                ok=201,
                ok_schema="Doctor",
                body="DoctorCreate",
                errors=(400, 409, 422),
            ),
        },
        "/doctors/{doctor_id}": {
            "get": _op(
                "Detalhes de um médico",
                "Médicos",
                ok=200,
                ok_schema="Doctor",
                params=[doctor_id],
                errors=(404,),
            ),
            "delete": _op(
                "Remove um médico",
                "Médicos",
                ok=204,
                params=[doctor_id],
                errors=(404, 409),
                description="Some das listas e da agenda; as consultas antigas continuam no "
                "histórico. Recusado (409) se houver consultas futuras marcadas.",
            ),
        },
        "/doctors/{doctor_id}/availability": {
            "get": _op(
                "Horários livres do médico em um dia",
                "Médicos",
                ok=200,
                ok_schema="Availability",
                params=[
                    doctor_id,
                    _param("date", "query", day, "Dia (AAAA-MM-DD).", required=True),
                ],
                errors=(400, 404),
            )
        },
        "/patients": {
            "get": _op(
                "Lista pacientes",
                "Pacientes",
                ok=200,
                ok_schema="PatientPage",
                errors=(400,),
                params=[_param("q", "query", _STR, "Busca por nome ou CPF."), *PAGINATION],
            ),
            "post": _op(
                "Cadastra um paciente",
                "Pacientes",
                ok=201,
                ok_schema="Patient",
                body="PatientCreate",
                errors=(400, 409, 422),
            ),
        },
        "/patients/{patient_id}": {
            "get": _op(
                "Detalhes de um paciente",
                "Pacientes",
                ok=200,
                ok_schema="Patient",
                params=[patient_id],
                errors=(404,),
            ),
            "patch": _op(
                "Altera os dados de um paciente",
                "Pacientes",
                ok=200,
                ok_schema="Patient",
                body="PatientUpdate",
                params=[patient_id],
                errors=(400, 404, 409, 422),
                description="Envie só os campos que mudam. O CPF continua validado e não pode "
                "repetir o de outro paciente; `phone: null` apaga o telefone.",
            ),
        },
        "/appointments": {
            "get": _op(
                "Lista consultas",
                "Consultas",
                ok=200,
                ok_schema="AppointmentPage",
                errors=(400,),
                params=[
                    _param("doctor_id", "query", _INT, "Filtra pelo médico."),
                    _param("patient_id", "query", _INT, "Filtra pelo paciente."),
                    _param("date", "query", day, "Filtra pelo dia (AAAA-MM-DD)."),
                    _param("status", "query", _STATUS, "Filtra pela situação."),
                    *PAGINATION,
                ],
            ),
            "post": _op(
                "Agenda uma consulta",
                "Consultas",
                ok=201,
                ok_schema="Appointment",
                body="AppointmentCreate",
                errors=(400, 404, 409, 422),
                description="Valida expediente, grade de horários, fins de semana e "
                "conflitos de médico e de paciente.",
            ),
        },
        "/appointments/{appointment_id}": {
            "get": _op(
                "Detalhes de uma consulta",
                "Consultas",
                ok=200,
                ok_schema="Appointment",
                params=[appointment_id],
                errors=(404,),
            )
        },
        "/appointments/{appointment_id}/cancel": {
            "post": _op(
                "Cancela uma consulta",
                "Consultas",
                ok=200,
                ok_schema="Appointment",
                params=[appointment_id],
                errors=(404, 409),
            )
        },
        "/appointments/{appointment_id}/complete": {
            "post": _op(
                "Conclui uma consulta",
                "Consultas",
                ok=200,
                ok_schema="Appointment",
                params=[appointment_id],
                errors=(404, 409),
            )
        },
        "/appointments/{appointment_id}/reopen": {
            "post": _op(
                "Reabre uma consulta concluída",
                "Consultas",
                ok=200,
                ok_schema="Appointment",
                params=[appointment_id],
                errors=(404, 409),
            )
        },
    }


@cache
def build_spec(version: str) -> dict:
    schemas = {}
    for name, model in {**REQUEST_MODELS, **GESTAO_MODELS}.items():
        schema = model.model_json_schema(ref_template=REF)
        # Modelos aninhados (ex.: os itens de uma receita) viram componentes próprios.
        schemas.update(schema.pop("$defs", {}))
        schemas[name] = schema
    schemas.update(RESPONSE_SCHEMAS)
    schemas["Result"] = {"type": "object", "description": "Objeto com os dados pedidos."}
    return {
        "openapi": "3.1.0",
        "info": {
            "title": "AgendaMed API",
            "version": version,
            "description": "API REST para agendamento de consultas médicas. Faça login em "
            "`/auth/login`, copie o `access_token` e clique em **Authorize**.",
        },
        "tags": [
            {"name": "Autenticação"},
            {"name": "Médicos"},
            {"name": "Pacientes"},
            {"name": "Consultas"},
            {"name": "Prontuário"},
            {"name": "Prescrições"},
            {"name": "Financeiro"},
            {"name": "Estoque"},
            {"name": "Gestão"},
            {"name": "Cadastros"},
            {"name": "Sistema"},
        ],
        "paths": {**_paths(), **_gestao_paths()},
        "components": {
            "schemas": schemas,
            "securitySchemes": {
                "bearerAuth": {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}
            },
        },
    }
