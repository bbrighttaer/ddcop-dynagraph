dcop_alg="cocoa"
graph_alg="ddfs"
rnd_seed=0
num_agents=30
num_remove=5
num_targets=15
grid_size=5
scenarios_file="scenarios.pkl"

python src/factory.py -p max -s $rnd_seed -a $dcop_alg -g $graph_alg mst-simulation --num_agents $num_agents --num_remove $num_remove --grid_size $grid_size --num_targets $num_targets -f $scenarios_file