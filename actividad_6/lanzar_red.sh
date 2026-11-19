if [ "$1" == "stop" ]; then pkill -f "Router.py 127.0.0.1" ; exit 0; fi
V=$1; shift
mkdir -p logs; rm -f logs/*.log
for P in "$@"; do
  N=$((P-8880))
  if [ "$P" == "7000" ]; then F=rutas_default.txt; L=logs/default.log
  else F=rutas_R${N}_${V}.txt; L=logs/R${N}.log; fi
  python3 -u Router.py 127.0.0.1 $P $F > $L 2>&1 &
done
sleep 1
