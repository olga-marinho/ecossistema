import os
import random
import arcade
import pyglet
import pyglet.font as pyglet_font

from flor import Flor
from vento import Vento
from detector import Detector
from insetos import (
    carregar_insetos_iniciais,
    converter_insetos_estado,
    obter_configs_estado,
    gerar_inseto_por_config
)
from plantas import criar_plantas, Planta
from relva import Relva


PROPORCAO_ORIGINAL       = 1440 / 284
LARGURA_BASE_JANELA      = 1200
ESCALA_LARGURA_ECRA      = 0.42
LARGURA_MIN_JANELA       = 640
NUM_POSES_MAX            = 5
FULLSCREEN_ALVO_LARGURA  = 9720
FULLSCREEN_ALVO_ALTURA   = 1920

MODO_COMUNICACAO         = os.getenv("MODO_COMUNICACAO", "mqtt").lower()
PORTA_ESP32              = os.getenv("PORTA_ESP32", "COM10")
PORTA_ANEMOMETRO         = os.getenv("PORTA_ANEMOMETRO", "COM9")
MQTT_BROKER              = os.getenv("MQTT_BROKER", "broker.emqx.io")
MQTT_PORTA               = int(os.getenv("MQTT_PORTA", "1883"))
MQTT_USER                = os.getenv("MQTT_USER", "")
MQTT_PASSWORD            = os.getenv("MQTT_PASSWORD", "")
MQTT_TOPIC_BASE          = os.getenv("MQTT_TOPIC_BASE", "ecossistema")

LIMITE_NOTURNO           = 0.5
FRASE                    = "SOMOS TODOS PARTE DO ECOSSISTEMA!"
VENTO_SIMULADO_TECLA     = 1.0
NOME_FONTE               = "Baste"

MOSTRAR_CAMERA_DEBUG     = True
TOLERANCIA_QUEDA_PESSOAS_FRAMES = 12


def _env_int(nome: str, padrao: int) -> int:
    try:
        return int(os.getenv(nome, str(padrao)))
    except (TypeError, ValueError):
        return int(padrao)


def _env_bool(nome: str, padrao: bool) -> bool:
    valor = os.getenv(nome)

    if valor is None:
        return bool(padrao)

    return valor.strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
        "sim",
        "s",
    }


def _env_float(nome: str, padrao: float) -> float:
    try:
        return float(os.getenv(nome, str(padrao)))
    except (TypeError, ValueError):
        return float(padrao)


_render_largura_raw = os.getenv("RENDER_INTERNO_LARGURA")
_render_altura_raw = os.getenv("RENDER_INTERNO_ALTURA")

RENDER_INTERNO_ATIVO = _env_bool(
    "RENDER_INTERNO_ATIVO",
    (_render_largura_raw is not None) or (_render_altura_raw is not None)
)

RENDER_INTERNO_LARGURA = max(
    1,
    _env_int("RENDER_INTERNO_LARGURA", 1440)
)

RENDER_INTERNO_ALTURA = max(
    1,
    _env_int("RENDER_INTERNO_ALTURA", 284)
)


T_FUNDO_S = max(
    0.1,
    _env_float(
        "T_FUNDO_S",
        _env_float("INTERVALO_ATUALIZACAO_FUNDO_SEGUNDOS", 10.0)
    )
)

T_LED_S = max(
    0.1,
    _env_float(
        "T_LED_S",
        _env_float("INTERVALO_ENVIO_LED_SEGUNDOS", 10.0)
    )
)

SUAV_FUNDO = max(0.0, min(1.0, _env_float("SUAV_FUNDO", 0.12)))
SUAV_LED = max(0.0, min(1.0, _env_float("SUAV_LED", 0.35)))


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _obter_ecra_maior():
    display = pyglet.display.get_display()
    screens = display.get_screens()

    melhor = max(screens, key=lambda s: s.width * s.height)

    print(f"[INFO] Ecrãs disponíveis: {[(s.width, s.height) for s in screens]}")
    print(f"[INFO] Ecrã escolhido: {melhor.width}x{melhor.height} em ({melhor.x},{melhor.y})")

    return melhor


def _calcular_dimensoes_janela(
    largura_ecra: int,
    altura_ecra: int
) -> tuple[int, int]:
    if ESCALA_LARGURA_ECRA is None:
        largura_janela = LARGURA_BASE_JANELA
    else:
        largura_janela = int(largura_ecra * ESCALA_LARGURA_ECRA)

    largura_janela = max(LARGURA_MIN_JANELA, largura_janela)
    largura_janela = min(largura_janela, largura_ecra)

    altura_janela = int(largura_janela / PROPORCAO_ORIGINAL)

    if altura_janela > altura_ecra:
        altura_janela = altura_ecra
        largura_janela = int(altura_janela * PROPORCAO_ORIGINAL)

    return largura_janela, altura_janela


class Ecossistema(arcade.Window):

    def __init__(self):

        diretorio = os.path.dirname(os.path.abspath(__file__))

        font_path = os.path.join(
            diretorio,
            "assets",
            "font",
            "BasteA-Medium.otf"
        )

        if os.path.exists(font_path):
            pyglet_font.add_file(font_path)

        ecra = _obter_ecra_maior()
        largura_ecra = ecra.width
        altura_ecra = ecra.height

        usar_fullscreen_alvo = (
            largura_ecra == FULLSCREEN_ALVO_LARGURA
            and altura_ecra == FULLSCREEN_ALVO_ALTURA
        )

        if usar_fullscreen_alvo:
            super().__init__(
                largura_ecra,
                altura_ecra,
                FRASE,
                resizable=False,
                fullscreen=True,
                screen=ecra,
            )
        else:
            largura_janela, altura_janela = _calcular_dimensoes_janela(
                largura_ecra,
                altura_ecra
            )

            super().__init__(
                largura_janela,
                altura_janela,
                FRASE,
                resizable=False,
                style=pyglet.window.Window.WINDOW_STYLE_BORDERLESS,
            )

            self.set_location(
                ecra.x + (largura_ecra - largura_janela) // 2,
                ecra.y + (altura_ecra - altura_janela) // 2
            )

        self._largura_tela = self.width
        self._altura_tela = self.height

        if RENDER_INTERNO_ATIVO:
            self.largura = RENDER_INTERNO_LARGURA
            self.altura = RENDER_INTERNO_ALTURA
        else:
            self.largura = self._largura_tela
            self.altura = self._altura_tela

        self._escala_render_x = (
            self._largura_tela / max(self.largura, 1)
        )

        self._escala_render_y = (
            self._altura_tela / max(self.altura, 1)
        )

        # Compatibilidade entre versoes do Arcade.
        if hasattr(arcade, "set_viewport"):
            arcade.set_viewport(
                0,
                self.largura,
                0,
                self.altura
            )
        elif hasattr(self, "set_viewport"):
            self.set_viewport(
                0,
                self.largura,
                0,
                self.altura
            )
        else:
            self.ctx.projection_2d = (
                0,
                self.largura,
                0,
                self.altura
            )

        if RENDER_INTERNO_ATIVO:
            print(
                "[INFO] Render interno ativo: "
                f"{self.largura}x{self.altura} "
                f"-> ecrã {self._largura_tela}x{self._altura_tela}"
            )

        margem_referencia = max(
            10,
            int(min(self._largura_tela, self._altura_tela) * 0.012)
        )

        escala_visual = max(
            1.0,
            self._escala_render_x,
            self._escala_render_y
        )

        self.margem = max(
            2,
            int(margem_referencia / escala_visual)
        )

        self.tamanho_texto = self._calcular_tamanho_texto()

        self.vento = Vento(
            porta_esp32=PORTA_ESP32,
            porta_anemometro=PORTA_ANEMOMETRO,
            modo_comunicacao=MODO_COMUNICACAO,
            mqtt_host=MQTT_BROKER,
            mqtt_port=MQTT_PORTA,
            mqtt_username=MQTT_USER,
            mqtt_password=MQTT_PASSWORD,
            mqtt_topic_base=MQTT_TOPIC_BASE
        )

        self.detector = Detector(
            num_poses=NUM_POSES_MAX,
            mostrar_camera_debug=MOSTRAR_CAMERA_DEBUG
        )

        self.flores: list[Flor] = []

        self.estado_insetos = "padrao"

        self.insetos = carregar_insetos_iniciais(
            self.altura,
            self.largura,
            self.estado_insetos
        )

        self.insetos_extras_ativos = []

        self._indice_config_inseto_por_estado = {
            "padrao": 0,
            "noturno": 0,
        }

        self.estado_plantas = "padrao"

        self._num_plantas_atual = 2

        self.plantas: list[Planta] = criar_plantas(
            self.altura,
            self.largura,
            self.estado_plantas,
            self._num_plantas_atual
        )

        self.relva = Relva(
            self.largura,
            self.altura
        )

        self._claridade_alvo = self._claridade()
        self._claridade_atual = self._claridade_alvo
        self._t_fundo = T_FUNDO_S
        self._t_led = T_LED_S
        self._cor_led = None
        self._num_pessoas_alvo = 0
        self._frames_queda_pessoas = 0

        self._ler_arduino = True
        self._vento_simulado = 0.0

    def _flores_ativas(self):
        return [
            f for f in self.flores
            if not f.a_desaparecer
        ]

    def _calcular_tamanho_texto(self) -> int:

        largura_disponivel = (
            self.largura - self.margem * 2
        )

        if self._escala_render_y > 1.0:
            tamanho_referencia = max(
                90,
                min(260, int(self._altura_tela * 0.22))
            )

            tamanho = max(
                1,
                int(tamanho_referencia / self._escala_render_y)
            )
        else:
            tamanho = max(
                90,
                min(260, int(self.altura * 0.22))
            )

        while tamanho > 1:

            try:
                doc = arcade.Text(
                    FRASE,
                    x=0,
                    y=0,
                    font_size=tamanho,
                    font_name=NOME_FONTE,
                )

                if doc.content_width <= largura_disponivel:
                    return tamanho
            except Exception:
                pass

            tamanho -= 1

        return 1

    def _claridade(self) -> float:

        if self.vento.ldr_disponivel:

            return max(
                0.0,
                min(1.0, self.vento.ldr)
            )

        mouse_y = getattr(
            self,
            "_mouse_y",
            self.altura
        )

        return max(
            0.0,
            min(1.0, mouse_y / max(self.altura, 1))
        )

    def on_update(self, delta_time):

        self.vento.atualizar(
            delta_time,
            ler_arduino=self._ler_arduino
        )

        direcao_vento = (
            self._vento_simulado
            if self._vento_simulado
            else self.vento.direcao
        )

        pessoas = sorted(
            self.detector.detetar(),
            key=lambda p: p.x
        )
        pessoas_por_id = {p.id: p for p in pessoas}

        flores_ativas = [f for f in self.flores if not f.a_desaparecer]

        for flor in flores_ativas:
            p_id = getattr(flor, "pessoa_id", None)

            if p_id is None:
                par_ids = getattr(flor, "par_ids", None)
                if isinstance(par_ids, tuple) and len(par_ids) == 1:
                    p_id = par_ids[0]
                    flor.pessoa_id = p_id

            pessoa = pessoas_por_id.get(p_id)

            if pessoa is not None:
                flor.atualizar(pessoa.x * self.largura)

                if pessoa.cor is not None:
                    flor.atualizar_cor(pessoa.cor)
            else:
                flor.iniciar_desaparecimento()

        ids_com_flor = {
            getattr(f, "pessoa_id", None)
            for f in flores_ativas
            if not f.a_desaparecer
        }

        for pessoa in pessoas:
            if pessoa.id not in ids_com_flor:
                nova_flor = Flor(
                    pessoa.x * self.largura,
                    self.altura,
                    self.largura,
                    cor_rgb=pessoa.cor
                )
                nova_flor.pessoa_id = pessoa.id
                self.flores.append(nova_flor)

        ids_com_inseto = {
            getattr(i, "pessoa_id", None)
            for i in self.insetos_extras_ativos
        }

        for pessoa in pessoas:
            if pessoa.id not in ids_com_inseto:

                configs = obter_configs_estado(self.estado_insetos)
                idx_estado = self._indice_config_inseto_por_estado.get(self.estado_insetos, 0)
                item = configs[idx_estado % len(configs)]
                self._indice_config_inseto_por_estado[self.estado_insetos] = idx_estado + 1

                novo_inseto = gerar_inseto_por_config(item, self.altura, self.largura)
                novo_inseto.is_extra_ativo = True
                novo_inseto.pessoa_id = pessoa.id
                self.insetos.append(novo_inseto)
                self.insetos_extras_ativos.append(novo_inseto)
                ids_com_inseto.add(pessoa.id)

        for flor in self.flores:
            if flor.a_desaparecer:
                flor.atualizar(flor.x)

        self.flores = [f for f in self.flores if not f.removida]

        dist_min = self.largura * 0.0625
        for _ in range(3):
            ativas = [f for f in self.flores if not f.a_desaparecer]
            for i in range(len(ativas)):
                for j in range(i + 1, len(ativas)):
                    f1 = ativas[i]
                    f2 = ativas[j]
                    dx = f2.x - f1.x
                    if abs(dx) < dist_min:
                        if dx == 0:
                            dx = 0.1
                        sobreposicao = dist_min - abs(dx)
                        direcao = 1.0 if dx > 0 else -1.0
                        f1.x -= (sobreposicao / 2.0) * direcao
                        f2.x += (sobreposicao / 2.0) * direcao

        margem_tela = dist_min / 2
        for f in self.flores:
            if f.x < margem_tela:
                f.x = margem_tela
                if f.x_alvo < margem_tela:
                    f.x_alvo = margem_tela
            elif f.x > self.largura - margem_tela:
                f.x = self.largura - margem_tela
                if f.x_alvo > self.largura - margem_tela:
                    f.x_alvo = self.largura - margem_tela

        ids_pessoas_ativas = {p.id for p in pessoas}
        insetos_ativos = []
        for inseto in self.insetos_extras_ativos:
            ins_id = getattr(inseto, "pessoa_id", None)
            if ins_id is not None and ins_id not in ids_pessoas_ativas:
                inseto.marcado_para_sair = True
                inseto.is_extra_ativo = False
            else:
                insetos_ativos.append(inseto)
        self.insetos_extras_ativos = insetos_ativos

        novo_num_plantas = 2 + (len(ids_pessoas_ativas) // 2)

        plantas_ativas = [p for p in self.plantas if not p.a_desaparecer]

        while len(plantas_ativas) < novo_num_plantas:
            nova_planta = criar_plantas(
                self.altura,
                self.largura,
                self.estado_plantas,
                1
            )[0]
            self.plantas.append(nova_planta)
            plantas_ativas.append(nova_planta)

        while len(plantas_ativas) > novo_num_plantas:
            planta_a_remover = plantas_ativas.pop()
            planta_a_remover.iniciar_desaparecimento()

        self._num_plantas_atual = novo_num_plantas

        for planta in self.plantas:
            planta.atualizar()
            
        self.plantas = [p for p in self.plantas if not p.removida]

        for inseto in self.insetos:
            inseto.update(direcao_vento)

        self._t_fundo += delta_time
        if self._t_fundo >= T_FUNDO_S:
            self._t_fundo = 0.0
            self._claridade_alvo = self._claridade()

        self._claridade_atual = lerp(
            self._claridade_atual,
            self._claridade_alvo,
            SUAV_FUNDO
        )

        self._t_led += delta_time

        if (
            self._t_led >= T_LED_S
            and self.vento.conectado
            and self._ler_arduino
        ):
            self._t_led = 0.0

            cor = self.detector.cor_dos_torsos()

            if cor is not None:

                if self._cor_led is None:
                    self._cor_led = cor
                else:
                    self._cor_led = tuple(
                        int(lerp(self._cor_led[i], cor[i], SUAV_LED))
                        for i in range(3)
                    )

                self.vento.enviar_cor(*self._cor_led)

    def on_draw(self):

        t = self._claridade_atual

        novo_estado = (
            "noturno"
            if t < LIMITE_NOTURNO
            else "padrao"
        )


        if novo_estado != self.estado_insetos:

            self.estado_insetos = novo_estado

            self.insetos = converter_insetos_estado(
                self.insetos,
                self.altura,
                self.largura,
                self.estado_insetos
            )

            self.insetos_extras_ativos = [
                i for i in self.insetos
                if getattr(i, "is_extra_ativo", False)
            ]

        if novo_estado != self.estado_plantas:

            self.estado_plantas = novo_estado

            novas_plantas = []

            for planta_antiga in self.plantas:

                nova_planta = Planta(
                    planta_antiga.x,
                    self.altura,
                    self.largura,
                    self.estado_plantas
                )

                nova_planta.progresso_crescimento = (
                    planta_antiga.progresso_crescimento
                )
                
                nova_planta.a_desaparecer = planta_antiga.a_desaparecer
                nova_planta.folha_visivel = planta_antiga.folha_visivel

                nova_planta._atualizar_textura_planta()

                novas_plantas.append(
                    nova_planta
                )

            self.plantas = novas_plantas

        r = 0

        g = int(
            lerp(22, 116, t)
        )

        b = int(
            lerp(153, 255, t)
        )

        self.clear((r, g, b))

        arcade.Text(
            FRASE,
            self.margem,
            self.altura
            - self.margem
            - self.tamanho_texto,
            arcade.color.Color(
                0x3C,
                0xBE,
                0x00
            ),
            self.tamanho_texto,
            font_name=NOME_FONTE,
        ).draw()

        direcao_vento = (
            self._vento_simulado
            if self._vento_simulado
            else self.vento.direcao
        )


        for planta in self.plantas:
            planta.desenhar(direcao_vento)

        for flor in self.flores:
            flor.desenhar(direcao_vento)

        self.relva.desenhar(
            direcao_vento
        )

        self.insetos.draw()


    def on_key_press(self, symbol, modifiers):

        if symbol == arcade.key.K:

            self._ler_arduino = not self._ler_arduino

            estado = "ligada" if self._ler_arduino else "desligada"
            print(f"[INFO] Comunicacao Arduino {estado}")

        elif symbol == arcade.key.V:

            self._vento_simulado = (
                VENTO_SIMULADO_TECLA
            )

        elif symbol == arcade.key.ESCAPE:

            self.close()

    def on_key_release(self, symbol, modifiers):

        if symbol == arcade.key.V:

            self._vento_simulado = 0.0

    def on_close(self):

        self.detector.fechar()
        self.vento.fechar()

        super().on_close()


def main():

    Ecossistema()

    arcade.run()


if __name__ == "__main__":
    main()