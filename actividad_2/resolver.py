import socket
import dnslib
from dnslib import DNSRecord
from dnslib.dns import CLASS, QTYPE, RR


IP_VM = "127.0.0.1"  
PORT = 8000

def parsear_mensaje(data: bytes):

    mensaje = DNSRecord.parse(data)
    qname = mensaje.get_q().get_qname()   # el nombre de dominio consultado
    ancount = mensaje.header.a            #  Answer
    nscount = mensaje.header.auth         #  Authority
    arcount = mensaje.header.ar           #  Additional

    answer_section = mensaje.rr           # registros en Answer
    authority_section = mensaje.auth      # registros en Authority
    additional_section = mensaje.ar

    return {
        "qname": qname,
        "ancount": ancount,
        "nscount": nscount,
        "arcount": arcount,
        "answer": answer_section,
        "authority": authority_section,
        "additional": additional_section,
        "raw": mensaje,
    }

ROOT_IP = "198.41.0.4"

def enviar_query(mensaje_bytes: bytes, ip_addr: str, port=53, timeout=3):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(timeout)
    try:
        sock.sendto(mensaje_bytes, (ip_addr, port))
        data, _ = sock.recvfrom(4096)
    finally:
        sock.close()
    return data


##funcion auxiliar 
def filtrar_por_tipo(lista_registros, tipo):
    resultado = []
    for registro in lista_registros:
        if registro.rtype == tipo:
            resultado.append(registro)
    return resultado

def resolver(mensaje_consulta: bytes, ip_addr=ROOT_IP, ns_name=".", debug=True) -> bytes:
    query_parseada = DNSRecord.parse(mensaje_consulta)
    qname = str(query_parseada.get_q().get_qname())

    if debug:
        print(f"(debug) Consultando '{qname}' a '{ns_name}' con dirección IP '{ip_addr}'")

    respuesta_bytes = enviar_query(mensaje_consulta, ip_addr)
    respuesta = DNSRecord.parse(respuesta_bytes)

    respuestas_A = filtrar_por_tipo(respuesta.rr, QTYPE.A)
    if respuestas_A:
        return respuesta_bytes

    ns_en_authority = filtrar_por_tipo(respuesta.auth, QTYPE.NS)

    if ns_en_authority:
        nombre_ns_actual = str(ns_en_authority[0].rdata)

        ips_en_additional = filtrar_por_tipo(respuesta.ar, QTYPE.A)
        if ips_en_additional:
            siguiente_ip = str(ips_en_additional[0].rdata)
            return resolver(mensaje_consulta, siguiente_ip, nombre_ns_actual, debug)
        else:
            query_ns = DNSRecord.question(nombre_ns_actual)
            respuesta_ns_bytes = resolver(query_ns.pack(), ROOT_IP, ".", debug)
            respuesta_ns = DNSRecord.parse(respuesta_ns_bytes)

            ips_ns = filtrar_por_tipo(respuesta_ns.rr, QTYPE.A)
            if ips_ns:
                siguiente_ip = str(ips_ns[0].rdata)
                return resolver(mensaje_consulta, siguiente_ip, nombre_ns_actual, debug)

    return None

#### 6

HISTORIAL_MAXIMO = 20
TOP_CACHE = 3

historial_consultas = []
cache_ips = {}

def agregar_al_historial(qname: str):
    historial_consultas.append(qname)
    if len(historial_consultas) > HISTORIAL_MAXIMO:
        historial_consultas.pop(0)


## recorre historial_consultas y por cada nombre en el diccionario suma 1 y si no esta agrega valor 1
def contar_repeticiones():
    conteo = {}
    for nombre in historial_consultas:
        if nombre in conteo:
            conteo[nombre] = conteo[nombre] + 1
        else:
            conteo[nombre] = 1
    return conteo

def obtener_top_3(conteo: dict):

    conteo_copia = dict(conteo)
    top_3 = []
    for _ in range(TOP_CACHE):
        if not conteo_copia:
            break

        nombre_mas_repetido = None
        cantidad_maxima = -1

        for nombre in conteo_copia:
            if conteo_copia[nombre] > cantidad_maxima:
                cantidad_maxima = conteo_copia[nombre]
                nombre_mas_repetido = nombre

        top_3.append(nombre_mas_repetido)
        del conteo_copia[nombre_mas_repetido]
    
    return top_3

def actualizar_cache(qname: str, ip: str):
    agregar_al_historial(qname)

    conteo = contar_repeticiones()
    top_3 = obtener_top_3(conteo)

    cache_ips[qname] = ip

    for nombre in list(cache_ips.keys()):
        if nombre not in top_3:
            del cache_ips[nombre]

def buscar_en_cache(qname: str):
    return cache_ips.get(qname)

def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((IP_VM, PORT))
    print(f"Resolver escuchando en {IP_VM}:{PORT}")

    while True:
        data, client_address = sock.recvfrom(4096)
        query_parseada = DNSRecord.parse(data)
        qname = str(query_parseada.get_q().get_qname())

        ip_en_cache = buscar_en_cache(qname)

        if ip_en_cache:
            print(f"(debug) '{qname}' encontrado en caché -> {ip_en_cache}")
            respuesta = query_parseada.reply()
            respuesta.add_answer(*RR.fromZone(f"{qname} A {ip_en_cache}"))
            sock.sendto(respuesta.pack(), client_address)
            agregar_al_historial(qname)
        else:
            try:
                respuesta_bytes = resolver(data)
            except Exception as e:
                print(f"Error resolviendo la consulta: {e}")
                respuesta_bytes = None

            if respuesta_bytes:
                respuesta_parseada = DNSRecord.parse(respuesta_bytes)
                respuesta_parseada.header.id = query_parseada.header.id
                sock.sendto(respuesta_parseada.pack(), client_address)

                ips = filtrar_por_tipo(respuesta_parseada.rr, QTYPE.A)
                if ips:
                    actualizar_cache(qname, str(ips[0].rdata))


if __name__ == "__main__":
    main()