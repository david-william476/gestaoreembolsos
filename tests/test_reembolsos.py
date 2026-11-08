from datetime import date, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.database import Base, make_session_factory
from app.main import create_app
from app.models import Department, User
from app.security import hash_password


@pytest.fixture
def ambiente(tmp_path):
    db_file = tmp_path / "test.db"
    app = create_app(f"sqlite:///{db_file.as_posix()}")
    factory = app.state.session_factory
    with factory() as db:
        comercial = Department(name="Comercial")
        tecnologia = Department(name="Tecnologia")
        financeiro = Department(name="Financeiro")
        db.add_all([comercial, tecnologia, financeiro])
        db.flush()
        users = [
            User(name="Ana", email="ana@example.com", password_hash=hash_password("Ana123!"), department_id=comercial.id, role="colaborador"),
            User(name="Bruno", email="bruno@example.com", password_hash=hash_password("Bruno123!"), department_id=tecnologia.id, role="colaborador"),
            User(name="Patricia", email="patricia@example.com", password_hash=hash_password("Patricia123!"), department_id=comercial.id, role="gestor"),
            User(name="Marcos", email="marcos@example.com", password_hash=hash_password("Marcos123!"), department_id=tecnologia.id, role="gestor"),
            User(name="Financeiro", email="financeiro@example.com", password_hash=hash_password("Fin123!"), department_id=financeiro.id, role="financeiro"),
        ]
        db.add_all(users)
        db.commit()
        ids = {"comercial": comercial.id, "tecnologia": tecnologia.id}
    with TestClient(app) as client:
        yield client, ids
    app.state.engine.dispose()


def entrar(client, email, password):
    response = client.post("/auth/token", data={"username": email, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def criar_solicitacao(client, headers, referencia="REC-001", **extras):
    body = {
        "category": "transporte",
        "amount": "180.00",
        "expense_date": date.today().isoformat(),
        "justification": "Deslocamento para atendimento ao cliente",
        "receipt_reference": referencia,
    }
    body.update(extras)
    response = client.post("/solicitacoes", headers=headers, json=body)
    assert response.status_code == 201, response.text
    return response.json()


def enviar(client, headers, request_id):
    response = client.post(f"/solicitacoes/{request_id}/enviar", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def test_cenario_01_colaborador_nao_consulta_solicitacao_alheia(ambiente):
    client, _ = ambiente
    ana = entrar(client, "ana@example.com", "Ana123!")
    bruno = entrar(client, "bruno@example.com", "Bruno123!")
    pedido = criar_solicitacao(client, bruno, "BRUNO-1")
    response = client.get(f"/solicitacoes/{pedido['id']}", headers=ana)
    assert response.status_code == 404
    assert "180" not in response.text


def test_cenario_02_gestor_de_outro_departamento_nao_aprova(ambiente):
    client, _ = ambiente
    bruno = entrar(client, "bruno@example.com", "Bruno123!")
    patricia = entrar(client, "patricia@example.com", "Patricia123!")
    pedido = criar_solicitacao(client, bruno, "TEC-1")
    enviar(client, bruno, pedido["id"])
    response = client.post(f"/solicitacoes/{pedido['id']}/analise-gestor", headers=patricia, json={"decision": "aprovar"})
    assert response.status_code == 404


def test_cenario_03_senha_incorreta_nao_autentica(ambiente):
    client, _ = ambiente
    response = client.post("/auth/token", data={"username": "ana@example.com", "password": "errada"})
    assert response.status_code == 401
    assert "password_hash" not in response.text
    assert "Ana123" not in response.text


def test_cenario_04_cadastro_nao_aceita_alteracao_de_perfil_ou_departamento(ambiente):
    client, ids = ambiente
    ana = entrar(client, "ana@example.com", "Ana123!")
    response = client.post("/solicitacoes", headers=ana, json={
        "category": "transporte", "amount": "50.00", "expense_date": date.today().isoformat(),
        "justification": "Táxi para reunião", "receipt_reference": "SEC-1",
        "role": "financeiro", "department_id": ids["tecnologia"], "requester_id": 999,
    })
    assert response.status_code == 422
    profile = client.get("/auth/me", headers=ana).json()
    assert profile["role"] == "colaborador"
    assert profile["department_id"] == ids["comercial"]


def test_cenario_05_financeiro_nao_pula_etapa_do_gestor(ambiente):
    client, _ = ambiente
    ana = entrar(client, "ana@example.com", "Ana123!")
    finance = entrar(client, "financeiro@example.com", "Fin123!")
    pedido = criar_solicitacao(client, ana, "FLOW-1")
    enviar(client, ana, pedido["id"])
    response = client.post(f"/solicitacoes/{pedido['id']}/analise-financeira", headers=finance, json={"decision": "aprovar"})
    assert response.status_code == 409


def test_cenario_06_solicitacao_enviada_nao_pode_ser_alterada(ambiente):
    client, _ = ambiente
    ana = entrar(client, "ana@example.com", "Ana123!")
    pedido = criar_solicitacao(client, ana, "LOCK-1")
    enviar(client, ana, pedido["id"])
    response = client.patch(f"/solicitacoes/{pedido['id']}", headers=ana, json={"amount": "1800.00"})
    assert response.status_code == 409
    stored = client.get(f"/solicitacoes/{pedido['id']}", headers=ana).json()
    assert Decimal(stored["amount"]) == Decimal("180.00")


def test_cenario_07_filtro_de_gestor_restringe_ao_departamento(ambiente):
    client, ids = ambiente
    ana = entrar(client, "ana@example.com", "Ana123!")
    bruno = entrar(client, "bruno@example.com", "Bruno123!")
    patricia = entrar(client, "patricia@example.com", "Patricia123!")
    comercial = criar_solicitacao(client, ana, "FILTER-C")
    tecnologia = criar_solicitacao(client, bruno, "FILTER-T")
    response = client.get("/solicitacoes?situacao=rascunho", headers=patricia)
    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [comercial["id"]]
    assert all(item["department_id"] == ids["comercial"] for item in response.json())
    forbidden_filter = client.get(f"/solicitacoes?department_id={ids['tecnologia']}", headers=patricia)
    assert forbidden_filter.status_code == 403


def test_cenario_08_historico_completo_identifica_responsaveis(ambiente):
    client, _ = ambiente
    ana = entrar(client, "ana@example.com", "Ana123!")
    patricia = entrar(client, "patricia@example.com", "Patricia123!")
    finance = entrar(client, "financeiro@example.com", "Fin123!")
    pedido = criar_solicitacao(client, ana, "HISTORY-1")
    request_id = pedido["id"]
    enviar(client, ana, request_id)
    gestor = client.post(f"/solicitacoes/{request_id}/analise-gestor", headers=patricia, json={"decision": "aprovar", "note": "Despesa compatível com o projeto"})
    assert gestor.status_code == 200
    financeira = client.post(f"/solicitacoes/{request_id}/analise-financeira", headers=finance, json={"decision": "aprovar", "note": "Comprovante conferido"})
    assert financeira.status_code == 200
    paga = client.post(f"/solicitacoes/{request_id}/pagamento", headers=finance)
    assert paga.status_code == 200
    assert paga.json()["status"] == "paga"
    history = paga.json()["history"]
    assert [entry["stage"] for entry in history] == ["submissao", "gestor", "financeiro", "pagamento"]
    assert [entry["reviewer_name"] for entry in history] == ["Ana", "Patricia", "Financeiro", "Financeiro"]
    assert [entry["decision"] for entry in history] == ["enviada", "aprovar", "aprovar", "paga"]


def test_referencia_duplicada_do_mesmo_colaborador_e_rejeitada(ambiente):
    client, _ = ambiente
    ana = entrar(client, "ana@example.com", "Ana123!")
    criar_solicitacao(client, ana, "DUP-1")
    response = client.post("/solicitacoes", headers=ana, json={
        "category": "alimentacao", "amount": "20.00", "expense_date": date.today().isoformat(),
        "justification": "Almoço de trabalho", "receipt_reference": "DUP-1",
    })
    assert response.status_code == 409


def test_valor_zero_e_data_futura_sao_rejeitados(ambiente):
    client, _ = ambiente
    ana = entrar(client, "ana@example.com", "Ana123!")
    base = {"category": "alimentacao", "amount": "0", "expense_date": date.today().isoformat(), "justification": "Refeição durante visita", "receipt_reference": "INVALID-1"}
    zero = client.post("/solicitacoes", headers=ana, json=base)
    assert zero.status_code == 422
    base["amount"] = "10.00"
    base["expense_date"] = (date.today() + timedelta(days=1)).isoformat()
    future = client.post("/solicitacoes", headers=ana, json=base)
    assert future.status_code == 422


def test_recusa_exige_justificativa_e_registra_historico(ambiente):
    client, _ = ambiente
    ana = entrar(client, "ana@example.com", "Ana123!")
    patricia = entrar(client, "patricia@example.com", "Patricia123!")
    pedido = criar_solicitacao(client, ana, "REJECT-1")
    enviar(client, ana, pedido["id"])
    no_note = client.post(f"/solicitacoes/{pedido['id']}/analise-gestor", headers=patricia, json={"decision": "recusar"})
    assert no_note.status_code == 422
    rejected = client.post(f"/solicitacoes/{pedido['id']}/analise-gestor", headers=patricia, json={"decision": "recusar", "note": "Comprovante ilegível"})
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "recusada"
    assert rejected.json()["history"][-1]["note"] == "Comprovante ilegível"


def test_operacoes_restritas_exigem_login(ambiente):
    client, _ = ambiente
    assert client.get("/solicitacoes").status_code == 401
    assert client.post("/solicitacoes/1/pagamento").status_code == 401


def test_financeiro_so_consulta_solicitacoes_encaminhadas_ou_ja_analisadas(ambiente):
    client, _ = ambiente
    ana = entrar(client, "ana@example.com", "Ana123!")
    finance = entrar(client, "financeiro@example.com", "Fin123!")
    draft = criar_solicitacao(client, ana, "FIN-DRAFT")
    pending_manager = criar_solicitacao(client, ana, "FIN-MANAGER")
    enviar(client, ana, pending_manager["id"])
    listing = client.get("/solicitacoes", headers=finance)
    assert listing.status_code == 200
    assert all(item["id"] not in (draft["id"], pending_manager["id"]) for item in listing.json())
    hidden = client.get(f"/solicitacoes/{pending_manager['id']}", headers=finance)
    assert hidden.status_code == 404
