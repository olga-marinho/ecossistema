import arcade
import random
import os
import math


TERRESTRES = ("formiga", "caracol", "minhoca")


class Inseto(arcade.Sprite):
    def __init__(self, prefixo, num_frames, altura_janela, largura_janela, escala_base, dados=None):
        super().__init__()
        self.prefixo = prefixo
        self.largura_janela = largura_janela
        self.altura_janela = altura_janela
        self.frames_left, self.frames_right = self._carregar_frames(prefixo, num_frames)
        self.scale = escala_base
        self.frame_index = 0
        self.anim_timer = 0

        self.base_y = 0

        self.direcao = random.choice([-1, 1]) if not dados else (1 if dados[2] > 0 else -1)
        self.velocidade = self._definir_velocidade() * self.direcao

        if dados:
            self.center_x, y_antigo, _, _ = dados
            self.base_y = self._posicionar_y(y_antigo)
            self.center_y = self.base_y
        else:
            self.center_x = -self.width if self.direcao == 1 else largura_janela + self.width
            self.base_y = self._posicionar_y(random.uniform(altura_janela * 0.25, altura_janela * 0.75))
            self.center_y = self.base_y

        self.texture = (self.frames_right if self.velocidade > 0 else self.frames_left)[0]

    def _carregar_frames(self, prefixo, num_frames):
        left, right = [], []
        for i in range(1, num_frames + 1):
            caminho = os.path.join(os.path.dirname(__file__), "assets", "imgs", f"{prefixo}_{i:02d}.png")
            tex = arcade.load_texture(caminho)
            left.append(tex)
            right.append(tex.flip_left_right())
        return left, right

    def update(self):
        self.center_x += self.velocidade
        self._aplicar_movimento_especifico()

        frames = self.frames_right if self.velocidade > 0 else self.frames_left
        self.anim_timer += 1
        if self.anim_timer >= 3:
            self.frame_index = (self.frame_index + 1) % len(frames)
            self.texture = frames[self.frame_index]
            self.anim_timer = 0

        if self.direcao == 1 and self.center_x > self.largura_janela + self.width:
            self.center_x = -self.width
        elif self.direcao == -1 and self.center_x < -self.width:
            self.center_x = self.largura_janela + self.width

    def _aplicar_movimento_especifico(self):
        pass

    def _definir_velocidade(self):
        raise NotImplementedError

    def _posicionar_y(self, y_padrao):
        raise NotImplementedError


class InsetoTerrestre(Inseto):
    def _definir_velocidade(self):
        return random.uniform(0.8, 1.5)

    def _posicionar_y(self, _):
        return (self.height / 2) + (self.altura_janela * 0.05)


class InsetoVoador(Inseto):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.angulo = random.uniform(0, 6.28)

    def _definir_velocidade(self):
        return random.uniform(2.0, 4.0)

    def _posicionar_y(self, y_padrao):
        if y_padrao < (self.altura_janela * 0.2):
            return random.uniform(self.altura_janela * 0.25, self.altura_janela * 0.75)
        return y_padrao

    def _aplicar_movimento_especifico(self):
        self.angulo += 0.1
        amplitude = self.altura_janela * 0.05
        self.center_y = self.base_y + (math.sin(self.angulo) * amplitude)


def carregar_insetos(altura, largura, tipo="padrao", dados=None):
    config = [
        {"prefixo": "inseto_pirilampo", "frames": 3, "escala": 0.034},
        {"prefixo": "inseto_caracol", "frames": 5, "escala": 0.034},
        {"prefixo": "inseto_minhoca", "frames": 4, "escala": 0.02}
    ] if tipo == "noturno" else [
        {"prefixo": "inseto_abelha", "frames": 3, "escala": 0.03},
        {"prefixo": "inseto_formiga", "frames": 3, "escala": 0.03},
        {"prefixo": "inseto_joaninha", "frames": 4, "escala": 0.024}
    ]

    lista = arcade.SpriteList()
    caminho_base = os.path.join(os.path.dirname(__file__), "assets", "imgs")
    for i, item in enumerate(config):
        dado = dados[i] if dados and i < len(dados) else None
        if not os.path.exists(os.path.join(caminho_base, f"{item['prefixo']}_01.png")):
            continue
        e_terrestre = any(t in item["prefixo"].lower() for t in TERRESTRES)
        classe = InsetoTerrestre if e_terrestre else InsetoVoador
        lista.append(classe(item["prefixo"], item["frames"], altura, largura, item["escala"], dado))
    return lista
