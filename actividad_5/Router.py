import socket
import sys

BUFF_SIZE = 1024

def parse_packet(IP_packet: bytes) -> dict:
    ip = ".".join(str(b) for b in IP_packet[0:4])
    port = int.from_bytes(IP_packet[4:6], "big")
    ttl = IP_packet[6]
    message = IP_packet[7:].decode()
    return {"ip": ip, "port": port, "ttl": ttl, "message": message}


def create_packet(parsed_IP_packet: dict) -> bytes:
    ip_bytes = socket.inet_aton(parsed_IP_packet["ip"])
    port_bytes = parsed_IP_packet["port"].to_bytes(2, "big")
    ttl_byte = parsed_IP_packet["ttl"].to_bytes(1, "big")
    return ip_bytes + port_bytes + ttl_byte + parsed_IP_packet["message"].encode()

def _ip_to_int(ip: str) -> int:
    return int.from_bytes(socket.inet_aton(ip), "big")


def _in_network(ip: str, cidr: str) -> bool:
    net, bits = cidr.split("/")
    shift = 32 - int(bits)
    return (_ip_to_int(ip) >> shift) == (_ip_to_int(net) >> shift)


# Estado de round-robin: para cada "area" (misma red + mismo rango de puertos) 
# guardamos el indice de la ultima ruta usada. 
# La clave incluye el archivo de rutas para que distintas tablas no se mezclen.
_ultima_ruta = {}


def check_routes(routes_file_name: str, destination_address: tuple):
    dest_ip, dest_port = destination_address
    area = None          # (cidr, p_ini, p_fin) de la primera linea que calza
    candidatas = []      # todas las rutas de esa misma area, en orden
    with open(routes_file_name) as f:
        for line in f:
            line = line.strip()
            if line == "" or line.startswith("#"):
                continue
            cidr, p_ini, p_fin, hop_ip, hop_port = line.split()
            if not (_in_network(dest_ip, cidr)
                    and int(p_ini) <= dest_port <= int(p_fin)):
                continue
            clave = (cidr, p_ini, p_fin)
            if area is None:
                area = clave
            if clave == area:
                candidatas.append((hop_ip, int(hop_port)))

    if area is None:
        return None

    estado = (routes_file_name, area)
    idx = (_ultima_ruta.get(estado, -1) + 1) % len(candidatas)
    _ultima_ruta[estado] = idx
    return candidatas[idx]


def main():
    router_ip = sys.argv[1]
    router_port = int(sys.argv[2])
    routes_file = sys.argv[3]
    my_address = (router_ip, router_port)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(my_address)
    print(f"Router escuchando en {my_address} con rutas {routes_file}", flush=True)

    while True:
        IP_packet, _ = sock.recvfrom(BUFF_SIZE)
        parsed = parse_packet(IP_packet)
        destination = (parsed["ip"], parsed["port"])

        # Paquete con TTL agotado: se ignora
        if parsed["ttl"] <= 0:
            print(f"Se recibió paquete {IP_packet} con TTL 0", flush=True)
            continue

        if destination == my_address:
            print(parsed["message"], flush=True)
            continue

        next_hop = check_routes(routes_file, destination)
        if next_hop is None:
            print(f"No hay rutas hacia {destination} para paquete {IP_packet}",
                  flush=True)
        else:
            # decrementar TTL antes de hacer forward
            parsed["ttl"] -= 1
            forwarded = create_packet(parsed)
            print(f"redirigiendo paquete {forwarded} con destino final "
                  f"{destination} desde {my_address} hacia {next_hop}",
                  flush=True)
            sock.sendto(forwarded, next_hop)


if __name__ == "__main__":
    main()