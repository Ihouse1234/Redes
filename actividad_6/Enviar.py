import socket
import sys

from Router import create_packet

ip_final = sys.argv[1]
puerto_final = int(sys.argv[2])
mensaje = sys.argv[3]
ip_envio = sys.argv[4]
puerto_envio = int(sys.argv[5])
ttl = int(sys.argv[6]) if len(sys.argv) > 6 else 64
id_ = int(sys.argv[7]) if len(sys.argv) > 7 else 1

if mensaje.startswith("@"):
    mensaje = open(mensaje[1:], "rb").read()
else:
    mensaje = mensaje.encode()

paquete = create_packet({"ip": ip_final, "port": puerto_final, "ttl": ttl,
                         "id": id_, "offset": 0, "flag": 0, "message": mensaje})
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.sendto(paquete, (ip_envio, puerto_envio))
print(f"Enviado paquete de {len(paquete)} bytes (header 20 + mensaje {len(mensaje)}) "
      f"hacia {(ip_envio, puerto_envio)}")