import arcade
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


def _gerar_svg_planta(
    altura_caule: float,
    largura_janela: float,
    altura_janela: float,
    stroke_px: float,
    cor_base: str,
    cor_topo: str,
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
        altura_janela * (
            ALTURA_MAX_PLANTA - ALTURA_MIN_PLANTA
        ),
        1
    )

    num_us = 1 if altura_norm < 0.5 else 2

    x_esq = margin + r
    x_dir = vb_w - margin - r

    x_topo = vb_w / 2

    y_topo = margin
    y_base = vb_h - margin

    altura_v_total = (
        y_base - y_topo
    ) - num_us * 2 * r

    if num_us == 1:

        seg_inicial = altura_v_total * 0.65

        segs_v = [
            seg_inicial,
            altura_v_total - seg_inicial
        ]

    else:

        seg_inicial = altura_v_total * 0.45
        seg_meio = altura_v_total * 0.15

        seg_final = (
            altura_v_total
            - seg_inicial
            - seg_meio
        )

        segs_v = [
            seg_inicial,
            seg_meio,
            seg_final
        ]

    x = x_topo
    y = y_topo

    path_d = f"M {x:.3f},{y:.3f}"

    direcao = random.choice([-1, 1])

    for i in range(num_us):

        seg_v = segs_v[i]

        if direcao > 0:
            x_h_fim = random.uniform(
                x_dir * 0.80,
                x_dir
            )
        else:
            x_h_fim = random.uniform(
                x_esq,
                x_esq + (x_dir - x_esq) * 0.20
            )

        y_c1 = y + seg_v

        path_d += f" V {y_c1:.3f}"

        if direcao > 0:
            path_d += (
                f" A {r:.3f},{r:.3f} "
                f"0 0,0 "
                f"{(x + r):.3f},{(y_c1 + r):.3f}"
            )
        else:
            path_d += (
                f" A {r:.3f},{r:.3f} "
                f"0 0,1 "
                f"{(x - r):.3f},{(y_c1 + r):.3f}"
            )

        x_h_antes = x_h_fim - r * direcao

        path_d += f" H {x_h_antes:.3f}"

        if direcao > 0:
            path_d += (
                f" A {r:.3f},{r:.3f} "
                f"0 0,1 "
                f"{x_h_fim:.3f},{(y_c1 + 2*r):.3f}"
            )
        else:
            path_d += (
                f" A {r:.3f},{r:.3f} "
                f"0 0,0 "
                f"{x_h_fim:.3f},{(y_c1 + 2*r):.3f}"
            )

        x = x_h_fim
        y = y_c1 + 2 * r

        direcao *= -1

    path_d += f" V {y_base:.3f}"

    x_topo_norm = x_topo / vb_w

    svg = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {vb_w:.3f} {vb_h:.3f}">
  <defs>
    <linearGradient id="gp" x1="0" y1="{y_base:.3f}" x2="0" y2="{y_topo:.3f}" gradientUnits="userSpaceOnUse">
      <stop offset="0" stop-color="{cor_base}"/>
      <stop offset="0.56" stop-color="{cor_topo}"/>
    </linearGradient>
  </defs>

  <path
    d="{path_d}"
    fill="none"
    stroke="url(#gp)"
    stroke-width="{stroke_px:.3f}"
    stroke-linecap="round"
    stroke-linejoin="round"
  />
</svg>'''

    return svg.encode("utf-8"), x_topo_norm


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

        self.textura, self.x_offset = self._gerar_textura()

        self.folha_esquerda = random.random() < 0.5

        self.textura_folha = self._carregar_folha()

    def _gerar_textura(self):

        try:

            if self.estado == "noturno":

                cor_base = COR_CAULE_BASE_NOTURNO
                cor_topo = COR_CAULE_TOPO_NOTURNO

            else:

                cor_base = COR_CAULE_BASE_PADRAO
                cor_topo = COR_CAULE_TOPO_PADRAO

            svg_bytes, x_norm = _gerar_svg_planta(
                self.altura_caule,
                self.largura_janela,
                self.altura_janela,
                self.stroke,
                cor_base,
                cor_topo,
            )

            altura_px = int(self.altura_caule * 2)

            png_bytes = cairosvg.svg2png(
                bytestring=svg_bytes,
                output_height=altura_px
            )

            img = Image.open(
                io.BytesIO(png_bytes)
            ).convert("RGBA")

            textura = arcade.Texture(
                name=f"planta_{id(self)}_{random.random()}",
                image=img,
            )

            return textura, x_norm

        except Exception as e:

            print(f"Erro ao gerar planta: {e}")

            return None, 0.5

    def _carregar_folha(self):

        diretorio = os.path.dirname(
            os.path.abspath(__file__)
        )

        nome_img = (
            "cogumelo.png"
            if self.estado == "noturno"
            else "folha.png"
        )

        caminho = os.path.join(
            diretorio,
            "assets",
            "imgs",
            nome_img
        )

        if not os.path.exists(caminho):

            print(f"Imagem não encontrada em: {caminho}")

            return None

        return _carregar_textura_folha(
            caminho,
            flip=self.folha_esquerda
        )

    def desenhar(self):

        if not self.textura:
            return

        tc = self.textura

        proporcao = tc.width / tc.height

        alt_final = self.altura_caule
        larg_final = alt_final * proporcao

        caule_center_x = (
            self.x
            - (self.x_offset - 0.5) * larg_final
        )

        caule_center_y = (
            (alt_final / 2)
            - (alt_final * 0.07)
        )

        sprite_c = arcade.Sprite()

        sprite_c.texture = tc

        sprite_c.width = larg_final
        sprite_c.height = alt_final

        sprite_c.center_x = caule_center_x
        sprite_c.center_y = caule_center_y

        arcade.draw_sprite(sprite_c)

        topo_x = self.x
        topo_y = self.altura_caule

        if self.textura_folha:

            if self.estado == "noturno":
                escala = ESCALA_COGUMELO_VW
            else:
                escala = ESCALA_FOLHA_VW

            larg_folha = (
                self.largura_janela
                * escala
            )

            prop_folha = (
                self.textura_folha.height
                / self.textura_folha.width
            )

            alt_folha = larg_folha * prop_folha

            margem_px = (
                self.largura_janela
                * MARGEM_FOLHA_VW
            )

            sprite_f = arcade.Sprite()

            sprite_f.texture = self.textura_folha

            sprite_f.width = larg_folha
            sprite_f.height = alt_folha

            if self.estado == "noturno":

                sprite_f.center_x = topo_x
                sprite_f.center_y = topo_y - (alt_folha/2)

            else:

                sprite_f.center_y = topo_y - alt_folha

                if self.folha_esquerda:

                    sprite_f.center_x = (
                        topo_x
                        - larg_folha / 2
                        - margem_px
                    )

                else:

                    sprite_f.center_x = (
                        topo_x
                        + larg_folha / 2
                        + margem_px
                    )

            arcade.draw_sprite(sprite_f)


def criar_plantas(
    altura_janela: float,
    largura_janela: float,
    estado: str = "padrao"
) -> list[Planta]:

    margem = largura_janela * 0.05

    zona = largura_janela - 2 * margem

    plantas = []

    for i in range(Planta.NUM_PLANTAS):

        x_min = margem + i * (
            zona / Planta.NUM_PLANTAS
        )

        x_max = margem + (
            i + 1
        ) * (
            zona / Planta.NUM_PLANTAS
        )

        x = random.uniform(x_min, x_max)

        plantas.append(
            Planta(
                x,
                altura_janela,
                largura_janela,
                estado
            )
        )

    return plantas