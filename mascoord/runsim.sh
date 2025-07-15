#!/bin/bash

# List of dcop_alg methods
dcop_algs=("dpop" "cocoa")

# List of graph_alg methods
graph_algs=("dbfs" "ddfs" "digca")

# Number of seeds (repeat each experiment for these seeds)
NUM_SEEDS=5

# Fixed parameters
num_agents=30
num_remove=5
num_targets=15
grid_size=5
scenarios_file="scenarios_a30_r5.pkl"

# Record start time
start_time=$(date +%s)

# Loop through each combination of dcop_alg and graph_alg
for dcop_alg in "${dcop_algs[@]}"; do
  for graph_alg in "${graph_algs[@]}"; do
    # repeat the experiment with different random seeds
    for ((seed=0; seed<NUM_SEEDS; seed++)); do
      echo "---------------------------------------------------------------------------"
      echo "Running experiment: dcop_alg=$dcop_alg | graph_alg=$graph_alg | seed=$seed"
      echo "---------------------------------------------------------------------------"

      echo "Running with dcop_alg=$dcop_alg, graph_alg=$graph_alg, seed=$seed"
      python src/factory.py -p max -s "$seed" -a "$dcop_alg" -g "$graph_alg" mst-simulation \
        --num_agents "$num_agents" --num_remove "$num_remove" --grid_size "$grid_size" \
        --num_targets "$num_targets" -f "$scenarios_file"
    done
  done
done

# Record end time
end_time=$(date +%s)

# Calculate total time in minutes
total_time_min=$(( (end_time - start_time) / 60 ))

echo "============================================================"
echo "All experiments completed. Total elapsed time: $total_time_min minutes."
echo "============================================================"
