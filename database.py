from sqlalchemy.orm import DeclarativeBase, Mapped

class Base(DeclarativeBase):
    pass

class Machine(Base):
    __tablename__ = "machine"