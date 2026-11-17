from Router import parse_packet, create_packet, check_routes

# parse_packet <-> create_packet (con TTL)
# 127.0.0.1 = 127,0,0,1 ; puerto 8883 ; TTL 10 ; mensaje "hola"
IP_packet_v1 = bytes([127, 0, 0, 1]) + (8883).to_bytes(2, "big") + bytes([10]) + b"hola"
parsed_IP_packet = parse_packet(IP_packet_v1)
print(parsed_IP_packet)
IP_packet_v2 = create_packet(parsed_IP_packet)
print("IP_packet_v1 == IP_packet_v2 ? {}".format(IP_packet_v1 == IP_packet_v2))

# check_routes con el ejemplo 2 (R1-R2-R3 en linea)
print("\ncheck_routes sobre rutas_R2_v2.txt")
for dest in [("127.0.0.1", 8881), ("127.0.0.1", 8883), ("127.0.0.1", 8884)]:
    print(dest, "->", check_routes("rutas_R2_v2.txt", dest))
