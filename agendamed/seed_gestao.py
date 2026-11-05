"""Exemplos do prontuário, do financeiro, do estoque e da gestão (Clínica Vida).

Sem eles, essas telas abrem zeradas. As datas são relativas a "hoje": cerca de um mês de
consultas concluídas nos dias úteis anteriores, com o faturamento (particular pago no dia,
convênio a receber em 30 dias), as despesas fixas, um estoque com um item abaixo do mínimo
e alguns registros de prontuário e receitas.
"""

import sqlite3
from datetime import date, datetime, time, timedelta

from agendamed.gestao import (
    CLINIC_ID,
    AppointmentCharge,
    ClinicalSummaryUpdate,
    FinanceAccountCreate,
    Gestao,
    GestaoDb,
    HealthPlanCreate,
    PrescriptionCreate,
    ProcedureCreate,
    RecordEntryCreate,
    StockItemCreate,
    StockMovementCreate,
    TransactionCreate,
    TransactionUpdate,
)
from agendamed.models import AppointmentStatus
from agendamed.repositories import AppointmentRepository

# (médico, procedimento, horário, convênio?) de cada dia passado; o paciente vai em rodízio.
PAST_DAY = [
    (0, "consulta", time(8, 30), False), (0, "retorno", time(10, 0), False),
    (0, "eletro", time(14, 0), False), (0, "consulta", time(16, 0), True),
    (1, "consulta_ped", time(9, 0), False), (1, "consulta_ped", time(11, 20), True),
    (2, "consulta_derm", time(9, 45), False), (2, "retorno", time(13, 30), False),
]
METHODS = ("pix", "cartao_credito", "dinheiro", "cartao_debito")


def _past_working_days(today: date, count: int) -> list[date]:
    days, day = [], today - timedelta(days=1)
    while len(days) < count:
        if day.weekday() < 5:
            days.append(day)
        day -= timedelta(days=1)
    return sorted(days)


def seed_management(conn: sqlite3.Connection, doctor_ids: list[int], patient_ids: list[int],
                    user_id: int, now: datetime) -> None:
    g = Gestao(GestaoDb(conn), CLINIC_ID)
    today = now.date()
    today_s, now_s = today.isoformat(), now.replace(microsecond=0).isoformat()

    procedures = {
        "consulta": g.save_procedure(ProcedureCreate(
            name="Consulta cardiológica", tuss_code="10101012", price_cents=38000)),
        "consulta_ped": g.save_procedure(ProcedureCreate(
            name="Consulta pediátrica", tuss_code="10101012", price_cents=30000)),
        "consulta_derm": g.save_procedure(ProcedureCreate(
            name="Consulta dermatológica", tuss_code="10101012", price_cents=34000)),
        "retorno": g.save_procedure(ProcedureCreate(name="Retorno", price_cents=15000)),
        "eletro": g.save_procedure(ProcedureCreate(
            name="Eletrocardiograma", tuss_code="20101074", price_cents=12000)),
    }
    plan = g.save_health_plan(HealthPlanCreate(name="Unimed", ans_code="123456"))
    g.save_health_plan(HealthPlanCreate(name="Bradesco Saúde", ans_code="005711"))
    caixa = g.add_account(FinanceAccountCreate(name="Caixa"))
    banco = g.add_account(FinanceAccountCreate(name="Banco"))

    appointments = AppointmentRepository(conn)
    slots = {0: 30, 1: 20, 2: 45}
    past_days = _past_working_days(today, 22)
    turn = 0
    for day_index, day in enumerate(past_days):
        for doctor_index, proc_key, start, with_plan in PAST_DAY:
            if doctor_index >= len(doctor_ids):
                continue
            start_at = datetime.combine(day, start)
            appointment_id = appointments.create(
                doctor_id=doctor_ids[doctor_index], patient_id=patient_ids[turn % len(patient_ids)],
                start_at=start_at, end_at=start_at + timedelta(minutes=slots[doctor_index]),
                notes=None,
            )
            turn += 1
            if turn % 11 == 0:  # algumas desmarcadas, para o painel mostrar cancelamentos
                appointments.update_status(appointment_id, AppointmentStatus.CANCELLED)
                continue
            appointments.update_status(appointment_id, AppointmentStatus.COMPLETED)
            recent = day_index >= len(past_days) - 2 and proc_key == "eletro"
            paid = not with_plan and not recent
            charge = g.charge_appointment(appointment_id, AppointmentCharge(
                procedure_id=procedures[proc_key]["id"],
                health_plan_id=plan["id"] if with_plan else None,
                plan_card=f"0{turn:010d}" if with_plan else None,
                plan_guide=f"G{turn:06d}" if with_plan else None,
                paid_on=day if paid else None,
                payment_method=METHODS[turn % len(METHODS)] if paid else None,
                account_id=(caixa if turn % 3 == 0 else banco)["id"] if paid else None,
            ), today_s)
            if with_plan:  # o convênio paga uns 30 dias depois do atendimento
                g.update_transaction(charge["id"], TransactionUpdate(
                    due_date=day + timedelta(days=30)), today_s)

    # Despesas fixas do mês passado (pagas) e deste mês (pagas as que já venceram).
    this_month = today.replace(day=1)
    last_month = (this_month - timedelta(days=1)).replace(day=1)
    for month in (last_month, this_month):
        for description, category, cents, day in (
            ("Aluguel das salas", "Aluguel", 650000, 10),
            ("Energia elétrica", "Contas da casa", 98000, 15),
            ("Folha da recepção", "Pessoal", 540000, 28),
            ("Contabilidade", "Serviços", 90000, 20),
            ("Internet e telefone", "Contas da casa", 32000, 25),
        ):
            due = month.replace(day=day)
            paid = due <= today
            g.add_transaction(TransactionCreate(
                kind="expense", description=description, category=category, amount_cents=cents,
                due_date=due, paid_on=due if paid else None,
                payment_method="transferencia" if paid else None,
                account_id=banco["id"] if paid else None,
            ), today_s)

    for name, unit, minimum, entries, used in (
        ("Luvas de procedimento", "cx", 6, 20, 9),
        ("Eletrodos descartáveis", "pct", 5, 12, 9),  # abaixo do mínimo: aparece o alerta
        ("Papel lençol", "rolo", 4, 15, 6),
        ("Álcool 70%", "frasco", 3, 10, 4),
        ("Seringas 5 ml", "un", 50, 200, 80),
    ):
        item = g.add_stock_item(StockItemCreate(name=name, unit=unit, min_quantity=minimum))
        g.move_stock(item["id"], StockMovementCreate(delta=entries, reason="Compra"),
                     user_id, now_s)
        g.move_stock(item["id"], StockMovementCreate(delta=-used, reason="Uso nos atendimentos"),
                     user_id, now_s)

    # Prontuário e receitas de exemplo de uma paciente da cardiologia.
    ana, cardio = patient_ids[0], doctor_ids[0]
    g.save_clinical_summary(ana, ClinicalSummaryUpdate(
        allergies="Dipirona", conditions="Hipertensão arterial leve",
        medications="Losartana 50 mg, 1 vez ao dia", blood_type="O+"), user_id, now_s)
    for kind, content in (
        ("anamnese", "Paciente relata palpitações esporádicas há 2 meses, sem desmaios. "
                     "Pratica caminhada 3 vezes por semana."),
        ("exame_fisico", "PA 132/84 mmHg, FC 76 bpm, ritmo regular, sem sopros."),
        ("conduta", "Solicitado eletrocardiograma e Holter 24 h. Manter losartana. "
                    "Retorno em 30 dias com os exames."),
    ):
        g.add_record_entry(ana, RecordEntryCreate(kind=kind, content=content), cardio,
                           user_id, now_s)
    g.add_prescription(ana, PrescriptionCreate(kind="exames", items=[
        {"name": "Eletrocardiograma de repouso"}, {"name": "Holter 24 horas"},
        {"name": "Hemograma completo"}, {"name": "Perfil lipídico"},
    ]), cardio, user_id, now_s)
    g.add_prescription(ana, PrescriptionCreate(kind="simples", items=[
        {"name": "Losartana potássica 50 mg", "dosage": "30 comprimidos",
         "instructions": "Tomar 1 comprimido pela manhã, todos os dias."},
    ]), cardio, user_id, now_s)
