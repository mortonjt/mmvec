# ----------------------------------------------------------------------------
# Copyright (c) 2016--, gneiss development team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING.txt, distributed with this software.
# ----------------------------------------------------------------------------
import importlib
import qiime2.plugin
import qiime2.sdk
from rhapsody import __version__
from qiime2.plugin import (Str, Properties, Int, Float,  Metadata)
from q2_types.feature_table import FeatureTable, Frequency
from q2_types.feature_data import FeatureData
from q2_types.ordination import PCoAResults

from rhapsody.q2 import (
    MMvecConditional, MMvecConditionalFormat, MMvecConditionalDirFmt,
    MMvecEmbedding, MMvecEmbeddingFormat, MMvecEmbeddingDirFmt,
    mmvec
)

plugin = qiime2.plugin.Plugin(
    name='rhapsody',
    version=__version__,
    website="https://github.com/biocore/rhapsody",
    short_description=('Plugin for performing microbe-metabolite '
                       'co-occurence analysis.'),
    description=('This is a QIIME 2 plugin supporting microbe-metabolite '
                 'co-occurence analysis using mmvec.'),
    package='rhapsody')


plugin.methods.register_function(
    function=mmvec,
    inputs={'microbes': FeatureTable[Frequency],
            'metabolites': FeatureTable[Frequency]},
    parameters={
        'metadata': Metadata,
        'training_column': Str,
        'num_testing_examples': Int,
        'min_feature_count': Int,
        'epochs': Int,
        'batch_size': Int,
        'latent_dim': Int,
        'input_prior': Float,
        'output_prior': Float,
        'learning_rate': Float,
        'summary_interval': Int
    },
    outputs=[
        ('embeddings', MMvecEmbedding)
    ],
    input_descriptions={
        'microbes': 'Input table of microbial counts.',
        'metabolites': 'Input table of metabolite intensities.',
    },
    output_descriptions={
        'embeddings': ('Low dimensional representations of the microbes '
                       'and metabolites')
    },
    parameter_descriptions={
        'metadata': 'Sample metadata table with covariates of interest.',
        'training_column': ("The metadata column specifying which "
                            "samples are for training/testing. "
                            "Entries must be marked `Train` for training "
                            "examples and `Test` for testing examples. "),
        'num_testing_examples': ("The number of random examples to select "
                                 "if `training_column` isn't specified"),
        'epochs': ('The number of total number of iterations '
                   'over the entire dataset'),
        'batch_size': ('The number of samples to be evaluated per '
                       'training iteration'),
        'input_prior': ('Width of normal prior for the microbial '
                        'coefficients .Smaller values will regularize '
                        'parameters towards zero. Values must be greater '
                        'than 0.'),
        'output_prior': ('Width of normal prior for the metabolite '
                         'coefficients. Smaller values will regularize '
                         'parameters towards zero. Values must be greater '
                         'than 0.'),
        'learning_rate': ('Gradient descent decay rate.')
    },
    name='Microbe metabolite vectors',
    description=("Performs co-occurrence analysis for exploring "
                 "microbe-metabolite interactions"),
    citations=[]
)


plugin.register_formats(MMvecEmbeddingFormat, MMvecEmbeddingDirFmt)
plugin.register_semantic_types(MMvecEmbedding)
plugin.register_semantic_type_to_format(
    FeatureData[MMvecEmbedding], MMvecEmbeddingDirFmt)

importlib.import_module('rhapsody.q2._transformer')
