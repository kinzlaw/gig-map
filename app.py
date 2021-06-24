#!/usr/bin/env python3

# Import the helper functions

from app.helpers import read_data, make_nj_tree, plot_tree, plot_heatmap

# Import the menu-driven-figure library
from menu_driven_figure.app import MenuDrivenFigure

import argparse
from functools import lru_cache
import logging
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

##################
# SET UP LOGGING #
##################

# Set the level of the logger to INFO
logFormatter = logging.Formatter(
    '%(asctime)s %(levelname)-8s [gig-map] %(message)s'
)
logger = logging.getLogger('gig-map')
logger.setLevel(logging.INFO)

# Write to STDOUT
consoleHandler = logging.StreamHandler()
consoleHandler.setFormatter(logFormatter)
logger.addHandler(consoleHandler)


###################
# PARSE ARGUMENTS #
###################

# Create the parser
parser = argparse.ArgumentParser(
    description='Display the distribution of annotated genes across microbial genomes'
)

# Add the arguments
parser.add_argument(
    '--alignments',
    type=str,
    required=True,
    help='Dataset of gene alignments (suffix: .hdf5)'
)
parser.add_argument(
    '--gene-annotations',
    type=str,
    default=None,
    help='(optional) Annotations for genes to use for plotting (must contain a column named `gene_id`)'
)
parser.add_argument(
    '--genome-annotations',
    type=str,
    default=None,
    help='(optional) Annotations for genomes to use for plotting (must contain a column named `genome_id`)'
)

# Parse the arguments
args = parser.parse_args()

# Read and format the data
data = read_data(args.__dict__)

# Define the menu items to be presented to the user
# The `menus` object is a list, which organizes the menus into tabs
menus = [
    # Second level is a dict, which defines the content of each menu tab
    # This example only has a single tab, but each additional dict
    # will add another tab to the menu display
    dict(
        # Label to be displayed at the top of the tab
        label="Filter Alignments",
        params=[
            dict(
                # ID used to access the value of this menu item
                elem_id="minimum-pctid",
                # Define the type of menu item
                type="input",
                # Define the value type
                input_type="number",
                # Label displayed along this menu item
                label="Minimum Alignment Identity",
                # Default value
                value=90.,
            ),
            dict(
                elem_id="minimum-coverage",
                # Define the type of menu item
                type="input",
                # Define the value type
                input_type="number",
                # Label displayed along this menu item
                label="Minimum Alignment Coverage",
                # Default value
                value=90.,
            )
        ]
    ),
    dict(
        # Label to be displayed at the top of the tab
        label="Format Display",
        params=[
            # Show a heatmap or a t-SNE map
            dict(
                # ID used to access the value of this menu item
                elem_id="display-type",
                # Label displayed along this menu item
                label="Display Type",
                # Dropdown
                type="dropdown",
                # Available options
                options=[
                    dict(
                        label="Heatmap + Tree",
                        value="heatmap"
                    ),
                    dict(
                        label="t-SNE Map",
                        value="tsne"
                    ),
                ],
                # Default value
                value="heatmap"
            ),
            # Allow the user to color the genes by the
            # coverage or identity of the alignment, as well
            # as any additional user-provided metadata
            dict(
                elem_id="color-genes-by",
                label="Color Genes By",
                type="dropdown",
                options=data['available_gene_labels'],
                value="pident",
            ),
            # Set up the labels for each gene
            dict(
                elem_id="label-genes-by",
                label="Label Genes By",
                type="dropdown",
                options=data['available_gene_labels'],
                value="",
            ),
            # Set up the labels for each genome
            dict(
                elem_id="label-genomes-by",
                label="Label Genomes By",
                type="dropdown",
                options=data['available_genome_labels'],
                value="",
                # Only show this menu item if the 'heatmap' option
                # is selected above
                show_if=dict(
                    target='display-type',
                    value='heatmap'
                )
            ),
            # Set the colorscale used for the heatmap
            dict(
                elem_id="heatmap-colorscale",
                label="Heatmap Color Scale",
                type="dropdown",
                options=[
                    dict(label=v, value=v)
                    for v in px.colors.named_colorscales()
                ],
                value="blues",
                show_if=dict(
                    target='display-type',
                    value='heatmap'
                )
            ),
            # Show either the genome names or the colorbar
            dict(
                elem_id="show-on-right",
                label="Right Margin Display",
                type="dropdown",
                options=[
                    dict(
                        label="Genome Labels",
                        value="genome-labels",
                    ),
                    dict(
                        label="Color Scale",
                        value="colorscale",
                    ),
                ],
                value="colorscale",
                show_if=dict(
                    target='display-type',
                    value='heatmap'
                )
            ),
            # Allow the user to set a title to the plot
            dict(
                # ID used to access the value of this menu item
                elem_id="plot-title",
                # Label displayed along this menu item
                label="Plot Title",
                # Free-form input box
                type="input",
                # Input must be a string
                input_type="string",
                # Default value
                value="",
            ),
            # Set the width of the tree
            dict(
                elem_id="tree-width",
                label="Tree Width",
                type="slider",
                min_val=0.1,
                max_val=0.9,
                value=0.4,
                step=0.01,
                show_if=dict(
                    target='display-type',
                    value='heatmap'
                )
            ),
            # Set the width of the figure
            dict(
                elem_id="figure-width",
                label="Figure Width",
                type="slider",
                min_val=200,
                max_val=2400,
                value=800,
                step=20,
            ),
            dict(
                elem_id="figure-height",
                label="Figure Height",
                type="slider",
                min_val=200,
                max_val=2400,
                value=460,
                step=20,
            ),
        ]
    ),
]


@lru_cache(maxsize=1)
def get_mask(min_pctid, min_cov):

    # Compute the mask for which genes/genomes pass the filter
    return (data["alignments_pident"] >= min_pctid) & \
           (data["alignments_coverage"] >= min_cov)


# Generate a wide table of alignments based on minimum thresholds
def format_alignments_wide(min_pctid, min_cov, display_value):

    # The options for `display_value` are:
    #   pident
    #   coverage
    #   description
    #   mask (returns a bool for each cell reflecting the filter)
    assert display_value in ['pident', 'coverage', 'description', 'mask']

    # Compute the mask for which genes/genomes pass the filter
    # Using a subfunction allows us to cache the value to help with
    # multiple calls to the format_alignments_wide() function
    mask = get_mask(min_pctid, min_cov)

    # If that is all we need to return
    if display_value == "mask":

        # Return the DataFrame of bools
        return mask

    # Otherwise:
    else:

        # Format the key for the source data
        data_key = f"alignments_{display_value}"

        # Make sure that the key is valid
        assert data_key in list(data.keys())

        # Return the alignments which pass the filter
        return data[data_key].where(mask)


def plot_gig_map(_, selections):
    """Render the gig-map display based on the data and the user's menu selections."""

    # The two options for display are 'heatmap' and 'tnse'
    assert selections["display-type"] in ['heatmap', 'tsne']

    # If the user selected the option to display a heatmap + tree
    if selections["display-type"] == "heatmap":

        # Render that figure
        return plot_gig_map_heatmap(selections)

    # Otherwise
    else:

        assert selections["display-type"] == 'tsne'

        # Render that figure
        return plot_gig_map_tsne(selections)

def get_gene_annot_values(selections):
    """Return a dict with the specified annotation for 'color-genes-by'."""

    # Make sure that the specified value is in the annotation table
    assert selections["color-genes-by"] in data["gene_annotations"].columns.values

    # Make a dict with numeric values
    value_dict = data[
        "gene_annotations"
    ][
        selections["color-genes-by"]
    ].apply(
        lambda v: pd.to_numeric(v, errors="coerce")
    ).dropna(
    ).to_dict()

    # Make sure that there are at least some numeric values
    msg = f"Column {selections['color-genes-by']} contains no numeric values"
    assert len(value_dict) > 0, msg

    return value_dict

def plot_gig_map_tsne(selections):
    """Render the t-SNE map display."""

    # Read the t-SNE coordinates
    tsne = data["tsne"]

    print(selections["color-genes-by"])

    # Genes cannot be colored by genome-specific alignment data
    # If the user has selected another piece of metadata to color by
    if selections["color-genes-by"] not in [None, "pident", "coverage"]:

        # Get the values for each gene as a dict
        value_dict = get_gene_annot_values(selections)

        # Add it to the t-SNE table
        tsne = tsne.assign(
            **{
                selections['color-genes-by']: pd.Series(value_dict)
            }
        )

        # Set the name of the column to use for colors
        color_by_column=selections['color-genes-by']

    else:

        # Set a null value for the color_by_column
        color_by_column = None

    # If a value was selected to label genes by
    if selections["label-genes-by"] in data["gene_annotations"].columns.values:

        # Just add the column to the table
        tsne = tsne.assign(
            **{
                selections["label-genes-by"]: data["gene_annotations"][selections["label-genes-by"]]
            }
        )
    
    print(tsne.head())

    fig = px.scatter(
        data_frame=tsne.reset_index(),
        x='t-SNE 1',
        y='t-SNE 2',
        hover_name='index',
        color=color_by_column,
        hover_data=tsne.columns.values
    )

    # Set up the layout
    fig.update_layout(
        # White background
        paper_bgcolor='white',
        plot_bgcolor='white',
        # Figure title
        title=dict(
            text=selections['plot-title'],
            xanchor="center"
        ),
        # Figure height and width
        height=selections['figure-height'],
        width=selections['figure-width'],
    )

    return fig


def plot_gig_map_heatmap(selections):
    """Render the heatmap + tree display."""

    # Format a wide table with gene alignments
    # If the user wants to display alignment stats
    if selections["color-genes-by"] in ["pident", "coverage"]:

        # Make a table with the alignment stats
        plot_df = format_alignments_wide(
            selections["minimum-pctid"],
            selections["minimum-coverage"],
            selections["color-genes-by"]
        )

    # Otherwise, the user wants to color by gene annotation
    else:

        # Get the values for each gene as a dict
        value_dict = get_gene_annot_values(selections)

        # Start with a table filtered by alignment characteristics, and filled in with True/False
        plot_df = format_alignments_wide(
            selections["minimum-pctid"],
            selections["minimum-coverage"],
            "mask"
        # Now replace any non-null value (for which an alignment is present) with the annotation
        ).replace(
            to_replace={
                gene_name: {
                    True: gene_value,
                    False: None
                }
                for gene_name, gene_value in value_dict.items()
            }
        )

    # Drop any genomes which don't have any alignments which pass the threshold
    plot_df = plot_df.loc[
        plot_df.notnull().any(axis=1)
    ]

    # Make sure that there are at least two genomes with alignments
    assert plot_df.shape[0] > 1, "<=1 genome with alignments passing filter"

    # Make a table with the text descriptions of each alignment
    text_df = format_alignments_wide(
        selections["minimum-pctid"],
        selections["minimum-coverage"],
        "description"
    ).reindex(
        index=plot_df.index.values
    )

    # Create a tree using the set of genomes which contain alignments
    node_positions = make_nj_tree(plot_df.index.values, data['distances'])

    # The figure will render with a dendrogram on the left and a heatmap on the right

    # Set up a base level figure
    fig = go.Figure()

    # Render the tree
    fig.add_trace(
        plot_tree(
            node_positions,
            selections,
            data,
            xaxis="x",  # Primary X axis
            yaxis="y",  # Primary Y axis
        )
    )

    # Render the heatmap
    fig.add_trace(
        plot_heatmap(
            dict(
                values=plot_df,
                text=text_df
            ),
            node_positions,
            selections,
            data,
            xaxis="x2",  # Secondary X axis
            yaxis="y",   # Primary Y axis
        )
    )

    # Set up the labels for the genomes to add to the axis
    genome_labels = list(node_positions.genome_order)

    # If the user elected to label the genomes by something other than their ID
    if selections["label-genomes-by"] != "":

        # Map the labels to the values from the annotation table
        genome_labels = list(map(
            data["genome_annotations"][selections["label-genomes-by"]].get,
            genome_labels
        ))

    # Set up the layout
    fig.update_layout(
        # Set up the primary x-axis (with the tree)
        xaxis=dict(
            title_text="Genome Distance (ANI)",
            domain=[0, selections["tree-width"]],
            range=[
                node_positions.df['x'].max() * -0.01,
                node_positions.df['x'].max() * 1.01,
            ]
        ),
        # Primary y-axis (with the tree)
        yaxis=dict(
            tickmode="array",
            tickvals=list(range(node_positions.df.shape[0])),
            ticktext=genome_labels,
            side="right",
            anchor="x2",
            showticklabels=selections["show-on-right"] == "genome-labels"
        ),
        # Secondary x-axis (with the heatmap),
        xaxis2=dict(
            domain=[selections["tree-width"], 1.0],
        ),
        paper_bgcolor='white',
        plot_bgcolor='white',
        # Figure title
        title=dict(
            text=selections['plot-title'],
            xanchor="center"
        ),
        # Figure height and width
        height=selections['figure-height'],
        width=selections['figure-width'],
    )

    return fig

# Instantiate the MenuDrivenFigure object
mdf = MenuDrivenFigure(
    data=data,
    menus=menus,
    function=plot_gig_map,
    title="Genes in Genomes Map"
)

# Launch the Dash/Flask app
mdf.run_server(
    host='0.0.0.0',
    port=8080,
    debug=True,
)