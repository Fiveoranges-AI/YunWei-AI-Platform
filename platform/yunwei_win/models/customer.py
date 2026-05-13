from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from yunwei_win.db import Base
from yunwei_win.models._base import TimestampMixin

if TYPE_CHECKING:
    from yunwei_win.models.contact import Contact
    from yunwei_win.models.order import Order


class Customer(Base, TimestampMixin):
    __tablename__ = "customers"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    full_name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    short_name: Mapped[str | None] = mapped_column(String, nullable=True)
    address: Mapped[str | None] = mapped_column(String, nullable=True)
    tax_id: Mapped[str | None] = mapped_column(String, nullable=True)

    contacts: Mapped[list[Contact]] = relationship(back_populates="customer")
    orders: Mapped[list[Order]] = relationship(back_populates="customer")
