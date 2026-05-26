import math
import serial
import serial.tools.list_ports


VELOCIDADE_MAX = 10.0


def _listar_portas():
    return serial.tools.list_ports.comports()


def _encontrar_porta():
    for p in _listar_portas():
        desc = (p.description + (p.manufacturer or "")).lower()
        if any(k in desc for k in ("arduino", "ch340", "ch341", "cp210", "ftdi")):
            return p.device
    return None


class Vento:
    def __init__(self, porta=None):
        self.direcao = 0.0
        self.velocidade = 0.0
        self.ldr = 0.5
        self.ldr_disponivel = False
        self._angulo = 0.0
        self._serial = None

        porta = porta or _encontrar_porta()
        if porta:
            try:
                self._serial = serial.Serial(porta, 9600, timeout=0)
                print(f"Arduino em {porta}")
            except Exception as e:
                print(f"Erro ao abrir {porta}: {e}")
                self._serial = None

    @property
    def conectado(self):
        return self._serial is not None

    def atualizar(self, delta_time):
        if self._serial:
            try:
                linha = self._serial.readline().decode().strip()
                if linha:
                    if "," in linha:
                        partes = linha.split(",")
                        try:
                            self.ldr += (int(partes[0]) / 1023.0 - self.ldr) * 0.05
                            self.ldr_disponivel = True
                            valor_vento = float(partes[1])
                        except (ValueError, IndexError):
                            valor_vento = 0.0
                    else:
                        try:
                            valor_vento = float(linha)
                        except ValueError:
                            valor_vento = 0.0
                    self.velocidade += (min(valor_vento / VELOCIDADE_MAX, 1.0) - self.velocidade) * 0.1
            except Exception:
                pass
        else:
            self.velocidade = 0.0

        self._angulo += delta_time * 0.4
        self.direcao = math.sin(self._angulo) * self.velocidade

    def enviar_cor(self, r, g, b):
        if self._serial:
            try:
                self._serial.write(f"{int(r)},{int(g)},{int(b)}\n".encode())
            except Exception:
                pass
