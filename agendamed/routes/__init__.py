"""Rotas da API: os endereços que a interface (e quem usa a API) chama.

Cada arquivo é um blueprint do Flask, registrado em `create_app`:

auth.py          /auth/...           cadastro, login e dados de quem entrou
    doctors.py       /doctors/...        médicos e horários livres
    patients.py      /patients/...       pacientes
    appointments.py  /appointments/...   consultas
    docs.py          /docs e /openapi.json  documentação da API
    gestao/          prontuário, prescrições, financeiro, estoque e relatórios
    _helpers.py      peças usadas por todas as rotas (login, parâmetros...)
"""
