"""Rotas da API NexusCorp e regras do fluxo de reembolsos."""

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload
from .config import DATABASE_URL
from .database import Base, build_engine, get_db, make_session_factory
from .models import Department, Reimbursement, ReviewHistory, User
from .schemas import Category, DecisionInput, ReimbursementCreate, ReimbursementOut, ReimbursementUpdate, Status, TokenOut, UserOut
from .security import (
    create_access_token as criar_token_acesso,
    get_current_user as obter_usuario_atual,
    require_roles as exigir_perfil,
    verify_password as conferir_senha,
)


def create_app(database_url: str | None = None) -> FastAPI:
    """Monta a API; testes podem fornecer seu próprio banco isolado."""
    app = FastAPI(
        title="NexusCorp — Gestão de Reembolsos",
        description="API de reembolsos com controle de acesso por perfil e departamento.",
        version="1.0.0",
    )
    motor_banco = build_engine(database_url or DATABASE_URL)
    # Cria as tabelas necessárias sem apagar registros que já existem.
    Base.metadata.create_all(motor_banco)
    app.state.engine = motor_banco
    app.state.session_factory = make_session_factory(motor_banco)

    # Verificação simples para confirmar que a aplicação está respondendo.
    @app.get("/health", tags=["Sistema"])
    def verificar_api():
        return {"status": "ok"}

    # A resposta de erro é genérica para não revelar se o e-mail existe.
    @app.post("/auth/token", response_model=TokenOut, tags=["Autenticação"])
    def entrar(formulario: OAuth2PasswordRequestForm = Depends(), banco: Session = Depends(get_db)):
        usuario = banco.query(User).filter(User.email == formulario.username.lower()).first()
        if usuario is None or not usuario.active or not conferir_senha(formulario.password, usuario.password_hash):
            raise HTTPException(status_code=401, detail="E-mail ou senha inválidos", headers={"WWW-Authenticate": "Bearer"})
        return {"access_token": criar_token_acesso(usuario), "token_type": "bearer"}

    @app.get("/auth/me", response_model=UserOut, tags=["Autenticação"])
    def consultar_usuario_atual(usuario: User = Depends(obter_usuario_atual)):
        return {"id": usuario.id, "name": usuario.name, "email": usuario.email, "department_id": usuario.department_id, "department_name": usuario.department.name, "role": usuario.role}

    def carregar_solicitacao(banco: Session, request_id: int) -> Reimbursement:
        solicitacao = banco.query(Reimbursement).options(
            joinedload(Reimbursement.requester), joinedload(Reimbursement.department),
            joinedload(Reimbursement.history).joinedload(ReviewHistory.reviewer),
        ).filter(Reimbursement.id == request_id).populate_existing().first()
        if solicitacao is None:
            raise HTTPException(status_code=404, detail="Solicitação não encontrada")
        return solicitacao

    def verificar_acesso_solicitacao(solicitacao: Reimbursement, usuario: User) -> None:
        """Oculta solicitações fora do alcance permitido para cada perfil."""
        if usuario.role == "colaborador" and solicitacao.requester_id != usuario.id:
            raise HTTPException(status_code=404, detail="Solicitação não encontrada")
        if usuario.role == "gestor" and solicitacao.department_id != usuario.department_id:
            raise HTTPException(status_code=404, detail="Solicitação não encontrada")
        if usuario.role == "financeiro" and solicitacao.status not in ("aguardando_financeiro", "aprovada", "paga"):
            if not any(registro.stage == "financeiro" for registro in solicitacao.history):
                raise HTTPException(status_code=404, detail="Solicitação não encontrada")

    def montar_resposta_solicitacao(solicitacao: Reimbursement) -> dict:
        return {
            "id": solicitacao.id, "requester_id": solicitacao.requester_id, "requester_name": solicitacao.requester.name,
            "department_id": solicitacao.department_id, "department_name": solicitacao.department.name,
            "category": solicitacao.category, "amount": solicitacao.amount, "expense_date": solicitacao.expense_date,
            "justification": solicitacao.justification, "receipt_reference": solicitacao.receipt_reference,
            "status": solicitacao.status, "created_at": solicitacao.created_at, "updated_at": solicitacao.updated_at,
            "history": [{
                "id": registro.id, "reviewer_id": registro.reviewer_id, "reviewer_name": registro.reviewer.name,
                "reviewer_role": registro.reviewer.role, "stage": registro.stage, "decision": registro.decision,
                "decided_at": registro.decided_at, "note": registro.note,
            } for registro in solicitacao.history],
        }

    # O solicitante e o departamento são obtidos da sessão, nunca do JSON recebido.
    @app.post("/solicitacoes", response_model=ReimbursementOut, status_code=201, tags=["Solicitações"])
    def criar_solicitacao(dados: ReimbursementCreate, banco: Session = Depends(get_db), usuario: User = Depends(obter_usuario_atual)):
        solicitacao = Reimbursement(requester_id=usuario.id, department_id=usuario.department_id, category=dados.category.value, amount=dados.amount, expense_date=dados.expense_date, justification=dados.justification, receipt_reference=dados.receipt_reference, status="rascunho")
        banco.add(solicitacao)
        try:
            banco.commit()
        except IntegrityError:
            banco.rollback()
            raise HTTPException(status_code=409, detail="Referência de comprovante já utilizada por este colaborador")
        solicitacao = carregar_solicitacao(banco, solicitacao.id)
        return montar_resposta_solicitacao(solicitacao)

    # Cada perfil recebe apenas as solicitações que tem autorização para consultar.
    @app.get("/solicitacoes", response_model=list[ReimbursementOut], tags=["Solicitações"])
    def listar_solicitacoes(
        department_id: int | None = Query(default=None), filtro_situacao: Status | None = Query(default=None, alias="situacao"),
        categoria: Category | None = Query(default=None, alias="categoria"), banco: Session = Depends(get_db),
        usuario: User = Depends(obter_usuario_atual),
    ):
        consulta = banco.query(Reimbursement).options(joinedload(Reimbursement.requester), joinedload(Reimbursement.department), joinedload(Reimbursement.history).joinedload(ReviewHistory.reviewer))
        if usuario.role == "colaborador":
            consulta = consulta.filter(Reimbursement.requester_id == usuario.id)
            if department_id is not None and department_id != usuario.department_id:
                raise HTTPException(status_code=403, detail="Filtro de departamento não permitido")
            consulta = consulta.filter(Reimbursement.department_id == usuario.department_id)
        elif usuario.role == "gestor":
            if department_id is not None and department_id != usuario.department_id:
                raise HTTPException(status_code=403, detail="Gestores só podem consultar seu departamento")
            consulta = consulta.filter(Reimbursement.department_id == usuario.department_id)
        else:
            consulta = consulta.filter(or_(
                Reimbursement.status.in_(("aguardando_financeiro", "aprovada", "paga")),
                Reimbursement.history.any(ReviewHistory.stage == "financeiro"),
            ))
            if department_id is not None:
                consulta = consulta.filter(Reimbursement.department_id == department_id)
        if filtro_situacao is not None:
            consulta = consulta.filter(Reimbursement.status == filtro_situacao.value)
        if categoria is not None:
            consulta = consulta.filter(Reimbursement.category == categoria.value)
        return [montar_resposta_solicitacao(solicitacao) for solicitacao in consulta.order_by(Reimbursement.id).all()]

    @app.get("/solicitacoes/{request_id}", response_model=ReimbursementOut, tags=["Solicitações"])
    def consultar_solicitacao(request_id: int, banco: Session = Depends(get_db), usuario: User = Depends(obter_usuario_atual)):
        solicitacao = carregar_solicitacao(banco, request_id)
        verificar_acesso_solicitacao(solicitacao, usuario)
        return montar_resposta_solicitacao(solicitacao)

    # A edição só é permitida ao dono enquanto a solicitação ainda é rascunho.
    @app.patch("/solicitacoes/{request_id}", response_model=ReimbursementOut, tags=["Solicitações"])
    def editar_solicitacao(request_id: int, dados: ReimbursementUpdate, banco: Session = Depends(get_db), usuario: User = Depends(obter_usuario_atual)):
        solicitacao = carregar_solicitacao(banco, request_id)
        if solicitacao.requester_id != usuario.id or usuario.role != "colaborador":
            raise HTTPException(status_code=403, detail="Somente o solicitante pode editar seu rascunho")
        if solicitacao.status != "rascunho":
            raise HTTPException(status_code=409, detail="A solicitação não está mais em rascunho")
        alteracoes = dados.model_dump(exclude_unset=True)
        for key, valor in alteracoes.items():
            if valor is not None:
                setattr(solicitacao, key, valor.value if hasattr(valor, "value") else valor)
        try:
            banco.commit()
        except IntegrityError:
            banco.rollback()
            raise HTTPException(status_code=409, detail="Referência de comprovante já utilizada por este colaborador")
        return montar_resposta_solicitacao(carregar_solicitacao(banco, request_id))

    # Depois do envio, o registro não pode ser excluído.
    @app.delete("/solicitacoes/{request_id}", status_code=204, tags=["Solicitações"])
    def excluir_solicitacao(request_id: int, banco: Session = Depends(get_db), usuario: User = Depends(obter_usuario_atual)):
        solicitacao = carregar_solicitacao(banco, request_id)
        if solicitacao.requester_id != usuario.id or usuario.role != "colaborador":
            raise HTTPException(status_code=403, detail="Somente o solicitante pode excluir seu rascunho")
        if solicitacao.status != "rascunho":
            raise HTTPException(status_code=409, detail="A solicitação não está mais em rascunho")
        banco.delete(solicitacao)
        banco.commit()

    # O envio inicia o fluxo e também registra esse primeiro evento no histórico.
    @app.post("/solicitacoes/{request_id}/enviar", response_model=ReimbursementOut, tags=["Fluxo de aprovação"])
    def enviar_solicitacao(request_id: int, banco: Session = Depends(get_db), usuario: User = Depends(obter_usuario_atual)):
        solicitacao = carregar_solicitacao(banco, request_id)
        if solicitacao.requester_id != usuario.id:
            raise HTTPException(status_code=403, detail="Somente o solicitante pode enviar a solicitação")
        if solicitacao.status != "rascunho":
            raise HTTPException(status_code=409, detail="A solicitação não está em rascunho")
        solicitacao.status = "aguardando_gestor"
        banco.add(ReviewHistory(reimbursement_id=solicitacao.id, reviewer_id=usuario.id, stage="submissao", decision="enviada", note=None))
        banco.commit()
        return montar_resposta_solicitacao(carregar_solicitacao(banco, request_id))

    # A mesma rotina aplica as regras comuns às análises do gestor e do financeiro.
    def registrar_decisao(request_id: int, situacao_esperada: str, perfil: str, etapa: str, dados: DecisionInput, banco: Session, usuario: User) -> dict:
        """Aplica uma decisão somente quando perfil e etapa correspondem."""
        solicitacao = carregar_solicitacao(banco, request_id)
        if usuario.role != perfil:
            raise HTTPException(status_code=403, detail="Perfil sem permissão para esta etapa")
        if solicitacao.requester_id == usuario.id:
            raise HTTPException(status_code=403, detail="Não é permitido analisar uma solicitação de sua própria autoria")
        if perfil == "gestor" and solicitacao.department_id != usuario.department_id:
            raise HTTPException(status_code=404, detail="Solicitação não encontrada")
        if solicitacao.status != situacao_esperada:
            raise HTTPException(status_code=409, detail="A solicitação não está na etapa de análise esperada")
        if dados.decision.value == "recusar" and not (dados.note and dados.note.strip()):
            raise HTTPException(status_code=422, detail="A justificativa é obrigatória para recusar uma solicitação")
        if dados.decision.value == "recusar":
            solicitacao.status = "recusada"
        elif perfil == "gestor":
            solicitacao.status = "aguardando_financeiro"
        else:
            solicitacao.status = "aprovada"
        banco.add(ReviewHistory(reimbursement_id=solicitacao.id, reviewer_id=usuario.id, stage=etapa, decision=dados.decision.value, note=dados.note.strip() if dados.note else None))
        banco.commit()
        return montar_resposta_solicitacao(carregar_solicitacao(banco, request_id))

    @app.post("/solicitacoes/{request_id}/analise-gestor", response_model=ReimbursementOut, tags=["Fluxo de aprovação"])
    def analisar_com_gestor(request_id: int, dados: DecisionInput, banco: Session = Depends(get_db), usuario: User = Depends(obter_usuario_atual)):
        return registrar_decisao(request_id, "aguardando_gestor", "gestor", "gestor", dados, banco, usuario)

    @app.post("/solicitacoes/{request_id}/analise-financeira", response_model=ReimbursementOut, tags=["Fluxo de aprovação"])
    def analisar_com_financeiro(request_id: int, dados: DecisionInput, banco: Session = Depends(get_db), usuario: User = Depends(obter_usuario_atual)):
        return registrar_decisao(request_id, "aguardando_financeiro", "financeiro", "financeiro", dados, banco, usuario)

    # Só uma aprovação financeira concluída permite registrar o pagamento.
    @app.post("/solicitacoes/{request_id}/pagamento", response_model=ReimbursementOut, tags=["Fluxo de aprovação"])
    def registrar_pagamento(request_id: int, banco: Session = Depends(get_db), usuario: User = Depends(exigir_perfil("financeiro"))):
        solicitacao = carregar_solicitacao(banco, request_id)
        if solicitacao.requester_id == usuario.id:
            raise HTTPException(status_code=403, detail="Não é permitido pagar uma solicitação de sua própria autoria")
        if solicitacao.status != "aprovada":
            raise HTTPException(status_code=409, detail="Somente solicitações aprovadas pelo financeiro podem ser pagas")
        solicitacao.status = "paga"
        banco.add(ReviewHistory(reimbursement_id=solicitacao.id, reviewer_id=usuario.id, stage="pagamento", decision="paga", note=None))
        banco.commit()
        return montar_resposta_solicitacao(carregar_solicitacao(banco, request_id))

    @app.get("/departamentos", tags=["Consultas"])
    def listar_departamentos(banco: Session = Depends(get_db), usuario: User = Depends(obter_usuario_atual)):
        departamentos = banco.query(Department).order_by(Department.name).all()
        if usuario.role == "colaborador":
            departamentos = [departamento for departamento in departamentos if departamento.id == usuario.department_id]
        elif usuario.role == "gestor":
            departamentos = [departamento for departamento in departamentos if departamento.id == usuario.department_id]
        return [{"id": departamento.id, "name": departamento.name} for departamento in departamentos]

    return app


app = create_app()
