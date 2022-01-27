#!/usr/bin/env python3

import argparse
from collections import defaultdict
import logging
import pandas as pd
from plotly_subplots import PlotlySubplots
import sys
from types import FunctionType
from uuid import uuid4

class FigureArgument:
    """Define an argument used to drive the creation of a figure."""

    def __init__(
        self,
        key:str=None,
        description:str=None,
        type=str,
        default=None,
    ):

        assert isinstance(key, str), "key must be a string"
        assert isinstance(description, str), "description must be a string"

        assert not " " in key, "key cannot contain spaces"

        self.key = key
        self.description = description
        self.type = type
        self.default = default


class FigureElement:
    """Define a component of the overall FigureBuilder."""

    def __init__(
        self,
        id:str=None,
        args:list=None,
        read_f:FunctionType=None,
        plot_f:FunctionType=None,
    ):
        """
        Instantiate a figure element.
        id:     An identifier for the element
        args:   A list of FigureArgument objects;
        read_f: A function which returns a data object,
                based on the values provided for those arguments;
        plot_f: A function which adds to a PlotlySubplot object,
                based on the data object and arguments;
        """
        
        assert isinstance(id, str), "id must be provided as a str"
        assert isinstance(args, list), "args must be provided as a list"
        for arg in args:
            assert isinstance(arg, FigureArgument), "args must be a list of FigureArgument objects"
        assert isinstance(read_f, FunctionType), "read_f must be a function"
        assert isinstance(plot_f, FunctionType), "plot_f must be a function"

        self.id = id
        self.args = args
        self.read_f = read_f
        self.plot_f = plot_f
    

class FigureBuilder:
    """Class to coordinate the construction of a figure from flexible data inputs."""

    def __init__(
        self,
        logging_id:str="figure-builder",
        description:str="Figure description",
        args:list=[],
        read_f:FunctionType=None,
        elements:list=None
    ):

        # Store the logging_id associated with this figure builder
        self.logging_id = logging_id

        # Store the description used for the argument parser
        self.description = description

        msg = "Global arguments (args=) must be a list"
        assert isinstance(args, list), msg
        self.args = args

        msg = "Each argument must be a FigureArgument"
        for arg in self.args:
            assert isinstance(arg, FigureArgument), msg

        msg = "read_f must be a function"
        assert isinstance(read_f, FunctionType)
        self.read_f = read_f

        # Validate and store all of the `elements`
        self.elements = self.validate_elements(elements)

        # Create a self.logger object
        self.create_logger()

    def validate_elements(self, elements):
        """Validate that the input `elements` are unique FigureElements."""

        assert isinstance(elements, list), "`elements` must be a list"
        
        # All of the element `id` string must be unique
        all_ids = set()

        # All of the items in `elements` must be FigureElement
        msg = "Figure elements must be FigureElement objects"
        for element in self.elements:
            assert isinstance(element, FigureElement), msg

            assert element.id not in all_ids, f"Element id '{element.id}' is not unique"
            all_ids.add(element.id)

        return elements

    def create_logger(self):
        """Create a logging instance."""

        # Set the level of the logger to INFO
        logFormatter = logging.Formatter(
            f'%(asctime)s %(levelname)-8s [{self.logging_id}] %(message)s'
        )
        self.logger = logging.getLogger(str(uuid4()))
        self.logger.setLevel(logging.INFO)

        # Write to STDOUT
        consoleHandler = logging.StreamHandler()
        consoleHandler.setFormatter(logFormatter)
        self.logger.addHandler(consoleHandler)

        # Print the description of the figure builder
        self.log(self.description)

        # Print the version of Python being used
        self.log(f"Python version: {sys.version}")
        self.log(sys.version_info)

        # Print the version of Pandas being used
        self.log(f"Pandas version: {pd.__version__}")

    def log(self, msg):
        """Emit a message in the logging stream."""
        
        # By default, all logging message will be INFO
        self.logger.info(msg)

    def parse_args(self):
        """Parse arguments from the command line."""

        # Instantiate the argument parser
        self.parser = argparse.ArgumentParser(
            description=self.description
        )

        # Iterate over each of the global-level arguments
        for arg in self.args:

            # Add this argument to the parser
            self.parser.add_argument(
                f"--{arg.key}",
                type=arg.type,
                default=arg.default,
                help=arg.description
            )

        # Iterate over each of the elements of the figure
        for element in self.elements:

            # Create an argument group
            arg_group = self.parser.add_argument_group(
                element.id,
            )

            # Iterate over each of the arguments for that element
            for arg in element.args:

                # Add this argument to the parser
                arg_group.add_argument(
                    f"--{element.id}-{arg.key}",
                    type=arg.type,
                    default=arg.default,
                    help=arg.description
                )

        # All arguments from the command line will be stored
        # in a nested dict, where the first key is either
        # 'global' or an `element_id`
        self.params = defaultdict(dict)

        # Parse the arguments, iterating over each one
        for kw, val in self.parser.parse_args().__dict__.items():

            self.add_param(kw, val)

        # Log the params
        self.log("Parameters:")
        for param_group, params in self.params.items():
            self.log(f"Group: {param_group}")
            for kw, val in params.items():
                self.log(f"       {kw}: {val}")
        self.log("End of Parameters")

    def add_param(self, kw, val):
        """Add a single argument to either the 'global' or `element_id` namespace."""

        # First iterate over the global arguments
        for arg in self.args:

            # If the keyword matches
            if arg.key.replace("-", "_") == kw:

                # Then add this value to the 'global' namespace
                self.params['global'][kw] = val
                return

        # Next, iterate over each of the elements of the figure
        for element in self.elements:

            # Iterate over each of the arguments for this element
            for arg in element.args:

                # If the keyword matches
                if f"{element.id}_{arg.key.replace('-', '_')}" == kw:

                    # Then add this value to the `element.id` namespace
                    self.params[element.id][arg.key] = val
                    return
        
        # At this point, no match was found
        msg = f"Could not find a match for argument: {kw}"
        raise Exception(msg)

    def read_data(self):
        """Read in data using the `read_f` functions provided."""

        # All data will be stored in a dict
        self.data = dict()

        # First, read in the data for the global namespace
        self.log("Reading in data from the global namespace")
        self.data['global'] = self.read_f(**self.params['global'])

        # Next, iterate over each figure element
        for element in self.elements:

            # Read in the data for each of those elements
            self.log(f"Reading in data for element: {element.id}")
            self.data[element.id] = element.read_f(**self.params[element.id])

    def make_plots(self):
        """Make a plot using the arguments, data, and functions defined."""

        # Instantiate a subplot object
        self.subplots = PlotlySubplots()

        # For each element
        for element in self.elements:

            # Call the plotting function
            element.plot_f(
                self.subplots,
                self.params[element.id],
                self.data[element.id],
                self.params,
                self.data,
            )
