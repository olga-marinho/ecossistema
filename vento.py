import math
import json
import random
import serial
import serial.tools.list_ports

try:
    import paho.mqtt.client as mqtt
except Exception:
    mqtt = None


VELOCIDADE_MAX = 10.0


def _listar_portas():
    return serial.tools.list_ports.comports()


def _eh_porta_compativel(porta_info):
    desc = (porta_info.description + (porta_info.manufacturer or "")).lower()
    return any(k in desc for k in ("arduino", "ch340", "ch341", "cp210", "ftdi", "usb serial"))


def _encontrar_portas(max_portas=2):
    portas = []
    for p in _listar_portas():
        if _eh_porta_compativel(p):
            portas.append(p.device)
        if len(portas) >= max_portas:
            break
    return portas


def _extrair_numero_payload(payload_str, chaves):
    texto = (payload_str or "").strip()

    if not texto:
        return None

    try:
        dado = json.loads(texto)
        if isinstance(dado, dict):
            for chave in chaves:
                if chave in dado:
                    return float(dado[chave])
    except Exception:
        pass

    try:
        return float(texto)
    except ValueError:
        pass

    if "," in texto:
        primeira = texto.split(",", 1)[0].strip()
        try:
            return float(primeira)
        except ValueError:
            return None

    return None


class Vento:
    def __init__(
        self,
        porta_esp32=None,
        porta_anemometro=None,
        modo_comunicacao="serial",
        mqtt_host="broker.emqx.io",
        mqtt_port=1883,
        mqtt_username="",
        mqtt_password="",
        mqtt_topic_base="ecossistema",
    ):
        self.direcao = 0.0
        self.velocidade = 0.0
        self.ldr = 0.5
        self.ldr_disponivel = False
        self._angulo = 0.0
        self._modo_comunicacao = (modo_comunicacao or "serial").strip().lower()
        self._serial_esp32 = None
        self._serial_anemometro = None
        self._mqtt_client = None
        self._mqtt_conectado = False
        self._mqtt_host = mqtt_host
        self._mqtt_port = int(mqtt_port)
        self._mqtt_username = mqtt_username or ""
        self._mqtt_password = mqtt_password or ""
        self._mqtt_topic_base = (mqtt_topic_base or "ecossistema").strip().rstrip("/")
        self._topico_ldr = f"{self._mqtt_topic_base}/sensor/ldr"
        self._topico_wind = f"{self._mqtt_topic_base}/sensor/wind"
        self._topico_led = f"{self._mqtt_topic_base}/led/rgb"

        detectadas = _encontrar_portas(max_portas=4)

        if self._modo_comunicacao == "serial" and porta_esp32 is None and detectadas:
            porta_esp32 = detectadas[0]

        if porta_anemometro is None:
            for p in detectadas:
                if p != porta_esp32:
                    porta_anemometro = p
                    break

        if self._modo_comunicacao == "serial" and porta_esp32:
            try:
                self._serial_esp32 = serial.Serial(porta_esp32, 9600, timeout=0)
                print(f"ESP32 em {porta_esp32}")
            except Exception as e:
                print(f"Erro ao abrir ESP32 em {porta_esp32}: {e}")
                self._serial_esp32 = None

        if porta_anemometro:
            try:
                self._serial_anemometro = serial.Serial(porta_anemometro, 9600, timeout=0)
                print(f"Anemometro em {porta_anemometro}")
            except Exception as e:
                print(f"Erro ao abrir anemometro em {porta_anemometro}: {e}")
                self._serial_anemometro = None

        if self._modo_comunicacao == "mqtt":
            self._iniciar_mqtt()

    def _iniciar_mqtt(self):
        if mqtt is None:
            print("MQTT indisponivel: instale paho-mqtt")
            return

        client_id = f"ecossistema_py_{random.randint(1000, 999999)}"
        self._mqtt_client = mqtt.Client(client_id=client_id)
        self._mqtt_client.on_connect = self._on_mqtt_connect
        self._mqtt_client.on_disconnect = self._on_mqtt_disconnect
        self._mqtt_client.on_message = self._on_mqtt_message

        if self._mqtt_username:
            self._mqtt_client.username_pw_set(self._mqtt_username, self._mqtt_password)

        try:
            self._mqtt_client.connect(self._mqtt_host, self._mqtt_port, keepalive=30)
            print(f"MQTT em {self._mqtt_host}:{self._mqtt_port}")
        except Exception as e:
            print(f"Erro ao ligar MQTT em {self._mqtt_host}:{self._mqtt_port}: {e}")
            self._mqtt_client = None
            self._mqtt_conectado = False

    def _on_mqtt_connect(self, client, userdata, flags, reason_code, properties=None):
        codigo = getattr(reason_code, "value", reason_code)
        if codigo == 0:
            self._mqtt_conectado = True
            client.subscribe(self._topico_ldr)
            client.subscribe(self._topico_wind)
        else:
            self._mqtt_conectado = False

    def _on_mqtt_disconnect(self, client, userdata, reason_code, properties=None):
        self._mqtt_conectado = False

    def _on_mqtt_message(self, client, userdata, msg):
        topico = str(msg.topic)
        payload = msg.payload.decode(errors="ignore").strip()

        if topico == self._topico_ldr:
            valor = _extrair_numero_payload(payload, ("ldr", "value"))
            if valor is not None:
                self._atualizar_ldr_valor(valor)
            return

        if topico == self._topico_wind:
            valor = _extrair_numero_payload(payload, ("wind", "value"))
            if valor is not None:
                self._atualizar_vento_valor(valor)
            return

        self._processar_linha(payload, "mqtt")

    @property
    def conectado(self):
        if self._modo_comunicacao == "mqtt":
            return self._mqtt_conectado
        return self._serial_esp32 is not None

    @property
    def anemometro_conectado(self):
        return self._serial_anemometro is not None

    def _atualizar_ldr_valor(self, valor):
        if valor is None:
            return

        escala = 4095.0 if valor > 1023 else 1023.0
        normalizado = max(0.0, min(1.0, valor / escala))
        self.ldr += (normalizado - self.ldr) * 0.05
        self.ldr_disponivel = True

    def _atualizar_vento_valor(self, valor):
        if valor is None:
            return

        alvo = min(max(valor / VELOCIDADE_MAX, 0.0), 1.0)
        self.velocidade += (alvo - self.velocidade) * 0.1

    def _processar_linha(self, linha, origem):
        if not linha:
            return

        linha = linha.strip()
        if not linha:
            return

        upper = linha.upper()

        if upper.startswith("LDR,"):
            try:
                self._atualizar_ldr_valor(int(linha.split(",", 1)[1]))
            except ValueError:
                pass
            return

        if upper.startswith("WIND,"):
            try:
                self._atualizar_vento_valor(float(linha.split(",", 1)[1]))
            except ValueError:
                pass
            return

        if "," in linha:
            partes = linha.split(",")
            ldr_valor = None
            vento_valor = None
            if len(partes) >= 2:
                try:
                    ldr_valor = int(partes[0])
                except ValueError:
                    ldr_valor = None
                try:
                    vento_valor = float(partes[1])
                except ValueError:
                    vento_valor = None
            self._atualizar_ldr_valor(ldr_valor)
            self._atualizar_vento_valor(vento_valor)
            return

        if origem == "esp32":
            try:
                self._atualizar_ldr_valor(int(linha))
            except ValueError:
                pass
            return

        if origem == "anemometro":
            try:
                self._atualizar_vento_valor(float(linha))
            except ValueError:
                pass

    def atualizar(self, delta_time, ler_arduino=True):
        if ler_arduino:
            if self._modo_comunicacao == "mqtt" and self._mqtt_client is not None:
                try:
                    self._mqtt_client.loop(timeout=0.001)
                except Exception:
                    self._mqtt_conectado = False

            if self._modo_comunicacao == "serial" and self._serial_esp32:
                try:
                    for _ in range(4):
                        linha = self._serial_esp32.readline().decode(errors="ignore").strip()
                        if not linha:
                            break
                        self._processar_linha(linha, "esp32")
                except Exception:
                    pass

            if self._serial_anemometro:
                try:
                    for _ in range(4):
                        linha = self._serial_anemometro.readline().decode(errors="ignore").strip()
                        if not linha:
                            break
                        self._processar_linha(linha, "anemometro")
                except Exception:
                    pass
        else:
            self.ldr_disponivel = False
            self.velocidade += (0.0 - self.velocidade) * 0.1

        self._angulo += delta_time * 0.4
        self.direcao = math.sin(self._angulo) * self.velocidade

    def enviar_cor(self, r, g, b):
        if self._modo_comunicacao == "mqtt" and self._mqtt_client is not None and self._mqtt_conectado:
            try:
                self._mqtt_client.publish(self._topico_led, f"{int(r)},{int(g)},{int(b)}")
            except Exception:
                pass
            return

        if self._serial_esp32:
            try:
                self._serial_esp32.write(f"{int(r)},{int(g)},{int(b)}\n".encode())
            except Exception:
                pass

    def fechar(self):
        if self._mqtt_client is not None:
            try:
                self._mqtt_client.disconnect()
            except Exception:
                pass

        if self._serial_esp32 is not None:
            try:
                self._serial_esp32.close()
            except Exception:
                pass

        if self._serial_anemometro is not None:
            try:
                self._serial_anemometro.close()
            except Exception:
                pass
