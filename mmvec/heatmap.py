import seaborn as sns
import matplotlib.pyplot as plt
import numpy as np
import warnings


_heatmap_choices = {
    'metric': {'braycurtis', 'canberra', 'chebyshev', 'cityblock',
               'correlation', 'cosine', 'dice', 'euclidean', 'hamming',
               'jaccard', 'kulsinski', 'mahalanobis', 'matching', 'minkowski',
               'rogerstanimoto', 'russellrao', 'seuclidean', 'sokalmichener',
               'sokalsneath', 'sqeuclidean', 'yule'},
    'method': {'single', 'complete', 'average', 'weighted', 'centroid',
               'median', 'ward'}}

_cmaps = {
    'heatmap': [
        'PiYG', 'PRGn', 'BrBG', 'PuOr', 'RdGy', 'RdBu',
        'RdYlBu', 'RdYlGn', 'Spectral', 'coolwarm', 'bwr', 'seismic',
        'viridis', 'plasma', 'inferno', 'magma', 'cividis'],
    'margins': [
        'cubehelix', 'Pastel1', 'Pastel2', 'Paired',
        'Accent', 'Dark2', 'Set1', 'Set2', 'Set3',
        'tab10', 'tab20', 'tab20b', 'tab20c',
        'viridis', 'plasma', 'inferno', 'magma', 'cividis']}


def ranks_heatmap(ranks, microbe_metadata=None, metabolite_metadata=None,
                  method='average', metric='euclidean',
                  color_palette='seismic', margin_palette='cubehelix',
                  x_labels=False, y_labels=False, level=3):
    '''
    Generate clustermap of microbe X metabolite conditional probabilities.

    Parameters
    ----------
    ranks: pd.DataFrame of conditional probabilities.
        Microbes (rows) X metabolites (columns).
    microbe_metadata: pd.Series of microbe metadata for annotating plots
    metabolite_metadata: pd.Series of metabolite metadata for annotating plots
    method: str
        Hierarchical clustering method used in clustermap.
    metric: str
        Hierarchical clustering distance metric used in clustermap.
    color_palette: str
        Color palette for clustermap.
    margin_palette: str
        Name of color palette to use for annotating metadata
        along margin(s) of clustermap.
    x_labels: bool
        Plot x-axis (metabolite) labels?
    y_labels: bool
        Plot y-axis (microbe) labels?
    level: int
        taxonomic level for annotating clustermap. Set to -1 if not parsing
        semicolon-delimited taxonomies or wish to print entire annotation.

    Returns
    -------
    sns.clustermap
    '''
    # subset microbe metadata based on rows/columns
    if microbe_metadata is not None:
        microbe_metadata, ranks, row_colors, row_class_colors = \
            _process_microbe_metadata(
                ranks, microbe_metadata, level, margin_palette)
    else:
        row_colors = None

    # subset metabolite metadata based on rows/columns
    if metabolite_metadata is not None:
        metabolite_metadata, ranks, col_colors, col_class_colors = \
            _process_metabolite_metadata(
                ranks, metabolite_metadata, margin_palette)
    else:
        col_colors = None

    # Generate heatmap
    hotmap = sns.clustermap(ranks, cmap=color_palette, center=0,
                            col_colors=col_colors, row_colors=row_colors,
                            figsize=(12, 12), method=method, metric=metric,
                            cbar_kws={'label': 'Log Conditional\nProbability'})

    # add legends
    if col_colors is not None:
        for label in col_class_colors.keys():
            hotmap.ax_col_dendrogram.bar(
                0, 0, color=col_class_colors[label], label=label, linewidth=0)
        hotmap.ax_col_dendrogram.legend(
            title=metabolite_metadata.name, ncol=5, bbox_to_anchor=(0.9, 0.95),
            bbox_transform=plt.gcf().transFigure)
    if row_colors is not None:
        for label in row_class_colors.keys():
            hotmap.ax_row_dendrogram.bar(
                0, 0, color=row_class_colors[label], label=label, linewidth=0)
        hotmap.ax_row_dendrogram.legend(
            title=microbe_metadata.name, ncol=1, bbox_to_anchor=(0.1, 0.7),
            bbox_transform=plt.gcf().transFigure)

    # toggle axis labels
    if not x_labels:
        hotmap.ax_heatmap.set_xticklabels('')
    if not y_labels:
        hotmap.ax_heatmap.set_yticklabels('')

    return hotmap


def paired_heatmaps(ranks, microbes_table, metabolites_table, microbe_metadata,
                    features, top_k_metabolites=50, level=-1,
                    normalize='log10', color_palette='magma'):
    '''
    Creates paired heatmaps of microbe abundances and metabolite abundances.

    Parameters
    ----------
    ranks: pd.DataFrame of conditional probabilities.
        Microbes (rows) X metabolites (columns).
    microbes_table: biom.Table
        Microbe feature abundances per sample.
    metabolites_table: biom.Table
        Metabolite feature abundances per sample.
    microbe_metadata: pd.Series
        Microbe metadata for annotating plots
    features: list
        Select microbial feature IDs to display on paired heatmap.
    top_k_metabolites: int
        Select top k metabolites associated with the chosen features to
        display on heatmap.
    level: int
        taxonomic level for annotating clustermap.
        Set to -1 if not parsing semicolon-delimited taxonomies.
    normalize: str
        Column normalization strategy to use for heatmaps. Must
        be "log10", "z_score", or None
    color_palette: str
        Color palette for heatmaps.
    '''
    # validate microbes
    missing_microbes = set(features) - set(microbes_table.ids('observation'))
    if len(missing_microbes) > 0:
        raise ValueError('features must represent feature IDs in '
                         'microbes_table. Missing microbe(s): {0}'.format(
                            missing_microbes))

    # filter select microbes from microbe table and sort by abundance
    sort_orders = [False] + [True] * (len(features) - 1)
    select_microbes = microbes_table.copy().filter(features, 'observation')
    select_microbes = select_microbes.to_dataframe().T
    select_microbes = select_microbes[features]  # sort cols by features order
    select_microbes = select_microbes.sort_values(
        features[::-1], ascending=sort_orders)

    # find top 50 metabolites (highest positive ranks)
    microb_ranks = ranks.loc[features]
    top_metabolites = microb_ranks.max()
    top_metabolites = top_metabolites.sort_values(ascending=False)
    top_metabolites = top_metabolites[:top_k_metabolites].index

    # grab top 50 metabolites in metabolite table
    select_metabolites = metabolites_table.copy().filter(
        top_metabolites, 'observation').to_dataframe().T

    # sort metabolite columns by rank
    select_metabolites = select_metabolites.reindex(
        microb_ranks[top_metabolites].sort_values(
            features[::-1], ascending=sort_orders, axis=1).columns, axis=1)

    # align sample IDs across tables
    select_microbes, select_metabolites = select_microbes.align(
        select_metabolites, join='inner', axis=0)

    # optionally annotate microbe data with taxonomy
    if microbe_metadata is not None:
        annotations = microbe_metadata.reindex(select_microbes.columns)
        # parse semicolon-delimited taxonomy
        if level > -1:
            annotations = _parse_taxonomy_strings(annotations, level)
    else:
        annotations = select_microbes.columns

    # optionally normalize data
    if normalize is not None:
        select_microbes = _normalize_by_column(select_microbes, normalize)
        select_metabolites = _normalize_by_column(select_metabolites,
                                                  normalize)
        cbar_label = normalize + ' Frequency'
    else:
        cbar_label = 'Frequency'

    # generate heatmaps
    heatmaps, axes = plt.subplots(
        nrows=1, ncols=2, sharey=True, figsize=(12, 6))

    sns.heatmap(select_microbes.values, cmap=color_palette,
                cbar_kws={'label': cbar_label}, ax=axes[0],
                xticklabels=annotations, yticklabels=False)
    sns.heatmap(select_metabolites.values, cmap=color_palette,
                cbar_kws={'label': cbar_label}, ax=axes[1],
                xticklabels=False, yticklabels=False)
    axes[0].set_ylabel('Samples')
    axes[0].set_xlabel('Microbes')
    axes[1].set_xlabel('Metabolites')

    return heatmaps


def _parse_heatmap_metadata_annotations(metadata_column, margin_palette):
    '''
    Transform feature or sample metadata into color vector for annotating
    margin of clustermap.
    Parameters
    ----------
    metadata_column: pd.Series of metadata for annotating plots
    margin_palette: str
        Name of color palette to use for annotating metadata
        along margin(s) of clustermap.
    Returns
    -------
    Returns vector of colors for annotating clustermap and dict mapping colors
    to classes.
    '''
    # Create a categorical palette to identify md col
    metadata_column = metadata_column.astype(str)
    col_names = sorted(metadata_column.unique())

    # Select Color palette
    if margin_palette == 'colorhelix':
        col_palette = sns.cubehelix_palette(
            len(col_names), start=2, rot=3, dark=0.3, light=0.8, reverse=True)
    else:
        col_palette = sns.color_palette(margin_palette, len(col_names))
    class_colors = dict(zip(col_names, col_palette))

    # Convert the palette to vectors that will be drawn on the matrix margin
    col_colors = metadata_column.map(class_colors)

    return col_colors, class_colors


def _parse_taxonomy_strings(taxonomy_series, level):
    '''
    taxonomy_series: pd.Series of semicolon-delimited taxonomy strings
    level: int
        taxonomic level for annotating clustermap.
     Returns
     -------
    Returns a pd.Series of taxonomy names at specified level,
        or terminal annotation
    '''
    return taxonomy_series.apply(lambda x: x.split(';')[:level][-1].strip())


def _process_microbe_metadata(ranks, microbe_metadata, level, margin_palette):
    _warn_metadata_filtering('microbe')
    microbe_metadata, ranks = microbe_metadata.align(
        ranks, join='inner', axis=0)
    # parse semicolon-delimited taxonomy
    if level > -1:
        microbe_metadata = _parse_taxonomy_strings(microbe_metadata, level)
    # map metadata categories to row colors
    row_colors, row_class_colors = _parse_heatmap_metadata_annotations(
        microbe_metadata, margin_palette)

    return microbe_metadata, ranks, row_colors, row_class_colors


def _process_metabolite_metadata(ranks, metabolite_metadata, margin_palette):
    _warn_metadata_filtering('metabolite')
    _ids = set(metabolite_metadata.index) & set(ranks.columns)
    ranks = ranks[sorted(_ids)]
    metabolite_metadata = metabolite_metadata.reindex(ranks.columns)
    # map metadata categories to column colors
    col_colors, col_class_colors = _parse_heatmap_metadata_annotations(
        metabolite_metadata, margin_palette)

    return metabolite_metadata, ranks, col_colors, col_class_colors


def _warn_metadata_filtering(metadata_type):
    warning = ('Conditional probabilities table and {0} metadata will be '
               'filtered to contain only the intersection of IDs in each. If '
               'this behavior is undesired, ensure that all {0} IDs are '
               'present in both the table and the metadata '
               'file'.format(metadata_type))
    warnings.warn(warning, UserWarning)


def _normalize_by_column(table, method):
    '''
    Normalize column data in a dataframe for plotting in clustermap.

    table: pd.DataFrame
        Input data.
    method: str
        Normalization method to use.

    Returns normalized table as pd.DataFrame
    '''
    if method == 'z_score':
        return (table - table.mean()) / table.std()
    elif method == 'log10':
        return table.apply(lambda x: np.log10(x + 1))
