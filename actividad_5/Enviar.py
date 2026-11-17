import socket
import sys

from Router import create_packet


ip_final = sys.argv[1]
puerto_final = int(sys.argv[2])
mensaje = sys.argv[3]
ip_envio = sys.argv[4]
puerto_envio = int(sys.argv[5])
ttl = int(sys.argv[6]) if len(sys.argv) > 6 else 64

paquete = create_packet({"ip": ip_final, "port": puerto_final,
                         "ttl": ttl, "message": mensaje})

s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.sendto(paquete, (ip_envio, puerto_envio))
print(f"Enviado {paquete} hacia {(ip_envio, puerto_envio)}")