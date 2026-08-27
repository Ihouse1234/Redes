import socket
import json
import sys

# =====================================================================
#  CC4303 - Proxy FINAL (Parte 2 completa)
#  Ultimo paso: recibir mensajes con un buffer de recepcion MAS PEQUENO
#  que el mensaje. La idea (inspirada en las funciones de la semana 1) es
#  hacer recv en un bucle acumulando bytes hasta saber que llego todo.
#
#  Preguntas del informe (respondidas en los comentarios):
#   * Como se que el HEAD llego completo?  -> aparece el patron \r\n\r\n.
#   * Que pasa si los headers no caben en el buffer? -> nada; se acumulan
#     en varios recv. TCP es un flujo, no se pierde nada (a diferencia de UDP).
#   * Como se que el BODY llego completo? -> segun Content-Length, chunked,
#     o cierre de la conexion.
#   * Como se si llego el mensaje completo? -> HEAD completo Y BODY completo.
#
#  Solo se usan librerias permitidas: socket, json, sys.
# =====================================================================

IMG_PATH = "/__proxy_blocked_image__"


# ---------------------------------------------------------------------
#  Lector con buffer chico
# ---------------------------------------------------------------------
# Un socket TCP entrega un FLUJO de bytes. Con un buffer chico, cada recv
# trae solo un pedacito. Esta clase acumula lo recibido en un buffer interno
# y solo pide mas bytes a la red cuando hace falta. Ademas, al leer el HEAD
# puede venir parte del BODY pegada en el mismo recv: ese sobrante queda
# guardado en self.buffer para no perderlo.
class SocketReader:
    def __init__(self, connection_socket, recv_buffer):
        self.socket = connection_socket
        self.recv_buffer = recv_buffer      # <-- puede ser 50, 10, incluso 1
        self.buffer = b""
        self.closed = False

    def _fill(self):
        if self.closed:
            return False
        chunk = self.socket.recv(self.recv_buffer)   # trae a lo mas recv_buffer bytes
        if not chunk:
            self.closed = True
            return False
        self.buffer += chunk
        return True

    def read_until(self, delimiter):
        # sigue haciendo recv hasta que el delimitador aparezca en lo acumulado
        while delimiter not in self.buffer:
            if not self._fill():
                data, self.buffer = self.buffer, b""
                return data, False
        cut = self.buffer.find(delimiter) + len(delimiter)
        data, self.buffer = self.buffer[:cut], self.buffer[cut:]   # sobrante guardado
        return data, True

    def read_exactly(self, n):
        while len(self.buffer) < n:
            if not self._fill():
                break
        data, self.buffer = self.buffer[:n], self.buffer[n:]
        return data

    def read_until_close(self):
        while self._fill():
            pass
        data, self.buffer = self.buffer, b""
        return data


def receive_http_message(reader, is_request):
    """
    Lee un mensaje HTTP completo (HEAD + BODY) con buffer chico.
    Devuelve (head_bytes, body_bytes, head_lines).
    """
    head_block, found = reader.read_until(b"\r\n\r\n")
    if not found or not head_block:
        return None
    head = head_block[:-4]                       
    head_lines = head.split(b"\r\n")

    # 2) BODY: decido el criterio de fin segun los headers
    content_length = None
    is_chunked = False
    for line in head_lines[1:]:
        low = line.lower()
        if low.startswith(b"content-length:"):
            content_length = int(line.split(b":", 1)[1].strip())
        elif low.startswith(b"transfer-encoding:") and b"chunked" in low:
            is_chunked = True

    if is_chunked:
        body = read_chunked_body(reader)
    elif content_length is not None:
        body = reader.read_exactly(content_length)     # exactamente N bytes
    elif is_request:
        body = b""                                     # request sin CL: sin body
    else:
        body = reader.read_until_close()               # respuesta: hasta el cierre
    return head, body, head_lines


def read_chunked_body(reader):
    body = b""
    while True:
        size_line, ok = reader.read_until(b"\r\n")
        if not size_line:
            break
        try:
            size = int(size_line.split(b";")[0].strip(), 16)
        except ValueError:
            break
        if size == 0:
            reader.read_until(b"\r\n")
            break
        body += reader.read_exactly(size)
        reader.read_exactly(2)                         
    return body

def get_destination(head_lines):
    first_line = head_lines[0].decode("latin-1")
    parts = first_line.split(" ")
    target = parts[1] if len(parts) > 1 else ""
    host_port, path = "", "/"
    if target.startswith("http://"):
        rest = target[len("http://"):]
        slash = rest.find("/")
        host_port = rest if slash == -1 else rest[:slash]
        path = "/" if slash == -1 else rest[slash:]
    else:
        path = target
        for line in head_lines[1:]:
            text = line.decode("latin-1")
            if text.lower().startswith("host:"):
                host_port = text.split(":", 1)[1].strip()
                break
    if ":" in host_port:
        host, port = host_port.split(":", 1)
        return host, int(port), path
    return host_port, 80, path


def build_request_bytes(head_lines, body, extra_headers):
    """Rearma la request agregando/reemplazando headers (para el servidor)."""
    lines = [head_lines[0]]
    for line in head_lines[1:]:
        name = line.split(b":", 1)[0].lower()
        if name in {k.lower().encode("latin-1") for k in extra_headers}:
            continue                                   # lo reemplazaremos abajo
        lines.append(line)
    for k, v in extra_headers.items():
        lines.append(f"{k}: {v}".encode("latin-1"))
    return b"\r\n".join(lines) + b"\r\n\r\n" + body


def is_blocked(host, path, blocked_list, port=None):
    candidates = [(host + path).rstrip("/")]
    if port is not None:
        candidates.append((f"{host}:{port}" + path).rstrip("/"))
    for entry in blocked_list:
        entry_clean = entry.rstrip("/")
        if "/" in entry_clean:
            for requested in candidates:
                if requested == entry_clean or requested.startswith(entry_clean + "/"):
                    return True
        else:
            if host == entry_clean or f"{host}:{port}" == entry_clean:
                return True
    return False


def guess_content_type(path):
    lower = path.lower()
    if lower.endswith((".jpg", ".jpeg")):
        return "image/jpeg"
    if lower.endswith(".png"):
        return "image/png"
    if lower.endswith(".gif"):
        return "image/gif"
    return "application/octet-stream"


def build_403_response():
    html = (
        "<!DOCTYPE html><html><head><meta charset='utf-8'>"
        "<title>403 Prohibido</title></head>"
        "<body style='text-align:center;font-family:sans-serif'>"
        "<h1>403 - Sitio bloqueado por el proxy</h1>"
        f"<img src='{IMG_PATH}' alt='bloqueado' style='max-width:400px'>"
        "</body></html>"
    ).encode("utf-8")
    head = (f"HTTP/1.1 403 Forbidden\r\nContent-Type: text/html; charset=utf-8\r\n"
            f"Content-Length: {len(html)}\r\nConnection: close\r\n\r\n").encode("latin-1")
    return head + html


def build_image_response(image_path):
    try:
        with open(image_path, "rb") as fh:
            data = fh.read()
        status, ctype = "200 OK", guess_content_type(image_path)
    except OSError:
        data, status, ctype = b"imagen no encontrada", "404 Not Found", "text/plain"
    head = (f"HTTP/1.1 {status}\r\nContent-Type: {ctype}\r\n"
            f"Content-Length: {len(data)}\r\nConnection: close\r\n\r\n").encode("latin-1")
    return head + data


def apply_forbidden_words(body, forbidden_words):
    for pair in forbidden_words:
        for word_a, word_b in pair.items():
            body = body.replace(word_a.encode("utf-8"), word_b.encode("utf-8"))
    return body


def rebuild_response(head_lines, body):
    new_lines = [head_lines[0]]
    for line in head_lines[1:]:
        low = line.lower()
        if low.startswith(b"content-length:") or low.startswith(b"transfer-encoding:"):
            continue
        new_lines.append(line)
    new_lines.append(f"Content-Length: {len(body)}".encode("latin-1"))
    return b"\r\n".join(new_lines) + b"\r\n\r\n" + body


def handle_client(client_socket, config, recv_buffer):
    blocked_list = config.get("blocked", [])
    image_path = config.get("blocked_image", "gato.jpg")
    user = config.get("user", "Anonimo")
    forbidden_words = config.get("forbidden_words", [])

    # 1) leemos la request del cliente con buffer chico
    client_reader = SocketReader(client_socket, recv_buffer)
    parsed = receive_http_message(client_reader, is_request=True)
    if parsed is None:
        return
    req_head_lines, req_body = parsed[2], parsed[1]

    host, port, path = get_destination(req_head_lines)

    if path == IMG_PATH:
        client_socket.sendall(build_image_response(image_path))
        return

    if is_blocked(host, path, blocked_list, port):
        print(f" -> [BLOQUEADO] {host}:{port}{path} -> 403")
        client_socket.sendall(build_403_response())
        return

    # 2) armamos la request para el servidor (header + sin gzip + cierre limpio)
    request = build_request_bytes(req_head_lines, req_body, {
        "X-ElQuePregunta": user,
        "Connection": "close",
        "Accept-Encoding": "identity",
    })
    print(f" -> reenviando a {host}:{port}{path}  (recv_buffer={recv_buffer})")

    origin_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    origin_socket.settimeout(10)
    try:
        origin_socket.connect((host, port))
        origin_socket.sendall(request)
        # 3) leemos la respuesta del servidor, tambien con buffer chico
        origin_reader = SocketReader(origin_socket, recv_buffer)
        resp = receive_http_message(origin_reader, is_request=False)
    except OSError as error:
        print(f"    [ERROR] {host}:{port} ({error})")
        client_socket.sendall(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
        origin_socket.close()
        return
    finally:
        origin_socket.close()

    if resp is None:
        return
    resp_head_lines, resp_body = resp[2], resp[1]

    # 4) reemplazo de palabras + Content-Length recalculado
    resp_body = apply_forbidden_words(resp_body, forbidden_words)
    client_socket.sendall(rebuild_response(resp_head_lines, resp_body))
    print(f"    [OK] {len(resp_body)} bytes de body enviados al cliente")


def main():
    config_path = sys.argv[1] if len(sys.argv) > 1 else "config.json"
    with open(config_path) as fh:
        config = json.load(fh)
    host = config.get("host", "0.0.0.0")
    port = config.get("port", 8000)
    recv_buffer = config.get("recv_buffer", 4096)     # <-- baje a 50 para el test

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((host, port))
    server_socket.listen(5)
    print(f"Proxy FINAL en {host}:{port}  |  recv_buffer={recv_buffer}")

    try:
        while True:
            client_socket, _ = server_socket.accept()
            try:
                handle_client(client_socket, config, recv_buffer)
            except Exception as error:
                print(f"    [EXC] {error}")
            finally:
                client_socket.close()
    except KeyboardInterrupt:
        print("\nCerrando proxy...")
    finally:
        server_socket.close()


if __name__ == "__main__":
    main()