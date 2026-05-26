import os
import arcade
from pyglet import font as pyglet_font

from flor import Flor
from vento import Vento
from detector import Detector
from insetos import carregar_insetos
from plantas import criar_plantas, Planta
from relva import Relva


PROPORCAO_ORIGINAL = 1440 / 284
NUM_POSES_MAX = 5
PORTA_ARDUINO = "COM9"
LIMITE_NOTURNO = 0.25
FRAMES_ENTRE_ENVIOS_COR = 3
FRASE = "SOMOS TODOS PARTE DO ECOSSISTEMA!"
VENTO_SIMULADO_TECLA = 1.0


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


class Ecossistema(arcade.Window):
    def __init__(self):
        ecran = arcade.get_display_size()
        largura_total = ecran[0]
        altura_proporcional = int(largura_total / PROPORCAO_ORIGINAL)

        super().__init__(largura_total, altura_proporcional, "Ecossistema", resizable=True)
        self.largura = largura_total
        self.altura = altura_proporcional

        diretorio = os.path.dirname(os.path.abspath(__file__))
        font_path = os.path.join(diretorio, "assets", "font", "BasteA-Medium.otf")
        pyglet_font.add_file(font_path)

        self.margem = 10
        self.tamanho_texto = self._calcular_tamanho_texto()

        self.vento = Vento(porta=PORTA_ARDUINO)
        self.detector = Detector(num_poses=NUM_POSES_MAX)
        self.flores: list[Flor] = []

        self.estado_insetos = "padrao"
        self.insetos = carregar_insetos(self.altura, self.largura, self.estado_insetos)

        self.estado_plantas = "padrao"
        self.plantas: list[Planta] = criar_plantas(self.altura, self.largura, self.estado_plantas)

        self.relva = Relva(self.largura, self.altura)

        self._frame_cor = 0
        self._vento_simulado = 0.0

    def _calcular_tamanho_texto(self):
        largura_disponivel = self.largura - self.margem * 2
        tamanho = 200
        while tamanho > 1:
            doc = arcade.Text(FRASE, x=0, y=0, font_size=tamanho, font_name="Baste A Medium")
            if doc.content_width <= largura_disponivel:
                return tamanho
            tamanho -= 1
        return 1

    def _claridade(self):
        if self.vento.ldr_disponivel:
            return max(0.0, min(1.0, self.vento.ldr))
        mouse_y = getattr(self, "_mouse_y", self.altura)
        return max(0.0, min(1.0, mouse_y / max(self.altura, 1)))

    def on_update(self, delta_time):
        self.vento.atualizar(delta_time)

        pessoas = sorted(self.detector.detetar(), key=lambda p: p.x)

        while len(self.flores) < len(pessoas):
            p = pessoas[len(self.flores)]
            self.flores.append(Flor(p.x * self.largura, self.altura, self.largura, cor_rgb=p.cor))
        while len(self.flores) > len(pessoas):
            self.flores.pop()

        for flor, p in zip(self.flores, pessoas):
            flor.atualizar(p.x * self.largura)

        for inseto in self.insetos:
            inseto.update()

        self._frame_cor += 1
        if self._frame_cor % FRAMES_ENTRE_ENVIOS_COR == 0 and self.vento.conectado:
            cor = self.detector.cor_dos_torsos()
            if cor is not None:
                r, g, b = cor
                self.vento.enviar_cor(r, g, b)

    def on_draw(self):
        t = self._claridade()
        novo_estado = "noturno" if t < LIMITE_NOTURNO else "padrao"

        if novo_estado != self.estado_insetos:
            dados_insetos = [(i.center_x, i.center_y, i.direcao, i.velocidade) for i in self.insetos]
            self.estado_insetos = novo_estado
            self.insetos = carregar_insetos(self.altura, self.largura, self.estado_insetos, dados_insetos)

        if novo_estado != self.estado_plantas:
            self.estado_plantas = novo_estado
            self.plantas = criar_plantas(self.altura, self.largura, self.estado_plantas)

        r, g, b = 0, int(lerp(22, 116, t)), int(lerp(153, 255, t))
        self.clear((r, g, b))

        arcade.Text(
            FRASE,
            self.margem,
            self.altura - self.margem - self.tamanho_texto,
            arcade.color.Color(0x3c, 0xbe, 0x00),
            self.tamanho_texto,
            font_name="Baste A Medium",
        ).draw()

        direcao_vento = self._vento_simulado if self._vento_simulado else self.vento.direcao

        for planta in self.plantas:
            planta.desenhar()

        for flor in self.flores:
            flor.desenhar(direcao_vento)

        self.relva.desenhar(direcao_vento)
        self.insetos.draw()

    def on_key_press(self, symbol, modifiers):
        if symbol == arcade.key.K:
            self._vento_simulado = VENTO_SIMULADO_TECLA

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
