import socket
import sys

from Router import create_packet

ip_final, puerto_final, ttl = sys.argv[1].split(";")
router_inicial = (sys.argv[2], int(sys.argv[3]))
entrada = open(sys.argv[4]) if len(sys.argv) > 4 else sys.stdin

s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
for linea in entrada:
    linea = linea.rstrip("\n")
    paquete = create_packet({"ip": ip_final, "port": int(puerto_final),
                             "ttl": int(ttl), "message": linea})
    s.sendto(paquete, router_inicial)
