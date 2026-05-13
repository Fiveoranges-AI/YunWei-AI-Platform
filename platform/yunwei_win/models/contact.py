from __future__ import annotations

import enum
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Enum as SQLEnum
from sqlalchemy import ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from yunwei_win.db import Base
from yunwei_win.models._base import TimestampMixin

if TYPE_CHECKING:
    from yunwei_win.models.customer import Customer


class ContactRole(str, enum.Enum):
    seller = "seller"
    buyer = "buyer"
    delivery = "delivery"
    acceptance = "acceptance"
    invoice = "invoice"
    other = "other"


class Contact(Base, TimestampMixin):
    __tablename__ = "contacts"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("customers.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str | None] = mapped_column(String, nullable=True)
    phone: Mapped[str | None] = mapped_column(String, nullable=True)
    mobile: Mapped[str | None] = mapped_column(String, nullable=True)
    email: Mapped[str | None] = mapped_column(String, nullable=True)
    role: Mapped[ContactRole] = mapped_column(
        SQLEnum(ContactRole, name="contact_role"),
        nullable=False,
        default=ContactRole.other,
    )
    address: Mapped[str | None] = mapped_column(String, nullable=True)
    wechat_id: Mapped[str | None] = mapped_column(String, nullable=True)
    needs_review: Mapped[bool] = mapped_column(default=False, nullable=False)

    customer: Mapped[Customer | None] = relationship(back_populates="contacts")
