import socket
import json
import sys

with open(sys.argv[1]) as archivo:
    config = json.load(archivo)

nombre = config["user"]

def recibir_mensaje_completo(conexion, buff_size=1024):
    # esto evita el bug que tuviste antes: un solo recv() no garantiza
    # que llegue el mensaje completo, así que acumulamos hasta ver \r\n\r\n
    buffer = b""
    while b"\r\n\r\n" not in buffer:
        pedazo = conexion.recv(buff_size)
        if not pedazo:
            break
        buffer += pedazo
    return buffer


def parse_HTTP_message(http_message: bytes) -> dict:
    head, body = http_message.split(b"\r\n\r\n", 1)
    lineas = head.split(b"\r\n")
    metodo, path, version = lineas[0].decode().split(" ")

    headers = {}
    for linea in lineas[1:]:
        nombre, valor = linea.decode().split(":", 1)
        headers[nombre.strip()] = valor.strip()

    return {"metodo": metodo, "path": path, "version": version,
            "headers": headers, "body": body}


def create_HTTP_message(data: dict) -> bytes:
    primera_linea = f'{data["version"]} {data["status"]} {data["reason"]}'
    lineas_headers = [f"{nombre}: {valor}" for nombre, valor in data["headers"].items()]
    head = "\r\n".join([primera_linea] + lineas_headers)
    return head.encode() + b"\r\n\r\n" + data["body"]


server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_socket.bind(("0.0.0.0", 8000))
server_socket.listen(3)
print("Esperando que alguien se conecte...")

conexion, direccion = server_socket.accept()

mensaje = recibir_mensaje_completo(conexion)
print(mensaje)                        # print ANTES de decode, tal como pide el enunciado

parsed = parse_HTTP_message(mensaje)
print("Parseado:", parsed)

html = b"<html><body><h1>Hola Probando!</h1></body></html>"

respuesta = create_HTTP_message({
    "version": "HTTP/1.1", "status": "200", "reason": "OK",
    "headers": {
        "Content-Type": "text/html",
        "Content-Length": str(len(html)),
        "X-ElQuePregunta": nombre,
    },
    "body": html
})
conexion.send(respuesta)

conexion.close()