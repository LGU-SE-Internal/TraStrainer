# TraStrainer

```
./main.py sample single trastrainer rcabench ts0-mysql-container-kill-9t6n24
./main.py sample single shifter rcabench ts0-mysql-container-kill-9t6n24

python ./main.py sample batch -s trastrainer -s trastrainer_no_metrics -s sifter -s sieve -s wt -d rcabench_sampler_filtered --rate 0.001 --rate 0.005 --rate 0.01 --rate 0.05 --rate 0.1 --mode online --clear --no-skip-finished
```