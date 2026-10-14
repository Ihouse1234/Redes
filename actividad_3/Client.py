import sys
from SocketTCP import SocketTCP


def main():
    host = sys.argv[1]
    port = int(sys.argv[2])
    address = (host, port)

    # leemos TODO el archivo desde stdin como bytes
    data = sys.stdin.buffer.read()

    client = SocketTCP()
    client.connect(address)          # 3-way handshake
    client.send(data)                # Stop & Wait (envia largo + contenido)
    client.close()                   # cierre de conexion (Host A)
    print(f"[cliente] enviados {len(data)} bytes y conexion cerrada",
          file=sys.stderr)


if __name__ == "__main__":
    main()