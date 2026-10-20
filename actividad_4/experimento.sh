#!/bin/bash
# uso: bash experimento.sh <archivo> <cc|sincc> <repeticiones>
ARCHIVO=$1
CC=$2
N=$3

for i in $(seq 1 $N); do
    PUERTO=$((8000 + RANDOM % 1000))
    timeout 120 python3 Server.py localhost $PUERTO go_back_n > recibido_exp.txt 2>/dev/null &
    sleep 0.5
    SALIDA=$(timeout 120 python3 Client.py localhost $PUERTO go_back_n $CC < $ARCHIVO 2>&1)
    wait
    RES=$(echo "$SALIDA" | grep "\[resultado\]")
    if [ -z "$RES" ]; then
        echo "corrida $i ($CC): FALLO. Ultimas lineas del cliente:"
        echo "$SALIDA" | tail -5
        continue
    fi
    if diff -q $ARCHIVO recibido_exp.txt > /dev/null; then OK="integro"; else OK="DISTINTO"; fi
    echo "corrida $i ($CC): $RES $OK"
done