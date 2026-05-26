import arcade
import os
import random


INCLINACAO_MAX_GRAUS = 18.0
ESCALA_ALTURA = 0.18
VARIACAO_ESCALA = 0.35
PASSO_RELATIVO = 0.7
JITTER_PASSO = 0.35
JITTER_FATOR = 0.22


class Relva:
    def __init__(self, largura_janela, altura_janela):
        self.largura_janela = largura_janela
        self.altura_janela = altura_janela
        self.tufos = []

        diretorio = os.path.dirname(os.path.abspath(__file__))
        caminho = os.path.join(diretorio, "assets", "imgs", "relva.png")
        if not os.path.exists(caminho):
            print(f"relva.png não encontrada em {caminho}")
            return

        self.textura = arcade.load_texture(caminho)
        self.proporcao = self.textura.width / self.textura.height

        altura_base = altura_janela * ESCALA_ALTURA
        largura_base = altura_base * self.proporcao
        passo = max(1.0, largura_base * PASSO_RELATIVO)

        x = -largura_base / 2
        while x < largura_janela + largura_base:
            escala = ESCALA_ALTURA * random.uniform(1 - VARIACAO_ESCALA, 1 + VARIACAO_ESCALA)
            factor_vento = random.uniform(1 - JITTER_FATOR, 1 + JITTER_FATOR)
            self.tufos.append({
                "x": x,
                "escala": escala,
                "factor": factor_vento,
            })
            x += passo * random.uniform(1 - JITTER_PASSO, 1 + JITTER_PASSO)

    def desenhar(self, direcao_vento):
        if not self.tufos:
            return

        for tufo in self.tufos:
            angle_graus = -float(direcao_vento) * INCLINACAO_MAX_GRAUS * tufo["factor"]

            alt_final = self.altura_janela * tufo["escala"]
            larg_final = alt_final * self.proporcao

            sprite = arcade.Sprite()
            sprite.texture = self.textura
            sprite.width = larg_final
            sprite.height = alt_final
            sprite.center_x = tufo["x"]
            sprite.center_y = 0
            sprite.angle = angle_graus
            arcade.draw_sprite(sprite)
