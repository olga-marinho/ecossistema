import arcade
import math
import random
import os
import io
import re

import cairosvg
import lxml.etree as ET
from PIL import Image

ESCALA_FLOR = 1 / 16
LARGURA_MAX_CAULE = 1 / 7
COR_CAULE_BASE = "#006633"
COR_CAULE_TOPO = "#3cbe00"
INCLINACAO_MAX_GRAUS = 22.0

LARGURA_PETALA_PX = 300
PASSOS_CRESCIMENTO_CAULE = 12

CORES_PETALA = [
    "#e74c3c",
    "#e67e22",
    "#f1c40f",
    "#9b59b6",
    "#e91e63",
    "#00bcd4",
    "#ff5722",
]


_CACHE_TEXTURA_PETALA = {}


def _clamp_rgb(cor_rgb):
    return (
        max(0, min(255, int(cor_rgb[0]))),
        max(0, min(255, int(cor_rgb[1]))),
        max(0, min(255, int(cor_rgb[2]))),
    )


def _hex_para_rgb(hex_color):
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))


def _rgb_para_hex(cor_rgb):
    r, g, b = _clamp_rgb(cor_rgb)
    return f"#{r:02x}{g:02x}{b:02x}"


def _listar_svgs_flor(pasta):
    caminhos = []

    for i in range(1, 8):
        caminho_svg = os.path.join(pasta, f"flor_0{i}.svg")
        if os.path.exists(caminho_svg):
            caminhos.append(caminho_svg)

    return caminhos


def _obter_textura_petala_colorida(caminho_svg, cor_rgb):
    cor_hex = _rgb_para_hex(cor_rgb)
    chave = (caminho_svg, cor_hex)

    textura = _CACHE_TEXTURA_PETALA.get(chave)

    if textura is not None:
        return textura

    tree = ET.parse(caminho_svg)
    root = tree.getroot()

    for style_el in root.iter("{http://www.w3.org/2000/svg}style"):
        texto = style_el.text

        if texto:
            texto = re.sub(
                r"(\.cls-1\s*\{[^}]*fill:\s*)([^;]+)(;)",
                rf"\g<1>{cor_hex}\g<3>",
                texto
            )
            style_el.text = texto

    svg_bytes = ET.tostring(
        root,
        xml_declaration=True,
        encoding="UTF-8"
    )

    png_bytes = cairosvg.svg2png(
        bytestring=svg_bytes,
        output_width=LARGURA_PETALA_PX
    )

    img = Image.open(io.BytesIO(png_bytes)).convert("RGBA")

    textura = arcade.Texture(
        name=f"petala_{os.path.basename(caminho_svg)}_{cor_hex}",
        image=img
    )

    _CACHE_TEXTURA_PETALA[chave] = textura

    return textura


def _gerar_dados_caule(altura_caule, largura_janela, altura_janela, stroke_px):
    largura_util = largura_janela * LARGURA_MAX_CAULE
    margin = stroke_px
    vb_w = largura_util + stroke_px * 2
    vb_h = altura_caule + stroke_px * 2

    r = altura_caule * 0.07
    r = max(r, stroke_px * 1.2)
    r = min(r, largura_util * 0.18)

    altura_norm = (altura_caule - altura_janela * 0.25) / max(altura_janela * 0.5, 1)
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


class Flor:

    def __init__(self, x: float, altura_janela: float, largura_janela: float, cor_rgb=None):
        self.x = float(x)
        self.x_alvo = float(x)

        self.altura_janela = altura_janela
        self.largura_janela = largura_janela

        self.altura_caule = random.uniform(
            altura_janela * 0.25,
            altura_janela * 0.75,
        )

        self.progresso_crescimento = 0.0

        self.a_desaparecer = False
        self.flor_visivel = True
        self.removida = False

        self.stroke = largura_janela / 100

        (
            self.path_d,
            self.vb_w,
            self.vb_h,
            self.caule_x_offset,
            self.comprimento_total,
            self.y_base,
            self.y_topo

        ) = _gerar_dados_caule(
            self.altura_caule,
            self.largura_janela,
            self.altura_janela,
            self.stroke
        )

        self._cache_texturas_caule = {}
        self._indice_textura_caule = -1
        self.textura_caule = None
        self._atualizar_textura_caule()

        self.textura_flor = None
        self._svg_petala_path = None
        self._cor_petala_atual = None

        diretorio = os.path.dirname(os.path.abspath(__file__))

        pasta = os.path.join(
            diretorio,
            "assets",
            "imgs"
        )

        svgs = _listar_svgs_flor(pasta)

        if svgs:

            self._svg_petala_path = random.choice(svgs)

            if cor_rgb is not None:
                cor = _clamp_rgb(cor_rgb)
            else:
                cor = _hex_para_rgb(
                    random.choice(CORES_PETALA)
                )

            self.atualizar_cor(cor)


    def iniciar_desaparecimento(self):
        self.a_desaparecer = True


    def atualizar_cor(self, cor_rgb):
        if self._svg_petala_path is None or cor_rgb is None:
            return

        cor_clamp = _clamp_rgb(cor_rgb)

        if self._cor_petala_atual == cor_clamp:
            return

        try:
            self.textura_flor = _obter_textura_petala_colorida(
                self._svg_petala_path,
                cor_clamp
            )
            self._cor_petala_atual = cor_clamp
        except Exception as e:
            print(f"Erro ao atualizar cor da petala '{self._svg_petala_path}': {e}")


    def _indice_progresso_caule(self):
        indice = int(round(self.progresso_crescimento * PASSOS_CRESCIMENTO_CAULE))
        return max(0, min(PASSOS_CRESCIMENTO_CAULE, indice))


    def _obter_textura_caule_por_indice(self, indice):
        textura = self._cache_texturas_caule.get(indice)

        if textura is not None:
            return textura

        progresso_discreto = indice / PASSOS_CRESCIMENTO_CAULE
        textura = self._renderizar_textura_caule(progresso_discreto)

        if textura is not None:
            self._cache_texturas_caule[indice] = textura

        return textura


    def _atualizar_textura_caule(self):
        indice = self._indice_progresso_caule()

        if indice == self._indice_textura_caule:
            return

        self._indice_textura_caule = indice
        self.textura_caule = self._obter_textura_caule_por_indice(indice)


    def _renderizar_textura_caule(self, progresso: float) -> arcade.Texture:

        try:

            dash_array_str = (
                f'stroke-dasharray="{self.comprimento_total:.3f} '
                f'{self.comprimento_total:.3f}"'
            )

            offset_val = -self.comprimento_total * (1.0 - progresso)

            dash_offset_str = (
                f'stroke-dashoffset="{offset_val:.3f}"'
            )

            svg = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.vb_w:.3f} {self.vb_h:.3f}">
  <defs>
    <linearGradient id="grad" x1="0" y1="{self.y_base:.3f}" x2="0" y2="{self.y_topo:.3f}" gradientUnits="userSpaceOnUse">
      <stop offset="0" stop-color="{COR_CAULE_BASE}"/>
      <stop offset="0.56" stop-color="{COR_CAULE_TOPO}"/>
    </linearGradient>
  </defs>

  <path
    d="{self.path_d}"
    fill="none"
    stroke="url(#grad)"
    stroke-width="{self.stroke:.3f}"
    stroke-linecap="round"
    stroke-linejoin="round"
    {dash_array_str}
    {dash_offset_str}
  />
</svg>'''
            svg_bytes = svg.encode("utf-8")
            altura_px = int(self.altura_caule * 2)
            png_bytes = cairosvg.svg2png(
                bytestring=svg_bytes,
                output_height=altura_px
            )
            img = Image.open(io.BytesIO(png_bytes)).convert("RGBA")
            return arcade.Texture(
                name=f"caule_{id(self)}_{progresso:.3f}",
                image=img,
            )

        except Exception as e:
            print(f"Erro ao renderizar textura do caule: {e}")
            return None

    def atualizar(self, x_alvo: float):

        self.x_alvo = float(x_alvo)

        self.x += (self.x_alvo - self.x) * 0.12

        velocidade = 0.08

        if not self.a_desaparecer:

            if self.progresso_crescimento < 1.0:

                self.progresso_crescimento += velocidade

                if self.progresso_crescimento >= 1.0:
                    self.progresso_crescimento = 1.0

        else:

            if self.flor_visivel:
                self.flor_visivel = False

            else:

                self.progresso_crescimento -= velocidade

                if self.progresso_crescimento <= 0.0:
                    self.progresso_crescimento = 0.0
                    self.removida = True

        self._atualizar_textura_caule()

    def desenhar(self, direcao_vento: float):

        angle_graus = -float(direcao_vento) * INCLINACAO_MAX_GRAUS

        angle_rad = math.radians(angle_graus)

        cos_a = math.cos(angle_rad)
        sin_a = math.sin(angle_rad)

        if self.textura_caule:

            tc = self.textura_caule

            proporcao = tc.width / tc.height

            alt_final = self.altura_caule
            larg_final = alt_final * proporcao

            cx_base = self.x - (
                self.caule_x_offset - 0.5
            ) * larg_final

            cy_base = (
                (alt_final / 2)
                - (alt_final * 0.07)
            )

            dx = cx_base - self.x
            dy = cy_base

            cx_rot = self.x + dx * cos_a - dy * sin_a
            cy_rot = dx * sin_a + dy * cos_a

            sprite_c = arcade.Sprite()

            sprite_c.texture = tc
            sprite_c.width = larg_final
            sprite_c.height = alt_final

            sprite_c.center_x = cx_rot
            sprite_c.center_y = cy_rot

            sprite_c.angle = angle_graus

            arcade.draw_sprite(sprite_c)

        topo_x = self.x - self.altura_caule * sin_a
        topo_y = self.altura_caule * cos_a

        if (
            self.textura_flor
            and self.progresso_crescimento >= 1.0
            and self.flor_visivel
        ):

            proporcao = (
                self.textura_flor.height
                / self.textura_flor.width
            )

            larg_final = self.largura_janela * ESCALA_FLOR

            alt_final = larg_final * proporcao

            sprite_f = arcade.Sprite()

            sprite_f.texture = self.textura_flor

            sprite_f.width = larg_final
            sprite_f.height = alt_final

            sprite_f.center_x = topo_x
            sprite_f.center_y = topo_y

            sprite_f.angle = angle_graus

            arcade.draw_sprite(sprite_f)