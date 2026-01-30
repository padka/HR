from typing import List, Optional
from sqlalchemy import String, Integer, ForeignKey, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.domain.base import Base

class CityExpert(Base):
    __tablename__ = "city_experts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    city_id: Mapped[int] = mapped_column(ForeignKey("cities.id", ondelete="CASCADE"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    city: Mapped["City"] = relationship("City", back_populates="city_experts")

    def __repr__(self) -> str:
        return f"<CityExpert {self.name} city={self.city_id}>"


class CityExecutive(Base):
    __tablename__ = "city_executives"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    city_id: Mapped[int] = mapped_column(ForeignKey("cities.id", ondelete="CASCADE"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    city: Mapped["City"] = relationship("City", back_populates="executives")

    def __repr__(self) -> str:
        return f"<CityExecutive {self.name} city={self.city_id}>"