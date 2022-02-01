from cartesian_tree import make_nj_tree
from figure_builder import FigureBuilder, FigureElement, FigureArgument
import gzip
import numpy as np
import os
import pandas as pd
import plotly.graph_objects as go
from scipy.cluster import hierarchy


class GigMapFigure(FigureBuilder):

    def __init__(self):

        super().__init__(
            # Short description used for the argument parser
            description="Render a display showing the distribution of annotated genes across microbial genomes",
            # Short ID used to label logs
            logging_id="gig-map-render",
            # Global arguments
            args=[
                FigureArgument(
                    key="output-prefix",
                    description="Prefix for output file (default: gigmap-render)",
                    default="gigmap-render"
                ),
                FigureArgument(
                    key="output-folder",
                    description="Folder for output file (default: ./)",
                    default="./"
                ),
            ],
            # List of FigureElement objects
            elements = [
                # Genome annotations
                GenomeAnnotations(),
                # Gene annotations
                GeneAnnotations(),
                # Dendrogram showing the relatedness of genomes
                GenomeTree(),
                # Heatmap showing the occurrance of genes across genomes
                GeneGenomeHeatmap(),
                # Colorbar annotating the GeneGenomeHeatmap
                GeneGenomeColorbar()
            ]
        )

    def read_f(
        self,
        fb,  # FigureBuilder instance
        output_prefix=None,
        output_folder=None
    ):
        """Read in the data for gig-map in the global namespace."""

        self.output_prefix = output_prefix
        self.output_folder = output_folder

    def plot_f(self, fb):
        """Apply global plot configuration after all of the other params are set."""

        # Set the global layout elements
        fb.subplots.fig.update_layout(
            paper_bgcolor='white',
            plot_bgcolor='white'
        )


class HeatmapElement(FigureElement):

    def __init__(
        self,
        id=None,
        # Name of horizontal axis
        x_axis=None,
        # Column in CSV for horizontal axis
        x_col=None,
        # Name of vertial axis
        y_axis=None,
        # Column in CSV for vertical axis
        y_col=None,
        # Column in CSV for values
        val_col=None,
        # Value to be added for missing values
        fill_value=0,
        # Relative horizontal position of panel within larger figure
        x_index=None,
        # Relative vertial position of panel within larger figure
        y_index=None,
    ):

        # Attach the layout of this heatmap
        assert x_axis is not None, "Must provide x_axis="
        self.x_axis = x_axis
        assert x_col is not None, "Must provide x_col="
        self.x_col = x_col
        assert y_axis is not None, "Must provide y_axis="
        self.y_axis = y_axis
        assert y_col is not None, "Must provide y_col="
        self.y_col = y_col
        assert val_col is not None, "Must provide val_col="
        self.val_col = val_col
        assert fill_value is not None, "Must provide fill_value="
        self.fill_value = fill_value
        assert x_index is not None, "Must provide x_index="
        self.x_index = x_index
        assert y_index is not None, "Must provide y_index="
        self.y_index = y_index

        # Instantiate the base FigureElement object
        super().__init__(
            id=id,
            args=[
                FigureArgument(
                    key="csv",
                    description=f"File containing {x_axis}-{y_axis} data"
                ),
                FigureArgument(
                    key=f"{x_axis}_col",
                    default=x_col,
                    description=f"Column in CSV containing {x_axis} data (default: {x_col}"
                ),
                FigureArgument(
                    key=f"{y_axis}_col",
                    default=y_col,
                    description=f"Column in CSV containing {y_axis} data (default: {y_col}"
                ),
                FigureArgument(
                    key="val_col",
                    default=val_col,
                    description="Column in CSV used to populate values"
                ),
                FigureArgument(
                    key="colorscale",
                    default="blues",
                    description="Color scale used for values in heatmap"
                ),
            ]
        )

    def read_f(
        self,
        # FigureBuilder instance
        fb,
        # Path to CSV containing data to plot
        csv=None,
        # All other keyword arguments
        **kwargs
    ):
        """Read in data needed for the heatmap."""

        # If the user did not provide a genome heatmap
        if csv is None:

            fb.log(f"User did not provide --{self.id}-csv, omitting display")

            # Disable this display
            self.disable()

        # If a CSV was provided
        else:

            # Read in the table of alignments
            fb.log(f"Reading in {csv}")
            df_long = pd.read_csv(csv)

            # Get the column names to use for the x, y, and values
            x_col = kwargs[f"{self.x_axis}_col"]
            y_col = kwargs[f"{self.y_axis}_col"]
            val_col = kwargs["val_col"]

            # Attach the colorscale indicated by the user
            self.colorscale = kwargs["colorscale"]

            # Make sure that the file contains these columns
            assert x_col in df_long.columns.values, f"{csv} does not contain column {x_col}"
            assert y_col in df_long.columns.values, f"{csv} does not contain column {y_col}"
            assert val_col in df_long.columns.values, f"{csv} does not contain column {val_col}"

            # Record the minimum and maximum values
            self.min_val = df_long[val_col].min()
            fb.log(f"Minimum value: {self.min_val}")
            self.max_val = df_long[val_col].max()
            fb.log(f"Maximum value: {self.max_val}")

            # Format a wide table
            fb.log(f"Pivoting to wide format")
            # Attach the table to this object
            self.df_wide = df_long.pivot(
                index=y_col,
                columns=x_col,
                values=val_col
            ).fillna(
                self.fill_value
            )

            # If the x_axis has not already been fixed
            if not fb.axis(self.x_axis).is_fixed:

                # Set the order based on similarity of values
                fb.axis(self.x_axis).set_order(
                    order_by_linkage(self.df_wide.T)
                )

            # If the y_axis has not already been fixed
            if not fb.axis(self.y_axis).is_fixed:

                # Set the order based on similarity of values
                fb.axis(self.y_axis).set_order(
                    order_by_linkage(self.df_wide)
                )

    def plot_f(self, fb):
        """Plot the heatmap."""

        # Order the rows and columns based on the linked axes
        self.df_wide = self.df_wide.reindex(
            columns=fb.axis(self.x_axis).order(),
            index=fb.axis(self.y_axis).order()
        )

        # Rename the axes
        self.df_wide = self.df_wide.rename(
            columns=fb.axis(self.x_axis).label_dict(),
            index=fb.axis(self.y_axis).label_dict()
        )

        # Special-case the 'blues' colorscale
        if self.colorscale == 'blues':

            # Set the bottom of the colorscale to be below the range presented
            # so that the lowest value is halfway through the colorscale
            self.zmin = self.min_val - (self.max_val - self.min_val)

        # Otherwise
        else:

            # Set the bottom of the colorscale as the lowest value
            self.zmin = self.min_val

        # Define the position at which this panel will be rendered
        fb.log(f"Adding subplot for {self.id} (x={self.x_index}, y={self.y_index})")
        fb.subplots.add(
            # ID for the subplot
            id=self.id,
            # Ordinal position on the horizontal axis
            x_index=self.x_index,
            # Ordinal position on the vertial axis
            y_index=self.y_index,
            # Share the x-coordinates with all other subplots in this column
            share_x=True,
            # Share the y-coordinates with all other subplots in this row
            share_y=True,
        )
        
        # Add the trace for the plot
        fb.log(f"Plotting heatmap for {self.id}")
        fb.subplots.plot(
            id=self.id,
            trace=go.Heatmap(
                x=self.df_wide.columns.values,
                z=self.df_wide.values,
                zmin=self.zmin,
                zmax=self.max_val,
                xaxis=fb.subplots.get_axis_label(self.id, ax="x"),
                yaxis=fb.subplots.get_axis_label(self.id, ax="y"),
                colorscale=self.colorscale,
                showscale=False
            )
        )

        # Format the axes for this plot
        fb.log(f"Formatting axes for {self.id}")
        fb.subplots.format_axis(
            id=self.id,
            ax="y",
            params=dict(
                tickmode="array",
                tickvals=list(range(fb.axis("genome").length())),
                ticktext=fb.axis("genome").labels(),
                showticklabels=True,
                automargin=True,
            )
        )

        # Make sure that the labels for the x axis are on the bottom
        fb.subplots.anchor_xaxis(self.x_index, side="bottom")

        # Make sure that the labels for the y axis are on the right
        fb.subplots.anchor_yaxis(self.y_index, side="right")


class GeneGenomeHeatmap(HeatmapElement):

    def __init__(self):

        super().__init__(
            id="genomeHeatmap",
            x_axis="gene",
            x_col="sseqid",
            y_axis="genome",
            y_col="genome",
            val_col="pident",
            fill_value=0,
            x_index=1,
            y_index=0
        )


class HeatmapColorbarElement(FigureElement):
    """Plot a colorbar annotating values for a heatmap."""

    def __init__(
        self,
        id=None,
        # Identifier for the associated heatmap
        heatmap_id=None,
        # Relative horizontal position of panel within larger figure
        x_index=None,
        # Relative vertial position of panel within larger figure
        y_index=None,
        # Label to display on colorbar
        label=None,
    ):

        # Attach the layout of this heatmap
        assert heatmap_id is not None, "Must provide heatmap_id="
        self.heatmap_id = heatmap_id
        assert x_index is not None, "Must provide x_index="
        self.x_index = x_index
        assert y_index is not None, "Must provide y_index="
        self.y_index = y_index
        assert label is not None, "Must provide label="
        self.label = label

        # Instantiate the base FigureElement object
        super().__init__(
            id=id,
            args=[]
        )

    def read_f(
        self,
        # FigureBuilder instance
        fb
    ):
        """No additional data is needed for the colorbar."""

        # Make a dict of elements defined in the figure
        element_dict = {
            element.id: element
            for element in fb.elements
        }

        # If there is no heatmap
        if element_dict.get(self.heatmap_id) is None:

            fb.log(f"No heatmap element found ('{self.heatmap_id}'), disabling colorbar")
            
            # Disable this element
            self.disable()

        # If the heatmap is not enabled
        if element_dict[self.heatmap_id].enabled is False:

            fb.log(f"Heatmap element is disabled ('{self.heatmap_id}'), disabling colorbar")

            # Disable this element
            self.disable()

        # Attach the associated heatmap element to this object
        self.heatmap_elem = element_dict[self.heatmap_id]

    def plot_f(self, fb):
        """Plot the colorbar to accompany the heatmap."""

        # Get the min/max values from the associated heatmap
        min_val = self.heatmap_elem.min_val
        max_val = self.heatmap_elem.max_val
        colorscale = self.heatmap_elem.colorscale
        zmin = self.heatmap_elem.zmin

        value_list = [
            v
            for v in np.linspace(
                min_val, max_val, num=100
            )
        ]

        # Define the position at which this panel will be rendered
        fb.log(f"Adding subplot for {self.id} (x={self.x_index}, y={self.y_index})")
        fb.subplots.add(
            # ID for the subplot
            id=self.id,
            # Ordinal position on the horizontal axis
            x_index=self.x_index,
            # Ordinal position on the vertial axis
            y_index=self.y_index,
            # Make this subplot smaller than the others
            height=0.05,
            # Add padding around the panel
            padding=0.05
        )
        
        # Add the trace for the plot
        fb.log(f"Plotting colorbar for {self.id}, paired with {self.heatmap_id}")
        fb.subplots.plot(
            id=self.id,
            trace=go.Heatmap(
                y=[self.label],
                x=value_list,
                z=[value_list],
                zmin=zmin,
                zmax=max_val,
                colorscale=colorscale,
                showscale=False,
                hovertemplate="%{z}<extra></extra>",
            )

        )

        # Format the axes for this plot
        fb.log(f"Formatting axes for {self.id}")
        fb.subplots.format_axis(
            id=self.id,
            ax="y",
            params=dict(
                showticklabels=True,
                automargin=True,
            )
        )

        # Make sure that the labels for the y axis are on the right
        fb.subplots.anchor_yaxis(self.y_index, side="right")

        # Make sure that the labels for the x axis are on the bottom
        fb.subplots.anchor_xaxis(self.x_index, side="bottom")


class GeneGenomeColorbar(HeatmapColorbarElement):

    def __init__(self):

        super().__init__(
            id="genomeColorbar",
            heatmap_id="genomeHeatmap",
            x_index=2,
            y_index=-1,
            label="Percent Identity"
        )


class GenomeTree(FigureElement):

    def __init__(
        self,
        # Ordinal position on the horizontal axis
        x_index=0,
        # Ordinal position on the vertial axis
        y_index=0
    ):

        super().__init__(
            # ID for the element
            id="genomeTree",
            # Arguments which need to be provided by the user
            args=[
                FigureArgument(
                    key="distmat",
                    description="Distance matrix used to generate genome dendrogram (optional)"
                )
            ]
        )

        self.x_index = x_index
        self.y_index = y_index

    def read_f(
        self,
        fb,  # FigureBuilder instance
        distmat=None,
        **kwargs
    ):
        """Read in data needed for the genome tree."""

        # If the user did not provide a distmat file path
        if distmat is None:

            # Disable this element
            fb.log("No --distmat provide, skipping genome tree")
            self.disable()
        
        # If a filepath was provided
        else:

            # Read in the distance matrix
            fb.log(f"Reading {distmat}")
            dm = pd.read_csv(distmat, index_col=0)

            # If a genome annotation file was provided, then the 'genome'
            # axis will contain the set of genomes which can be found in
            # the annotation table in the 'genome_id' columns

            if fb.axis('genome').exists:

                # Get the genomes which overlap between that list
                # and this distance matrix
                genomes = list(
                    set(dm.index.values) & fb.axis('genome').member_set()
                )

                fb.log(f"Genomes with annotations and distances: {len(genomes):,}")

                # Subset the distance matrix to this set of genomes
                dm = dm.reindex(
                    index=genomes,
                    columns=genomes
                )

            # Build a neighbor-joining tree from this table of distances
            self.node_positions = make_nj_tree(dm.index.values, dm)

            # Use the order of genomes in the tree to override all others
            fb.axis("genome").set_order(
                self.node_positions.genome_order
            )

            # Fix the order
            fb.axis("genome").is_fixed = True

    def plot_f(self, fb):
        """Plot a genome tree on the FigureBuilder."""

        # Define the position at which this panel will be rendered
        fb.log(f"Adding subplot for {self.id} (x={self.x_index}, y={self.y_index})")
        fb.subplots.add(
            # ID for the subplot
            id=self.id,
            # Ordinal position on the horizontal axis
            x_index=self.x_index,
            # Ordinal position on the vertial axis
            y_index=self.y_index,
            # Share the y-coordinates with all other subplots
            share_y=True
        )
        
        # Make an object to map the neighbor joining tree on a cartesian plot
        fb.log(f"Formatting layout for {self.id}")

        # Add the traces to the plot

        # Scatterplot for the nodes
        fb.log(f"Plotting nodes for {self.id}")
        fb.subplots.plot(
            id=self.id,
            trace=go.Scattergl(
                name="Neighbor Joining Tree",
                showlegend=False,
                mode="lines",
                x=self.node_positions.x_coords(),
                y=self.node_positions.y_coords(),
                text=self.node_positions.text(),
                hoverinfo="text",
            )
        )

        # Also show a set of dotted lines extending each tip
        fb.log(f"Plotting lines for {self.id}")
        fb.subplots.plot(
            id=self.id,
            trace=go.Scattergl(
                showlegend=False,
                mode="lines",
                x=self.node_positions.extension_x_coords(),
                y=self.node_positions.extension_y_coords(),
                hoverinfo="skip",
                line=dict(
                    color="black",
                    dash="dot",
                    width=1,
                )
            )
        )

        # Format the axes for this plot
        fb.log(f"Formatting axes for {self.id}")
        fb.subplots.format_axis(
            id=self.id,
            ax="x",
            params=dict(
                range=[
                    self.node_positions.df['x'].max() * -0.025,
                    self.node_positions.df['x'].max() * 1.025,
                ]
            )
        )

        fb.subplots.format_axis(
            id=self.id,
            ax="y",
            params=dict(
                tickmode="array",
                tickvals=list(range(fb.axis("genome").length())),
                ticktext=fb.axis("genome").labels(),
                showticklabels=True,
                automargin=True,
            )
        )

        # Make sure that the labels for the y axis are always on the
        # rightmost panel
        fb.subplots.anchor_yaxis(self.y_index, side="right")

        fb.log(f"Done plotting {self.id}")


class AxisAnnot(FigureElement):

    def __init__(
        self,
        id=None,
        # Label given for the entities which are being annotated (e.g. 'gene', 'genome')
        axis_label=None,
        # The axis is oriented either vertically or horizontally
        orient=None,
        # Set the index position along that axis
        index_pos=None,
        # Default column in the CSV which contains IDs
        id_col=None
    ):

        # Attach arguments to this object
        assert axis_label is not None, "Must provide axis_label="
        self.axis_label = axis_label
        assert orient is not None, "Must provide orient="
        self.orient = orient
        assert index_pos is not None, "Must provide index_pos="
        self.index_pos = index_pos
        assert id_col is not None, "Must provide id_col="
        self.id_col = id_col

        # Instantiate the base FigureElement object
        super().__init__(
            id=id,
            args=[
                FigureArgument(
                    key="csv",
                    description=f"File containing {axis_label} annotations (CSV)"
                ),
                FigureArgument(
                    key=f"index-col",
                    description=f"Column from the CSV identifying each {axis_label}",
                    default=f"{axis_label}_id"
                ),
                FigureArgument(
                    key=f"label-col",
                    description=f"Column from the CSV used for labeling"
                ),
                FigureArgument(
                    key=f"max-label-len",
                    description=f"Maximum number of characters allowed for {axis_label} labels (default: 60)",
                    type=int,
                    default=60
                ),
                FigureArgument(
                    key=f"order",
                    description=f"Text file containing ordered list of {axis_label} names (no header)"
                )
            ]
        )

    def read_f(
        self,
        fb,
        csv=None,
        index_col=None,
        label_col=None,
        max_label_len=None,
        order=None
    ):
        """Generic function for reading in a table of annotations."""
        
        # If the user did not provide an annotation filepath
        if csv is None:

            # If the user supplied an argument indicating a column to
            # use for labeling
            if label_col is not None:

                # Warn the user that the setting cannot be used
                fb.log(f"Warning: --{self.id}-label-col was set to '{label_col}', but no --{self.id}-csv was provided")

            # Disable the plot
            self.disable()

        # If the user did provide a path
        else:
            fb.log(f"Reading {csv}")

            # Make sure that the path exists
            assert os.path.exists(csv), f"Cannot find file '{csv}'"

            # Read in the table and save it as an annotations table
            df = pd.read_csv(csv)

            # The CSV must contain a column with the header `index_col`
            msg = f"Column '{index_col}' not found in header for {csv}"
            assert index_col in df.columns.values, msg

            # Set the index of the table
            df.set_index(index_col, inplace=True)

            # If the user supplied an argument indicating a column to
            # use for labeling
            if label_col is not None:

                # That column must be present in the CSV header
                msg = f"Column '{label_col}' not found in header for {csv}"
                assert label_col in df.columns.values, msg

            # Otherwise, if no labels were provided
            else:

                # Set up a dummy _labels column
                df = df.assign(
                    **{
                        "_labels": df.index.values
                    }
                )
                label_col = "_labels"

            # If a file was provided with the intended order
            if order is not None:

                # Read in the lines from the file
                index_order = read_lines(fb, order)

                # Every index value should be in the annotation table
                for index_val in index_order:

                    msg = f"Value '{index_val}' not found in column '{label_col}' in '{csv}'"
                    assert index_val in df.index.values, msg

                # Reorder the annotation table
                df = df.reindex(index=index_order)

            # Set the axis labels using the values in this column
            fb.axis(self.axis_label).set(
                df[label_col].apply(
                    # Trim the labels to a maximum length
                    lambda s: s[:max_label_len]
                )
            )

            # If the order was provided
            if order is not None:

                # Fix the order of the axis
                fb.axis(self.axis_label).is_fixed = True

            fb.log(f"Read in {df.shape[0]:,} {self.axis_label} annotations")

    def plot_f(self, fb):
        pass


class GeneAnnotations(AxisAnnot):

    def __init__(self):

        super().__init__(
            id="geneAnnot",
            axis_label="gene",
            orient="h",
            index_pos=-1,
            id_col="combined_name"
        )


class GenomeAnnotations(AxisAnnot):

    def __init__(self):

        super().__init__(
            id="genomeAnnot",
            axis_label="genome",
            orient="v",
            index_pos=2,
            id_col="Formatted Name"
        )


def read_lines(fb, fp):
    """Read in a list of lines from a file"""

    msg = f"File not found: '{fp}'"
    assert os.path.exists(fp), msg

    fb.log(f"Reading in {fp}")

    if fp.endswith(".gz"):
        open_f = gzip.open
    else:
        open_f = open

    with open_f(fp, 'rt') as handle:
        lines = [
            line.rstrip("\n")
            for line in handle
        ]

    msg = f"No lines found in {fp}"
    assert len(lines) > 0, msg

    fb.log(f"Read in {len(lines):,} lines from {fp}")

    return lines


def apply_genome_labels(fig):
    """
    Based on the user input, format the labels which will be used for the genomes.
    This function will update the contents of fig.data['global']['genome_labels']
    """

    # Get a dict mapping genome names to formatted labels
    label_genomes_dict = get_genome_label_map(fig)

    # Apply the map to `genome_order`, write to `genome_labels`
    fig.data['global']['genome_labels'] = list(map(
        lambda l: label_genomes_dict.get(l, l),
        fig.data['global']['genome_order']
    ))


def get_genome_label_map(fig):
    """Return a dict which will map genome names to genome labels."""

    # If the user has not elected to rename the genomes in the plot
    if fig.params['global']['label_genomes_by'] is None:

        # Then return an empty dict
        return dict()

    # Otherwise, if the user has elected to rename the genomes in the plot
    else:

        # Reference the name of the column being used to label
        label_col = fig.params['global']['label_genomes_by']
        fig.log(f"Renaming genomes by {label_col}")

        # Reference the CSV used to annotate genomes
        genome_annotations = fig.data["global"]["genome_annotations"]

        # A genome annotation table must have been provided
        msg = "Must provide --genome-annotations with --label-genomes-by"
        assert genome_annotations is not None, msg

        # The DataFrame must contain a column which matches the name
        msg = f"Cannot find a columns named {label_col} in {fig.params['genome-annotations']}"
        assert label_col in genome_annotations.columns.values, msg

        # Replace the values in the 'name' column of the DataFrame used for plotting
        label_genomes_dict = genome_annotations[label_col].to_dict()

        # Truncate the labels to `max_genome_label_len` and return the dict
        return {
            k: v[:fig.params["global"]["max_genome_label_len"]]
            for k, v in label_genomes_dict.items()
        }


def order_by_linkage(df, method="ward", metric="euclidean", logger=None):
    """Return the order of rows based on linkage clustering"""

    if logger is not None:
        logger.info(f"Ordering table by {method} linkage and {metric} distances")

    # Perform linkage clustering
    L = hierarchy.linkage(
        df,
        method=method,
        metric=metric,
        optimal_ordering=True
    )

    # Return the order of index labels yielded by that clustering approach
    return [
        df.index.values[i]
        for i in hierarchy.leaves_list(L)
    ]