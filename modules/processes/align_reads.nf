// Join pairs of FASTA files
process join_read_pairs {
    container "${params.container__gigmap}"
    label 'io_limited'
    
    input:
    tuple val(sample_name), path("inputs/")
    
    output:
    tuple val(sample_name), path("${sample_name}${params.reads_suffix}")

    """#!/bin/bash
set -e
cat inputs/* > "${sample_name}${params.reads_suffix}"
    """
}

// Count the number of reads per specimen
process count_reads {
    container "${params.container__pandas}"
    label 'io_limited'
    
    input:
    // Place all input files in an input/ folder, naming with a simple numeric index
    tuple val(sample_name), path("input/input*.fastq.gz")
    
    output:
    path "${sample_name}.num_reads.txt"

    """#!/bin/bash

# Decompress all FASTQ files
# Concatenate them
# Count the number of lines, divided by 4
gunzip -c input/input*.fastq.gz | awk 'NR % 4 == 1' | wc -l > ${sample_name}.num_reads.txt
    """
}

// Align short reads against a gene catalog in amino acid space
process diamond {
    container "${params.container__diamond}"
    label 'mem_medium'
    
    input:
    // Place all input files in an input/ folder, naming with a simple numeric index
    file refdb
    tuple val(sample_name), path("input/input*.fastq.gz")
    
    output:
    tuple val(sample_name), path("${sample_name}.aln.gz")

    shell:
    template "align_reads.sh"

}

// Filter the alignments with the FAMLI algorithm
process famli {
    container "${params.container__famli}"
    label 'mem_medium'
    publishDir "${params.output}/alignments/", mode: "copy", overwrite: true
    
    input:
    tuple val(sample_name), file(input_aln)
    
    output:
    path "${sample_name}.json.gz"

    script:
    template "famli.sh"
}


// Combine the outputs from short read alignment across all specimens
process gather {
    container "${params.container__pandas}"
    label 'io_limited'
    publishDir "${params.output}", mode: "copy", overwrite: true
    
    input:
    path "famli/*"
    path "read_counts/*"
    
    output:
    path "read_alignments.csv.gz"

    """
    gather_alignments.py
    """   
}
