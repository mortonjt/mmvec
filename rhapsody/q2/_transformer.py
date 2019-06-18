import pandas as pd

from rhapsody.q2 import MMvecEmbeddingFormat
from rhapsody.q2.plugin_setup import plugin


# posterior types
@plugin.register_transformer
def _22(ff: MMvecEmbeddingFormat) -> pd.DataFrame:
    return qiime2.Metadata.load(str(ff)).to_dataframe()


@plugin.register_transformer
def _23(ff: MMvecEmbeddingFormat) -> qiime2.Metadata:
    return qiime2.Metadata.load(str(ff))


@plugin.register_transformer
def _24(data: pd.DataFrame) -> MMvecEmbeddingFormat:
    ff = MMvecEmbeddingFormat()
    qiime2.Metadata(data).save(str(ff))
    return ff
