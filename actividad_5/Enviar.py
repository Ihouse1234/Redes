import socket
import sys

from Router import create_packet

# Uso:
#   python3 enviar.py IP_final puerto_final "mensaje" IP_envio puerto_envio
# Ejemplo (mensaje a R3 entrando por R1):
#   python3 enviar.py 127.0.0.1 8883 "hola" 127.0.0.1 8881

ip_final = sys.argv[1]
puerto_final = int(sys.argv[2])
mensaje = sys.argv[3]
ip_envio = sys.argv[4]
puerto_envio = int(sys.argv[5])

paquete = create_packet({"ip": ip_final, "port": puerto_final, "message": mensaje})

s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.sendto(paquete, (ip_envio, puerto_envio))
print(f"Enviado {paquete} hacia {(ip_envio, puerto_envio)}")