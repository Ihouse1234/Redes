import random
import socket
import time
from Router import create_packet, fragment_IP_packet

def datagrama(id_, texto):
    return create_packet({"ip": "127.0.0.1", "port": 8885, "ttl": 10, "id": id_,
                          "offset": 0, "flag": 0, "message": texto.encode()})

A = fragment_IP_packet(datagrama(11, "A" * 60 + "-mensaje del ID 11-" + "a" * 40), 50)
B = fragment_IP_packet(datagrama(22, "B" * 50 + "-mensaje del ID 22-" + "b" * 30), 50)
print(f"ID 11: {len(A)} fragmentos, ID 22: {len(B)} fragmentos")

s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
def enviar(frags, etiqueta):
    print("enviando:", etiqueta)
    for f in frags:
        s.sendto(f, ("127.0.0.1", 8885))
        time.sleep(0.05)
    time.sleep(0.3)

enviar(A + B, "ID 11 en orden, luego ID 22 en orden")
enviar(A[::-1] + B[::-1], "ID 11 al reves, luego ID 22 al reves")
mezcla = [A[0], B[2], A[3], B[0], A[1], B[1], A[2]] + B[3:] + A[4:]
enviar(mezcla, "intercalados y desordenados")
random.seed(3)
alea = A + B
random.shuffle(alea)
enviar(alea, "todos mezclados al azar")
