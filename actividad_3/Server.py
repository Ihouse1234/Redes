import sys
from SocketTCP import SocketTCP

BUFF_SIZE = 2048        # buffer del SocketTCP

def main():
    if len(sys.argv) > 1:
        host = sys.argv[1]
    else:
        host = "localhost"
    if len(sys.argv) > 2:
        port = int(sys.argv[2])
    else:
        port = 8000
    address = (host, port)

    server = SocketTCP()
    server.bind(address)
    print(f"[servidor] escuchando en {address}", file=sys.stderr)

    conn, new_addr = server.accept()           # 3-way handshake
    print(f"[servidor] conexion establecida, socket en {new_addr}",
          file=sys.stderr)

    # recibimos el mensaje completo
    data = conn.recv(BUFF_SIZE)
    while conn.bytes_restantes > 0:            # mensaje mas grande que el buffer
        data += conn.recv(BUFF_SIZE)

    conn.recv_close()                          # cierre de conexion (Host B)

    # escribimos lo recibido en salida estandar (bytes)
    sys.stdout.buffer.write(data)
    sys.stdout.buffer.flush()
    print(f"[servidor] recibidos {len(data)} bytes y conexion cerrada",
          file=sys.stderr)


if __name__ == "__main__":
    main()