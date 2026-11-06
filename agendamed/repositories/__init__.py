"""Camada de acesso a dados: todo o SQL da aplicação fica aqui.

Arquivos deste pacote:

    base.py          página de resultados (Page) e a classe base dos repositórios
    users.py         acessos da equipe
    doctors.py       médicos
    patients.py      pacientes
    appointments.py  consultas

Os dados da gestão (prontuário, financeiro, estoque...) ficam em agendamed/gestao/.
Importe daqui mesmo: `from agendamed.repositories import PatientRepository`.
"""

from agendamed.repositories.appointments import AppointmentRepository
from agendamed.repositories.base import Page, Repository
from agendamed.repositories.doctors import DoctorRepository
from agendamed.repositories.patients import PatientRepository
from agendamed.repositories.users import UserRepository

__all__ = [
    "AppointmentRepository",
    "DoctorRepository",
    "Page",
    "PatientRepository",
    "Repository",
    "UserRepository",
]
