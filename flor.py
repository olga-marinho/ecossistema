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

CORES_PETALA = [
    "#e74c3c",
    "#e67e22",
    "#f1c40f",
    "#9b59b6",
    "#e91e63",
    "#00bcd4",
    "#ff5722",
]


def _carregar_svg_com_cor(svg_path: str, cor_petala: str, largura_px: int = 300) -> arcade.Texture:
    tree = ET.parse(svg_path)
    root = tree.getroot()
    for style_el in root.iter("{http://www.w3.org/2000/svg}style"):
        texto = style_el.text
        if texto:
            texto = re.sub(
                r'(\.cls-1\s*\{[^}]*fill:\s*)([^;]+)(;)',
                rf'\g<1>{cor_petala}\g<3>',
                texto
            )
            style_el.text = texto
    svg_bytes = ET.tostring(root, xml_declaration=True, encoding="UTF-8")
    png_bytes = cairosvg.svg2png(bytestring=svg_bytes, output_width=largura_px)
    img = Image.open(io.BytesIO(png_bytes)).convert("RGBA")
    return arcade.Texture(
        name=f"{svg_path}_{cor_petala}_{random.random()}",
        image=img
    )


def _gerar_dados_caule(altura_caule, largura_janela, altura_janela, stroke_px):
    """
    Gera a estrutura e a geometria fixa do caule uma única vez, 
    calculando também o comprimento total exato de toda a linha (incluindo curvas).
    """
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
        self.stroke = largura_janela / 100

        (self.path_d, self.vb_w, self.vb_h, 
         self.caule_x_offset, self.comprimento_total, 
         self.y_base, self.y_topo) = _gerar_dados_caule(
            self.altura_caule, self.largura_janela, self.altura_janela, self.stroke
        )

        self.textura_caule = self._renderizar_textura_caule(self.progresso_crescimento)

        self.textura_flor = None
        diretorio = os.path.dirname(os.path.abspath(__file__))
        pasta = os.path.join(diretorio, "assets", "imgs")

        svgs = [
            os.path.join(pasta, f"flor_0{i}.svg")
            for i in range(1, 8)
            if os.path.exists(os.path.join(pasta, f"flor_0{i}.svg"))
        ]
        if svgs:
            svg_path = random.choice(svgs)
            if cor_rgb is not None:
                cor = "#{:02x}{:02x}{:02x}".format(*cor_rgb)
            else:
                cor = random.choice(CORES_PETALA)
            try:
                self.textura_flor = _carregar_svg_com_cor(svg_path, cor, largura_px=300)
                print(f"Flor carregada: {os.path.basename(svg_path)} | cor: {cor}")
            except Exception as e:
                print(f"Erro ao carregar SVG '{svg_path}': {e}")
        else:
            print("Nenhum SVG encontrado em:", pasta)

    def _renderizar_textura_caule(self, progresso: float) -> arcade.Texture:
        """Gera a imagem aplicando um offset negativo para esconder o ponto inicial do topo."""
        try:
            # O truque: criamos um traço contínuo e jogamos ele para fora com offset negativo. 
            # À medida que cresce, a linha desliza de baixo para cima sem criar artefatos no topo!
            dash_array_str = f'stroke-dasharray="{self.comprimento_total:.3f} {self.comprimento_total:.3f}"'
            offset_val = -self.comprimento_total * (1.0 - progresso)
            dash_offset_str = f'stroke-dashoffset="{offset_val:.3f}"'

            svg = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.vb_w:.3f} {self.vb_h:.3f}">
  <defs>
    <linearGradient id="grad" x1="0" y1="{self.y_base:.3f}" x2="0" y2="{self.y_topo:.3f}" gradientUnits="userSpaceOnUse">
      <stop offset="0"    stop-color="{COR_CAULE_BASE}"/>
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
            png_bytes = cairosvg.svg2png(bytestring=svg_bytes, output_height=altura_px)
            img = Image.open(io.BytesIO(png_bytes)).convert("RGBA")
            
            return arcade.Texture(
                name=f"caule_{id(self)}_{progresso:.3f}_{random.random()}",
                image=img,
            )
        except Exception as e:
            print(f"Erro ao renderizar textura do caule: {e}")
            return None

    def atualizar(self, x_alvo: float):
        self.x_alvo = float(x_alvo)
        self.x += (self.x_alvo - self.x) * 0.12

        # --- ANIMAÇÃO MAIS RÁPIDA ---
        if self.progresso_crescimento < 1.0:
            velocidade_desenho = 0.08  # Aumentado de 0.04 para 0.08 (Cresce bem rápido agora!)
            self.progresso_crescimento += velocidade_desenho
            
            if self.progresso_crescimento >= 1.0:
                self.progresso_crescimento = 1.0
            
            self.textura_caule = self._renderizar_textura_caule(self.progresso_crescimento)

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

            cx_base = self.x - (self.caule_x_offset - 0.5) * larg_final
            cy_base = (alt_final / 2) - (alt_final * 0.07)

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

        # O topo onde a flor nasce só será alcançado visualmente quando o progresso for 1.0
        topo_x = self.x - self.altura_caule * sin_a
        topo_y = self.altura_caule * cos_a

        # --- APARIÇÃO DA FLOR ---
        if self.textura_flor and self.progresso_crescimento >= 1.0:
            proporcao = self.textura_flor.height / self.textura_flor.width
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