# Contrato entre as partes do M1

Este documento fixa o que cada parte do M1 entrega e recebe. Ele vale para os quatro agentes que trabalham em paralelo (plataforma, leitor-laudo, saida-regressao e plugin) e para o integrador. Quando o código e este documento divergirem, vale o código dos arquivos compartilhados, e quem achou a diferença registra uma pendência.

Caminhos relativos começam na raiz do repositório. O motor fica em `plugins/desdobra/motor`, e o pacote Python em `plugins/desdobra/motor/desdobra`. Neste documento, `motor/` quer dizer `plugins/desdobra/motor/` e `testes/` quer dizer `plugins/desdobra/testes/`.

## 1. Quem é dono de cada pasta

Cada agente só edita o que é dele. Para mudar um arquivo compartilhado, o agente registra uma pendência com o texto exato da mudança, e o integrador aplica.

| Dono | Arquivos |
|---|---|
| fundação (integrador) | `motor/desdobra/__init__.py`, `__main__.py`, `cli.py`, `resultado.py`, `arquivos.py`, `limites.py`, `contratos/`, `job/`, `plataforma/__init__.py`; `motor/fontes-de-limites.json`; `motor/pyproject.toml`, `motor/_construcao/`; `motor/requirements.lock`, `motor/requirements-dev.lock`; `motor/schemas/estado-1.json`, `envelope-1.json`, `fontes-de-limites-1.json`, `recusa-1.json`; `testes/conftest.py`, `testes/test_contratos.py`, `testes/test_job.py`, `testes/test_limites.py`, `testes/test_cli.py`, `testes/test_nucleo_plataforma.py`; `.claude-plugin/marketplace.json`, `plugins/desdobra/.claude-plugin/plugin.json`; `dev/gerar_lock.py`, `dev/requisitos-*.txt`; `docs/m1-interfaces.md`; `README.md`, `.gitignore` |
| plataforma | `motor/desdobra/plataforma/windows.py`, `motor/desdobra/plataforma/mac.py`, `testes/test_plataforma*` |
| leitor-laudo | `motor/desdobra/leitor/`, `motor/desdobra/laudo/`, `motor/schemas/estrutura-1.json`, `motor/schemas/laudo-1.json`, `testes/test_leitor*`, `testes/test_laudo*`, `testes/sinteticos/` |
| saida-regressao | `motor/desdobra/sugestao/`, `motor/desdobra/regressao/`, `motor/schemas/pacote-modelo-1.json`, `motor/schemas/regressao-1.json`, `motor/schemas/segredos-bloqueados-1.json`, `testes/test_sugestao*` (inclusive `test_sugestao_apoio.py`, material sintético compartilhado pelos testes de sugestão e regressão), `testes/test_regressao*`, `testes/test_pacote*` |
| plugin | `plugins/desdobra/skills/`, `plugins/desdobra/hooks/`, `motor/desdobra/doctor/`, `motor/schemas/doctor-1.json` (se criar), scripts de preparo do ambiente do plugin, `docs/` (menos este arquivo), `testes/test_doctor*` |

`plugins/desdobra/tela/` e `plugins/desdobra/biblioteca-specs/` ficam vazios no M1.

## 2. Regras que valem para todos

1. **PSD de cliente só no processo filho.** O processo principal nunca chama `PSDImage.open` em arquivo de cliente. Ele pode ler os 4 primeiros bytes (`8BPS`) para recusar um arquivo errado, com `desdobra.arquivos.tem_assinatura_psd`. Nunca use `smart_object.open()` nem `SmartObject.save()`. Leia `.data` só quando `kind == 'data'`, e abra sempre com `PSDImage.open(io.BytesIO(dados), ...)`. Nunca siga `fullPath` nem `relPath` de linkado.
2. **Fonte.** Nenhum código lê, copia, guarda ou serve arquivo de fonte. `desdobra.arquivos.eh_arquivo_de_fonte` reconhece fonte pela extensão e pelos 4 primeiros bytes; o job recusa fonte nas entradas. Pacote é reconhecido pela assinatura (zip `PK`, tar com `ustar` na posição 257, gzip `1f 8b`, bzip2, xz, 7z, rar e zstd) e pela extensão. Zip e tar são inspecionados sem extrair (nomes e primeiros bytes de cada membro, na memória) e são recusados quando têm membro com nome ou assinatura de fonte ou outro pacote dentro; pacote comprimido ou ilegível, que não dá para inspecionar sem extrair, também é recusado.
3. **Material de cliente fora do repositório.** Teste usa só PSD sintético gerado na hora. Nenhum nome de camada, texto de peça, nome de cliente ou marca, nem caminho do corpus, em código, teste, comentário ou documento. O corpus entra por argumento da CLI.
4. **Número de regra só pelo registro.** Ver a seção 6.
5. **Gravação atômica.** Todo arquivo do job é gravado por `desdobra.arquivos.gravar_bytes_atomico`, `gravar_texto_atomico`, `gravar_json_atomico` ou `desdobra.contratos.gravar` (que valida antes). O temporário tem o prefixo `.tmp-` e fica na mesma pasta.
6. **Contrato antes de gravar.** Todo arquivo de contrato é validado com `desdobra.contratos` antes de gravar e depois de ler.
7. **Texto para o usuário** em português do Brasil, sem travessão nem meia-risca e sem emoji. Identificadores em português sem acento.
8. **Log** (`log/eventos.jsonl` do job) só com eventos, códigos e números. Nunca texto de peça, nome de camada, saída de erro do filho ou conteúdo bruto.

## 3. Resultado e códigos de retorno (`desdobra/resultado.py`)

Todo subcomando devolve um `Resultado`:

```python
Resultado(comando: str,            # por exemplo 'ler', 'job proxima'
          codigo: int = Codigo.OK,
          situacao: str = 'ok',      # ok | ok_com_bloqueio | portao | concluido | erro | recusado | bloqueado | nao_disponivel
          fase: str | None = None,
          o_que_fazer: str | None = None,   # texto fixo do motor
          contagens: dict[str, int] = {},
          ids: dict[str, int | str | list[int]] = {},   # job_id, sha256, layer_id
          numeros: dict[str, float | None] = {},
          conteudo: dict = {},       # nomes, textos, miniaturas: só sai pelo filtro do envelope
          pasta_job: Path | None = None,
          linhas_humanas: list[str] = [])   # só no modo humano
```

Regras do `Resultado`:
- `o_que_fazer`, as chaves de `contagens`, `ids` e `numeros` e os valores de `ids` nunca levam nome de camada, texto de peça, nome de arquivo de cliente nem caminho. As chaves seguem `^[a-z][a-z0-9_]*$`.
- `ids` aceita inteiro, lista de inteiros ou texto hexadecimal de 8 a 64 caracteres (sha256, job_id).
- Conteúdo do job vai só em `conteudo`, no formato da seção 9.
- `linhas_humanas` pode ter qualquer texto, porque nunca sai no envelope.

Códigos (`Codigo`, um `IntEnum`):

| Código | Nome | Quando |
|---|---|---|
| 0 | OK | sucesso, inclusive fim da esteira |
| 1 | ERRO_INTERNO | exceção não tratada: bug do motor |
| 2 | USO | argumentos inválidos |
| 3 | RECUSADO | entrada recusada (arquivo inválido, contrato violado, entrada alterada fora do motor) |
| 4 | ORCAMENTO | memória ou tempo estourado de forma controlada |
| 5 | AUDITORIA | o gancho de auditoria do filho barrou uma ação |
| 9 | NAO_DISPONIVEL | comando ainda não existe neste build ou neste sistema |
| 10 | PORTAO | parou num portão humano |
| 20 | FASE_FALHOU | uma fase do job terminou com código diferente de zero |
| 21 | OCUPADO | outro processo do desdobra está usando o job |
| 30 | REGRESSAO_PIOROU | a regressão achou piora contra a linha de base (ou falha de segurança na varredura) |

`desdobra.resultado.MODOS_DADOS = ('a', 'b', 'c')`, do mais aberto ao mais fechado. `modo_mais_fechado(*modos)` e `modo_permitido(modo, teto)` fazem as contas.

## 4. CLI (`desdobra/cli.py`)

- Cada componente expõe `registrar(subparsers)` no próprio módulo. A função cria os subcomandos com `subparsers.add_parser(...)` e marca cada um com `set_defaults(executar=<função>, nome_comando='<nome>')`. A função recebe o `argparse.Namespace` e devolve um `Resultado`. Ela não imprime nada que importe: no modo envelope, a CLI segura stdout e stderr do handler.
- A lista de componentes está em `cli.COMPONENTES`:

| Módulo | Subcomandos | Dono |
|---|---|---|
| `desdobra.job` | `job criar`, `job proxima`, `job estado`, `job trocar-entrada` | fundação |
| `desdobra.leitor` | `ler` | leitor-laudo |
| `desdobra.regressao` | `regressao` | saida-regressao |
| `desdobra.doctor` | `doctor` | plugin |
| `desdobra.limites` | `limites` | fundação |

  Enquanto o módulo não existe, o subcomando responde código 9 (`nao_disponivel`). Basta criar o módulo com `registrar` para ele entrar; não é preciso mexer no `cli.py`.
- Opções globais, **antes** do subcomando: `--envelope` e `--teto-modo-dados {a,b,c}`. Exemplo: `desdobra --envelope --teto-modo-dados b job proxima <pasta>`.
- No modo humano, a CLI imprime `linhas_humanas`, as contagens, os avisos do detector de segredos (`desdobra.sugestao.envelope.avisos_de_segredo`: padrão e camada, nunca o trecho; com job, grava também `sugestoes/segredos-bloqueados.json`) e `O QUE FAZER: ...`, e sai com `resultado.codigo`.
- No modo envelope, a CLI imprime uma linha só, o envelope (seção 9), pela função única `cli.imprimir_envelope`, que chama `desdobra.sugestao.envelope.imprimir`. Erro de argumento vira código 2 sem eco dos argumentos; exceção vira código 1 com o nome do tipo da exceção, sem traceback.
- O modo do envelope é o `modo_dados` do `estado.json` de `resultado.pasta_job`, limitado pelo `teto_modo_dados` do estado e pelo `--teto-modo-dados`. Sem job, o modo é `c`.
- Chamada pelo Python do ambiente: `python -I -B -m desdobra ...` ou o script `desdobra` do ambiente.

## 5. Contratos (`desdobra/contratos`)

- Nome `"<nome>/<versão>"`; esquema em `motor/schemas/<nome>-<versão>.json`, JSON Schema 2020-12, com `"$id": "urn:desdobra:schema:<nome>:<versão>"` e `properties.esquema = {"const": "<nome>/<versão>"}`. Todo arquivo de contrato tem o campo `esquema`.
- API: `contratos.validar(dados, 'laudo/1', origem=None)`, `contratos.ler(caminho, 'laudo/1')`, `contratos.gravar(caminho, dados, 'laudo/1')`, `contratos.carregar_esquema(nome)`, `contratos.listar_esquemas()`. Erro: `ErroContrato` com `esquema`, `onde` (ponteiro JSON, por exemplo `/camadas/3/situacao`) e uma mensagem que diz o arquivo, o contrato, o campo e o que falhou.
- Mudança compatível (campo opcional novo) fica na mesma versão. Mudança incompatível cria a versão seguinte, por exemplo `laudo-2.json`.
- `testes/test_contratos.py` confere que todo esquema da pasta é válido e bate com o nome do arquivo.

Esquemas do M1:

| Contrato | Arquivo | Quem grava | Dono |
|---|---|---|---|
| `estado/1` | `estado.json` do job | `desdobra.job` | fundação |
| `fontes-de-limites/1` | `motor/fontes-de-limites.json` | integrador | fundação |
| `envelope/1` | stdout com `--envelope` | `desdobra.cli` com `desdobra.sugestao.envelope` | fundação (esquema), saida-regressao (montagem) |
| `recusa/1` | `recusa.json` do filho | filho do leitor | fundação |
| `estrutura/1` | `estrutura.json` do filho | filho do leitor | leitor-laudo |
| `laudo/1` | `laudo/laudo.json` | `desdobra.laudo` | leitor-laudo |

## 6. Registro de limites (`desdobra/limites.py` e `motor/fontes-de-limites.json`)

Cada limite tem `id` (por exemplo `prova_pixel.limiar_diferenca`), `valor` (número, texto ou lista; `null` só se `a_calibrar`), `unidade`, `fonte` (`{"arquivo", "secao"}` ou `null`), `situacao` (`medido`, `decidido`, `folha`, `a_calibrar`), `efeito` (`reprova`, `avisa`, `registra`) e `nota`.

Regras que o carregador e o esquema garantem:
- sem fonte, a situação é `a_calibrar`;
- `a_calibrar` nunca reprova (o registro com `a_calibrar` e `reprova` é recusado; `Limite.efeito_efetivo` também rebaixa para `avisa`);
- `decidido` cita `decisoes-v1.md`; `medido` cita `pesquisa/...`; `folha` cita `biblioteca-specs/...` ou `pesquisa/specs-...`;
- a fonte é relativa à pasta do projeto de pesquisa (onde ficam `pesquisa/`, `decisoes-v1.md` e `arquitetura-v1.md`).

API:

```python
from desdobra import limites
limites.valor('prova_pixel.limiar_diferenca')    # 24; ErroLimite se não existe ou se está sem valor
limites.obter('coberta_no_kv.ocupa_canvas_fracao')   # Limite
limites.efeito('segredos.padroes')                # 'reprova' | 'avisa' | 'registra' (efeito efetivo)
limites.obter(id).citacao()   # {'limite_id','valor','unidade','fonte','situacao','efeito'}: grave isto ao lado da medida
```

**Convenção dos números sem fonte** (verificada por `testes/test_limites.py`, que reprova o build). Fora de `desdobra/limites.py`, em todo `.py` do pacote `desdobra`, é proibido:
1. constante numérica como operando direto de comparação (`<`, `<=`, `>`, `>=`, `==`, `!=`, `in`, `not in`), inclusive dentro de tupla, lista ou conjunto comparado: `x > 24`, `n in (2, 3)`;
2. atribuição a nome em MAIÚSCULAS no nível do módulo ou de classe com constante numérica no valor: `LIMIAR = 24`, `ORCAMENTO = 512 * MB`.

Exceções:
- os números neutros 0, 1 e -1 (e 0.0, 1.0, -1.0);
- os membros de classes `Enum`, `IntEnum`, `Flag` ou `IntFlag` (códigos de protocolo);
- a linha com o comentário `# numero-neutro: <motivo>`, com o motivo escrito. Serve para fato de formato de arquivo (o cabeçalho do PSD tem 26 bytes, a versão é 1 ou 2), tamanho de buffer e outros números que não decidem nada.

O mesmo teste confere que todo id passado como texto literal para `limites.valor`, `limites.obter` ou `limites.efeito` existe no registro. Limite novo entra por pendência ao integrador, com valor, unidade, fonte, situação, efeito e nota.

Limites já registrados para o M1:

| id | valor | situação | para quem |
|---|---|---|---|
| `prova_pixel.limiar_diferenca` | 24 | medido | leitor-laudo, regressao |
| `prova_pixel.fracao_reprova` | null | a_calibrar | laudo (só registra) |
| `prova_pixel.regiao_min_px`, `prova_pixel.max_regioes` | 20, 40 | a_calibrar | leitor |
| `coberta_no_kv.fracao_coberta_min` | 1.0 | a_calibrar | laudo |
| `coberta_no_kv.ocupa_canvas_fracao` | 1.0 | a_calibrar | laudo |
| `quadros.fracao_canvas_grupo_topo` | 0.9 | a_calibrar | laudo (valor do instrumento da pesquisa que deu 14 de 27; a seção da pesquisa não traz o número) |
| `quadros.min_candidatos` | 2 | decidido | laudo |
| `isolador.base_python_bytes` | 102760448 | medido | leitor (orçamento; efeito avisa: decide o código, a parada pede confirmação do DA) |
| `isolador.fator_abertura_max` | 2.64 | medido | leitor (orçamento) |
| `isolador.margem_orcamento` | 1.25 | a_calibrar | leitor (orçamento; efeito avisa) |
| `isolador.tempo_max_s` | 600 | a_calibrar | leitor, plataforma (efeito avisa: a parada pede confirmação do DA) |
| `isolador.fracao_pico_memoria` | 0.95 | a_calibrar | plataforma |
| `isolador.stdout_max_bytes` | 1048576 | a_calibrar | plataforma |
| `leitor.max_alloc_bytes` | 4294967296 | medido | leitor (efeito avisa: bloqueio de composição) |
| `leitor.profundidade_max_smart` | 2 | a_calibrar | leitor (efeito avisa: alerta smart_object_nao_aberto) |
| `laudo.miniatura_lado_px`, `laudo.previa_lado_px` | 384, 1600 | a_calibrar | leitor |
| `laudo.tolerancia_escala_texto` | 1e-6 | a_calibrar | laudo (D7) |
| `regressao.arquivo_grande_bytes` | 524288000 | a_calibrar | regressao |
| `segredos.padroes` | lista de expressões regulares (inclui o valor rotulado como segredo) | decidido | sugestao |
| `segredos.entropia_min_bits` | 3.0 | a_calibrar | sugestao (só registra; o código ainda não lê) |
| `isolador.bytes_por_px_canvas` | 128 | a_calibrar | leitor (orçamento; efeito avisa) |
| `laudo.tolerancia_malha_px` | 0.01 | a_calibrar | laudo (D6) |
| `laudo.tolerancia_nao_afim_px`, `laudo.tolerancia_paralelogramo_px` | 0.01, 0.02 | a_calibrar | laudo (D6) |
| `ambiente.python_versoes_aceitas` | ["3.14"] | medido | doctor e gancho |
| `ambiente.trava_preparo_max_s` | 600 | a_calibrar | gancho |
| `regressao.tolerancia_prova_pixel_pct` | 0 | decidido | regressao |
| `regressao.varredura_min_caracteres` | 4 | a_calibrar | regressao (varredura da saída padrão: separa o modo de procurar termo longo e curto; os dois contam como achado) |

`desdobra limites` lista o registro.

## 7. Pasta do job e esteira (`desdobra/job`)

### 7.1 Pasta

| Caminho | Conteúdo | Quem grava |
|---|---|---|
| `estado.json` | `estado/1` | só `desdobra.job` |
| `entrada/kv.psd` ou `entrada/kv.psb` | o KV, congelado | `job criar`, `job trocar-entrada` |
| `entrada/campanha/...`, `entrada/specs/...` | outros arquivos, congelados | idem |
| `laudo/laudo.json` | `laudo/1` | fase `ler` |
| `laudo/bruto/<sha256>/` | saída de cada filho do leitor (seção 8.3) | fase `ler` |
| `laudo/miniaturas/`, `laudo/contato/`, `laudo/assets/<sha256>.png` | imagens do laudo | fase `ler` |
| `laudo/.trabalho/` | pasta de trabalho vazia de cada filho; apagada ao fim | fase `ler` |
| `sugestoes/` | `pacote-modelo.json`, `segredos-bloqueados.json`, e só no modo a `miniaturas/` | `desdobra.sugestao` |
| `log/eventos.jsonl` | eventos e códigos | todos, por `nucleo.registrar_evento` |
| `.desdobra.trava` | trava do job enquanto um comando roda | `desdobra.job` |

Toda entrada é congelada: copiada, conferida por sha256 contra a origem, gravada só leitura e registrada em `estado.entradas` com `sha256`, `bytes` e `congelada_em`. Fonte é recusada. `job proxima` confere `entrada/` inteira antes de rodar: arquivo mudado, sumido ou novo dá código 3 com o que fazer. A troca legítima é `job trocar-entrada`.

### 7.2 Comandos

```
desdobra job criar <pasta> --kv <arquivo> --modo-dados {a,b,c} [--teto-modo-dados {a,b,c}] [--campanha <pasta>] [--specs <pasta>]
(--psd é sinônimo de --kv)
desdobra job proxima <pasta> [--todas]      (ou --job <pasta>)
desdobra job estado <pasta>
desdobra job trocar-entrada <pasta> <entrada/...> <arquivo_novo>
```

`--modo-dados` é obrigatório e não tem valor inicial. Com `--teto-modo-dados`, um modo mais aberto que o teto é recusado. O teto pode vir depois de `criar` ou como opção global antes do subcomando; sem a opção depois de `criar`, vale a global.

### 7.3 Fases, hash e invalidação

`desdobra.job.fases.Fase(id, tipo, descricao, entradas, depende_de, saidas, comando, o_que_fazer, cumprido)`:
- `tipo` é `fase` (o motor roda `comando(pasta)` num subprocesso) ou `portao` (o humano faz a parte dele; `cumprido(pasta)` diz se fez);
- `entradas` e `saidas` são padrões glob relativos à pasta do job;
- o hash de uma fase cobre as `entradas` dela e as `saidas` das fases em `depende_de`, cada padrão com o próprio sha256 (arquivo: sha256 do arquivo; pasta ou vários arquivos: sha256 da lista ordenada de caminho e sha256);
- uma fase está válida quando está `concluida`, os hashes de agora batem com os gravados e as fases de que depende estão válidas. Mudar uma entrada invalida a fase que a usa e, em cadeia, as que dependem dela; as outras ficam como estão. Se a fase de cima roda de novo e grava a mesma saída, a de baixo volta a valer sem rodar. As saídas da própria fase também contam: ao concluir, a fase grava `hash_saidas`, e saída apagada ou mudada depois disso invalida a fase.

`job proxima` acha a primeira fase inválida e:
- se é portão cumprido, marca concluído e segue;
- se é portão não cumprido, para com código 10, situação `portao` e `o_que_fazer` do portão;
- se é fase, roda o comando com cwd na pasta do job, com as opções `--teto-memoria-bytes N` e `--tempo-max-s N` do `job proxima` acrescentadas ao comando quando o DA as deu. Código diferente de zero marca `falhou` e para com código 20. Código 0 sem as `saidas` prometidas também falha. Código 0 com as saídas marca `concluida` e grava os hashes de antes de rodar;
- sem `--todas`, para depois de uma fase; com `--todas`, segue até portão, falha ou fim. No fim, situação `concluido` e código 0.

A fase grava em `estado.json` (`fases.<id>.opcoes`) as opções com que rodou. Um `job proxima` com `--teto-memoria-bytes` ou `--tempo-max-s` diferente do gravado invalida a fase concluída (motivo `o teto confirmado pelo DA mudou`) e a roda de novo com o teto novo; o mesmo teto, ou nenhuma opção, deixa a fase como está. Esse é o caminho que o `o_que_fazer` da leitura parada num limite a calibrar manda o DA seguir.

Bloqueio da fase no envelope do `job proxima`: quando a fase termina com `situacao` `ok_com_bloqueio` (código 0) ou `bloqueado` (código diferente de zero), o envelope do `job proxima` sai com essa situação (`ok_com_bloqueio` com código 0, ou `bloqueado` com código 20) e com o `o_que_fazer` da fase. Com `--todas`, a esteira segue depois de `ok_com_bloqueio`, e o envelope final, no lugar de `concluido`, sai `ok_com_bloqueio`, com o `o_que_fazer`, as contagens (por exemplo `recusas` e `bloqueios_documento`) e o `fase` da fase que bloqueou. Quando a fase sai com o código 5 (alarme do gancho de auditoria), o `job proxima` sai com código 20, `contagens.codigo_da_fase` 5 e o `o_que_fazer` da auditoria que a fase mandou.

A esteira do M1 (`FASES_M1`) tem uma fase só: `ler`, com entradas `entrada/kv.*` e `entrada/campanha` (o laudo propõe o casamento de cada smart object linkado com os arquivos da campanha, então acrescentar ou trocar um arquivo nela invalida a fase), saídas `laudo/laudo.json` e `sugestoes/pacote-modelo.json` e comando `python -I -B -m desdobra --envelope ler --job <pasta>`.

A fase roda com `--envelope`. O `job proxima` lê a última linha `envelope/1` da saída da fase (já filtrada pelo modo do job) e repassa no próprio `Resultado` as contagens, os ids, os números e o conteúdo dela, mais `codigo_da_fase`. Assim a skill usa só a esteira. O `o_que_fazer` da fase aparece nas linhas humanas.

Regras para o subcomando que roda como fase: ele recebe `--job <pasta>`, não pega a trava do job (quem pega é `job proxima`), não mexe em `estado.json`, grava só as próprias saídas, de forma atômica, e sai com o código do seu protocolo. O que ele imprime fica só na memória do `job proxima` e aparece só no modo humano.

## 8. Leitor e laudo

### 8.1 `desdobra ler`

```
desdobra ler --job <pasta>                         (fase do job: lê entrada/kv.* e grava em laudo/)
desdobra ler <psd> --saida <pasta>   (avulso, para a regressão; a pasta de saída recebe a mesma árvore de laudo/; o envelope sai sempre no modo c)
opções dos dois usos: --teto-memoria-bytes N e --tempo-max-s N (teto confirmado pelo DA, no lugar do calculado)
```

`--teto-memoria-bytes` tem de ser um inteiro maior que zero e até o maior `size_t` do sistema; `--tempo-max-s` tem de ser um número finito maior que zero (`nan` e `inf` não valem). Fora disso, `ler` e `job proxima` saem com código 2 (erro de uso) e o `o_que_fazer` diz qual valor não serve (`desdobra.leitor.erro_no_teto`).

Fluxo no processo principal (que nunca parseia o PSD):
1. lê os 26 bytes do cabeçalho só com `struct` (`desdobra.leitor.cabecalho.ler_de_arquivo`), sem psd-tools, e calcula o orçamento: `orcamento = (isolador.base_python_bytes + isolador.fator_abertura_max * bytes_abertos + isolador.bytes_por_px_canvas * min(largura * altura, 64 * bytes_abertos)) * isolador.margem_orcamento`, em bytes inteiros. O 64 é a razão máxima do PackBits (fato do formato, `# numero-neutro`): o orçamento nunca acredita num canvas maior que isso, e é o que faz o cabeçalho forjado de 29999 x 29999 ser recusado;
2. cria uma pasta de trabalho vazia em `laudo/.trabalho/<n>/` e a pasta de saída `laudo/bruto/<sha256 do arquivo>/`;
3. chama `plataforma.obter().executar_isolado(comando_do_filho, orcamento, limites.valor('isolador.tempo_max_s'), pasta_trabalho)`;
4. lê e valida `estrutura.json` (ou `recusa.json`);
5. para cada smart object embutido PSD/PSB listado na estrutura, até `leitor.profundidade_max_smart`, chama outro filho com `--recorte` e `--profundidade`;
6. monta o laudo pela função pura de `desdobra.laudo`, valida contra `laudo/1` e grava `laudo/laudo.json`.

Com `--job`, `ler` grava também `sugestoes/pacote-modelo.json` (`desdobra.sugestao.pacote.gravar_pacote`), e o `conteudo` do Resultado sai de `pacote.conteudo_para_resultado(laudo)`.

Códigos de `ler`: 0 laudo gravado (mesmo com camadas bloqueantes); 3 arquivo recusado inteiro, com `laudo.json` gravado assim mesmo, `camadas: []` e a recusa em `recusas`; 4 orçamento estourado na leitura estrutural; 5 alarme do gancho de auditoria, no filho do documento ou no filho de qualquer smart object embutido (a recusa entra no laudo com etapa `smart_object_<etapa>`, e o `o_que_fazer` é o da auditoria); 1 bug. Composição que estoura o orçamento não derruba a leitura: vira `prova_pixel.feita = false` com motivo `orcamento`, uma recusa sem `layer_id` na etapa `composicao` (contada em `resumo.bloqueios_documento`) e código 0 com `situacao` `ok_com_bloqueio`. Qualquer recusa com código 0 também sai como `ok_com_bloqueio`, para o envelope nunca dizer só `ok` quando há bloqueio.

Limites que decidem o código (`desdobra.leitor.LIMITES_QUE_DECIDEM_CODIGO`): o orçamento de memória (`isolador.base_python_bytes`, `isolador.fator_abertura_max`, `isolador.bytes_por_px_canvas`, `isolador.margem_orcamento`) e o tempo (`isolador.tempo_max_s`). A recusa por orçamento ou tempo leva `limites` (as citações) e `decisao`: `pede_confirmacao_do_da` quando algum limite do cálculo está a calibrar (hoje é o caso), `teto_confirmado_pelo_da` quando a leitura rodou com `--teto-memoria-bytes` ou `--tempo-max-s`, e `reprova` só quando todos têm fonte. Com `pede_confirmacao_do_da`, a `situacao` do envelope é `bloqueado`, e o `o_que_fazer` diz como o DA confirma um teto maior. O `job proxima` repassa as duas opções à fase do motor. A recusa do cabeçalho cuja imagem declarada passa do orçamento tem tipo `orcamento`. A recusa da composição (etapa `composicao`, tipo `memoria` ou `tempo`) recebe `limites` e `decisao` do mesmo jeito; na de memória, as citações incluem também `leitor.max_alloc_bytes`, porque o filho compõe com o menor entre esse teto e o orçamento. O `o_que_fazer` de limite a calibrar manda rodar `desdobra job proxima <pasta do job> --teto-memoria-bytes N` (ou `--tempo-max-s N`), ou `desdobra ler` de novo com a mesma opção fora do job.

`Resultado` de `ler`: `contagens` com `camadas`, `lidas`, `degradadas`, `bloqueantes`, `quadros`, `cobertas_no_kv`, `smart_objects`; `numeros` com `tempo_s`, `pico_bytes`, `pct_px_acima_qualquer_canal`; `ids` com `arquivo_sha256`; `conteudo.camadas` com `layer_id`, `nome`, `tipo`, `situacao` e `textos` de cada camada (o envelope filtra).

### 8.2 Protocolo do processo filho

Chamada:

```
python -I -B -m desdobra.leitor.filho <arquivo> <pasta_saida> --orcamento-bytes N --profundidade N --profundidade-max N [--recorte INICIO:TAMANHO] [--sem-composicao]
```

- `<arquivo>` é o PSD ou PSB de entrada (só leitura). Com `--recorte`, o filho lê só os `TAMANHO` bytes a partir de `INICIO` desse arquivo (os dados de um smart object embutido, achados pelo índice próprio) e abre com `PSDImage.open(io.BytesIO(dados), max_alloc_bytes=..., parse_limits=...)`.
- `--profundidade` é o nível do que está sendo aberto (0 = documento). Com `--profundidade` maior que `--profundidade-max`, o filho recusa (código 3, tipo `profundidade`).
- `--sem-composicao` pula a recomposição e a prova de pixel.
- O filho roda com cwd na pasta de trabalho vazia e não faz nada arriscado antes de ler a linha `iniciar\n` da entrada padrão (`plataforma.LINHA_LIBERAR`). O isolador manda essa linha só depois de confinar o processo.
- Depois de ler a linha, o filho instala um gancho de auditoria (`sys.addaudithook`) como alarme. Todo caminho é conferido depois de resolvido (`os.path.realpath`), para link simbólico ou junção não levarem para fora. Permite abrir para leitura o arquivo de entrada, os módulos do Python e do ambiente, `motor/schemas/*.json` e `motor/fontes-de-limites.json`; permite gravar, copiar, mudar data e listar só dentro de `<pasta_saida>` (listar também nas pastas do ambiente e do `sys.path`), e nunca num arquivo com mais de um nome (hardlink). Barra criar link (`os.link`, `os.symlink`, `_winapi.CreateJunction`), pipe com nome, `_winapi.CreateFile` fora da saída (a não ser leitura de caminho permitido), `ctypes.dlopen`, `winreg`, criar, abrir ou matar processo, abrir socket e qualquer outro arquivo. Um bloqueio vira `recusa.json` com tipo `auditoria` e código 5. Risco residual: `os.stat` e `os.path.exists` não geram evento de auditoria, e código nativo passa por fora do gancho.
- BLAS com 1 fio vem do ambiente montado pela plataforma.
- Todo o resultado vai para o disco, em `<pasta_saida>`, com gravação atômica:

| Arquivo | Quando |
|---|---|
| `estrutura.json` (`estrutura/1`) | leitura feita (código 0) |
| `recusa.json` (`recusa/1`) | arquivo recusado inteiro (códigos 3, 4, 5) |
| `previa.png`, `recomposicao.png`, `diferenca.png` | quando a prova de pixel foi feita |
| `miniaturas/<layer_id>.png` | miniaturas por camada, lado maior em `laudo.miniatura_lado_px` |

- Na saída padrão, o filho imprime no máximo uma linha JSON: `{"esquema": "filho/1", "codigo": <int>, "arquivo": "estrutura.json" | "recusa.json"}`. Nada de nome de camada nem texto. O pai não depende dessa linha: ele lê o disco.
- Códigos: 0 estrutura gravada; 2 argumentos errados; 3 recusado (cabeçalho, orçamento do cabeçalho, formato, leitura com ValueError ou OSError, profundidade); 4 MemoryError controlado; 5 gancho de auditoria; 1 exceção não tratada (bug; traceback só no stderr).
- Antes de parsear, o filho confere os 26 bytes do cabeçalho (assinatura, versão, eixos, canais, bits) e estima a memória da composição contra `--orcamento-bytes`. O PSD sintético de 29999 x 29999 tem de ser recusado aqui, antes de alocar.
- Linkado (`liFE`, `liFA`) é só registrado: nome, tamanho e data. O filho nunca abre o caminho gravado.
- O filho de smart object (profundidade > 0) não faz a passada de pixels (miniaturas, assets, cobertura) e decodifica o composto sem conversão de cor, só para medir se ele é de uma cor só.
- No Windows, `Py_FatalError` sai com o código 3, o mesmo de `recusado`. O pai só trata o código 3 como recusa quando `recusa.json` existe e valida; sem o arquivo, é bug ou queda.
- O gancho de auditoria permite ler módulos em `sys.base_prefix`, porque no Windows o processo que roda é o Python base (seção 10).

### 8.3 `estrutura/1` (versão inicial, dono leitor-laudo)

O esquema completo está em `motor/schemas/estrutura-1.json`. Em resumo: `leitor` (versões), `origem` (nome, sha256, bytes, profundidade, recorte, pai), `documento` (dimensões, formato, versão, modo, bits, canais, ICC com hash, quem gravou, prévia, pranchetas, layer comps), `indice_smart` (registros lnk2, lnk3, lnkD com deslocamento e tamanho dos dados, sha256 do embutido, registro do linkado), `camadas` (identidade, árvore, visibilidade própria e efetiva, opacidade, preenchimento, blend, clipping, caixa e caixa de tinta, máscara, efeitos com `desenhado_pelo_render`, ajuste com `entra_no_composto`, smart object, texto por run, pixels com `fracao_coberta` e `fracao_canvas` e as contagens inteiras `px_visiveis`, `px_cobertos` e `px_area_ref`, mais `pulado`, `medidas_regras`), `prova_pixel` (com as contagens inteiras `px_acima_qualquer_canal` e `px_total`), `recursos`, `erros` e `arquivos`. A estrutura só tem fatos medidos; o julgamento é do laudo. Campos opcionais acrescentados no M1: `auditoria` (gancho instalado e bloqueios) e `efeitos_pulados` (modelo da mensagem do log do psd-tools e os layer_id, nunca a mensagem formatada).

### 8.4 `laudo/1` (versão inicial, dono leitor-laudo)

O esquema completo está em `motor/schemas/laudo-1.json`, com os campos de `arquitetura-v1.md` §5.2. Pontos que os outros agentes usam:
- cada camada tem `identidade = {arquivo_sha256, layer_id}`, `tipo` (`texto`, `forma`, `pixel`, `cor_solida`, `preenchimento`, `ajuste`, `grupo`, `prancheta`, `smart_embutido`, `smart_linkado`, `outro`), `situacao` (`lida`, `degradada`, `bloqueante`) e `motivos`, cada motivo com `regra`, `descricao`, `medida`, `limite` (citação) e `fonte`;
- as regras são B1 a B3 e D1 a D8 da sonda. A D9 foi aposentada no psd-tools 1.26.0 e o esquema não aceita `D9`;
- `geometria.coberta_no_kv`: `coberta`, `fracao_coberta`, `ocupa_canvas`, `fracao_canvas`, `limites` e `sugestao_da_regra = {funcao: estrutura | fora_da_peca, regra: decisao-10, fonte}`. A função vem só como sugestão citada; o laudo não tem campo de função;
- `documento.quadros` e `documento.variantes_ocultas` são entidades; `quadros[].regra` é `pranchetas` ou `grupos_de_topo`;
- `fontes_usadas[].situacao` é `nao_conferida` no M1, porque a conferência das faces instaladas entra no M2;
- `prova_pixel.limiar` é a citação do limite `prova_pixel.limiar_diferenca`;
- `efeitos_suportados` registra a lista de efeitos e ajustes que o psd-tools 1.26.0 desenha, conferida no M1;
- cada camada tem `alertas` (casos de smart object da pesquisa e os subcasos da antiga D9, que não mudam a situação);
- `coberta_no_kv` leva a sugestão só em `sugestao_da_regra` (`funcao` `estrutura` ou `fora_da_peca`, a regra e a fonte). A decisão usa as contagens inteiras de pixels da estrutura/1 (`px_cobertos`, `px_visiveis`, `px_area_ref`, declaradas como inteiras no esquema), sem arredondamento: a conta é exata em fração, com o limite lido como a fração decimal escrita no registro (0,07 vale 7/100); `fracao_coberta` e `fracao_canvas` ficam só para leitura.
- Camada de texto com tinta em fonte não conferida leva o alerta `fonte_nao_conferida` (no M1, todas: a conferência das faces entra no M2). O envelope do `ler` conta `fontes_nao_conferidas` e `camadas_com_fonte_nao_conferida`.
- Passada de pixels que passa do orçamento numa camada (`pixels.pulado`) é B2, bloqueante.
- Smart object embutido além da profundidade máxima fica com `abertura.situacao` `nao_aberto` e o alerta `smart_object_nao_aberto`.
- `prova_pixel` leva também as contagens inteiras `px_acima_qualquer_canal` e `px_total`; a porcentagem fica para leitura.
- `resumo` leva `bloqueios_documento` (recusas sem `layer_id`) e `n_fonte_nao_conferida`.

## 9. Envelope de saída (`envelope/1`)

O envelope é a única coisa que o motor imprime com `--envelope`. Campos obrigatórios: `esquema`, `modo_dados`, `comando`, `fase`, `situacao`, `codigo`, `o_que_fazer`, `contagens`, `ids`, `numeros`, `segredos_bloqueados`. O campo `conteudo` é opcional e depende do modo:

| Modo | `conteudo` |
|---|---|
| a | `camadas` (layer_id, nome, tipo, situacao, textos) e `miniaturas` (só caminhos `sugestoes/miniaturas/<arquivo>.png`, só de camadas sem texto) |
| b | só `camadas` |
| c | ausente |

Quem monta: `desdobra.sugestao.envelope.montar(resultado: Resultado, modo: str) -> dict`, do agente saida-regressao. A função:
- copia os campos fixos do `Resultado`;
- passa `resultado.conteudo` pelo detector de segredos (padrões de `segredos.padroes`) e pelo filtro do modo;
- tira do envelope toda camada com achado (nome e textos) e soma em `segredos_bloqueados`. O detalhe (layer_id e nome do padrão, nunca o trecho achado) vai para `sugestoes/segredos-bloqueados.json` do job, que só o DA vê;
- devolve um dict que valida contra `envelope/1`.

Enquanto `desdobra.sugestao.envelope` não existe, a CLI usa `cli.envelope_minimo`, que sempre devolve o modo `c`, sem `conteudo`.

Contratos da saída e da regressão: `segredos-bloqueados/1` (`sugestoes/segredos-bloqueados.json`, só para o DA), `pacote-modelo/1` (`sugestoes/pacote-modelo.json`) e `regressao/1` (`<saida>/regressao-<data>.json`).

## 10. Interface de plataforma (`desdobra/plataforma`)

```python
from desdobra import plataforma
p = plataforma.obter()          # PlataformaWindows no win32, PlataformaMac no darwin, PlataformaSemSuporte no resto
r = p.executar_isolado(comando: list[str], orcamento_bytes: int, tempo_s: float, pasta_trabalho: Path,
                       *, ambiente: dict[str, str] | None = None) -> ResultadoFilho
p.fontes_instaladas() -> list[FaceInstalada]     # M2; hoje NotImplementedError
p.porta_livre() -> int                           # porta livre em 127.0.0.1
p.interpretador() -> Path                        # o Python do ambiente
```

`ResultadoFilho(situacao, codigo, pico_bytes, stdout_bytes, stderr_resumo, tempo_s=0.0, motivo=None)`:

| Campo | Significado |
|---|---|
| `situacao` | `ok` (terminou sozinho; o código está em `codigo` e pode ser diferente de zero), `memoria` (bateu no teto: morto pelo sistema, ou falhou com pico acima de `isolador.fracao_pico_memoria` do teto), `tempo` (o pai matou por tempo), `queda` (término anormal: exceção nativa, código de erro do sistema, sinal), `recusado` (a plataforma não executou) |
| `codigo` | código de retorno do filho; `None` se ele nem rodou |
| `pico_bytes` | pico de memória medido pelo sistema (no Windows, `PeakProcessMemoryUsed` do Job Object); `None` se o sistema não mede |
| `stdout_bytes` | os bytes da saída padrão do filho, até `isolador.stdout_max_bytes` |
| `stderr_resumo` | fim da saída de erro, só para diagnóstico humano. Pode ter conteúdo do arquivo: nunca vai para envelope, log ou laudo |
| `tempo_s` | tempo de relógio |
| `motivo` | texto fixo da plataforma para `recusado`, `memoria`, `tempo` e `queda` |

Obrigações da implementação Windows (`windows.py`, a partir de `p04_isolamento.py`):
- Job Object com `JOB_OBJECT_LIMIT_PROCESS_MEMORY` (teto = `orcamento_bytes`), `JOB_OBJECT_LIMIT_ACTIVE_PROCESS` com 1 processo, `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE` e `JOB_OBJECT_LIMIT_DIE_ON_UNHANDLED_EXCEPTION`;
- inicia o filho sem shell, com cwd = `pasta_trabalho`, stdin, stdout e stderr em pipe, e um ambiente mínimo por lista de permissão (`VARIAVEIS_PERMITIDAS` de `plataforma/windows.py`: pastas do sistema, TEMP, TMP, número de processadores) com um PATH só com a pasta do Python e as do sistema, mais `OPENBLAS_NUM_THREADS=1`, `OMP_NUM_THREADS=1`, `MKL_NUM_THREADS=1`, `PYTHONDONTWRITEBYTECODE=1`, `PYTHONIOENCODING=utf-8` e `ambiente`. O ambiente do pai (com os tokens da sessão) nunca vai inteiro para o filho;
- atribui o processo ao job e só então escreve `LINHA_LIBERAR` (`b'iniciar\n'`) na entrada padrão e fecha a entrada. Se a atribuição falhar, mata o filho e devolve `recusado`;
- timeout de relógio no pai; ao estourar, `TerminateJobObject` e situação `tempo`;
- nunca levanta exceção por causa do filho.

Python de venv: quando `comando[0]` é o Python do ambiente (`sys.executable`) e ele é um venv, o isolador troca o lançador por `sys._base_executable` e passa `__PYVENV_LAUNCHER__=<lançador>`, como `multiprocessing/popen_spawn_win32.py` (bpo-35797). Motivo: com 1 processo ativo, o lançador do venv não cria o Python base e sai com 101. O isolador também acrescenta `-I` e `-B` quando faltam, recusa pasta de trabalho que não existe ou não está vazia, e as variáveis obrigatórias prevalecem sobre o argumento `ambiente`. O mesmo vale para o venv do plugin em `${CLAUDE_PLUGIN_DATA}`: o `interpretador.json` pode continuar apontando para o lançador.

O Mac (`mac.py`) é um esqueleto: `executar_isolado` devolve `recusado` com a mensagem de que o desdobra ainda não roda no Mac, sem tentar executar. Constantes de flag do Windows entram como `IntFlag` ou com `# numero-neutro: <motivo>`.

## 11. Regressão (`desdobra regressao`)

```
desdobra regressao --corpus <pasta dos PSDs> --linha-de-base <pasta com <slug>/laudo.json da sonda 1.26.0> --saida <pasta>
```

- A linha de base é a saída da sonda com psd-tools 1.26.0 (formato da sonda, não `laudo/1`), e o comparador de referência é o `comparar_126.py` da pesquisa. Os caminhos entram só por argumento; nenhum vai para o repositório. `--corpus`, `--linha-de-base` e `--saida` são resolvidos para caminho absoluto no início, e a leitura de cada arquivo recebe caminhos absolutos. `--saida` dentro do repositório do plugin é erro de uso (código 2), porque o relatório leva os slugs dos arquivos do corpus; o `.gitignore` também exclui `regressao-*.json`, `regressao-*.md`, `regressao-*/` e `saida-regressao*/` (menos o contrato `motor/schemas/regressao-1.json`).
- Para cada arquivo, roda `ler` avulso em `<saida>/<slug>/` e compara por camada, pela chave `layer_id`: situação (`lido` da sonda contra `lida` do laudo, e assim por diante), caixa, tipo, visibilidade efetiva e texto. Compara também a prova de pixel (`pct_px_acima_de_24_qualquer_canal` da sonda contra `prova_pixel.pct_px_acima_qualquer_canal`) e o tempo total.
- Cada diferença sai ligada a uma causa registrada (regra do laudo, mudança de versão, D9 aposentada) ou como "sem causa", para o Duda aprovar.
- Arquivos acima de `regressao.arquivo_grande_bytes` rodam um de cada vez.
- Saída: `<saida>/regressao-<data>.json` e o código 0 se nada piorou; com piora, código 30.
- A prova de pixel piora quando passa da base mais `regressao.tolerancia_prova_pixel_pct` (hoje 0).
- Verificações de segurança por arquivo (`verificacoes` no relatório): a saída padrão do `ler` no modo c fica em `<saida>/<slug>/saida-padrao.txt` e é varrida contra os nomes de camada, os textos e os trechos do próprio laudo, o caminho, o nome do arquivo e as pastas dele; o relatório guarda só contagens. Termo curto (abaixo de `regressao.varredura_min_caracteres`) é procurado como palavra inteira só no texto livre (`o_que_fazer` e `conteudo`) e conta como achado quando não é palavra dos textos fixos do motor. No menor arquivo que leu sem erro, a regressão roda também `job criar` e `job proxima` no modo c (`verificacoes.job_modo_c`) e varre a saída padrão, a saída de erro, o `estado.json`, o log e o pacote-modelo. O gancho de auditoria é conferido em `bruto/*/estrutura.json` e nas recusas, e os linkados usados são contados. Achado, alarme ou linkado usado conta como piora. O caminho do job no modo c que falha (`job criar` ou `job proxima` com código diferente de 0, ou sem laudo) entra em `falhas_de_seguranca`, e quando nenhum arquivo comparado leu sem erro e o job não roda, `verificacoes.job_modo_c_nao_rodou` fica 1 e também conta como falha de segurança.
- Também contam como piora: camada que fica mais grave (lida para degradada ou bloqueante, degradada para bloqueante) sem causa específica, camada que existe na linha de base e some agora (campo `existencia`, com ou sem `mudanca_de_versao`; entra em `camadas_mais_graves`), arquivo da linha de base que sumiu do corpus (`so_na_base`) e arquivo do corpus sem linha de base (`sem_base`). A causa `b3_fontes_conferidas_no_m2` só vale para camada com o alerta `fonte_nao_conferida`.
- A prova de pixel compara as contagens inteiras quando os dois lados as têm; contra a sonda, que grava a porcentagem com 4 casas, a de agora é levada à mesma resolução.
- O relatório leva `base_execucao` (tempo de relógio e paralelo da rodada da sonda, de `execucao.json` da linha de base), e o resumo mostra os dois tempos de relógio, separados das somas por arquivo.

## 12. Plugin e ambiente

- Marketplace na raiz (`.claude-plugin/marketplace.json`, nome `desdobra`, dono Trezion), plugin em `plugins/desdobra` (`plugin.json` com nome `desdobra` e versão `0.1.0`). A versão fica só no `plugin.json`; o motor lê a versão dali (`desdobra.__version__`).
- `plugin.json` declara `userConfig.teto_modo_dados` (`options` a, b, c, obrigatório, sem padrão). Nas skills, o valor entra por `${user_config.teto_modo_dados}`, e a skill passa `--teto-modo-dados` ao motor. Em gancho, o valor chega como `CLAUDE_PLUGIN_OPTION_TETO_MODO_DADOS` (https://code.claude.com/docs/en/plugins-reference.md, User configuration).
- Ambiente do plugin em `${CLAUDE_PLUGIN_DATA}`: o gancho SessionStart cria o venv, instala `motor/requirements.lock` com `python -m pip install --require-hashes --no-deps --only-binary=:all: -r <lock>` e instala o motor com `python -m pip install --no-deps --no-build-isolation -e ${CLAUDE_PLUGIN_ROOT}/motor`. O motor usa um backend de construção próprio (`motor/_construcao/construir.py`), sem setuptools, que só aceita instalação editável. A instalação editável grava um `.pth` com o caminho de `motor/`; como `${CLAUDE_PLUGIN_ROOT}` muda a cada versão do plugin, o gancho tem de refazer esse passo quando o caminho mudar, mesmo com o lock igual.
- O gancho grava `${CLAUDE_PLUGIN_DATA}/interpretador.json` com o caminho do Python do ambiente, porque `${CLAUDE_PLUGIN_ROOT}` e `${CLAUDE_PLUGIN_DATA}` não existem no Bash do Claude. A skill lê esse arquivo e chama `"<python>" -I -B -m desdobra --envelope --teto-modo-dados <teto> <comando> ...`.
- O lock só tem hashes de Windows x86-64 com CPython 3.14. Os de Mac entram no porte.

## 13. Testes

- Rodar: `.venv/Scripts/python.exe -m pytest plugins/desdobra/testes --basetemp=<pasta de trabalho fora do repositório> -p no:cacheprovider`.
- `testes/conftest.py` dá `psd_minimo()` (bytes de um PSD RGB de 1 x 1 sem camadas, escrito à mão), as fixtures `kv_psd` e `python`, e as constantes `RAIZ_PLUGIN`, `PASTA_MOTOR` e `PASTA_PACOTE`.
- PSD com camadas, smart object e casos de recusa são gerados na hora por `testes/sinteticos/` (leitor-laudo), numa pasta temporária. Nenhum PSD fica gravado no repositório.
- Cada agente nomeia os testes com o prefixo da tabela da seção 1.

## 14. Pendências da fundação

- O detector de números sem fonte cobre comparações e constantes em maiúsculas. Número de regra escondido em argumento padrão de função ou em chamada (`round(x, 3)`, `max(a, 8)`) não é pego; a revisão de código cobre esse caso.
- `--envelope` e `--teto-modo-dados` só valem antes do subcomando.
- A trava do job (`.desdobra.trava`) não detecta processo morto: depois de uma queda, o DA apaga o arquivo, como diz o O QUE FAZER.
- `interpretador.json` e `preparo.json`, gravados pelo gancho só com a biblioteca padrão, ainda não têm esquema em `motor/schemas`; o doctor lê os dois de forma defensiva.
