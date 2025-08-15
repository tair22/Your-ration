from sqlalchemy import Column, Integer, String, LargeBinary, Float, Numeric
from db import Base


class Users(Base):

    __tablename__ = 'users'

    login = Column(String, unique=True, index=True, primary_key=True)
    password = Column(String)
    email = Column(String)
    phone_number = Column(String)


class Items(Base):

    __tablename__ = 'items'

    id = Column(Integer, primary_key=True, index=True,  unique=True)
    name = Column(String)
    description = Column(String)
    image = Column(String)
    price = Column(Integer)


class Orders(Base):

    __tablename__ = 'orders'

    id = Column(Integer, primary_key=True, index=True)
    item_id = Column(Integer, primary_key=True)
    amount = Column(Integer)


class Cart(Base):

    __tablename__ = 'cart'
    
    item_id = Column(Integer, primary_key=True)
    amount = Column(Integer)


class EnergyValue(Base):
    __tablename__ = 'energy_value'
    
    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
        unique=True,
        nullable=False
    )
    calories = Column(
        Numeric,
        nullable=False
    )
    proteins = Column(
        Numeric,
        nullable=False
    )
    fats = Column(
        Numeric,
        nullable=False
    )
    carbs = Column(
        Numeric,
        nullable=False
    )

    def __repr__(self):
        return f"<EnergyValue(id={self.id}, calories={self.calories}, proteins={self.proteins})>"

class UserInfo(Base):
    __tablename__ = 'info'
    
    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
        unique=True,
        nullable=False
    )
    login = Column(
        String,
        nullable=False,
        unique=True
    )
    password = Column(
        String,
        nullable=False
    )
    age = Column(
        Integer,
        nullable=False
    )
    weight = Column(
        Numeric,
        nullable=False
    )

    def __repr__(self):
        return f"<UserInfo(id={self.id}, login='{self.login}', age={self.age})>"

if __name__ == "__main__":
    from sqlalchemy import create_engine
    engine = create_engine('sqlite:///nutrition.db')
    Base.metadata.create_all(engine)
    print("Таблицы energy_value и info успешно созданы!")