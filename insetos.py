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

        self.direcao   = random.choice([-1, 1]) if not dados else (1 if dados[2] > 0 else -1)
        self.velocidade = self._definir_velocidade() * self.direcao
        
        self.marcado_para_sair = False
        self.is_extra_ativo = False

        if dados:
            self.center_x, y_antigo, _, _ = dados
            self.base_y   = self._posicionar_y(y_antigo)
            self.center_y = self.base_y
        else:
            self.center_x = -self.width if self.direcao == 1 else largura_janela + self.width
            self.base_y   = self._posicionar_y(random.uniform(altura_janela * 0.25, altura_janela * 0.75))
            self.center_y = self.base_y

        self.texture = (self.frames_right if self.velocidade > 0 else self.frames_left)[0]

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

    def update(self):
        self.center_x += self.velocidade
        self._aplicar_movimento_especifico()

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

    def _aplicar_movimento_especifico(self):
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
        super().__init__(*args, **kwargs)
        self.angulo = random.uniform(0, 6.28)

    def _definir_velocidade(self):
        return (self.largura_janela / 1440) * random.uniform(2.0, 4.0)

    def _posicionar_y(self, y_padrao):
        if y_padrao < (self.altura_janela * 0.2):
            return random.uniform(self.altura_janela * 0.25, self.altura_janela * 0.75)
        return y_padrao

    def _aplicar_movimento_especifico(self):
        self.angulo  += 0.06
        amplitude     = self.altura_janela * 0.04
        self.center_y = self.base_y + (math.sin(self.angulo) * amplitude)


def obter_configs_estado(estado):
    """Devolve a lista de configurações possíveis de insetos de acordo com o estado."""
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
    """Instancia um único inseto com base numa configuração específica."""
    prefixo = item["prefixo"]
    escala_vw = ESCALA_VW.get(prefixo, 0.02)
    e_terrestre = any(t in prefixo.lower() for t in TERRESTRES)
    classe = InsetoTerrestre if e_terrestre else InsetoVoador
    
    ins = classe(prefixo, item["frames"], altura, largura, escala_vw, dados)
    ins.marcado_para_sair = marcado_para_sair
    return ins

def carregar_insetos_iniciais(altura, largura, estado):
    """Carrega apenas os 3 insetos base que estão sempre no ecossistema."""
    lista = arcade.SpriteList()
    configs = obter_configs_estado(estado)
    for item in configs:
        lista.append(gerar_inseto_por_config(item, altura, largura))
    return lista

def converter_insetos_estado(insetos_atuais, altura, largura, novo_estado):
    """Converte TODOS os insetos atuais (base e extras) para o novo formato de dia/noite, mantendo posições."""
    nova_lista = arcade.SpriteList()
    configs = obter_configs_estado(novo_estado)
    
    for i, inseto_velho in enumerate(insetos_atuais):
        item = configs[i % len(configs)] 
        dados = (inseto_velho.center_x, inseto_velho.center_y, inseto_velho.direcao, inseto_velho.velocidade)
        
        novo_ins = gerar_inseto_por_config(
            item, altura, largura, dados, getattr(inseto_velho, "marcado_para_sair", False)
        )
        novo_ins.is_extra_ativo = getattr(inseto_velho, "is_extra_ativo", False)
        nova_lista.append(novo_ins)
        
    return nova_lista