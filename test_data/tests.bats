#!/usr/bin/env bats

@test "Download genomes" {
    TOOL=download_genomes
    rm -rf ${TOOL}
    mkdir ${TOOL}
    cd ${TOOL}
    
    # Specify the tool and launcher to use
    wb setup_dataset --tool ${TOOL} --launcher nextflow_docker

    # Specify which table of genomes to download and
    # run the dataset, waiting until it finishes
    wb run_dataset --genome_csv ../Escherichia_virus_T4.csv --wait

    # Print the process error and output to the screen
    cat ._wb/error.txt
    cat ._wb/output.txt
    ls -lahtr

    # Print the logs
    cat ._wb/output.txt
    cat ._wb/error.txt

    # Make sure that the genomes were downloaded
    (( $(ls genomes/*.fna.gz | wc -l) == 8 ))
}

@test "Download genes" {
    TOOL=download_genes
    rm -rf ${TOOL}
    mkdir ${TOOL}
    cd ${TOOL}

    # Specify the tool and launcher to use
    wb setup_dataset --tool ${TOOL} --launcher nextflow_docker
    
    # Specify which table of genomes to download and
    # run the dataset, waiting until it finishes
    wb run_dataset --genome_csv ../Escherichia_virus_T4.csv --wait

    # Print the process error and output to the screen
    cat ._wb/error.txt
    cat ._wb/output.txt
    ls -lahtr

    # Print the logs
    cat ._wb/output.txt
    cat ._wb/error.txt

    # Make sure that the genes were downloaded
    (( $(ls genes/*.faa.gz | wc -l) == 8 ))
}

@test "Deduplicate genes" {
    TOOL=deduplicate_genes
    rm -rf ${TOOL}
    mkdir ${TOOL}
    cd ${TOOL}

    # Specify the tool and launcher to use
    wb setup_dataset --tool ${TOOL} --launcher nextflow_docker
    
    # Specify the folder which contains the set of genes to deduplicate
    wb run_dataset --genes ../download_genes/genes/ --nxf_profile testing --wait

    # Print the process error and output to the screen
    cat ._wb/error.txt
    cat ._wb/output.txt
    cat ._wb/tool/run.sh
    cat ._wb/tool/env
    cat .nextflow.log
    ls -lahtr

    # Print the logs
    cat ._wb/output.txt
    cat ._wb/error.txt

    # Make sure that the genes were deduplicated
    [ -s centroids.faa.gz ]
    [ -s centroids.membership.csv.gz ]
    [ -s centroids.annot.csv.gz ]
}

@test "Align genomes" {
    TOOL=align_genomes
    rm -rf ${TOOL}
    mkdir ${TOOL}
    cd ${TOOL}

    # Specify the tool and launcher to use
    wb setup_dataset --tool ${TOOL} --launcher nextflow_docker

    # Specify the genes and genomes to align
    wb run_dataset \
        --genes ../deduplicate_genes/centroids.faa.gz \
        --genomes ../download_genomes/genomes \
        --nxf_profile testing \
        --wait

    # Print the logs
    cat ._wb/output.txt
    cat ._wb/error.txt

    # Make sure that the outputs were created
    [ -s genomes.aln.csv.gz ]
    [ -s markers.fasta.gz ]
    [ -s gigmap.rdb ]

}

@test "Collect results" {

    TOOL=collect
    rm -rf ${TOOL}
    mkdir ${TOOL}
    cd ${TOOL}

    # Specify the tool and launcher to use
    wb setup_dataset --tool ${TOOL} --launcher nextflow_docker

    # Specify the genes and genomes to align
    wb run_dataset \
        --genomes ../download_genomes/genomes \
        --genome_aln ../align_genomes/genomes.aln.csv.gz \
        --gene_order ../align_genomes/genomes.gene.order.txt.gz \
        --marker_genes ../align_genomes/markers.fasta.gz \
        --nxf_profile testing \
        --wait

    # Print the logs
    cat ._wb/output.txt
    cat ._wb/error.txt

    # Make sure that the outputs were created
    [ -s gigmap.rdb ]

}