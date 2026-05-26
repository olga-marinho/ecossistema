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
NUM_POSES_MAX            = 5
PORTA_ARDUINO            = "COM9"
LIMITE_NOTURNO           = 0.5
FRAMES_ENTRE_ENVIOS_COR  = 3
FRASE                    = "SOMOS TODOS PARTE DO ECOSSISTEMA!"
VENTO_SIMULADO_TECLA     = 1.0
NOME_FONTE               = "Baste A Medium"


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _obter_ecra_maior() -> tuple[int, int, int, int]:
    display = pyglet.display.get_display()
    screens = display.get_screens()

    melhor = max(screens, key=lambda s: s.width * s.height)

    print(f"[INFO] Ecrãs disponíveis: {[(s.width, s.height) for s in screens]}")
    print(f"[INFO] Ecrã escolhido: {melhor.width}x{melhor.height} em ({melhor.x},{melhor.y})")

    return melhor.width, melhor.height, melhor.x, melhor.y


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

        largura_ecra, altura_ecra, ecra_x, ecra_y = _obter_ecra_maior()

        altura_proporcional = int(
            largura_ecra / PROPORCAO_ORIGINAL
        )

        if altura_proporcional <= altura_ecra:

            super().__init__(
                largura_ecra,
                altura_proporcional,
                FRASE,
                resizable=False,
                style=pyglet.window.Window.WINDOW_STYLE_BORDERLESS,
            )

            self.set_location(ecra_x, ecra_y)

        else:

            super().__init__(
                largura_ecra,
                altura_ecra,
                FRASE,
                fullscreen=True
            )

        self.largura = self.width
        self.altura = self.height

        self.margem = 10

        self.tamanho_texto = self._calcular_tamanho_texto()

        self.vento = Vento(porta=PORTA_ARDUINO)

        self.detector = Detector(
            num_poses=NUM_POSES_MAX
        )


        self.flores: list[Flor] = []


        self.estado_insetos = "padrao"

        self.insetos = carregar_insetos_iniciais(
            self.altura,
            self.largura,
            self.estado_insetos
        )

        self.insetos_extras_ativos = []

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

        self._frame_cor = 0

        self._vento_simulado = 0.0

    def _calcular_tamanho_texto(self) -> int:

        largura_disponivel = (
            self.largura - self.margem * 2
        )

        tamanho = 400

        while tamanho > 1:

            doc = arcade.Text(
                FRASE,
                x=0,
                y=0,
                font_size=tamanho,
                font_name=NOME_FONTE,
            )

            if doc.content_width <= largura_disponivel:
                return tamanho

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

        self.vento.atualizar(delta_time)

        pessoas = sorted(
            self.detector.detetar(),
            key=lambda p: p.x
        )

        while len(
            [f for f in self.flores if not f.a_desaparecer]
        ) < len(pessoas):

            p = pessoas[
                len([f for f in self.flores if not f.a_desaparecer])
            ]

            nova_flor = Flor(
                p.x * self.largura,
                self.altura,
                self.largura,
                cor_rgb=p.cor
            )

            self.flores.append(nova_flor)

            configs = obter_configs_estado(
                self.estado_insetos
            )

            item = random.choice(configs)

            novo_inseto = gerar_inseto_por_config(
                item,
                self.altura,
                self.largura
            )

            novo_inseto.is_extra_ativo = True

            self.insetos.append(novo_inseto)

            self.insetos_extras_ativos.append(
                novo_inseto
            )

        while len(
            [f for f in self.flores if not f.a_desaparecer]
        ) > len(pessoas):

            flor_a_remover = None

            for flor in reversed(self.flores):

                if not flor.a_desaparecer:
                    flor_a_remover = flor
                    break

            if flor_a_remover:
                flor_a_remover.iniciar_desaparecimento()

            if self.insetos_extras_ativos:

                inseto_a_remover = (
                    self.insetos_extras_ativos.pop()
                )

                inseto_a_remover.marcado_para_sair = True

                inseto_a_remover.is_extra_ativo = False

            break

        flores_ativas = [
            f for f in self.flores
            if not f.a_desaparecer
        ]

        for flor, p in zip(flores_ativas, pessoas):

            flor.atualizar(
                p.x * self.largura
            )

        for flor in self.flores:

            if flor.a_desaparecer:

                flor.atualizar(flor.x)

        self.flores = [
            flor for flor in self.flores
            if not flor.removida
        ]


        novo_num_plantas = (
            2 + (
                len([
                    f for f in self.flores
                    if not f.a_desaparecer
                ]) // 2
            )
        )

        while len(self.plantas) < novo_num_plantas:

            nova_planta = criar_plantas(
                self.altura,
                self.largura,
                self.estado_plantas,
                1
            )[0]

            self.plantas.append(
                nova_planta
            )

        while len(self.plantas) > novo_num_plantas:

            self.plantas.pop()

        self._num_plantas_atual = novo_num_plantas


        for planta in self.plantas:
            planta.atualizar()


        for inseto in self.insetos:
            inseto.update()


        self._frame_cor += 1

        if (
            self._frame_cor % FRAMES_ENTRE_ENVIOS_COR == 0
            and self.vento.conectado
        ):

            cor = self.detector.cor_dos_torsos()

            if cor is not None:

                r, g, b = cor

                self.vento.enviar_cor(
                    r,
                    g,
                    b
                )

    def on_draw(self):

        t = self._claridade()

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

                nova_planta.textura = (
                    nova_planta._renderizar_textura_planta(
                        nova_planta.progresso_crescimento
                    )
                )

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
            planta.desenhar()

        for flor in self.flores:
            flor.desenhar(direcao_vento)

        self.relva.desenhar(
            direcao_vento
        )

        self.insetos.draw()


    def on_key_press(self, symbol, modifiers):

        if symbol == arcade.key.K:

            self._vento_simulado = (
                VENTO_SIMULADO_TECLA
            )

        elif symbol == arcade.key.ESCAPE:

            self.close()

    def on_key_release(self, symbol, modifiers):

        if symbol == arcade.key.K:

            self._vento_simulado = 0.0

    def on_close(self):

        self.detector.fechar()

        super().on_close()


def main():

    Ecossistema()

    arcade.run()


if __name__ == "__main__":
    main()