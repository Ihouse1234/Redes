import sys
import time
from SocketTCP import SocketTCP


def main():
    """
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
        client.set_congestion_control(True)
        client.connect(address)          # 3-way handshake
        client.send(data, mode = mode)                # Go Back N (envia largo + contenido)
        client.close()                   # cierre de conexion (Host A)
        print(f"[cliente] enviados {len(data)} bytes y conexion cerrada",
                file=sys.stderr)
    """
    


    #PARA EXPERIMENTACION DESCOMENTAR:
    host = sys.argv[1]
    port = int(sys.argv[2])
    address = (host, port)
    mode = sys.argv[3] if len(sys.argv) > 3 else "stop_and_wait"
    cc = len(sys.argv) > 4 and sys.argv[4] == "cc"             

    data = sys.stdin.buffer.read()

    client = SocketTCP()
    client.set_congestion_control(cc)                          
    client.connect(address)
    inicio = time.time()                                       
    client.send(data, mode=mode)
    duracion = time.time() - inicio                            
    client.close()
    print(f"[cliente] enviados {len(data)} bytes y conexion cerrada ({mode})", file=sys.stderr)
    print(f"[resultado] tiempo={duracion:.2f}s segmentos={client.number_of_sent_segments}",
            file=sys.stderr) 




if __name__ == "__main__":
    main()