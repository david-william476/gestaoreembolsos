from datetime import date, datetime, timezone
from decimal import Decimal
from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .database import Base


def utcnow():
    return datetime.now(timezone.utc)


class Department(Base):
    """Departamento ao qual usuários e solicitações ficam vinculados."""
    __tablename__ = "departments"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    users: Mapped[list["User"]] = relationship(back_populates="department")


class User(Base):
    """Conta interna; a senha é armazenada somente como hash."""
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.id"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    department: Mapped[Department] = relationship(back_populates="users")
    requests: Mapped[list["Reimbursement"]] = relationship(back_populates="requester", foreign_keys="Reimbursement.requester_id")


class Reimbursement(Base):
    """Despesa e estado atual do pedido de reembolso."""
    __tablename__ = "reimbursements"
    __table_args__ = (UniqueConstraint("requester_id", "receipt_reference", name="uq_receipt_per_requester"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    requester_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.id"), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    expense_date: Mapped[date] = mapped_column(Date, nullable=False)
    justification: Mapped[str] = mapped_column(Text, nullable=False)
    receipt_reference: Mapped[str] = mapped_column(String(150), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="RASCUNHO", nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
    requester: Mapped[User] = relationship(back_populates="requests", foreign_keys=[requester_id])
    department: Mapped[Department] = relationship(foreign_keys=[department_id])
    history: Mapped[list["ReviewHistory"]] = relationship(back_populates="reimbursement", order_by="ReviewHistory.id", cascade="all, delete-orphan")


class ReviewHistory(Base):
    """Registro histórico de envio, análise ou pagamento."""
    __tablename__ = "review_history"
    id: Mapped[int] = mapped_column(primary_key=True)
    reimbursement_id: Mapped[int] = mapped_column(ForeignKey("reimbursements.id"), nullable=False, index=True)
    reviewer_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    stage: Mapped[str] = mapped_column(String(30), nullable=False)
    decision: Mapped[str] = mapped_column(String(30), nullable=False)
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    reimbursement: Mapped[Reimbursement] = relationship(back_populates="history")
    reviewer: Mapped[User] = relationship()
