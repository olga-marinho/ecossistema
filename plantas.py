import arcade
import math
import random
import io
import os

import cairosvg
from PIL import Image, ImageOps


ALTURA_MIN_PLANTA = 1 / 4
ALTURA_MAX_PLANTA = 5 / 8

COR_CAULE_BASE_PADRAO = "#006633"
COR_CAULE_TOPO_PADRAO = "#3cbe00"

COR_CAULE_BASE_NOTURNO = "#888888"
COR_CAULE_TOPO_NOTURNO = "#cccccc"

LARGURA_MAX_CAULE = 1 / 7
LARGURA_STROKE_FATOR = 1 / 100

ESCALA_FOLHA_VW = 0.02
ESCALA_COGUMELO_VW = 0.04

MARGEM_FOLHA_VW = 0.009
PASSOS_CRESCIMENTO_PLANTA = 8
ESCALA_RENDER_PLANTA = 0.7
ALTURA_RENDER_PLANTA_MIN_PX = 160
ALTURA_RENDER_PLANTA_MAX_PX = 900


def _carregar_textura_folha(caminho: str, flip: bool):
    try:
        img = Image.open(caminho).convert("RGBA")
        if flip:
            img = ImageOps.mirror(img)
        nome = f"folha_{'flip' if flip else 'normal'}_{random.random()}"
        return arcade.Texture(name=nome, image=img)
    except Exception as e:
        print(f"Erro ao carregar folha '{caminho}': {e}")
        return None


def _gerar_dados_planta(
    altura_caule: float,
    largura_janela: float,
    altura_janela: float,
    stroke_px: float
):
    largura_util = largura_janela * LARGURA_MAX_CAULE
    margin = stroke_px

    vb_w = largura_util + stroke_px * 2
    vb_h = altura_caule + stroke_px * 2

    r = altura_caule * 0.07
    r = max(r, stroke_px * 1.2)
    r = min(r, largura_util * 0.18)

    altura_norm = (
        altura_caule - altura_janela * ALTURA_MIN_PLANTA
    ) / max(
        altura_janela * (ALTURA_MAX_PLANTA - ALTURA_MIN_PLANTA),
        1
    )

    num_us = 1 if altura_norm < 0.5 else 2

    x_esq = margin + r
    x_dir = vb_w - margin - r

    x_topo = vb_w / 2
    y_topo = margin
    y_base = vb_h - margin

    altura_v_total = (y_base - y_topo) - num_us * 2 * r

    if num_us == 1:
        seg_inicial = altura_v_total * 0.65
        segs_v = [seg_inicial, altura_v_total - seg_inicial]
    else:
        seg_inicial = altura_v_total * 0.45
        seg_meio = altura_v_total * 0.15
        seg_final = altura_v_total - seg_inicial - seg_meio
        segs_v = [seg_inicial, seg_meio, seg_final]

    x = x_topo
    y = y_topo
    path_d = f"M {x:.3f},{y:.3f}"

    direcao = random.choice([-1, 1])
    comprimento_total = 0.0

    for i in range(num_us):
        seg_v = segs_v[i]
        y_c1 = y + seg_v
        
        path_d += f" V {y_c1:.3f}"
        comprimento_total += seg_v

        if direcao > 0:
            path_d += f" A {r:.3f},{r:.3f} 0 0,0 {(x + r):.3f},{(y_c1 + r):.3f}"
        else:
            path_d += f" A {r:.3f},{r:.3f} 0 0,1 {(x - r):.3f},{(y_c1 + r):.3f}"
        comprimento_total += 0.5 * math.pi * r

        if direcao > 0:
            x_h_fim = random.uniform(x_dir * 0.80, x_dir)
        else:
            x_h_fim = random.uniform(x_esq, x_esq + (x_dir - x_esq) * 0.20)

        x_h_antes = x_h_fim - r * direcao
        path_d += f" H {x_h_antes:.3f}"
        x_apos_arco1 = x + r * direcao
        comprimento_total += abs(x_h_antes - x_apos_arco1)

        if direcao > 0:
            path_d += f" A {r:.3f},{r:.3f} 0 0,1 {x_h_fim:.3f},{(y_c1 + 2*r):.3f}"
        else:
            path_d += f" A {r:.3f},{r:.3f} 0 0,0 {x_h_fim:.3f},{(y_c1 + 2*r):.3f}"
        comprimento_total += 0.5 * math.pi * r

        x = x_h_fim
        y = y_c1 + 2 * r
        direcao *= -1

    path_d += f" V {y_base:.3f}"
    comprimento_total += (y_base - y)

    x_topo_norm = x_topo / vb_w

    return path_d, vb_w, vb_h, x_topo_norm, comprimento_total, y_base, y_topo


class Planta:

    NUM_PLANTAS = 2

    def __init__(
        self,
        x: float,
        altura_janela: float,
        largura_janela: float,
        estado: str = "padrao"
    ):
        self.x = float(x)
        self.altura_janela = altura_janela
        self.largura_janela = largura_janela
        self.estado = estado

        self.altura_caule = random.uniform(
            altura_janela * ALTURA_MIN_PLANTA,
            altura_janela * ALTURA_MAX_PLANTA,
        )

        self.stroke = largura_janela * LARGURA_STROKE_FATOR
        self.progresso_crescimento = 0.0

        self.a_desaparecer = False
        self.folha_visivel = True
        self.removida = False

        if self.estado == "noturno":
            self.cor_base = COR_CAULE_BASE_NOTURNO
            self.cor_topo = COR_CAULE_TOPO_NOTURNO
        else:
            self.cor_base = COR_CAULE_BASE_PADRAO
            self.cor_topo = COR_CAULE_TOPO_PADRAO

        (self.path_d, self.vb_w, self.vb_h, 
         self.x_offset, self.comprimento_total, 
         self.y_base, self.y_topo) = _gerar_dados_planta(
            self.altura_caule, self.largura_janela, self.altura_janela, self.stroke
        )

        self._cache_texturas_planta = {}
        self._indice_textura_planta = -1
        self.textura = None
        self._atualizar_textura_planta()

        self._sprite_caule = arcade.Sprite()
        self._sprite_folha = arcade.Sprite()
        self.folha_esquerda = random.random() < 0.5
        self.textura_folha = self._carregar_folha()
        self.fator_vento = random.uniform(0.75, 1.25)

    def iniciar_desaparecimento(self):
        self.a_desaparecer = True

    def _renderizar_textura_planta(self, progresso: float) -> arcade.Texture:
        try:
            dash_array_str = f'stroke-dasharray="{self.comprimento_total:.3f} {self.comprimento_total:.3f}"'
            offset_val = -self.comprimento_total * (1.0 - progresso)
            dash_offset_str = f'stroke-dashoffset="{offset_val:.3f}"'

            svg = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.vb_w:.3f} {self.vb_h:.3f}">
  <defs>
    <linearGradient id="gp" x1="0" y1="{self.y_base:.3f}" x2="0" y2="{self.y_topo:.3f}" gradientUnits="userSpaceOnUse">
      <stop offset="0" stop-color="{self.cor_base}"/>
      <stop offset="0.56" stop-color="{self.cor_topo}"/>
    </linearGradient>
  </defs>

  <path
    d="{self.path_d}"
    fill="none"
    stroke="url(#gp)"
    stroke-width="{self.stroke:.3f}"
    stroke-linecap="round"
    stroke-linejoin="round"
    {dash_array_str}
    {dash_offset_str}
  />
</svg>'''

            svg_bytes = svg.encode("utf-8")
            altura_px = int(self.altura_caule * ESCALA_RENDER_PLANTA)
            altura_px = max(
                ALTURA_RENDER_PLANTA_MIN_PX,
                min(ALTURA_RENDER_PLANTA_MAX_PX, altura_px)
            )

            png_bytes = cairosvg.svg2png(
                bytestring=svg_bytes,
                output_height=altura_px
            )

            img = Image.open(io.BytesIO(png_bytes)).convert("RGBA")

            textura = arcade.Texture(
                name=f"planta_{id(self)}_{progresso:.3f}",
                image=img,
            )

            return textura

        except Exception as e:
            print(f"Erro ao renderizar textura da planta: {e}")
            return None

    def _carregar_folha(self):
        diretorio = os.path.dirname(os.path.abspath(__file__))
        nome_img = "cogumelo.png" if self.estado == "noturno" else "folha.png"
        caminho = os.path.join(diretorio, "assets", "imgs", nome_img)

        if not os.path.exists(caminho):
            print(f"Imagem não encontrada em: {caminho}")
            return None

        return _carregar_textura_folha(caminho, flip=self.folha_esquerda)

    def _indice_progresso_planta(self):
        indice = int(round(self.progresso_crescimento * PASSOS_CRESCIMENTO_PLANTA))
        return max(0, min(PASSOS_CRESCIMENTO_PLANTA, indice))

    def _obter_textura_planta_por_indice(self, indice):
        textura = self._cache_texturas_planta.get(indice)

        if textura is not None:
            return textura

        progresso_discreto = indice / PASSOS_CRESCIMENTO_PLANTA
        textura = self._renderizar_textura_planta(progresso_discreto)

        if textura is not None:
            self._cache_texturas_planta[indice] = textura

        return textura

    def _atualizar_textura_planta(self):
        indice = self._indice_progresso_planta()

        if indice == self._indice_textura_planta:
            return

        self._indice_textura_planta = indice
        self.textura = self._obter_textura_planta_por_indice(indice)

    def atualizar(self):
        velocidade_desenho = 0.08  
        
        if not self.a_desaparecer:
            if self.progresso_crescimento < 1.0:
                self.progresso_crescimento += velocidade_desenho
                if self.progresso_crescimento >= 1.0:
                    self.progresso_crescimento = 1.0
        else:
            if self.folha_visivel:
                self.folha_visivel = False
            else:
                self.progresso_crescimento -= velocidade_desenho
                if self.progresso_crescimento <= 0.0:
                    self.progresso_crescimento = 0.0
                    self.removida = True

        self._atualizar_textura_planta()


    def desenhar(self, direcao_vento=0.0):
        if not self.textura:
            return

        tc = self.textura
        proporcao = tc.width / tc.height

        alt_final = self.altura_caule
        larg_final = alt_final * proporcao

        caule_center_x = self.x - (self.x_offset - 0.5) * larg_final
        caule_center_y = (alt_final / 2) - (alt_final * 0.07)

        sprite_c = self._sprite_caule
        sprite_c.texture = tc
        sprite_c.width = larg_final
        sprite_c.height = alt_final
        sprite_c.center_x = caule_center_x
        sprite_c.center_y = caule_center_y
        sprite_c.center_x += float(direcao_vento) * self.largura_janela * 0.0025 * self.fator_vento
        sprite_c.angle = -float(direcao_vento) * 12.0 * self.fator_vento

        arcade.draw_sprite(sprite_c)

        if self.textura_folha and self.progresso_crescimento >= 1.0 and self.folha_visivel:
            topo_x = self.x + float(direcao_vento) * self.largura_janela * 0.006 * self.fator_vento
            topo_y = self.altura_caule

            if self.estado == "noturno":
                escala = ESCALA_COGUMELO_VW
            else:
                escala = ESCALA_FOLHA_VW

            larg_folha = self.largura_janela * escala
            prop_folha = self.textura_folha.height / self.textura_folha.width
            alt_folha = larg_folha * prop_folha
            margem_px = self.largura_janela * MARGEM_FOLHA_VW

            sprite_f = self._sprite_folha
            sprite_f.texture = self.textura_folha
            sprite_f.width = larg_folha
            sprite_f.height = alt_folha

            if self.estado == "noturno":
                sprite_f.center_x = topo_x
                sprite_f.center_y = topo_y - (alt_folha / 2)
            else:
                sprite_f.center_y = topo_y - alt_folha

                if self.folha_esquerda:
                    sprite_f.center_x = topo_x - larg_folha / 2 - margem_px
                else:
                    sprite_f.center_x = topo_x + larg_folha / 2 + margem_px

            arcade.draw_sprite(sprite_f)


def criar_plantas(
    altura_janela: float,
    largura_janela: float,
    estado: str = "padrao",
    num_plantas: int = None,
) -> list[Planta]:
    if num_plantas is None:
        num_plantas = Planta.NUM_PLANTAS

    margem = largura_janela * 0.05
    zona = largura_janela - 2 * margem
    plantas = []

    for i in range(num_plantas):
        x_min = margem + i * (zona / num_plantas)
        x_max = margem + (i + 1) * (zona / num_plantas)
        x = random.uniform(x_min, x_max)

        plantas.append(
            Planta(x, altura_janela, largura_janela, estado)
        )

    return plantas