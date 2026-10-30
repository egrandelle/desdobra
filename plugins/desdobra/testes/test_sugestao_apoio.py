# -*- coding: utf-8 -*-
"""Material sintetico dos testes de sugestao e regressao (sem teste proprio).

Nada aqui vem do corpus: nomes, textos e numeros sao inventados. Os segredos falsos sao montados na hora, aos
pedacos, para que o codigo-fonte nunca contenha uma sequencia que pareca chave de verdade (o teste de pacote
varre o repositorio com o mesmo detector).
"""
import random
import string

SHA_ARQUIVO = 'ab' * 32
ARQUIVO_CLIENTE = 'Peca Ficticia Lilas 1920x1080 FINAL.psd'
CAMINHO_CLIENTE = 'C:/Clientes/Agencia Ficticia/Campanha Azul/' + ARQUIVO_CLIENTE
FONTE_PS = 'FonteFicticiaPro-Bold'


def _aleatorio(n, alfabeto=string.ascii_letters + string.digits, semente=7):
    gerador = random.Random(semente + n)
    return ''.join(gerador.choice(alfabeto) for _ in range(n))


def segredos_falsos():
    """{nome do padrao no registro: segredo falso}. Montados aos pedacos."""
    maiusculas = string.ascii_uppercase + string.digits
    return {
        'chave de API do Google': 'AI' + 'za' + _aleatorio(35),
        'chave de acesso da AWS': 'AK' + 'IA' + _aleatorio(16, maiusculas),
        'token do GitHub': 'gh' + 'p_' + _aleatorio(36),
        'chave da Anthropic': 'sk' + '-ant-' + 'api03-' + _aleatorio(40),
        'chave da OpenAI': 'sk' + '-proj-' + _aleatorio(40),
        'token do Slack': 'xo' + 'xb-' + _aleatorio(12, string.digits) + '-' + _aleatorio(24),
        'chave do Stripe': 'sk' + '_live_' + _aleatorio(24),
        'chave privada': '-----BEG' + 'IN RSA PRIV' + 'ATE KEY-----',
        'token JWT': 'ey' + 'J' + _aleatorio(20) + '.ey' + 'J' + _aleatorio(20) + '.' + _aleatorio(30),
    }


def valor_rotulado():
    """Um 'senha: <valor>' com valor de alta entropia (letras e numeros)."""
    return 'se' + 'nha: ' + _aleatorio(24) + '7'


# ------------------------------------------------------------------ laudo/1 sintetico
def camada(lid, nome, tipo='pixel', texto=None, situacao='lida', regras=(), pai_id=None, caixa=(0, 0, 10, 10),
           visivel=True, coberta=None):
    t = None
    if texto is not None:
        t = {'conteudo': texto, 'runs': [{'inicio': 0, 'fim': len(texto), 'texto': texto, 'fonte_ps': FONTE_PS}]}
    motivos = [{'regra': r, 'descricao': 'motivo sintetico', 'medida': None, 'limite': None,
                'fonte': {'arquivo': 'arquitetura-v1.md', 'secao': '4.4'}} for r in regras]
    return {'identidade': {'arquivo_sha256': SHA_ARQUIVO, 'layer_id': lid}, 'nome': nome, 'tipo': tipo,
            'pai_id': pai_id, 'caminho_ids': [] if pai_id is None else [pai_id],
            'aparencia': {'visivel_efetiva': visivel, 'visivel_propria': visivel, 'opacidade': 255, 'preenchimento': 255,
                          'blend': 'normal', 'clipping': False, 'efeitos': []},
            'geometria': {'caixa': list(caixa), 'caixa_tinta': None, 'coberta_no_kv': coberta},
            'texto': t, 'smart_object': None, 'situacao': situacao, 'motivos': motivos}


def laudo(camadas, pct=0.5, feita=True, psd_tools='1.26.0', tempo_s=1.5, limiar=None):
    por = {'lida': 0, 'degradada': 0, 'bloqueante': 0}
    for c in camadas:
        por[c['situacao']] += 1
    return {
        'esquema': 'laudo/1',
        'origem': {'arquivo': ARQUIVO_CLIENTE, 'sha256': SHA_ARQUIVO, 'bytes': 1234,
                   'gravado_por': {'programa': 'Programa Ficticio', 'versao': '1.0'}, 'psd_tools': psd_tools,
                   'motor': '0.1.0'},
        'documento': {'largura': 1920, 'altura': 1080, 'formato': 'PSD', 'modo': 'RGB', 'bits': 8, 'icc': None,
                      'pranchetas': [], 'layer_comps': [], 'tem_previa': True, 'quadros': [], 'variantes_ocultas': []},
        'camadas': camadas,
        'fontes_usadas': [{'fonte_ps': FONTE_PS, 'camadas': [c['identidade']['layer_id'] for c in camadas
                                                             if c['texto']], 'situacao': 'nao_conferida'}],
        'prova_pixel': {'feita': feita, 'motivo': None if feita else 'orcamento', 'limiar': limiar or {
            'limite_id': 'prova_pixel.limiar_diferenca', 'valor': 24, 'unidade': 'nivel', 'fonte': None,
            'situacao': 'medido', 'efeito': 'registra'}, 'pct_px_acima_qualquer_canal': pct if feita else None},
        'regras': {},
        'recusas': [],
        'recursos': {'tempo_s': tempo_s, 'orcamento_bytes': 1 << 30},
        'resumo': {'n_camadas': len(camadas), 'por_situacao': por, 'por_situacao_visiveis': dict(por), 'por_regra': {},
                   'n_quadros': 0},
    }


def laudo_cheio_de_conteudo():
    """Laudo com nomes e textos distintos, mais camadas com segredo no nome e no texto.

    Devolve (laudo, textos_de_cliente, segredos): textos_de_cliente sao todos os nomes, textos, o nome do
    arquivo e o caminho, que nunca podem sair no modo c.
    """
    falsos = segredos_falsos()
    camadas = [
        camada(1, 'Fundo Gradiente Celeste Ficticio', tipo='preenchimento'),
        camada(2, 'Titulo Principal Ficticio', tipo='texto', texto='Promoção Fictícia Lilás'),
        camada(3, 'Selo Desconto Ficticio', tipo='texto', texto='Até 37% fictícios no app'),
        camada(4, 'Produto Recortado Ficticio', tipo='smart_embutido', situacao='degradada', regras=('D8',)),
        camada(5, 'Grupo Assinatura Ficticia', tipo='grupo'),
        camada(6, 'Logo Ficticio Vetor', tipo='forma', pai_id=5),
    ]
    lid = 10
    for nome_padrao, segredo in falsos.items():
        camadas.append(camada(lid, 'Camada com %s %s' % (nome_padrao, segredo), tipo='pixel'))
        camadas.append(camada(lid + 1, 'Texto com segredo %d' % lid, tipo='texto', texto='Use ' + segredo + ' agora'))
        lid += 2
    la = laudo(camadas)
    textos = [ARQUIVO_CLIENTE, CAMINHO_CLIENTE, FONTE_PS]
    for c in camadas:
        textos.append(c['nome'])
        if c['texto']:
            textos.append(c['texto']['conteudo'])
    return la, textos, list(falsos.values())


# ------------------------------------------------------------------ laudo da sonda sintetico (formato antigo)
def camada_sonda(lid, kind='pixel', status='lido', motivos=(), bbox=(0, 0, 10, 10), visivel=True, texto=None,
                 smart=None):
    t = None
    if texto is not None:
        t = {'conteudo': texto, 'runs': [{'inicio': 0, 'fim': len(texto), 'texto': texto, 'fonte_ps': FONTE_PS,
                                          'corpo_efetivo': 12.0}], 'paragrafos': []}
    return {'layer_id': lid, 'nome': 'Camada sintetica %d' % lid, 'kind': kind, 'classe': kind.title() + 'Layer',
            'visivel_propria': visivel, 'visivel_efetiva': visivel, 'bbox': list(bbox), 'texto': t,
            'smart_object': smart, 'laudo': {'status': status, 'motivos': list(motivos)}}


def laudo_sonda(camadas, pct=0.5, feita=True, status='ok', psd_tools='1.26.0', tempo_s=1.5):
    fid = {'feita': feita, 'motivo': None if feita else 'merged ou recomposicao indisponivel',
           'pct_px_acima_de_24_qualquer_canal': pct if feita else None}
    return {'versao_sonda': 'sintetica', 'psd_tools': psd_tools, 'tempo_s': tempo_s, 'camadas': camadas,
            'fidelidade': fid, 'erros': [],
            'resumo': {'fidelidade': {'pct_px_acima_de_24_qualquer_canal': pct} if feita else None,
                       'fidelidade_motivo': None},
            'status_execucao': {'status': status, 'motivo': None, 'tempo_s_externo': tempo_s + 1, 'returncode': 0}}


def laudo1_equivalente(sonda):
    """O laudo/1 que corresponde a um laudo da sonda sintetico (para testar o mapeamento nos dois sentidos)."""
    from desdobra.regressao import mapeamento
    camadas = []
    for c in sonda['camadas']:
        n = mapeamento.camada_da_sonda(c)
        regras = [r for r in n['regras'] if r != 'D9']
        situacao = n['situacao']
        nova = camada(c['layer_id'], c['nome'], tipo=n['tipo'], texto=n['texto'], situacao=situacao, regras=regras,
                      caixa=n['caixa'], visivel=n['visivel'])
        if c.get('texto'):
            nova['texto'] = {'conteudo': c['texto']['conteudo'],
                             'runs': [{'inicio': r['inicio'], 'fim': r['fim'], 'texto': r['texto'],
                                       'fonte_ps': r['fonte_ps']} for r in c['texto']['runs']]}
        camadas.append(nova)
    fid = sonda['fidelidade']
    return laudo(camadas, pct=fid['pct_px_acima_de_24_qualquer_canal'], feita=fid['feita'],
                 psd_tools=sonda['psd_tools'], tempo_s=sonda['tempo_s'])
