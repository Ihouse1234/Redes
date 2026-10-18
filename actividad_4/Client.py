import sys
from SocketTCP import SocketTCP


def main():
    host = sys.argv[1]
    port = int(sys.argv[2])
    address = (host, port)

    # leemos TODO el archivo desde stdin como bytes
    data = sys.stdin.buffer.read()

    if len(sys.argv) > 3:                                           
        mode = sys.argv[3]                                          
    else:                                                           
        mode = "stop_and_wait" 
        
    client = SocketTCP()
    client.connect(address)          # 3-way handshake
    client.send(data, mode = mode)                # Go Back N (envia largo + contenido)
    client.close()                   # cierre de conexion (Host A)
    print(f"[cliente] enviados {len(data)} bytes y conexion cerrada",
          file=sys.stderr)


if __name__ == "__main__":
    main()