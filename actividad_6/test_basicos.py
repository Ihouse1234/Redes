from Router import (parse_packet, create_packet, check_routes,
                    fragment_IP_packet, reassemble_IP_packet, HEADER_SIZE)

def paquete(msg, id_=347, ttl=10, port=8885):
    return create_packet({"ip": "127.0.0.1", "port": port, "ttl": ttl, "id": id_,
                          "offset": 0, "flag": 0, "message": msg})

print("--- Paso 1: parse_packet / create_packet")
IP_packet_v1 = (bytes([127, 0, 0, 1]) + (8885).to_bytes(2, "big") + bytes([10])
                + (347).to_bytes(4, "big") + (0).to_bytes(4, "big")
                + (5).to_bytes(4, "big") + bytes([0]) + b"hola!")
parsed = parse_packet(IP_packet_v1)
print(parsed)
IP_packet_v2 = create_packet(parsed)
print("IP_packet_v1 == IP_packet_v2 ? {}".format(IP_packet_v1 == IP_packet_v2))

print("\n--- Paso 2: check_routes devuelve (ruta, MTU)")
for f, dest in [("rutas_R2_v3_mtu.txt", ("127.0.0.1", 8885))]*4 + \
               [("rutas_R1_v3_mtu.txt", ("127.0.0.1", 8885)),
                ("rutas_R5_v3_mtu.txt", ("127.0.0.1", 8881)),
                ("rutas_R1_v3_mtu.txt", ("127.0.0.1", 9999))]:
    print(f, dest, "->", check_routes(f, dest))

print("\n--- Paso 3: fragment_IP_packet")
chico = paquete(b"hola!")                          # 25 bytes
print("paquete de", len(chico), "bytes, MTU 50 ->", len(fragment_IP_packet(chico, 50)), "fragmento(s)")
exacto = paquete(b"x" * 30)                        # 50 bytes justos
print("paquete de", len(exacto), "bytes, MTU 50 ->", len(fragment_IP_packet(exacto, 50)), "fragmento(s)")
grande = paquete(bytes(range(65, 65 + 26)) * 5)    # 130 bytes de mensaje -> 150 total
print("paquete de", len(grande), "bytes")
for mtu in (140, 100, 80, 55, 50):
    frs = fragment_IP_packet(grande, mtu)
    esperado = -(-130 // (mtu - HEADER_SIZE))      # techo
    ok = all(len(f) <= mtu for f in frs) and len(frs) == esperado
    print(f"  MTU {mtu}: {len(frs)} fragmentos (esperado {esperado}), "
          f"todos <= MTU: {all(len(f) <= mtu for f in frs)}  ->  {'OK' if ok else 'FALLA'}")
print("  flags/offsets MTU 55:", [(parse_packet(f)['offset'], parse_packet(f)['size'], parse_packet(f)['flag'])
                                  for f in fragment_IP_packet(grande, 55)])

print("\n--- Paso 5: fragmentar y re-ensamblar")
import random
for mtu in (140, 100, 80, 55, 50):
    fl = fragment_IP_packet(grande, mtu)
    v2 = reassemble_IP_packet(fl)
    random.shuffle(fl)
    v2b = reassemble_IP_packet(fl)
    print(f"  MTU {mtu}: IP_packet_v1 = IP_packet_v2 ? {grande == v2}  (desordenado: {grande == v2b})")
fl = fragment_IP_packet(grande, 50)
print("  lista incompleta (falta un fragmento) ->", reassemble_IP_packet(fl[:2] + fl[3:]))
print("  lista con solo el primero ->", reassemble_IP_packet(fl[:1]))
print("  lista con solo el ultimo ->", reassemble_IP_packet(fl[-1:]))
print("  paquete sin fragmentar (lista de 1) ->", reassemble_IP_packet([chico]) == chico)

print("\n--- Re-fragmentar un fragmento (MTU 100 y luego 50)")
primero = fragment_IP_packet(grande, 100)
resto = []
for f in primero:
    resto += fragment_IP_packet(f, 50)
print("  fragmentos finales:", len(resto), " todos <= 50:", all(len(f) <= 50 for f in resto))
print("  re-ensamblado igual al original ?", reassemble_IP_packet(resto) == grande)
