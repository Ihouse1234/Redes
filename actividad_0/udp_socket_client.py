import socket
import argparse
import sys

# =====================================================================
#  Cliente NO orientado a conexión (UDP)
#  Adaptado del ejemplo orientado a conexión (TCP):
#    - socket.SOCK_DGRAM  en vez de socket.SOCK_STREAM
#    - sendto / recvfrom  en vez de send / recv
#    - NO se usa connect()  (en UDP no hay "conexión")
#
#  Puede enviar:
#    * un mensaje por defecto definido en el código,
#    * un mensaje pasado por --message,
#    * lo que llegue por entrada estándar  (--stdin),
#    * el contenido de un archivo de texto  (--file ruta).
#
#  Como el mensaje puede ser MÁS GRANDE que el buffer, el cliente lo parte en
#  trozos de tamaño <= buffer y los envía en varios datagramas.
# =====================================================================


def contains_end_of_message(message_bytes, end_bytes):
    return message_bytes.endswith(end_bytes)


def remove_end_of_message(full_bytes, end_bytes):
    index = full_bytes.rfind(end_bytes)
    if index == -1:
        return full_bytes
    return full_bytes[:index]


def send_full_message(sock, data_bytes, address, buff_size, end_bytes):
    """Envía data_bytes en trozos <= buff_size y agrega la secuencia de fin."""
    payload = data_bytes + end_bytes
    for i in range(0, len(payload), buff_size):
        sock.sendto(payload[i:i + buff_size], address)


def receive_full_message(sock, buff_size, end_bytes, timeout=3.0):
    """
    Reensambla la respuesta (echo) del servidor hasta encontrar la secuencia
    de fin de mensaje. Devuelve (bytes_sin_terminador, address).
    Usa timeout para no colgarse si se pierden datagramas (netem).
    """
    sock.settimeout(timeout)
    full_message, address = sock.recvfrom(buff_size)
    try:
        while not contains_end_of_message(full_message, end_bytes):
            chunk, address = sock.recvfrom(buff_size)
            full_message += chunk
    except socket.timeout:
        print("    [!] Timeout esperando la respuesta: se perdieron datagramas "
              "(UDP no garantiza entrega).")
        return remove_end_of_message(full_message, end_bytes), address
    finally:
        sock.settimeout(None)
    return remove_end_of_message(full_message, end_bytes), address


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Cliente NO orientado a conexión (UDP)")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--buffer", type=int, default=10)
    parser.add_argument("--eom", default="\n",
                        help="Secuencia de fin de mensaje (debe coincidir con la "
                             "del servidor). Para archivos de texto con saltos de "
                             "línea use un centinela, p.ej. --eom '###FIN###'.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--message", "-m",
                       help="Mensaje a enviar (definido por línea de comandos)")
    group.add_argument("--file", "-f",
                       help="Ruta de un archivo de texto a enviar")
    parser.add_argument("--stdin", action="store_true",
                        help="Leer el mensaje desde entrada estándar")
    args = parser.parse_args()

    buff_size = args.buffer
    end_bytes = args.eom.encode()
    server_address = (args.host, args.port)

    # Decidimos qué datos enviar
    if args.file:
        with open(args.file, "rb") as fh:
            data_bytes = fh.read()
        origen = f"archivo '{args.file}'"
    elif args.stdin:
        data_bytes = sys.stdin.buffer.read()
        origen = "entrada estándar"
    elif args.message is not None:
        data_bytes = args.message.encode()
        origen = "argumento --message"
    else:
        # mensaje por defecto definido dentro del código del cliente
        data_bytes = "Hola, este es un mensaje de prueba".encode()
        origen = "mensaje por defecto"

    print("Creando socket - Cliente (UDP / no orientado a conexión)")
    # socket.SOCK_DGRAM = socket NO orientado a conexión.
    # En UDP no hace falta connect(): usamos sendto/recvfrom con la dirección destino.
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    print(f"... Enviando {len(data_bytes)} bytes ({origen}) a {server_address} "
          f"en trozos de {buff_size}")
    send_full_message(client_socket, data_bytes, server_address, buff_size, end_bytes)
    print("... Mensaje enviado")

    # Esperamos el echo y lo reensamblamos
    echo_bytes, _ = receive_full_message(client_socket, buff_size, end_bytes)
    echo_text = echo_bytes.decode(errors="replace")
    print(f" -> Respuesta (echo) del servidor: {echo_text!r}")

    # Verificación de integridad (clave para el test con netem: pérdida/delay)
    if echo_bytes == data_bytes:
        print(" [OK] El echo coincide EXACTAMENTE con lo enviado (sin pérdidas).")
    else:
        print(f" [!] El echo NO coincide: enviados {len(data_bytes)} bytes, "
              f"recibidos {len(echo_bytes)} bytes.")
        print("     Esto es esperable bajo pérdida/delay (netem): UDP no "
              "retransmite ni reordena datagramas.")

    client_socket.close()