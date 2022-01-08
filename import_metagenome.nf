#!/usr/bin/env nextflow

// Using DSL-2
nextflow.enable.dsl=2

// Set default parameters
params.help = false
params.rdb = false
params.geneshot_abund = false
params.geneshot_hdf = false
params.output_prefix = 'imported_metagenome'
params.output_folder = 'output'

// Software containers
params.container__pandas = "quay.io/fhcrc-microbiome/python-pandas:4a6179f"

// Function which prints help message text
def helpMessage() {
    log.info"""
    Usage:

    nextflow run FredHutch/gig-map/import_metagenome.nf <ARGUMENTS>

    Reads in a collection of metagenome alignments produced by the geneshot analysis tool and formats them
    as a single CSV which contains only the set of genes which are present in an existing gig-map alignment.

    The practical use of this workflow is to create a subset of metagenome abundances which can be compared
    against the presence of each gene in a collection of isolates.

    Required Arguments:
      --gigmap_csv          File contining alignments generated by gig-map (named {output_prefix}.csv.gz)
      --geneshot_abund      Folder containing the complete set of abundances generated by geneshot in
                            JSON format -- almost always within the abund/details/ geneshot output folder
      --output_prefix       Name of the HTML output (default: ${params.output_prefix})
      --output_folder       Folder for output file (default: ${params.output_folder})

    Optional Arguments:
      --geneshot_hdf        Geneshot output summary file named *.results.hdf5

    """.stripIndent()
}

process get_gene_list {
    container "${params.container__pandas}"
    label "io_limited"

    input:
    path aln_csv

    output:
    path "${aln_csv.name}.genes.txt.gz"

    script:
    """#!/usr/bin/env python3

import pandas as pd

print("Reading in ${aln_csv}")

# Only read in the first column
df = pd.read_csv("${aln_csv}", usecols=0)

msg = "The first column should be named qseqid"
assert df.columns.values[0] == 'qseqid', msg

print("Read in %d lines" % df.shape[0])

# Drop all duplicates
df = df.drop_duplicates()

print("Writing out %d unique lines" % df.shape[0])

# Write to ${aln_csv.name}.genes.txt.gz
df.to_csv("${aln_csv.name}.genes.txt.gz", index=None)
print("Wrote out to ${aln_csv.name}.genes.txt")

    """
}

process subset_abund {
    container "${params.container__pandas}"
    label "io_limited"

    input:
    path abund_json
    each path(gene_list)

    output:
    path "${abund_json.name}.subset.csv.gz", optional: true

    script:
    """#!/usr/bin/env python3

import gzip
import json
import pandas as pd

# Read in the list of genes
print("Reading in ${gene_list}")
gene_list = pd.read_csv("${gene_list}")
print("Read in %d gene names" % gene_list.shape[0])

msg = "The first column should be named qseqid"
assert gene_list.columns.values[0] == 'qseqid', msg

# Convert to a set
gene_set = set(gene_list.qseqid.tolist())

# Make sure that all values were unique
assert gene_list.shape[0] == len(gene_set), "Gene list was not unique"

print("Reading in ${abund_json}")
with gzip.open("${abund_json}", rt) as handle:
    abund = json.load(handle)

msg = "Abundance data should be formatted as a list"
assert isinstance(abund, list), msg

print("Read in %d aligned genes" % len(abund))

# Subset to just those genes found in the list
abund = [
    a
    for a in abund
    if a['id'] in gene_set
]

print("After filtering, %d abundances remain" % len(abund))

# Format as a DataFrame
abund = pd.DataFrame(abund)

fp_out = "${abund_json.name}.subset.csv.gz"

print("Writing out to %s" % fp_out)

abund.to_csv(fp_out, index=None)
print("Done")

    """
}

workflow {

    // Show help message if the user specifies the --help flag at runtime
    if (params.help){
        // Invoke the function above which prints the help message
        helpMessage()
        // Exit out and do not run anything else
        exit 0
    }

    // If an alignment CSV file is not provided
    if (!params.gigmap_csv){
        // Invoke the function above which prints the help message
        helpMessage()
        // Add a more specific help message
        log.info"""

        ERROR: Must provide the --gigmap_csv flag

        """
        // Exit out and do not run anything else
        exit 0
    }

    // If a geneshot output folder is not provided
    if (!params.geneshot_abund){
        // Invoke the function above which prints the help message
        helpMessage()
        // Add a more specific help message
        log.info"""

        ERROR: Must provide the --geneshot_abund flag

        """
        // Exit out and do not run anything else
        exit 0
    }

    // Get the list of genes which were aligned to any gene in this collection
    get_gene_list(
        Channel
            .fromPath(
                "${params.gigmap_csv}"
            )
    )

    // Subset each individual abundance file to just that gene of interest
    subset_abund(
        Channel
            .fromPath(
                "${params.geneshot_abund}**json.gz"
            )
    )

    // Merge each of those abundance into a single CSV

}