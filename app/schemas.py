from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class Role(str, Enum):
    COLLABORATOR = "colaborador"
    MANAGER = "gestor"
    FINANCE = "financeiro"


class Category(str, Enum):
    FOOD = "alimentacao"
    TRANSPORT = "transporte"
    LODGING = "hospedagem"
    MATERIALS = "materiais"
    OTHER = "outros"


class Status(str, Enum):
    DRAFT = "rascunho"
    WAITING_MANAGER = "aguardando_gestor"
    WAITING_FINANCE = "aguardando_financeiro"
    APPROVED = "aprovada"
    PAID = "paga"
    REJECTED = "recusada"


class Decision(str, Enum):
    APPROVE = "aprovar"
    REJECT = "recusar"


class ReimbursementCreate(BaseModel):
    """Dados aceitos ao criar uma solicitação; perfil e departamento vêm da sessão."""
    model_config = ConfigDict(extra="forbid")
    category: Category
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    expense_date: date
    justification: str = Field(min_length=3, max_length=2000)
    receipt_reference: str = Field(min_length=1, max_length=150)

    @field_validator("expense_date")
    @classmethod
    def expense_date_not_future(cls, value: date) -> date:
        if value > date.today():
            raise ValueError("A data da despesa não pode ser futura")
        return value

    @field_validator("receipt_reference")
    @classmethod
    def strip_receipt_reference(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("A referência do comprovante é obrigatória")
        return value


class ReimbursementUpdate(BaseModel):
    """Campos que o solicitante pode alterar enquanto o pedido é rascunho."""
    model_config = ConfigDict(extra="forbid")
    category: Category | None = None
    amount: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    expense_date: date | None = None
    justification: str | None = Field(default=None, min_length=3, max_length=2000)
    receipt_reference: str | None = Field(default=None, min_length=1, max_length=150)

    @field_validator("expense_date")
    @classmethod
    def update_date_not_future(cls, value: date | None) -> date | None:
        if value is not None and value > date.today():
            raise ValueError("A data da despesa não pode ser futura")
        return value


class DecisionInput(BaseModel):
    decision: Decision
    note: str | None = Field(default=None, max_length=2000)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    email: EmailStr
    department_id: int
    department_name: str
    role: Role


class HistoryOut(BaseModel):
    id: int
    reviewer_id: int
    reviewer_name: str
    reviewer_role: Role
    stage: str
    decision: str
    decided_at: datetime
    note: str | None


class ReimbursementOut(BaseModel):
    id: int
    requester_id: int
    requester_name: str
    department_id: int
    department_name: str
    category: Category
    amount: Decimal
    expense_date: date
    justification: str
    receipt_reference: str
    status: Status
    created_at: datetime
    updated_at: datetime
    history: list[HistoryOut] = []


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
