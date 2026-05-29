import arcade
import random
import os
import math

TERRESTRES = ("formiga", "caracol", "minhoca")

ESCALA_VW = {
    "inseto_pirilampo": 0.02808,
    "inseto_caracol":   0.03432,
    "inseto_minhoca":   0.04680,
    "inseto_abelha":    0.02808,
    "inseto_formiga":   0.02496,
    "inseto_joaninha":  0.02964,
}

ANIM_DELAY = 6


class Inseto(arcade.Sprite):
    def __init__(self, prefixo, num_frames, altura_janela, largura_janela, escala_vw, dados=None):
        super().__init__()
        self.prefixo         = prefixo
        self.largura_janela  = largura_janela
        self.altura_janela   = altura_janela

        self.frames_left, self.frames_right = self._carregar_frames(prefixo, num_frames)

        largura_alvo = largura_janela * escala_vw
        self.scale   = largura_alvo / self.frames_right[0].width

        self.frame_index = 0
        self.anim_timer  = 0
        self.base_y      = 0

        x_antigo = None
        y_antigo = None
        direcao_antiga = None
        velocidade_antiga = None
        frame_index_antigo = None
        anim_timer_antigo = None
        base_y_antigo = None

        if isinstance(dados, dict):
            x_antigo = dados.get("center_x")
            y_antigo = dados.get("center_y")
            direcao_antiga = dados.get("direcao")
            velocidade_antiga = dados.get("velocidade")
            frame_index_antigo = dados.get("frame_index")
            anim_timer_antigo = dados.get("anim_timer")
            base_y_antigo = dados.get("base_y")
        elif dados:
            x_antigo, y_antigo, direcao_antiga, velocidade_antiga = dados

        if direcao_antiga is None:
            self.direcao = random.choice([-1, 1])
        else:
            self.direcao = 1 if direcao_antiga > 0 else -1

        if velocidade_antiga is None:
            self.velocidade = self._definir_velocidade() * self.direcao
        else:
            self.velocidade = abs(float(velocidade_antiga)) * self.direcao
        
        self.marcado_para_sair = False
        self.is_extra_ativo = False

        if x_antigo is not None and y_antigo is not None:
            self.center_x = x_antigo

            manter_base_y = (
                isinstance(dados, dict)
                and isinstance(self, InsetoVoador)
                and dados.get("angulo") is not None
                and base_y_antigo is not None
            )

            if manter_base_y:
                self.base_y = float(base_y_antigo)
            else:
                self.base_y = self._posicionar_y(y_antigo)

            self.center_y = self.base_y
        else:
            self.center_x = -self.width if self.direcao == 1 else largura_janela + self.width
            self.base_y   = self._posicionar_y(random.uniform(altura_janela * 0.25, altura_janela * 0.75))
            self.center_y = self.base_y

        if frame_index_antigo is not None:
            self.frame_index = int(frame_index_antigo)

        if anim_timer_antigo is not None:
            self.anim_timer = int(anim_timer_antigo)

        frames = self.frames_right if self.velocidade > 0 else self.frames_left

        if frames:
            self.frame_index %= len(frames)
            self.texture = frames[self.frame_index]

    def _carregar_frames(self, prefixo, num_frames):
        left, right = [], []
        for i in range(1, num_frames + 1):
            caminho = os.path.join(
                os.path.dirname(__file__), "assets", "imgs", f"{prefixo}_{i:02d}.png"
            )
            tex = arcade.load_texture(caminho)
            left.append(tex)
            right.append(tex.flip_left_right())
        return left, right

    def update(self, direcao_vento=0.0):
        influencia_vento = float(direcao_vento) * self._fator_vento_horizontal() * abs(self.velocidade)
        deslocamento = self.velocidade + influencia_vento

        velocidade_minima = abs(self.velocidade) * 0.2
        if self.direcao > 0:
            deslocamento = max(deslocamento, velocidade_minima)
        else:
            deslocamento = min(deslocamento, -velocidade_minima)

        self.center_x += deslocamento
        self._aplicar_movimento_especifico(direcao_vento)

        frames = self.frames_right if self.velocidade > 0 else self.frames_left
        self.anim_timer += 1
        if self.anim_timer >= ANIM_DELAY:
            self.frame_index = (self.frame_index + 1) % len(frames)
            self.texture     = frames[self.frame_index]
            self.anim_timer  = 0

        if self.direcao == 1 and self.center_x > self.largura_janela + self.width:
            if getattr(self, "marcado_para_sair", False):
                self.kill() 
            else:
                self.center_x = -self.width
        elif self.direcao == -1 and self.center_x < -self.width:
            if getattr(self, "marcado_para_sair", False):
                self.kill()
            else:
                self.center_x = self.largura_janela + self.width

    def _fator_vento_horizontal(self):
        return 0.18

    def _aplicar_movimento_especifico(self, direcao_vento=0.0):
        pass

    def _definir_velocidade(self):
        raise NotImplementedError

    def _posicionar_y(self, y_padrao):
        raise NotImplementedError


class InsetoTerrestre(Inseto):
    def _definir_velocidade(self):
        return (self.largura_janela / 1440) * random.uniform(0.8, 1.5)

    def _posicionar_y(self, _):
        offset_base = self.altura_janela * 0.035 
        
        if "caracol" in self.prefixo:
            offset_base += (self.altura_janela * 0.025)
            
        return (self.height / 2) + offset_base


class InsetoVoador(Inseto):
    def __init__(self, *args, **kwargs):
        dados = kwargs.get("dados")
        if dados is None and len(args) >= 6:
            dados = args[5]

        super().__init__(*args, **kwargs)

        if isinstance(dados, dict) and dados.get("angulo") is not None:
            self.angulo = float(dados["angulo"])
        else:
            self.angulo = random.uniform(0, 6.28)

    def _definir_velocidade(self):
        return (self.largura_janela / 1440) * random.uniform(2.0, 4.0)

    def _posicionar_y(self, y_padrao):
        if y_padrao < (self.altura_janela * 0.2):
            return random.uniform(self.altura_janela * 0.25, self.altura_janela * 0.75)
        return y_padrao

    def _fator_vento_horizontal(self):
        return 0.55

    def _aplicar_movimento_especifico(self, direcao_vento=0.0):
        self.angulo  += 0.06
        amplitude     = self.altura_janela * 0.04
        deslocamento_vento_y = float(direcao_vento) * self.altura_janela * 0.02
        self.center_y = self.base_y + (math.sin(self.angulo) * amplitude) + deslocamento_vento_y


def obter_configs_estado(estado):
    if estado == "noturno":
        return [
            {"prefixo": "inseto_pirilampo", "frames": 3},
            {"prefixo": "inseto_caracol",   "frames": 4},
            {"prefixo": "inseto_minhoca",   "frames": 4},
        ]
    else:
        return [
            {"prefixo": "inseto_abelha",    "frames": 3},
            {"prefixo": "inseto_formiga",   "frames": 3},
            {"prefixo": "inseto_joaninha",  "frames": 4},
        ]

def gerar_inseto_por_config(item, altura, largura, dados=None, marcado_para_sair=False):
    prefixo = item["prefixo"]
    escala_vw = ESCALA_VW.get(prefixo, 0.02)
    e_terrestre = any(t in prefixo.lower() for t in TERRESTRES)
    classe = InsetoTerrestre if e_terrestre else InsetoVoador
    
    ins = classe(prefixo, item["frames"], altura, largura, escala_vw, dados)
    ins.marcado_para_sair = marcado_para_sair
    return ins

def carregar_insetos_iniciais(altura, largura, estado):
    lista = arcade.SpriteList()
    configs = obter_configs_estado(estado)
    for item in configs:
        lista.append(gerar_inseto_por_config(item, altura, largura))
    return lista

def converter_insetos_estado(insetos_atuais, altura, largura, novo_estado):
    nova_lista = arcade.SpriteList()
    configs = obter_configs_estado(novo_estado)
    
    for i, inseto_velho in enumerate(insetos_atuais):
        item = configs[i % len(configs)] 

        dados = {
            "center_x": inseto_velho.center_x,
            "center_y": inseto_velho.center_y,
            "base_y": getattr(inseto_velho, "base_y", inseto_velho.center_y),
            "direcao": getattr(inseto_velho, "direcao", 1),
            "velocidade": getattr(inseto_velho, "velocidade", 0),
            "frame_index": getattr(inseto_velho, "frame_index", 0),
            "anim_timer": getattr(inseto_velho, "anim_timer", 0),
            "angulo": getattr(inseto_velho, "angulo", None),
        }
        
        novo_ins = gerar_inseto_por_config(
            item, altura, largura, dados, getattr(inseto_velho, "marcado_para_sair", False)
        )
        novo_ins.is_extra_ativo = getattr(inseto_velho, "is_extra_ativo", False)
        nova_lista.append(novo_ins)
        
    return nova_lista