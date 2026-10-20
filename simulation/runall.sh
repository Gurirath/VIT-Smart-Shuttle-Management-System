cd "$(dirname "$0")"
for s in 1 3 5; do for sc in A B_real B_oracle; do python3 run_sim.py $s $sc results >> log_a.txt 2>&1; done; done &
for s in 2 4; do for sc in A B_real B_oracle; do python3 run_sim.py $s $sc results >> log_b.txt 2>&1; done; done &
wait
echo DONE >> log_a.txt
