cd "$(dirname "$0")"
python3 make_jobs.py > jobs.txt
rm -f stops.add.xml stops2.add.xml bg_*.xml corr_*.rou.xml bus_*.rou.xml bus2_*.rou.xml
for s in 1 2 3 4 5; do python3 build_scenario.py $s > /dev/null; done
xargs -P "${WORKERS:-2}" -L 1 sh -c 'env $0 "$@"' < jobs.txt >> log_runs.txt 2>&1
echo DONE >> log_runs.txt
