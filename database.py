import sys
from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from sqlalchemy import create_engine
import sqlalchemy_jsonfield

Base = declarative_base()

class Global_catalog(Base):
    __tablename__ = 'global'
    id = Column(Integer, primary_key = True)
    name = Column(String(80), nullable = False)
    image = Column(String(250), nullable = True)
    tagline = Column(String(250))
    catalogs = relationship("Catalog")
    @property
    def serialize(self):
        return {
            'id': self.id,
            'name': self.name,
            'image': self.image,
            'tagline': self.tagline,
        }

class Catalog(Base):
    __tablename__ = 'catalog'
    id = Column(Integer, primary_key = True)
    name = Column(String(80), nullable = False)
    image = Column(String(250), nullable = True)
    tagline = Column(String(250))
    global_catalog_id = Column(Integer, ForeignKey('global.id'))
    products = relationship("Product")
    @property
    def serialize(self):
        return {
            'id': self.id,
            'name': self.name,
            'image': self.image,
            'tagline': self.tagline,
            'global_catalog': self.global_catalog_id
        }


class Product(Base):
    __tablename__ = 'product'
    id = Column(Integer, primary_key = True)
    images = Column(String(250), nullable = False)
    header = Column(String(250), nullable = False)
    model = Column(String(250), nullable = False)
    price = Column(String(80), nullable = False)
    brand = Column(String(250), nullable = False)
    description = Column(String(250), nullable = True)
    specs = Column(sqlalchemy_jsonfield.JSONField(), nullable = False)
    catalog_id = Column(Integer, ForeignKey('catalog.id'))
    @property
    def serialize(self):
        return {
            'id' : self.id,
            'images': self.images,
            'header': self.header,
            'model': self.model,
            'price': self.price,
            'brand': self.brand,
            'description': self.description,
            'specs': self.specs,
            'catalog': self.catalog_id
        }

class User(Base):
    __tablename__ = 'user'
    id = Column(Integer, primary_key = True)
    name = Column(String(80), nullable = False)
    email = Column(String(250), nullable = False)
    password = Column(String(250), nullable = False)
    @property
    def serialize(self):
        return {
            'id': self.id,
            'name': self.name,
            'email': self.email,
        }


engine = create_engine('sqlite:///ecommerceapp.db')
Base.metadata.create_all(engine)
DBSession = sessionmaker(bind = engine)
