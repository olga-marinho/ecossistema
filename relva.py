import arcade
import os
import random

INCLINACAO_MAX_GRAUS = 18.0
ESCALA_ALTURA = 0.20 
QUANTIDADE_TUROS = 60  # Alterado para 60

class Relva:
    def __init__(self, largura_janela, altura_janela):
        self.largura_janela = largura_janela
        self.altura_janela = altura_janela
        self.tufos = arcade.SpriteList()

        diretorio = os.path.dirname(os.path.abspath(__file__))
        caminho = os.path.join(diretorio, "assets", "imgs", "relva.png")
        
        if not os.path.exists(caminho):
            return

        textura = arcade.load_texture(caminho)
        proporcao = textura.width / textura.height

        alt_fixa = altura_janela * ESCALA_ALTURA
        larg_fixa = alt_fixa * proporcao

        passo = largura_janela / QUANTIDADE_TUROS

        for i in range(QUANTIDADE_TUROS):
            sprite = arcade.Sprite()
            sprite.texture = textura
            sprite.width = larg_fixa
            sprite.height = alt_fixa
            
            sprite.center_x = (i * passo) + (passo / 2)
            
            # Ajuste de alinhamento:
            # center_y negativo baixa o sprite em relação ao limite inferior da janela
            # -10 pixels (ajusta este valor conforme necessário)
            sprite.center_y = -10 
            
            sprite.properties = {"factor": random.uniform(0.8, 1.2)}
            self.tufos.append(sprite)

    def desenhar(self, direcao_vento):
        for sprite in self.tufos:
            sprite.angle = -float(direcao_vento) * INCLINACAO_MAX_GRAUS * sprite.properties["factor"]
        
        self.tufos.draw()