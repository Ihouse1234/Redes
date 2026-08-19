import socket
import argparse

# =====================================================================
#  Servidor ECHO NO orientado a conexión (UDP)
#  Adaptado del ejemplo orientado a conexión (TCP):
#    - socket.SOCK_DGRAM  en vez de socket.SOCK_STREAM
#    - recvfrom / sendto  en vez de recv / send
#    - NO se usa listen() ni accept()  (en UDP no existe la "conexión")
# =====================================================================


# --- Funciones del protocolo inventado (armado / desarmado del mensaje) ---
# Trabajamos SIEMPRE en bytes y solo decodificamos al final. Así evitamos que
# un carácter UTF-8 partido entre dos datagramas (buffer chico) rompa .decode().

def contains_end_of_message(message_bytes, end_bytes):
    # True si los bytes acumulados terminan con la secuencia de fin de mensaje
    return message_bytes.endswith(end_bytes)


def remove_end_of_message(full_bytes, end_bytes):
    # quita la última aparición de la secuencia de fin de mensaje
    index = full_bytes.rfind(end_bytes)
    if index == -1:
        return full_bytes
    return full_bytes[:index]


def receive_full_message(server_socket, buff_size, end_bytes):
    """
    Recibe (posiblemente) varios datagramas hasta encontrar la secuencia de fin
    de mensaje. Devuelve (mensaje_en_bytes_sin_terminador, direccion_del_emisor).

    OJO (UDP): cada recvfrom entrega UN datagrama completo. Si ese datagrama es
    MÁS GRANDE que buff_size, el sistema TRUNCA el resto y esa parte SE PIERDE
    (a diferencia de TCP, que es un flujo continuo de bytes). Por eso, para
    mensajes largos, el emisor debe mandar trozos de tamaño <= buff_size.
    """
    # 1er datagrama: bloqueamos sin timeout (esperando a que llegue algún cliente)
    server_socket.settimeout(None)
    full_message, address = server_socket.recvfrom(buff_size)

    # Ya empezó una transmisión: ponemos timeout para no colgarnos para siempre
    # si se pierden datagramas (por ejemplo, al simular pérdida con netem).
    server_socket.settimeout(3.0)
    try:
        while not contains_end_of_message(full_message, end_bytes):
            chunk, address = server_socket.recvfrom(buff_size)
            full_message += chunk
    except socket.timeout:
        print("    [!] Timeout esperando el resto del mensaje: se perdieron "
              "datagramas (UDP no garantiza entrega ni orden).")
        return remove_end_of_message(full_message, end_bytes), address
    finally:
        server_socket.settimeout(None)

    return remove_end_of_message(full_message, end_bytes), address


def send_full_message(server_socket, data_bytes, address, buff_size, end_bytes):
    """
    Envía data_bytes al 'address' partiéndolo en trozos de tamaño <= buff_size,
    de modo que ningún datagrama exceda el buffer del receptor. Al final agrega
    la secuencia de fin de mensaje.
    """
    payload = data_bytes + end_bytes
    for i in range(0, len(payload), buff_size):
        server_socket.sendto(payload[i:i + buff_size], address)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Servidor echo NO orientado a conexión (UDP)")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--buffer", type=int, default=10,
                        help="Tamaño del buffer de recepción (por defecto 10)")
    parser.add_argument("--eom", default="\n",
                        help="Secuencia de fin de mensaje. Por defecto '\\n' "
                             "(compatible con netcat). Para enviar archivos de "
                             "texto con saltos de línea, use un centinela propio, "
                             "p.ej.  --eom '###FIN###'  (igual en cliente y servidor).")
    args = parser.parse_args()

    buff_size = args.buffer
    end_bytes = args.eom.encode()
    server_address = (args.host, args.port)

    print("Creando socket - Servidor (UDP / no orientado a conexión)")
    # socket.SOCK_DGRAM = socket NO orientado a conexión
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    # En UDP solo hacemos bind (no hay listen ni accept)
    server_socket.bind(server_address)

    print(f"... Escuchando en {server_address}  |  buffer={buff_size}  |  "
          f"fin_de_mensaje={end_bytes!r}")
    print("... Esperando clientes (Ctrl+C para terminar)")

    try:
        while True:
            # Recibimos el mensaje completo (reensamblando datagramas si hace falta)
            recv_bytes, client_address = receive_full_message(
                server_socket, buff_size, end_bytes)

            # Debug: imprimimos TODO lo que recibimos
            recv_text = recv_bytes.decode(errors="replace")
            print(f" -> Mensaje recibido desde {client_address}: {recv_text!r}")

            # Servidor ECHO: respondemos con el MISMO mensaje que recibimos,
            # de vuelta al emisor original.
            send_full_message(server_socket, recv_bytes, client_address,
                              buff_size, end_bytes)
            print(f" <- Echo enviado de vuelta a {client_address}")
    except KeyboardInterrupt:
        print("\nCerrando servidor...")
    finally:
        server_socket.close()