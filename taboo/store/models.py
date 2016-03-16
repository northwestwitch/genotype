# -*- coding: utf-8 -*-
from datetime import datetime
import logging
import os

from sqlalchemy import Column, ForeignKey, types
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.schema import UniqueConstraint

# base for declaring a mapping
Base = declarative_base()
logger = logging.getLogger(__name__)


class Genotype(Base):

    """Represent a genotype call for a position.

    For any given position and sample, only one genotype call be linked.

    Args:
        rsnumber (str): reference cluster id for the SNP
        sample (Sample): related ``Sample`` model
        allele_1 (str): first base in the call
        allele_2 (str): second base in the call
    """

    __tablename__ = 'genotype'
    __table_args__ = (UniqueConstraint('analysis_id', 'rsnumber',
                                       name='_sample_rsnumber'),)

    id = Column(types.Integer, primary_key=True)
    rsnumber = Column(types.String(10))
    analysis_id = Column(types.Integer, ForeignKey('analysis.id'))
    allele_1 = Column(types.String(1))
    allele_2 = Column(types.String(1))

    @property
    def is_cool(self):
        """Check if the genotype looks good."""
        return self.allele_1 != '0' or self.allele_2 != '0'

    def __str__(self):
        """Stringify genotype call.

        Returns:
            str: serialized representation of the genotype
        """
        # assume we aren't dealing with stranded data
        genotypes = sorted([self.allele_1, self.allele_2])
        return ''.join(genotypes)

    def __eq__(self, other):
        """Compare two Genotype records."""
        return str(self) == str(other)


class Sample(Base):

    """Represent a sample linked to a list of genotypes.

    The ``sample_id`` together with the experiment should for a unique
    combination.

    Args:
        sample_id (str): display name to use for sample
        experiment (str): type of experiment, e.g. 'sequencing'
        source (str): unique id to identify the source of the data
        genotypes (list): list of ``Genotype`` models
    """

    __tablename__ = 'sample'

    id = Column(types.Integer, primary_key=True)
    sample_id = Column(types.String(32), unique=True)
    expected_sex = Column(types.String(32))
    created_at = Column(types.DateTime, default=datetime.now)

    analyses = relationship('Analysis', backref='sample')
    results = relationship('Result', backref='sample')

    def is_ready(self):
        """Check if both experiments are loaded for the sample."""
        experiments = [analysis.experiment for analysis in self.analyses]
        return 'sequencing' in experiments and 'genotyping' in experiments

    @property
    def analysis_dict(self):
        """Dictify loaded analyses."""
        return {analysis.experiment: analysis for analysis in self.analyses}

    def sexes(self):
        """Return sex determinations from loaded analyses."""
        sexes = {analysis.experiment: analysis.sex for analysis in self.analyses}
        sexes['expected'] = self.expected_sex
        return sexes

    def same_sex(self):
        """Determine if the sex is the same for analyses."""
        sexes = self.sexes().values()

        if len(set(filter(None, sexes))) != 1:
            return 'fail'

        elif len(sexes) < 3 or None in sexes:
            return 'unknown'

        elif len(set(sexes)) == 1:
            return 'success'

        else:
            raise ValueError('unknown error')

    def is_success(self):
        """Check if a comparison was made successfully."""
        success_results = self.successful_results()
        if len(success_results) == 1:
            return True
        else:
            return False

    def is_analyzed(self):
        """Check if an analysis has been performed."""
        analyses = self.analysis_dict
        return 'genotyping' in analyses and analyses['genotyping'].results

    def successful_results(self):
        """Select all successful results."""
        expected_id = self.sample_id
        return [result for result in self.results
                if result_success(expected_id, result)]

    def matches(self):
        """Return the matching sample ids."""
        return [result.analysis.sample.sample_id for result in
                self.successful_results()]

    def top_samples(self):
        """Return sample ids for all results."""
        return [("{res.analysis.sample.sample_id} "
                 "[{res.matches}/{res.mismatches}/{res.unknowns}/51]"
                 .format(res=result)) for result in self.results[:2]]


def result_success(expected_id, result, min_matches=20, allowed_mismatches=3):
    """Check if a comparison is successful."""
    sample_id = result.analysis.sample.sample_id
    acceptable_mismatches = result.mismatches <= allowed_mismatches
    same_sample = sample_id == expected_id
    enough_matches = result.matches >= min_matches
    if same_sample and acceptable_mismatches and enough_matches:
        logger.debug('genotypes match the same sample')
        answer = True
    else:
        answer = False
        if same_sample and not acceptable_mismatches:
            logger.debug('genotyping failed on acceptable mismatches (%s)',
                         allowed_mismatches)
        elif not enough_matches:
            logger.debug('genotyping failed on not enough matches')
        else:
            if acceptable_mismatches:
                logger.debug("genotypes match a different sample: %s", sample_id)
            else:
                logger.debug("genotypes don't match any sample, top: %s", sample_id)
    return answer


class Result(Base):

    """Represent the result of a sample check."""

    __tablename__ = 'result'

    id = Column(types.Integer, primary_key=True)
    matches = Column(types.Integer)
    mismatches = Column(types.Integer)
    unknowns = Column(types.Integer)

    analysis_id = Column(types.Integer, ForeignKey('analysis.id'))
    sample_id = Column(types.Integer, ForeignKey('sample.id'))


class Analysis(Base):

    """Represent a SNP calling analysis performed on a Sample."""

    __tablename__ = 'analysis'
    __table_args__ = (UniqueConstraint('sample_id', 'experiment',
                                       name='_sample_exp'),)

    id = Column(types.Integer, primary_key=True)
    experiment = Column(types.String(32), nullable=False)
    source = Column(types.Text)
    # intended choices: female, male, unknown, conflict
    sex = Column(types.String(32))

    sample_id = Column(types.Integer, ForeignKey('sample.id'))

    genotypes = relationship('Genotype', order_by='Genotype.rsnumber',
                             backref='analysis')
    results = relationship('Result', backref='analysis')

    @property
    def short_source(self):
        """Basename of the source path."""
        return os.path.basename(self.source)

    def stringify(self):
        """Stringify genotypes for the sample.

        Returns:
            str: serialized representation of related genotypes
        """
        return '-'.join(str(genotype) for genotype in self.genotypes)
