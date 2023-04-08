from typing import List

from sqlalchemy import String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Machine(Base):
    __tablename__ = "machine"

    id: Mapped[str] = mapped_column(primary_key=True)
    image: Mapped[str] = mapped_column(String(30))
    installed_packages: Mapped[List["Package"]] = relationship(back_populates="host", cascade="all, "
                                                                                              "delete-orphan")


class Package(Base):
    __tablename__ = "package"

    id: Mapped[str] = mapped_column(primary_key=True)
    exported_apps: Mapped[List[str]] = relationship(back_populates="source", cascade="all, "
                                                                                     "delete-orphan")
    host: Mapped["Machine"] = relationship(back_populates="installed_packages")


class Exported(Base):
    __tablename__ = "exported"

    id: Mapped[str] = mapped_column(primary_key=True)

    name: Mapped[str] = mapped_column(String(60))
    type: Mapped[str] = mapped_column(String(30))

    source: Mapped["Package"] = relationship(back_populates="exported_apps")
