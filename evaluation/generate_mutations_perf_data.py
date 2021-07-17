import time
import pathlib

import pandas as pd
import numpy as np
import click
import pyvolve
import tskit
import msprime
import cpuinfo


@click.group()
def cli():
    pass


@click.command()
@click.argument("tree_file", type=click.Path())
def benchmark_pyvolve(tree_file):
    click.echo("Benchmarking pyvolve")

    ts = tskit.load(tree_file)
    tree = ts.first()
    # node_labels = {u: str(u) for u in ts.samples()}
    newick = tree.newick()  # node_labels=node_labels)
    # Not entirely sure this is the correct rate, but pyvolve won't tell
    # me how many mutations it has generated, so it's not simple.
    pyvolve_tree = pyvolve.read_tree(tree=newick, scale_tree=1)
    pyvolve_model = pyvolve.Partition(
        models=pyvolve.Model("nucleotide"), size=int(ts.sequence_length)
    )
    print("starting sim")
    sim = pyvolve.Evolver(tree=pyvolve_tree, partitions=pyvolve_model)
    before = time.perf_counter()
    sim(ratefile=None, infofile=None, seqfile=None)
    duration = time.perf_counter() - before
    print("Ran in duration ", duration)
    # print(sim)
    # seqs = sim.get_sequences(anc=True)  # seq-dict is sorted in pre-order


@click.command()
@click.argument("tree_file", type=click.Path())
def benchmark_msprime(tree_file):
    click.echo("Benchmarking msprime")
    ts = tskit.load(tree_file)
    before = time.perf_counter()
    ts = msprime.sim_mutations(ts, rate=1, random_seed=42)
    duration = time.perf_counter() - before
    print("Ran in duration ", duration)
    print("simulated ", ts.num_mutations, "mutations at ", ts.num_sites, "sites")
    ts.dump("tmp.trees")


@click.command()
@click.argument("tree_file", type=click.Path())
def convert_newick(tree_file):
    ts = tskit.load(tree_file)
    tree = ts.first()
    newick = tree.newick()
    print(newick)


def generate_tree(n, L, random_seed=42):
    print(f"Simulate = n {n} L = {L}Mb")
    ts = msprime.sim_ancestry(
        n,
        population_size=10 ** 4,
        ploidy=1,
        sequence_length=int(L * 10 ** 6),
        recombination_rate=1e-8,
        random_seed=random_seed,
    )
    output_dir = pathlib.Path("tmp/mutations")
    if not output_dir.exists():
        output_dir.mkdir(parents=True)
    output_path = output_dir / f"n:{n}_L:{L}.trees"
    ts.dump(output_path)


@click.command()
def generate_trees():
    """
    Generate the tree files used for benchmarking running mutations.
    """
    L = 10
    for n in np.linspace(10, 10 ** 5, 20).astype(int):
        generate_tree(n, L)

    n = 1000
    for L in np.linspace(1, 100, 20):
        generate_tree(n, L)


@click.command()
def benchmark_on_trees():
    """
    Run mutations simulations on all the tree files generated by
    the generate_trees command.
    """
    cpu = cpuinfo.get_cpu_info()
    with open("data/mutations_benchmark_cpu.txt", "w") as f:
        for k, v in cpu.items():
            print(k, "\t", v, file=f)

    data = []
    for path in pathlib.Path("tmp/mutations").glob("*.trees"):
        ts = tskit.load(path)
        for rate in [1e-7, 1e-8, 1e-9]:
            run_time = []
            num_mutations = []
            for _ in range(10):
                before = time.perf_counter()
                mts = msprime.mutate(ts, rate=rate)
                duration = time.perf_counter() - before
                run_time.append(duration)
                num_mutations.append(mts.num_mutations)
            data.append(
                {
                    "n": ts.num_samples,
                    "L": ts.sequence_length,
                    "time": np.mean(run_time),
                    "rate": rate,
                    "num_mutations": np.mean(num_mutations),
                    "num_trees": ts.num_trees,
                    "num_edges": ts.num_edges,
                }
            )
        df = pd.DataFrame(data)
        print(data[-1])
        df.to_csv("data/mutations_perf.csv")


cli.add_command(benchmark_pyvolve)
cli.add_command(benchmark_msprime)
cli.add_command(convert_newick)
cli.add_command(generate_trees)
cli.add_command(benchmark_on_trees)

if __name__ == "__main__":
    cli()