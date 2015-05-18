# -*- coding: utf-8 -*-
from sqlalchemy import Column, String, Integer, ForeignKey
from sqlalchemy.schema import UniqueConstraint

from .core import Base


class Genotype(Base):
    __tablename__ = 'genotype'
    __table_args__ = (UniqueConstraint('sample_id', 'rsnumber',
                                       name='_sample_rsnumber'),)

    id = Column(Integer, primary_key=True)
    rsnumber = Column(String(10))
    sample_id = Column(Integer, ForeignKey('sample.id'))
    allele_1 = Column(String(1))
    allele_2 = Column(String(1))

    def __str__(self):
        """Stringify genotype call."""
        return "{this.allele_1}{this.allele_2}".format(this=self)