import socket
import sys

BUFF_SIZE = 2048

HEADER_SIZE = 20


def parse_packet(IP_packet: bytes) -> dict:
    return {
        "ip": ".".join(str(b) for b in IP_packet[0:4]),
        "port": int.from_bytes(IP_packet[4:6], "big"),
        "ttl": IP_packet[6],
        "id": int.from_bytes(IP_packet[7:11], "big"),
        "offset": int.from_bytes(IP_packet[11:15], "big"),
        "size": int.from_bytes(IP_packet[15:19], "big"),
        "flag": IP_packet[19],
        "message": IP_packet[20:],          # bytes
    }


def create_packet(parsed_IP_packet: dict) -> bytes:
    p = parsed_IP_packet
    msg = p["message"]
    if isinstance(msg, str):
        msg = msg.encode()
    return (socket.inet_aton(p["ip"])
            + p["port"].to_bytes(2, "big")
            + p["ttl"].to_bytes(1, "big")
            + p["id"].to_bytes(4, "big")
            + p["offset"].to_bytes(4, "big")
            + len(msg).to_bytes(4, "big")      # Tamano siempre consistente
            + p["flag"].to_bytes(1, "big")
            + msg)


def _ip_to_int(ip: str) -> int:
    return int.from_bytes(socket.inet_aton(ip), "big")


def _in_network(ip: str, cidr: str) -> bool:
    # si la linea viene sin "/mascara" (como rutas_R5_v3_mtu del enunciado)
    # se compara la IP completa (/32)
    net, bits = cidr.split("/") if "/" in cidr else (cidr, "32")
    shift = 32 - int(bits)
    return (_ip_to_int(ip) >> shift) == (_ip_to_int(net) >> shift)


# Round-robin: indice de la ultima ruta usada por (archivo, area)
_ultima_ruta = {}


def check_routes(routes_file_name: str, destination_address: tuple):
    """Retorna (next_hop_address, MTU) o None si no hay ruta."""
    dest_ip, dest_port = destination_address
    area = None
    candidatas = []
    with open(routes_file_name) as f:
        for line in f:
            line = line.strip()
            if line == "" or line.startswith("#"):
                continue
            campos = line.split()
            cidr, p_ini, p_fin, hop_ip, hop_port = campos[:5]
            mtu = int(campos[5]) if len(campos) > 5 else None  # None = sin limite
            if not (_in_network(dest_ip, cidr)
                    and int(p_ini) <= dest_port <= int(p_fin)):
                continue
            clave = (cidr, p_ini, p_fin)
            if area is None:
                area = clave
            if clave == area:
                candidatas.append(((hop_ip, int(hop_port)), mtu))

    if area is None:
        return None
    estado = (routes_file_name, area)
    idx = (_ultima_ruta.get(estado, -1) + 1) % len(candidatas)
    _ultima_ruta[estado] = idx
    return candidatas[idx]


def fragment_IP_packet(IP_packet: bytes, MTU) -> list:
    """Lista de paquetes (bytes) tal que cada uno mide <= MTU. Largo >= 1."""
    if MTU is None or len(IP_packet) <= MTU:
        return [IP_packet]
    if MTU <= HEADER_SIZE:
        raise ValueError("MTU demasiado chico para el header")

    p = parse_packet(IP_packet)
    msg = p["message"]
    trozo = MTU - HEADER_SIZE            # bytes de mensaje por fragmento
    fragmentos = []
    for inicio in range(0, len(msg), trozo):
        parte = msg[inicio:inicio + trozo]
        es_ultimo_trozo = inicio + trozo >= len(msg)
        frag = dict(p)
        frag["message"] = parte
        frag["offset"] = p["offset"] + inicio
        # si el paquete que fragmentamos ya era un fragmento intermedio
        # (flag=1), su ultimo trozo tambien debe seguir con flag=1
        frag["flag"] = p["flag"] if es_ultimo_trozo else 1
        fragmentos.append(create_packet(frag))
    return fragmentos


def reassemble_IP_packet(fragment_list: list):
    """Paquete completo (bytes) o None si faltan fragmentos."""
    if not fragment_list:
        return None
    parsed = sorted((parse_packet(f) for f in fragment_list),
                    key=lambda q: (q["offset"], -len(q["message"])))
    if parsed[0]["offset"] != 0:
        return None

    mensaje = b""
    fin = None                      # largo total, se conoce con el flag 0
    for q in parsed:
        if q["offset"] > len(mensaje):
            return None             # hay un hueco
        # si hay solapamiento por duplicados, solo se toma lo nuevo
        mensaje += q["message"][len(mensaje) - q["offset"]:]
        if q["flag"] == 0:
            fin = q["offset"] + len(q["message"])
    if fin is None or len(mensaje) < fin:
        return None

    completo = dict(parsed[0])
    completo["message"] = mensaje[:fin]
    completo["offset"] = 0
    completo["flag"] = 0
    return create_packet(completo)


def main():
    router_ip = sys.argv[1]
    router_port = int(sys.argv[2])
    routes_file = sys.argv[3]
    my_address = (router_ip, router_port)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(my_address)
    print(f"Router escuchando en {my_address} con rutas {routes_file}", flush=True)

    fragmentos = {}      # ID -> lista de fragmentos/paquetes recibidos

    while True:
        IP_packet, _ = sock.recvfrom(BUFF_SIZE)
        parsed = parse_packet(IP_packet)
        destination = (parsed["ip"], parsed["port"])

        if parsed["ttl"] <= 0:
            print(f"Se recibió paquete {IP_packet} con TTL 0", flush=True)
            continue

        if destination == my_address:
            lista = fragmentos.setdefault(parsed["id"], [])
            lista.append(IP_packet)
            completo = reassemble_IP_packet(lista)
            if completo is not None:
                msg = parse_packet(completo)["message"]
                print(msg.decode(errors="replace"), flush=True)
                del fragmentos[parsed["id"]]
            continue

        # forwarding
        ruta = check_routes(routes_file, destination)
        if ruta is None:
            print(f"No hay rutas hacia {destination} para paquete {IP_packet}",
                  flush=True)
            continue
        next_hop, mtu = ruta
        parsed["ttl"] -= 1
        forwarded = create_packet(parsed)
        lista_frag = fragment_IP_packet(forwarded, mtu)
        print(f"redirigiendo paquete {forwarded} con destino final "
              f"{destination} desde {my_address} hacia {next_hop} "
              f"(MTU {mtu}, {len(lista_frag)} fragmento(s))", flush=True)
        for frag in lista_frag:
            sock.sendto(frag, next_hop)


if __name__ == "__main__":
    main()