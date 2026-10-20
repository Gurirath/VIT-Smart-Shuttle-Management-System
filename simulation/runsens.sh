cd "$(dirname "$0")"
run_variant() {
  name=$1; shift
  mkdir -p results_sens/$name
  for s in $SEEDS; do for sc in A B_real; do env "$@" python3 run_sim.py $s $sc results_sens/$name >> results_sens/log_$name.txt 2>&1; done; done
}
all() {
  run_variant seek40 SEEK_PROB=0.4
  run_variant seek80 SEEK_PROB=0.8
  run_variant tolhalf WTW_RANGE_S=60,390
  run_variant outage3x OUTAGE_EVERY_S=600
  run_variant demand120 DEMAND_SCALE=1.2
  run_variant demand80 DEMAND_SCALE=0.8
}
mkdir -p results_sens
(SEEDS="1 3"; all) &
(SEEDS="2"; all) &
wait
echo DONE > results_sens/DONE
