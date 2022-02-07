#!/usr/bin/env python3

import gzip
from itertools import count
import json
import logging
import os
import pandas as pd

def gather_from_folder(input_folder, suffix, read_f):
    """Read in a set of files from a folder and return a dict."""

    # Set up a dict
    output = dict()

    # Iterate over every file in the input folder
    for fp in os.listdir(input_folder):

        # The file must end with the specified suffix
        if not fp.endswith(suffix):
            continue

        # Parse the specimen name from the file path
        specimen = fp[:-len(suffix)]

        # Read in the file using the function
        logging.info(f"Reading in {input_folder}/{fp}")
        output[specimen] = read_f(os.path.join(input_folder, fp))

    logging.info(f"Read in data for {len(output):,} specimens")
    return output


def gather_famli(input_folder="famli", suffix=".json.gz"):
    """Read in the FAMLI results from each specimen as a dict."""

    return gather_from_folder(
        input_folder,
        suffix,
        read_famli
    )

def read_famli(fp):
    """Read a single FAMLI output file."""

    with gzip.open(fp, 'rt') as handle:
        df = pd.DataFrame(
            json.load(handle)
        )
    
    logging.info(f"Read in alignments to {df.shape[0]:,} genes")
    return df


def gather_counts(input_folder="read_counts", suffix=".num_reads.txt"):

    return gather_from_folder(
        input_folder,
        suffix,
        lambda f: int(open(f, 'r').readline().rstrip("\n"))
    )


def gather_alignments():
    """Collect alignment results across a collection of metagenomes."""

    # Read in all of the alignment information as a dict of FAMLI results
    famli_data = gather_famli()

    # Read in the total number of reads per specimen as a dict
    count_data = gather_counts()

    # Make sure that we have read counts for every set of alignments
    for specimen in famli_data:
        assert specimen in count_data, f"Did not find read counts for specimen '{specimen}'"

    # Concatenate all of the data
    df = pd.concat(
        [
            specimen_famli.assign(
                specimen=specimen,
                tot_reads=count_data[specimen]
            )
            for specimen, specimen_famli in famli_data.items()
        ]
    )

    # Write it out as a CSV
    df.to_csv("alignments.csv.gz", index=None)

if __name__ == "__main__":

    gather_alignments()