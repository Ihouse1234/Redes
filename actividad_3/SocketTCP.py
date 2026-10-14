import socket
import random
import time
import sys


def _dbg(*args):
    # el modo debug SIEMPRE escribe en stderr, para no contaminar stdout
    # (el servidor escribe el archivo recibido en stdout)
    if DEBUG:
        print(*args, file=sys.stderr)

# --- Modo DEBUG y simulacion de perdidas "a mano" (para el informe) ---
# Si no puede usar netem, ponga SIMULAR_PERDIDA_RATE > 0 (ej: 0.2 = 20%).
# Como TODO segmento sale por _send(), descartar envios al azar simula
# perdida en AMBAS direcciones (cada extremo descarta sus propios envios).
DEBUG = True
SIMULAR_PERDIDA_RATE = 0.0        


class SocketTCP:
    HEADER_SIZE = 7                       # 1(SYN)+1(ACK)+1(FIN)+4(SEQ)
    MAX_DATA = 16                         
    UDP_BUFF = HEADER_SIZE + MAX_DATA     
    TIMEOUT = 1.0                         # timeout fijo de Stop & Wait (seg)

    def __init__(self):
        # Constructor SIN parametros: se invoca como SocketTCP().
        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.destination_address = None   # contraparte (connect/accept)
        self.bind_address = None          # direccion propia (bind)
        self.seq = 0                       # numero de secuencia actual

        # estado de recv() entre llamadas (paso 5):
        self.bytes_restantes = 0          # cuanto falta del mensaje actual
        self.buffer_datos = b""           # datos recibidos aun no entregados

        # caso borde del handshake (paso 6): si el ultimo ACK se pierde, el
        # primer segmento de datos llega a accept(); lo guardamos aqui para
        # que la primera llamada a recv() lo consuma y no se pierda.
        self.pending_segment = None

    #  Envio con simulacion opcional de perdida (para debug/informe)
    def _send(self, segment, address):
        if SIMULAR_PERDIDA_RATE > 0 and random.random() < SIMULAR_PERDIDA_RATE:
            if DEBUG:
                p = self.parse_segment(segment)
                _dbg(f"   [perdida-simulada] se descarta envio "
                     f"syn={p['syn']} ack={p['ack']} fin={p['fin']} seq={p['seq']}")
            return                         # "perdemos" el segmento
        self.udp_socket.sendto(segment, address)

    @staticmethod
    def parse_segment(segment):
        return {
            "syn":  segment[0],
            "ack":  segment[1],
            "fin":  segment[2],
            "seq":  int.from_bytes(segment[3:7], "big"),
            "data": segment[7:],
        }

    @staticmethod
    def create_segment(segment_dict):
        syn  = segment_dict.get("syn", 0)
        ack  = segment_dict.get("ack", 0)
        fin  = segment_dict.get("fin", 0)
        seq  = segment_dict.get("seq", 0)
        data = segment_dict.get("data", b"")
        header = bytes([syn, ack, fin]) + seq.to_bytes(4, "big")
        return header + data

    def bind(self, address):
        self.bind_address = address
        self.udp_socket.bind(address)

    # ----- lado CLIENTE -----
    def connect(self, address):
        self.destination_address = address
        x = random.randint(0, 100)
        self.seq = x

        syn = self.create_segment({"syn": 1, "seq": x})
        self.udp_socket.settimeout(self.TIMEOUT)

        # enviar SYN y esperar SYN+ACK; retransmitir SYN si hay timeout
        while True:
            _dbg(f"[connect] --> SYN(seq={x})")
            self._send(syn, self.destination_address)
            try:
                respuesta, server_new_address = self.udp_socket.recvfrom(self.UDP_BUFF)
            except socket.timeout:
                _dbg("[connect] timeout esperando SYN+ACK, reenvio SYN")
                continue
            parsed = self.parse_segment(respuesta)
            if parsed["syn"] == 1 and parsed["ack"] == 1 and parsed["seq"] == x + 1:
                break

        self.destination_address = server_new_address   # nuevo puerto del server
        self.seq = x + 1
        _dbg(f"[connect] <-- SYN+ACK(seq={x+1}) desde {server_new_address}")

        # enviar ACK final. Si se pierde, el server lo recupera cuando le llegue el primer segmento de datos (ver accept + recv).
        ack = self.create_segment({"ack": 1, "seq": x + 2})
        self._send(ack, self.destination_address)
        self.seq = x + 2
        _dbg(f"[connect] --> ACK(seq={x+2}) handshake completo")

    # ----- lado SERVIDOR -----
    def accept(self):
        # esperar un SYN
        self.udp_socket.settimeout(None)
        while True:
            segmento, client_address = self.udp_socket.recvfrom(self.UDP_BUFF)
            parsed = self.parse_segment(segmento)
            if parsed["syn"] == 1 and parsed["ack"] == 0:
                break
        x = parsed["seq"]
        _dbg(f"[accept] <-- SYN(seq={x}) de {client_address}")

        # socket de conexion en puerto NUEVO
        connection = SocketTCP()
        host = self.bind_address[0]
        connection.udp_socket.bind((host, 0))
        connection.bind_address = connection.udp_socket.getsockname()
        connection.destination_address = client_address
        connection.seq = x + 1

        syn_ack = self.create_segment({"syn": 1, "ack": 1, "seq": x + 1})
        connection.udp_socket.settimeout(self.TIMEOUT)

        while True:
            _dbg(f"[accept] --> SYN+ACK(seq={x+1}) desde {connection.bind_address}")
            connection._send(syn_ack, client_address)
            try:
                respuesta, addr = connection.udp_socket.recvfrom(self.UDP_BUFF)
            except socket.timeout:
                _dbg("[accept] timeout esperando ACK, reenvio SYN+ACK")
                continue
            p = self.parse_segment(respuesta)
            if p["ack"] == 1 and p["fin"] == 0 and len(p["data"]) == 0 and p["seq"] == x + 2:
                _dbg(f"[accept] <-- ACK(seq={x+2}) handshake completo")
                break
            if p["seq"] == x + 2 and len(p["data"]) > 0:
                # llego el primer segmento de datos: el ACK se habia perdido
                _dbg("[accept] llego 1er dato (ACK perdido); handshake OK")
                connection.pending_segment = respuesta
                break

        connection.seq = x + 2
        return connection, connection.bind_address

    def _send_and_wait_ack(self, data_bytes):
        seq = self.seq
        segmento = self.create_segment({"seq": seq, "data": data_bytes})
        expected_ack = seq + len(data_bytes)

        self.udp_socket.settimeout(self.TIMEOUT)
        while True:
            self._send(segmento, self.destination_address)
            try:
                respuesta, _ = self.udp_socket.recvfrom(self.UDP_BUFF)
            except socket.timeout:
                _dbg(f"   [send] timeout esperando ACK(seq={expected_ack}), retransmito")
                continue
            parsed = self.parse_segment(respuesta)
            if parsed["ack"] == 1 and parsed["seq"] == expected_ack:
                break
        self.seq = expected_ack

    def send(self, message):
        # (1) primer segmento: el largo del mensaje
        self._send_and_wait_ack(str(len(message)).encode())
        # (2) el contenido en trozos <= 16 bytes
        for i in range(0, len(message), self.MAX_DATA):
            self._send_and_wait_ack(message[i:i + self.MAX_DATA])

    def _recv_in_order(self):
        # si el handshake dejo un segmento pendiente (caso borde), usarlo primero
        if self.pending_segment is not None:
            segmento = self.pending_segment
            self.pending_segment = None
            parsed = self.parse_segment(segmento)
            if parsed["seq"] == self.seq:
                data = parsed["data"]
                self.seq += len(data)
                ack = self.create_segment({"ack": 1, "seq": self.seq})
                self._send(ack, self.destination_address)
                return data

        self.udp_socket.settimeout(None)       # el receptor bloquea esperando
        while True:
            segmento, addr = self.udp_socket.recvfrom(self.UDP_BUFF)
            parsed = self.parse_segment(segmento)
            if parsed["seq"] == self.seq:       # segmento esperado
                data = parsed["data"]
                self.seq += len(data)
                self.destination_address = addr
                ack = self.create_segment({"ack": 1, "seq": self.seq})
                self._send(ack, addr)
                return data
            else:                               # duplicado: re-ACK
                ack = self.create_segment({"ack": 1, "seq": self.seq})
                self._send(ack, addr)

    def recv(self, buff_size):
        if self.bytes_restantes == 0:          # mensaje nuevo: leer el largo
            self.bytes_restantes = int(self._recv_in_order().decode())
            self.buffer_datos = b""

        objetivo = min(self.bytes_restantes, buff_size)
        while len(self.buffer_datos) < objetivo:
            self.buffer_datos += self._recv_in_order()

        entregado = self.buffer_datos[:objetivo]
        self.buffer_datos = self.buffer_datos[objetivo:]
        self.bytes_restantes -= objetivo
        return entregado

    # ----- Host A: inicia el cierre -----
    def close(self):
        y = self.seq
        fin = self.create_segment({"fin": 1, "seq": y})
        self.udp_socket.settimeout(self.TIMEOUT)

        got_ack = False
        got_fin = False
        z = None
        intentos = 0

        # Hasta 3 timeouts esperando ACK(y+1) y FIN(z) de la contraparte.
        while intentos < 3 and not got_fin:
            try:
                if not got_ack:
                    _dbg(f"[close] --> FIN(seq={y})")
                    self._send(fin, self.destination_address)
                respuesta, _ = self.udp_socket.recvfrom(self.UDP_BUFF)
                p = self.parse_segment(respuesta)
                if p["ack"] == 1 and p["seq"] == y + 1:
                    got_ack = True
                    _dbg(f"[close] <-- ACK(seq={y+1})")
                    continue                   # ahora esperamos el FIN
                if p["fin"] == 1:
                    z = p["seq"]
                    got_fin = True
                    _dbg(f"[close] <-- FIN(seq={z})")
            except socket.timeout:
                intentos += 1
                _dbg(f"[close] timeout {intentos}/3")

        if got_fin:
            # reenviar el ultimo ACK 3 veces, esperando timeout entre envios
            ack = self.create_segment({"ack": 1, "seq": z + 1})
            for _ in range(3):
                _dbg(f"[close] --> ACK(seq={z+1})")
                self._send(ack, self.destination_address)
                time.sleep(self.TIMEOUT)
        else:
            _dbg("[close] 3 timeouts sin respuesta: asumo cierre")

        self.udp_socket.close()

    # ----- Host B: continua el cierre al recibir un FIN -----
    def recv_close(self):
        # esperar el FIN de A (bloqueante)
        self.udp_socket.settimeout(None)
        while True:
            respuesta, addr = self.udp_socket.recvfrom(self.UDP_BUFF)
            p = self.parse_segment(respuesta)
            if p["fin"] == 1:
                y = p["seq"]
                self.destination_address = addr
                break
        _dbg(f"[recv_close] <-- FIN(seq={y})")

        z = self.seq
        ack = self.create_segment({"ack": 1, "seq": y + 1})
        fin = self.create_segment({"fin": 1, "seq": z})

        self.udp_socket.settimeout(self.TIMEOUT)
        intentos = 0
        # enviar ACK(y+1)+FIN(z) y esperar ACK(z+1); hasta 3 timeouts
        while intentos < 3:
            _dbg(f"[recv_close] --> ACK(seq={y+1}) + FIN(seq={z})")
            self._send(ack, self.destination_address)
            self._send(fin, self.destination_address)
            try:
                respuesta, _ = self.udp_socket.recvfrom(self.UDP_BUFF)
                p = self.parse_segment(respuesta)
                if p["ack"] == 1 and p["seq"] == z + 1:
                    _dbg(f"[recv_close] <-- ACK(seq={z+1}) cierre OK")
                    break
            except socket.timeout:
                intentos += 1
                _dbg(f"[recv_close] timeout {intentos}/3")

        self.udp_socket.close()