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

`plugins/desdobra/tela/` e `plugins/desdobra/biblioteca-specs/` ficam vazios no M1. A biblioteca recebe os perfis da Eletromidia PME e da Globo Ads no M3 (seção "M3: specs em 4 níveis e validador").

## 2. Regras que valem para todos

1. **PSD de cliente só no processo filho.** O processo principal nunca chama `PSDImage.open` em arquivo de cliente. Ele pode ler os 4 primeiros bytes (`8BPS`) para recusar um arquivo errado, com `desdobra.arquivos.tem_assinatura_psd`. Nunca use `smart_object.open()` nem `SmartObject.save()`. Leia `.data` só quando `kind == 'data'`, e abra sempre com `PSDImage.open(io.BytesIO(dados), ...)`. Nunca siga `fullPath` nem `relPath` de linkado.
2. **Fonte.** Arquivo de fonte só entra no job pela entrada própria `entrada/fontes/` (M2, seção "M2: fontes"), só é parseado no processo filho isolado (`desdobra.fontes.filho`) e só chega ao Chromium pela rota própria do servidor local. Fora disso, nenhum código lê, copia, guarda ou serve arquivo de fonte. `desdobra.arquivos.eh_arquivo_de_fonte` reconhece fonte pela extensão e pelos 4 primeiros bytes; o job recusa fonte em todas as outras entradas (`--campanha`, `--specs`, KV). Pacote é reconhecido pela assinatura (zip `PK`, tar com `ustar` na posição 257, gzip `1f 8b`, bzip2, xz, 7z, rar e zstd) e pela extensão. Zip e tar são inspecionados sem extrair (nomes e primeiros bytes de cada membro, na memória) e são recusados quando têm membro com nome ou assinatura de fonte ou outro pacote dentro; pacote comprimido ou ilegível, que não dá para inspecionar sem extrair, também é recusado.
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
| `desdobra.job` | `job criar`, `job proxima`, `job estado`, `job trocar-entrada`, `job remover-entrada` (M2) | fundação |
| `desdobra.leitor` | `ler` | leitor-laudo |
| `desdobra.regressao` | `regressao` | saida-regressao |
| `desdobra.doctor` | `doctor` | plugin |
| `desdobra.limites` | `limites` | fundação |
| `desdobra.specs` | `spec importar`, `spec confirmar`, `validar` (M3) | frente de specs |

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

Toda entrada é congelada: copiada, conferida por sha256 contra a origem, gravada só leitura e registrada em `estado.entradas` com `sha256`, `bytes` e `congelada_em`. Fonte só entra em `entrada/fontes/` (M2); nas outras entradas é recusada. `job proxima` confere `entrada/` inteira antes de rodar: arquivo mudado, sumido ou novo dá código 3 com o que fazer. A troca legítima é `job trocar-entrada`.

### 7.2 Comandos

```
desdobra job criar <pasta> --kv <arquivo> --modo-dados {a,b,c} [--teto-modo-dados {a,b,c}] [--campanha <pasta>] [--specs <pasta>]
(--psd é sinônimo de --kv)
desdobra job proxima <pasta> [--todas]      (ou --job <pasta>)
desdobra job estado <pasta>
desdobra job trocar-entrada <pasta> <entrada/...> <arquivo_novo>
desdobra job remover-entrada <pasta> entrada/fontes/<arquivo>      (M2)
```

`--modo-dados` é obrigatório e não tem valor inicial. Com `--teto-modo-dados`, um modo mais aberto que o teto é recusado. O teto pode vir depois de `criar` ou como opção global antes do subcomando; sem a opção depois de `criar`, vale a global.

### 7.3 Fases, hash e invalidação

`desdobra.job.fases.Fase(id, tipo, descricao, entradas, depende_de, saidas, comando, o_que_fazer, cumprido)`:
- `tipo` é `fase` (o motor roda `comando(pasta)` num subprocesso) ou `portao` (o humano faz a parte dele; `cumprido(pasta)` diz se fez);
- `entradas` e `saidas` são padrões glob relativos à pasta do job;
- o hash de uma fase cobre as `entradas` dela e as `saidas` das fases em `depende_de`, cada padrão com o próprio sha256 (arquivo: sha256 do arquivo; pasta ou vários arquivos: sha256 da lista ordenada de caminho e sha256);
- uma fase está válida quando está `concluida`, os hashes de agora batem com os gravados e as fases de que depende estão válidas. Mudar uma entrada invalida a fase que a usa e, em cadeia, as que dependem dela; as outras ficam como estão. Se a fase de cima roda de novo e grava a mesma saída, a de baixo volta a valer sem rodar. As saídas da própria fase também contam: ao concluir, a fase grava `hash_saidas`, e saída apagada ou mudada depois disso invalida a fase.

Bloqueio que fica no estado (M2): a fase com `bloqueio_persiste` (hoje só `fontes`) que termina com `situacao` `ok_com_bloqueio` grava em `fases.<id>.bloqueio` a situação, o `o_que_fazer` e as contagens inteiras do envelope dela. O bloqueio só sai quando a fase roda de novo sem ele (o DA troca ou remove a entrada); invalidar a fase também o tira. Enquanto uma fase válida tem bloqueio, o job não fica concluído: com todas as fases em dia, `proxima.tipo` é `bloqueio` (com a fase e o `o_que_fazer` dela), o `job proxima` sai com `situacao` `ok_com_bloqueio`, código 0, `fase` da fase que bloqueou, `contagens.bloqueios_pendentes` e as contagens gravadas, mesmo sem rodar nada (`fases_rodadas_agora` 0). Um `job proxima` que roda outra fase com o bloqueio pendente também sai `ok_com_bloqueio`, com o `o_que_fazer` da próxima fase e o do bloqueio. O `job estado` sai `ok_com_bloqueio`, com `contagens.bloqueios_pendentes` e a linha `<fase>: concluida com bloqueio pendente`.

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
- `fontes_usadas[].situacao` é `nao_conferida` na primeira passada (`desdobra ler`); a segunda passada (fase `laudo-fontes`, seção "M2: fontes") grava `presente`, `ausente` ou `divergente`, conferidos contra o arquivo enviado em `entrada/fontes/`;
- `prova_pixel.limiar` é a citação do limite `prova_pixel.limiar_diferenca`;
- `efeitos_suportados` registra a lista de efeitos e ajustes que o psd-tools 1.26.0 desenha, conferida no M1;
- cada camada tem `alertas` (casos de smart object da pesquisa e os subcasos da antiga D9, que não mudam a situação);
- `coberta_no_kv` leva a sugestão só em `sugestao_da_regra` (`funcao` `estrutura` ou `fora_da_peca`, a regra e a fonte). A decisão usa as contagens inteiras de pixels da estrutura/1 (`px_cobertos`, `px_visiveis`, `px_area_ref`, declaradas como inteiras no esquema), sem arredondamento: a conta é exata em fração, com o limite lido como a fração decimal escrita no registro (0,07 vale 7/100); `fracao_coberta` e `fracao_canvas` ficam só para leitura.
- Camada de texto com tinta em fonte não conferida leva o alerta `fonte_nao_conferida` (na primeira passada, todas; a segunda passada troca o alerta pela regra B3 com a conferência contra o arquivo enviado). O envelope do `ler` conta `fontes_nao_conferidas` e `camadas_com_fonte_nao_conferida`.
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
                       *, ambiente: dict[str, str] | None = None, entrada: bytes = b'') -> ResultadoFilho
p.fontes_instaladas() -> list[FaceInstalada]     # só diagnóstico, sem papel no portão; sem implementação (o diagnóstico do M2 é feito pelo Chromium na conferência)
p.console_interativo() -> (bool, str | None)    # M4: terminal interativo; no Windows, GetFileType e GetConsoleMode da entrada e da saida e janela de console
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
- atribui o processo ao job e só então escreve `LINHA_LIBERAR` (`b'iniciar\n'`) na entrada padrão, depois os bytes de `entrada` (M4: o render manda assim os PDFs do texto, que nunca vão para disco), e fecha a entrada. Se a atribuição falhar, mata o filho e devolve `recusado`;
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
- Chromium fixado (M2): depois do ambiente Python, o gancho confere o headless shell da revisão que o Playwright do venv pede (`playwright/driver/package/browsers.json`, nome `chromium-headless-shell`) em `${CLAUDE_PLUGIN_DATA}/ms-playwright`. Se a pasta `chromium_headless_shell-<revisão>` não tem a marca `INSTALLATION_COMPLETE`, ele roda `python -I -m playwright install --only-shell chromium` com `PLAYWRIGHT_BROWSERS_PATH=${CLAUDE_PLUGIN_DATA}/ms-playwright`; já presente, não baixa. Vale também no caminho rápido (ambiente pronto sem o Chromium: `acao` `chromium`). A etapa `chromium` entra em `preparo.json` com `codigo`, `tempo_s` e `baixado`, e `preparo.json.chromium` diz `presente`, `baixado` ou `falhou`. A falha do download não desfaz o ambiente Python: a linha de situação avisa e o doctor confere. O motor aponta o Playwright para a mesma pasta (`desdobra.chromium.apontar_playwright`): `PLAYWRIGHT_BROWSERS_PATH` quando já vem definido; no ambiente do plugin, `<pasta de dados>/ms-playwright`; fora dele, o padrão do Playwright.
- Doctor (M2): além do M1, confere a versão fixada do fontTools e do Playwright (pelos metadados, sem importar o fontTools), o Chromium fixado na pasta de navegadores do motor (`chromium_fixado`) e um carregamento de verdade (`fonte_no_chromium`): uma fonte sintética gerada num filho com o fontBuilder, servida pela rota própria no loopback, carregada pelo `@font-face` e conferida por CDP (face `isCustomFont` com o nome PostScript do arquivo), com a contagem de cópias no cache. Sem o Chromium, `fonte_no_chromium` sai `pulado`; `--sem-chromium` pula só essa verificação (desenvolvimento).
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

## M2: cor e design system (`desdobra/cor`, `desdobra/ds`)

Dono: frente de cor e design system do M2. Arquivos: `motor/desdobra/cor/`, `motor/desdobra/ds/`, `motor/schemas/design-system-1.json`, `limites-1.json`, `ds-parametros-cor-1.json`, as entradas `cor.*` e `ds.*` de `motor/fontes-de-limites.json` e os testes `testes/test_cor*` e `testes/test_ds*` (`test_ds_apoio.py` gera os perfis ICC, o PSD sintético e a conferência sintética).

### Cor (`desdobra.cor`)

- Todo descritor de cor (preenchimento SoCo e vscg, traço de forma vstk, ColorOverlay, Stroke e cor de texto) passa pelo perfil ICC do documento antes de virar token sRGB, pelo LittleCMS do Pillow (`ImageCms`). O perfil do documento é dado de cliente e só é aberto no processo filho da cor (arquitetura 7.1): `desdobra.cor.converter_isolado(caminho, parametros, cores, pasta_trabalho)` grava o pedido (intent, compensação e as cores rgb em 8 bits e Lab), roda `python -I -B -m desdobra.cor.filho <perfil.icc> <pedido.json> <pasta_saida> --orcamento-bytes N` com o mesmo isolador e gancho de auditoria do leitor (orçamento `(isolador.base_python_bytes + cor.fator_abertura_max x bytes) x isolador.margem_orcamento`, tempo `cor.tempo_max_s`) e lê `conversao.json` (`conversao-cor/1`: perfil com nome, sha256 e bytes, tratamento, motivo e os pares de cor, só números). Devolve um `ConversorPronto`, com a mesma interface do `Conversor`. Queda, memória, tempo e bug viram `perfil_ilegivel` com o motivo; o alarme do gancho dá código 5 no `ds montar`. O processo principal só confere o sha256 do arquivo do perfil. Documento sem perfil usa a curva sRGB. O token guarda a origem: modelo, valor no espaço do documento (e em 8 bits), perfil (nome, sha256, tratamento), intent e compensação de ponto preto.
- `Conversor(icc, parametros, indisponivel=False)`: `tratamento` é `icc_do_documento`, `sem_perfil_usa_srgb`, `perfil_indisponivel` (o documento tem perfil, mas a leitura não gravou o arquivo: o token sai `nao_convertido`, sem inventar) ou `perfil_ilegivel`. Documento fora do modo RGB fica `modo_fora_do_escopo`. Modelos RGB, HSB (vira RGB do documento) e Lab convertem; CMYK, cinza e cor de catálogo saem `nao_convertido` com o motivo.
- Asset com outro perfil: `tratamento_do_asset` devolve `converter_para_perfil_do_documento`, com `converte_pixels: true` (`decisoes-v1.md`, 29/10 nº 8, revista em 31/10). A conversão dos pixels acontece no render, no processo filho, porque abre o perfil do asset. A contagem no envelope é `assets_perfil_convertido`.
- Parâmetros do job: intent (`perceptual`, `relativo_colorimetrico`, `saturacao`, `absoluto_colorimetrico`), compensação de ponto preto e perfil embutido na saída. Sem parâmetro do job vale o padrão do registro (`cor.intent_saida`, `cor.compensacao_ponto_preto`, `cor.saida_perfil_embutido`, todos a calibrar, arquitetura 10.2, pergunta 5). `desdobra ds parametros-cor --job <pasta> [--intent X] [--compensacao-ponto-preto sim|nao] [--perfil-embutido sim|nao]` grava `parametros/cor.json` (`ds-parametros-cor/1`), que é entrada da fase `ds`.

### Mudança mínima no leitor

O filho grava o perfil do documento em `laudo/bruto/<sha256>/documento.icc` e põe `documento.icc.arquivo` na estrutura; cada camada ganha `cores_descritores` (classe e valores crus de cada descritor, com `descritor`, `ativo` e o bloco ou efeito de origem); a camada com máscara raster ativa ganha `pixels.alfa_visivel_sha256`, um PNG em tons de cinza com o alfa da camada vezes a máscara, em `laudo/assets/`. Os três campos são opcionais na `estrutura/1`. Leitura antiga, sem eles, sai com as pendências `cores_nao_convertidas` e `descritores_nao_lidos`.

### `desdobra ds montar --job <pasta>` e a fase `ds`

- Fase `ds` da esteira, depois de `ler` e da conferência de fontes; entradas `laudo/laudo.json`, `laudo/bruto/*/estrutura.json`, `fontes/conferencia.json` e `parametros/cor.json`; saídas `ds/design-system.json` (`design-system/1`) e `ds/limites.json` (`limites/1`). Aceita e ignora `--teto-memoria-bytes` e `--tempo-max-s`, que o `job proxima` repassa a toda fase. Roda no processo principal e nunca abre PSD nem arquivo de fonte.
- Tokens de cor: um por cor distinta no espaço do documento, com os usos (`camada`, `descritor`, `trecho`, `ativo`, `visivel`).
- Tokens de tipografia: um por trecho com tinta, com fonte PostScript, corpo, entrelinha, tracking, caixa-alta e faux bold do PSD; corpo efetivo pela escala vertical da matriz (`|det| / |coluna x|`); família, estilo, peso e métricas (`unidades_por_em`, `ascender`, `descender`, `cap_height`, `x_height`, `entrelinha_tipo`) da face casada em `fontes/conferencia.json` pelo nome PostScript do trecho (ou pelo `face_id` da camada), com a origem (face, sha256 do arquivo, versão da tabela name). Sem a conferência, as métricas ficam nulas, `situacao_fonte` é `fontes_nao_conferidas` e a pendência `fontes_nao_conferidas` entra no design system, sem quebrar.
- Medidas por camada visível: caixa, caixa de tinta, área de referência (canvas ou prancheta), rotação, folga por lado, folga pela máscara raster e folga de resolução do smart object embutido (ampliação sobre o original; vetorial marcado).
- Caixa do sujeito, para cada camada de pixel ou smart object embutido visível com asset: limiar `ds.sujeito_limiar_alfa` (128, medido) no maior componente conexo do alfa (o alfa visível, quando há máscara). Sem recorte (nenhum pixel da camada abaixo do limiar), o método é `pedir_ao_da`; recorte que encosta nas quatro bordas, como uma foto em elipse, continua sendo recorte. Asset acima do teto de decodificação do Pillow sai `nao_medido`. A função sujeito continua sendo do DA no briefing.
- `limites.json`: os limites do registro que o job usa (com citação), o parâmetro do job (`parametro_do_job`) e as referências do PSD (`psd.corpo_efetivo_min`, `psd.ampliacao_raster_max`, `psd.folga_tinta_min`), com `situacao: referencia_do_psd`, `efeito: registra` e `piso: false`, que o esquema obriga.
- Código 0 com `situacao` `ok`, ou `ok_com_bloqueio` quando as cores não foram convertidas; código 3 sem laudo, sem estrutura ou com contrato violado. O envelope leva só contagens (`cores`, `tipografia`, `sujeito_alfa`, `sujeito_pedir_ao_da`, `assets_perfil_atribuido`, `pendencias` e outras), sem conteúdo.

## M2: fontes (`desdobra/fontes`, `desdobra/chromium`, `desdobra/laudo/fontes.py`)

Dono: frente de fontes do M2. Arquivos: `motor/desdobra/fontes/`, `motor/desdobra/chromium/`, `motor/desdobra/laudo/fontes.py`, as mudanças em `arquivos.py`, `job/`, `cli.py`, `laudo/`, `leitor/__init__.py` (só a mensagem de fonte); `motor/schemas/leitura-fonte-1.json`, `conferencia-fontes-1.json` e os campos novos de `laudo-1.json`; as entradas `fontes.*` e `chromium.*` de `motor/fontes-de-limites.json`; `testes/test_fontes*` (`test_fontes_apoio.py` gera fontes sintéticas com o fontBuilder e PSD com texto e caixa TySh).

### Entrada `entrada/fontes/`

```
desdobra job criar <pasta> --kv <psd> --modo-dados {a,b,c} [--fontes <arquivo ou pasta> ...]
desdobra job trocar-entrada <pasta> entrada/fontes/<arquivo> <arquivo novo>      (troca ou acrescenta)
```

- `.DS_Store`, `Thumbs.db`, `desktop.ini` e os AppleDouble `._*` do Mac ficam fora de toda pasta copiada (`--fontes`, `--campanha`, `--specs`), sem recusar o job; o log ganha o evento `arquivos_do_sistema_ignorados` com a contagem.
- `job trocar-entrada` recusa (código 2) caminho que só difere na caixa de uma entrada que já existe, a mesma conferência casefold do `job criar`: no Windows os dois nomes seriam o mesmo arquivo.
- `job remover-entrada <pasta> entrada/fontes/<arquivo>` tira um arquivo de fonte do job (o nome exato, direto em `entrada/fontes/`; outro caminho dá código 2). Apaga só a cópia congelada, tira do `estado.entradas` e invalida pelo hash `fontes` e, em cadeia, `laudo-fontes` e `ds`. É o caminho do DA quando dois arquivos têm o mesmo nome PostScript.
- Aceitos: OTF, TTF, TTC (e OTC), WOFF e WOFF2 (`decisoes-v1.md`, arquitetura 14), reconhecidos pela assinatura (`OTTO`, `00 01 00 00`, `true`, `ttcf`, `wOFF`, `wOF2`), não pela extensão (`desdobra.arquivos.classificar_fonte`). Recusados: pacote, Type 1 (`%!PS-AdobeFont`, `%!FontType1`, PFB `80 01`, `typ1`, extensões `.pfb .pfa .pfm .afm .t42`), outro formato de fonte, arquivo que não é fonte, e, já no filho, variable font (tabela `fvar`) e arquivo que o fontTools não abre (`malformada`). A pasta passada em `--fontes` vira arquivos lado a lado em `entrada/fontes/` (nome repetido é erro); `.DS_Store`, `Thumbs.db` e `desktop.ini` ficam de fora.
- Cada arquivo é conferido no filho isolado antes de entrar; na recusa, o `job criar` desfaz a pasta que começou a montar. Congelamento, sha256 e só leitura como as outras entradas.
- Sem controle de licença (`decisoes-v1.md`, nº 19): toda fonte que a agência envia é tratada como fonte com direito de uso, e a responsabilidade pela licença é da agência ou do usuário. O job não tem arquivo de licenças: `job criar` não aceita `--licencas` (código 2), e `job trocar-entrada` e `job remover-entrada` recusam `entrada/licencas.json` (código 2).

### Processo filho das fontes (`desdobra.fontes.filho`)

```
python -I -B -m desdobra.fontes.filho <arquivo> <pasta_saida> --orcamento-bytes N
```

Mesmo isolador (`plataforma.executar_isolado`, orçamento `(isolador.base_python_bytes + fontes.fator_abertura_max x bytes) x isolador.margem_orcamento`, tempo `fontes.tempo_max_s`), mesma linha `iniciar` e mesmo gancho de auditoria do leitor. Lê os bytes para a memória e abre com o fontTools a partir de `io.BytesIO` (WOFF e WOFF2 descompactados na memória, TTC face por face). Grava `leitura.json` (`leitura-fonte/1`): por face, todos os registros do name ID 6, família e estilo (1, 2, 16, 17), nome completo, id único (3), versão (5), `head` (unidades por em), `hhea`, `OS/2` (usWeightClass, fsType, sTypo*, usWin*, sCapHeight, sxHeight), o cmap em faixas de códigos e, na TTC, o deslocamento e o tamanho do diretório de tabelas de cada face. Nunca contorno, glifo, atlas nem byte da fonte. Códigos: 0 lida; 3 recusada (`formato`, `type1`, `variavel`, `malformada`); 4 memória; 5 auditoria; 1 bug. O pai (`desdobra.fontes.leitura.ler`) transforma queda, memória, tempo e bug em recusa tipada, sem cair. O processo principal nunca importa o fontTools.

### Esteira

`nucleo.ESTEIRA = FASES_M2 = ler, fontes, laudo-fontes, ds` (`FASES_M1` continua só com `ler`).

| Fase | Comando | Entradas | Depende de | Saídas |
|---|---|---|---|---|
| `fontes` | `desdobra --envelope fontes conferir --job <pasta>` | `entrada/fontes` | `ler` | `fontes/conferencia.json` |
| `laudo-fontes` | `desdobra --envelope fontes laudo --job <pasta>` | | `ler`, `fontes` | `laudo/laudo-fontes.json` |

Trocar, acrescentar ou remover fonte invalida só `fontes` e, em cadeia, `laudo-fontes` e `ds`. As duas fases aceitam e ignoram `--teto-memoria-bytes` e `--tempo-max-s`. Saem com código 0, situação `ok` ou `ok_com_bloqueio`.

### `desdobra fontes conferir --job <pasta>`

1. Lê cada arquivo de `entrada/fontes/` no filho (`fontes/bruto/<sha256>/leitura.json`) e monta as faces, com id `f01`, `f02`... na ordem de (sha256, índice).
2. Casa cada nome PostScript dos trechos do laudo (primeira passada) com uma face, nesta ordem: qualquer registro do name ID 6, o id único (name ID 3, pedaço depois do `;`), a família e o estilo (16 e 17, ou 1 e 2). O par fora do name ID 6 sai com aviso (`casada_por_id_unico`, `casada_por_familia_estilo`). Mais de uma face casando pelo mesmo método (dois arquivos com o mesmo nome PostScript) é bloqueante (`mais_de_um_arquivo`): o motor não escolhe, e o DA tira o arquivo que não vale com `job remover-entrada`. Sem par: `nome_ps_sem_par` quando há face da mesma família (mais `face_divergente` quando nenhuma tem o peso pedido; a face de outro peso nunca entra no lugar) ou `arquivo_faltando`.
3. Cobertura: caracteres diferentes com tinta (depois da caixa alta) que o cmap não cobre (`glifo_faltando`, só a contagem).
4. Chromium: servidor local (`desdobra.chromium.servidor`): só 127.0.0.1, porta escolhida pelo sistema, rotas `/entrar/<token>` (vira cookie HttpOnly SameSite=Strict), `/pagina`, `/fonte/<id da face>` e `/controle`; Host e Origin conferidos; token e cookie comparados em bytes (valor fora do ASCII dá 404 ou 403, sem exceção); `Cache-Control: no-store` em toda resposta menos `/controle`; sem CORS; qualquer outro caminho, id ou sha256 dá 404; nada é impresso, nem erro de requisição. `/controle` é o controle positivo do teste de cache: uma folha de estilo só com um comentário de marcador aleatório (nunca fonte), com `Cache-Control: max-age=3600`, que a página carrega. A TTC é servida com o diretório da face copiado para o início do arquivo, com os números que o filho mediu. A página (só na memória) tem um `@font-face` por face com a família `dsd-<8 primeiros do job_id>-<id>` e o peso declarado (do nome do estilo, ou o usWeightClass sem estilo conhecido; a divergência entre os dois é aviso). O peso pelo nome compara palavras inteiras (separadas por hífen, espaço, sublinhado e troca de caixa) e fica com o maior casamento (ExtraBold antes de Bold); num nome com hífen vale só o sufixo depois do último hífen, então `Thinker-Bold` é 700. Cada camada de texto de ponto vira uma linha por quebra (U+000D, U+000A, U+0003), com o mapeamento da pesquisa (`pesquisa/corpus-testes.md` §4 itens 8 e 9): corpo do espaço de texto escalado para `chromium.corpo_medicao_px`, letter-spacing do tracking, kerning do AutoKerning, ligaduras, caixa alta com `cpsp`, `font-synthesis: none`, trechos vizinhos de mesmo estilo juntos. O Chromium (headless shell do Playwright, perfil numa pasta temporária curta criada pelo motor na máquina e apagada no fim, porque num caminho longo, acima de uns 220 caracteres no Windows, o Chromium deixa de gravar cache; sem resolver nome fora de 127.0.0.1) mede cada linha (`Range.getBoundingClientRect`) e responde por CDP (`CSS.getPlatformFontsForNode`) quais faces desenharam cada trecho e cada sonda de face. Confere quando todas são `isCustomFont` e o nome PostScript está nos registros do name ID 6 do arquivo; senão `fallback` (entrou face do sistema) ou `face_cdp_divergente`. Sem resposta do CDP (elemento sem nó ou sem fontes), o par sai bloqueante com `cdp_sem_resposta`, e a face usada também (na face não usada, aviso). Face que não carrega: `face_nao_carregou`.
5. Largura: maior linha, com e sem o letter-spacing do último caractere, contra `bounds` da caixa TySh (Rght - Left), na variante mais próxima. Acima de `fontes.largura_divergencia_pct` (0,2, a calibrar): `largura_divergente`, `decisao: pede_decisao_do_da`, bloqueante sem reprovação automática. Caixa de parágrafo, faux bold, escala diferente de 100%, warp ou trecho sem face: largura não comparada, com o motivo (`largura_nao_medida_*`).
6. Licença: fora do portão (`decisoes-v1.md`, nº 19). A conferência não confere canal, EULA, kit web, fsType nem restrição de uso desktop, e não bloqueia nem avisa por licença: uma fonte com fsType restrito e marcas de kit web passa como qualquer outra. A responsabilidade pela licença é da agência ou do usuário.
7. Diagnóstico (arquitetura 4.2, sem papel no portão): uma sonda pede a família do arquivo pelo nome, sem `@font-face`; se o CDP devolve face do sistema com o mesmo nome PostScript, a face leva `instalada_mesmo_nome`.
8. Teste de cache: fechado o Chromium, a varredura procura em todo arquivo do perfil o sha256, a assinatura de fonte e trechos de 256 bytes (início, meio e fim) de cada fonte servida (`cache.copias_encontradas`) e o marcador do controle positivo (`cache.controle_encontrado`), e o perfil é apagado (`cache.perfil_apagado`). `cache.feito` só é verdadeiro quando o controle aparece no perfil, o que prova que o perfil grava cache; senão `cache.motivo` diz por quê (`perfil_nao_gravou_o_controle` ou `chromium_nao_rodou`) e `resumo.cache_provado` é 0. `cache.perfil_caracteres` guarda o tamanho do caminho do perfil (sem o caminho). O teste do método mostra cópia com `max-age` e 0 cópia com `no-store`.
9. Varredura da pasta do job: arquivos de fonte fora de `entrada/fontes/` (`varredura.arquivos_de_fonte_fora_da_entrada`, esperado 0).

`fontes/conferencia.json` (`conferencia-fontes/1`): `faces[]` com `id`, `nome_ps`, `nomes_ps`, `familia`, `estilo`, `formato`, `sha256`, `indice`, `versao_name`, `peso_declarado`, `us_weight_class`, `metricas` {`unidades_por_em`, `ascender`, `descender`, `cap_height`, `x_height`, `entrelinha_tipo`}, `usada`, `carregada`, `face_cdp_confere`, `instalada_mesmo_nome`, `situacao` (`ok`, `aviso`, `bloqueante`) e `motivos[]` ({`codigo`, `situacao`, `descricao`, `medida`, `limite`}); `camadas[]`, um por par (camada, nome PostScript do PSD), com `layer_id`, `nome_ps`, `face_id` (ou null), `metodo_casamento`, `glifos_faltando`, `largura_erro_max_pct`, `largura_erro_pct` (com sinal), `face_cdp_confere`, `situacao`, `decisao` e `motivos[]`; `arquivos[]` (sha256, formato, aceito ou recusado e o motivo); `cache`; `varredura`; `chromium` (versão, Playwright, respostas por rota); `resumo` só com números. Sem texto de peça e sem caminho de arquivo de fonte. A situação da camada é a pior entre os motivos técnicos e a da face.

Sem manifesto de licença: o `manifesto-licenca.json` e os esquemas `manifesto-licenca/1` e `licencas-fontes/1` saíram (`decisoes-v1.md`, nº 19). O sha256, o formato e o nome PostScript de cada arquivo já ficam em `fontes/conferencia.json` (`arquivos[]` e `faces[]`).

Envelope de `fontes conferir`: só contagens (`faces`, `faces_bloqueantes`, `camadas_bloqueantes`, `sem_par`, `glifos_faltando`, `larguras_divergentes`, `cdp_confere`, `cdp_diverge`, `copias_no_cache`, `chromium_feito`, `fontes_fora_da_entrada` e outras), `ids.conferencia_sha256` e `numeros.largura_erro_max_pct`, em qualquer modo; nunca byte, miniatura de glifo ou caminho de fonte.

### Segunda passada do laudo (`desdobra fontes laudo`, `desdobra.laudo.fontes.aplicar_conferencia`)

Função pura do laudo da primeira passada e da conferência. Grava `laudo/laudo-fontes.json` (`laudo/1` com `passada: 2` e `conferencia_fontes` = {`arquivo`, `sha256` da conferência, `laudo_primeira_passada_sha256`}). Tira o alerta `fonte_nao_conferida` das camadas cobertas, põe a B3 na camada cujo par tem motivo técnico bloqueante (`arquivo_faltando`, `nome_ps_sem_par`, `face_divergente`, `glifo_faltando`, `fallback`, `face_cdp_divergente`, `cdp_sem_resposta`, `face_nao_carregou`, `largura_divergente`, `chromium_nao_conferiu`, `colecao_nao_servivel`, `mais_de_um_arquivo`), com a medida e a citação do limite de largura quando é o caso, e o alerta `fonte_conferida_com_aviso` quando só há aviso. `fontes_usadas[]` ganha `situacao` (`presente`, `ausente`, `divergente`) e `face_id`; fonte sem arquivo nunca sai `presente`: usada só em espaço, sai `ausente` com `so_em_espaco: true` (sem efeito na peça, sem B3); `resumo.n_b3_fontes` conta as camadas com B3 de fonte. O `laudo/laudo.json` da primeira passada não muda, e a regressão continua comparando só ele. O `pacote-modelo.json` continua saindo da primeira passada.

### Limites novos

`fontes.fator_abertura_max` (64, a calibrar), `fontes.tempo_max_s` (120, a calibrar), `fontes.largura_divergencia_pct` (0,2, a calibrar, efeito avisa), `chromium.corpo_medicao_px` (100, a calibrar) e `chromium.tempo_max_s` (120, a calibrar), os dois com fonte na arquitetura 4.5 e a origem do valor na nota; `cor.fator_abertura_max` (64, a calibrar) e `cor.tempo_max_s` (120, a calibrar), do filho da cor, com fonte na arquitetura 7.1.

### Pendências da frente de fontes

- O OTS do Chromium sanitiza a fonte carregada pela página antes de usar (arquitetura 7.1, a confirmar): o teste mostra que fonte malformada é recusada no filho antes de chegar ao Chromium, mas não testa o OTS.
- Faux bold, escala de trecho e caixa de parágrafo ficam sem comparação de largura (motivo registrado).

## M3: specs em 4 níveis e validador (`desdobra/specs`, `desdobra/sugestao/specs.py`)

Dono: frente de specs do M3. Arquivos: `motor/desdobra/specs/`, `motor/desdobra/sugestao/specs.py`, os esquemas `spec-1.json`, `leitura-folha-1.json`, `pacote-specs-1.json`, `mapeamento-specs-1.json`, `spec-confirmacoes-1.json` e `validacao-arquivo-1.json`, as entradas `specs.*` de `motor/fontes-de-limites.json`, a biblioteca `plugins/desdobra/biblioteca-specs/`, o gerador `dev/gerar_biblioteca_specs.py` e os testes `testes/test_specs*` (`test_specs_apoio.py` escreve à mão o PDF com texto, o PDF escaneado, o HTML, o CSV e o e-mail sintéticos).

### Entrada e esteira

- As folhas entram em `entrada/specs/` (`job criar --specs <pasta>` ou `job trocar-entrada <pasta> entrada/specs/<veiculador>/<arquivo> <arquivo>`). Cada subpasta é um veiculador (as folhas dela juntas, como as quatro páginas salvas da Globo); folha solta direto em `entrada/specs/` é um veiculador sozinha. O id do veiculador é o nome da subpasta (ou do arquivo), sem acento.
- Formatos aceitos, reconhecidos pela extensão e, no PDF, pela assinatura `%PDF-`: PDF (com ou sem camada de texto), HTML salvo (`.html`, `.htm`), CSV exportado pelo DA e texto (`.txt`, `.eml`). `.xlsx`, imagem solta e Word ficam fora (folha recusada, com a contagem `folhas_recusadas`). Sem OCR e sem raspar site.
- Fase `specs`, a última da esteira (`nucleo.ESTEIRA = FASES_M3`), sem dependência: entradas `entrada/specs`, `specs/confirmacoes.json` e `sugestoes/mapeamento-specs.json`; saídas `specs/rascunho.json`, `specs/formatos-do-job.json` e `sugestoes/pacote-specs.json`; comando `desdobra --envelope spec importar --job <pasta>`. Trocar uma folha invalida só esta fase. A confirmação não é portão da esteira: ela é do DA, no terminal, e quem precisa de formato confirmado lê `specs/formatos-do-job.json`.

### Processo filho das folhas (`desdobra.specs.filho`)

```
python -I -B -m desdobra.specs.filho <arquivo> <pasta_saida> --formato {pdf,html,csv,texto} --orcamento-bytes N --escala-recorte S
```

Toda folha, e não só o PDF, é lida no filho isolado, com o mesmo isolador, a mesma linha `iniciar` e o mesmo gancho de auditoria do leitor de PSD: o PDFium é código nativo diante de um arquivo de fora da agência (arquitetura 7.1), e o processo principal nunca parseia a folha. Orçamento `(isolador.base_python_bytes + specs.fator_abertura_max x bytes) x isolador.margem_orcamento`, tempo `specs.tempo_max_s`. Grava `specs/bruto/<sha256>-<formato>/leitura.json` (`leitura-folha/1`), reaproveitado só com o mesmo sha256, o mesmo formato, a mesma escala de recorte e a mesma versão do motor. Folha com mais de `specs.trechos_max` trechos, trecho com mais de `specs.trecho_caracteres_max` caracteres ou página de PDF com mais de `specs.pdf_trechos_por_pagina_max` pedaços é recusada inteira (`trechos_demais`, `trecho_longo`):
- PDF: um trecho por retângulo de texto do PDFium, com página e caixa em pontos. Página sem texto vira recorte: `p<NN>.png`, a página inteira na escala `specs.recorte_escala`. Nunca extrai fonte, imagem ou anexo;
- HTML: um trecho por bloco de texto, com a linha do HTML e a seção (o título mais próximo acima); tabela (`table`/`tr`/`td` ou `div` com as classes `table`, `row` e `col`) dá um trecho por célula, com o cabeçalho da coluna como rótulo e o número da linha da tabela (`linha_tabela`). Script, style e svg ficam de fora; nada é baixado;
- CSV: um trecho por célula, com linha, coluna e o cabeçalho como rótulo (separador `,`, `;` ou tabulação);
- texto e `.eml` (só o corpo em texto puro): um trecho por linha.

Códigos: 0 lida; 3 recusada (`formato`, `malformado`, `trechos_demais`, `trecho_longo`); 4 memória; 5 auditoria; 1 bug. O pai (`desdobra.specs.leitura.ler`) transforma queda, memória, tempo e bug em recusa tipada.

### Número só do trecho (`desdobra.specs.extrair`)

O número nasce só aqui, por expressão regular sobre o texto literal do trecho, com fronteira (nunca começa nem termina no meio de outro número) e tamanho limitado (a expressão fica linear num texto hostil), e cada valor guarda `numeros_literais` como aparecem na folha. `modelo.conferir_literais(doc)` lista todo número que não existe no trecho citado com a mesma fronteira ("5" não vale dentro de "15" nem de "1,5"), e o `recorte_texto` que parte palavra ou número; a importação para com erro interno se a lista não for vazia, e os testes conferem 100% dos números. Armadilhas viram alerta, nunca valor confirmado: `virgula_decimal` ("1,17m" sai 1.17), `separador_ambiguo` ("1.920", sem valor), `unidade_nao_declarada` ("300x600"), `unidade_incoerente` (área total maior que a útil pelo fator `specs.fator_incoerencia_unidade`, o "120m x 175m"), `area_util_maior_que_total`, `rotulo_separado_do_valor` (o rótulo e o valor em trechos diferentes, como no PDF da PME), `fora_do_escopo_v1` (medida em m, cm ou mm), `mais_de_um_numero` e `fontes_divergentes` (o motor não escolhe), `aproximado` ("cerca de", "aprox."), `praca_mista`, `praca_ambigua` e `uf_nao_declarada`.
- Peso em bytes inteiros: `{alvo_bytes, reprova_acima_bytes}`. Sem base declarada, o alvo é a leitura decimal (5 MB = 5.000.000) e a reprovação só vale acima da binária (5.242.880), com `base_unidade: nao_declarada`; KiB e MiB declarados dão as duas iguais (`binaria`). A unidade pode vir do cabeçalho da coluna (`unidade_do_rotulo`). "Kb" e "Mb" com b minúsculo saem lidos como byte, com o alerta `unidade_bit_ou_byte`, para o DA conferir.
- Dimensão `{largura, altura}` com a unidade; tipos como conjunto de MIME; faixa `[{lado, px}]` ("-" é lista vazia); área segura `{pct, px, lados}`; borda `{espessura_px, cor}`, condicional quando o texto diz "que tenham", "quando" ou "se", com o texto como condição; praça `[{uf, municipio, texto_original, ambiguidade}]`, sem completar a UF de uma cidade (São Paulo e Rio de Janeiro ficam `uf_ou_municipio`).
- Sufixo de nome de arquivo fica texto literal e nunca vira geometria.

### Modelo `spec/1` (`desdobra.specs.modelo`)

Um documento com `tipo` `rascunho`, `formatos_do_job` ou `perfil`, e as listas `folhas`, `veiculadores`, `circuitos` e `formatos`, cada registro com `campos` (campo para valor). Todo valor tem `id`, `campo`, `forma` (exato, maximo, faixa, conjunto, condicional), `valor`, `texto_original`, `numeros_literais`, `unidade`, `unidade_original`, `base_unidade`, `condicao`, `fonte` (`folha`, `pagina`, `trecho`, `rotulo_trecho`, `recorte`, `secao`, `recorte_texto`, `trechos_adicionais`), `origem` (`extraido_do_trecho`, `digitado_pelo_da_a_partir_do_recorte` ou `ausente`), `mapeamento` (`rotulo_da_folha`, `proposta_do_modelo`, `biblioteca`, `da`), `situacao` (`rascunho`, `confirmado`, `registro`), `alertas`, `confirmacao` e, na divergência, `leituras` (cada uma com o valor e a fonte, e `valor` nulo). O esquema obriga: `ausente` tem valor nulo e é `registro`; `digitado_pelo_da_a_partir_do_recorte` tem `fonte.recorte` e `texto_digitado`; no `formatos_do_job`, todo valor é `confirmado`.
- Campos por nível: folha (`versao_impressa`, `data_impressa`); veiculador (`nome`, `apelidos`, `concessionaria`, `peso_max`, `peso_max_hospedado`, `peso_max_tag`, `tipos_aceitos`, `borda_1px`, `qualidade_jpg_recomendada` e `prazo_envio`, os dois últimos só registro, mais `tetos_por_tamanho`); circuito (`ambiente`, `praca`, `modelo_tela`, `area_util`, `faixas_reservadas`, `restricoes`, `texto_original`); formato (`dimensao`, `orientacao_painel`, `rotacao` só registro, `area_util`, `faixas`, `area_segura`, `borda_1px`, os pesos, `tipos_aceitos`, `qualidade_jpg_recomendada`, `area_visivel`, `sangria`, `margem_seguranca`, `sufixo_nome_arquivo`). Campo que a folha não traz vira registro sem valor (teste de propriedade).
- Chave do formato: `veiculador|circuito|LxA` (com a unidade depois quando não é px). No PDF, o circuito é o texto da página que fica todo à esquerda da coluna dos rótulos (ambiente e praça, para mapear), e o que começa com `*` é restrição; no HTML, o nome da página salva; no CSV e no e-mail, as colunas e linhas de ambiente e praça da entrada. Chave repetida: todas as entradas com a mesma chave ganham `#<id do formato>` e o alerta `chave_repetida`, sem depender da ordem das folhas. O circuito sem texto tem id por folha (`<veiculador>:<folha>-p<NN>` ou `<folha>-geral`). Id que viria de texto com segredo (circuito, veiculador pela pasta) é neutro: `oculto-<sha256 curto>`.
- Herança: o formato sem o campo usa o do circuito (`area_util`, `faixas_reservadas`) ou o do veiculador (pesos, tipos, borda, qualidade), em `modelo.resolver`, com `herdado_de` no `formatos-do-job.json`.
- Tabela por tamanho do veiculador (o peso por tag da Globo, carga inicial e posterior): vale para o formato do mesmo tamanho (`aplicado_pela_tabela_por_tamanho`), pelo mesmo caminho dos outros valores: a ficha e a tabela (ou duas linhas da tabela) com valores diferentes viram divergência com as leituras. Se a ficha do formato dá outro peso por tag que a carga posterior da tabela, `peso_max_tag` fica com as duas leituras e valor nulo: o Half-Page, 550 KB na ficha contra 500 KB na tabela.
- Perfil por veiculador, versionado: outro conjunto de folhas (sha256) gera a versão seguinte, e a anterior vai para `historico`. O id da folha sai do sha256 e do caminho (a mesma folha em duas subpastas são duas folhas); como os ids dos valores levam o id da folha, a folha nova pede a confirmação do DA de novo.

### Propostas do Claude (`sugestoes/pacote-specs.json` e `sugestoes/mapeamento-specs.json`)

- `pacote-specs/1`: nos modos a e b, os trechos (folha, id, página, texto, rótulo, seção, se já foram mapeados) depois do detector de segredos (texto e rótulo com achado: o trecho sai; seção com achado: só a seção sai; alvo, chave ou veiculador com achado: sai; tudo conta em `segredos_bloqueados`, origem `trecho_spec` em `segredos-bloqueados.json`) e os alvos (ids e chaves); no modo c, só contagens.
- `mapeamento-specs/1`, escrito pelo Claude: cada proposta tem `folha`, `trecho`, `campo` (lista fechada), `alvo` opcional, `adicionais` (outros trechos da mesma página) e `recorte_texto` (pedaço literal do trecho). Não há lugar para valor nem número. O motor extrai o número do texto do trecho; o valor sai `rascunho` com `mapeamento: proposta_do_modelo`. Proposta com trecho inexistente ou com `recorte_texto` que não está no trecho, ou que parte palavra ou número ("5 MB" dentro de "15 MB"), é ignorada (`propostas_ignoradas`); no modo c, todas (`propostas_ignoradas_modo_c`).

### `desdobra spec confirmar --job <pasta> [--formato <chave>] [--campo <campo>]`

Só num terminal interativo, conferido por `desdobra.humano` (veja M4, disparo humano): recusa com código 3 com `--envelope`, sem console interativo ou em processo aberto pelo Claude. `confirmar.sessao` só grava com o `Disparo` que essa conferência emite. Pega a trava do job, refaz o rascunho e pergunta, sem resposta padrão (Enter vazio repete): nas fontes divergentes, qual leitura vale; em cada rascunho com valor, confirmar ou pular, vendo o trecho, o pedaço de onde o número saiu e quem ligou o campo ao trecho (rótulo da folha, proposta do Claude ou curadoria); em cada página sem texto, o campo (só os que valem: rotação, prazo e qualidade, que são registro, ficam fora; restrição vai para a lista do circuito) e o valor que o DA lê no recorte. Ctrl+C ou fim da entrada param a sessão e gravam as respostas dadas até ali. Grava as ações em `specs/confirmacoes.json` (`spec-confirmacoes/1`, com `por: da`, `meio: terminal` e a hora) e refaz o rascunho e os formatos do job. A confirmação guarda a impressão (sha256) do conteúdo do valor: valor mudado deixa a ação de lado (`acoes_ignoradas`), e o DA confirma de novo.

### `desdobra validar <arquivo> --formato <chave> (--job <pasta> | --perfil <spec.json>) [--condicao X] [--saida <relatorio.json>]`

Confere qualquer arquivo, inclusive export humano. Lê só o cabeçalho (PNG IHDR, os segmentos do JPEG até o SOF, pulando metadados de qualquer tamanho, tela lógica do GIF) e os primeiros bytes (MIME); nunca decodifica. A tag Orientation do Exif diferente de 1 vira aviso (`imagem_com_giro_no_exif`). Verificações (`validacao-arquivo/1`): dimensão (girado reprova, motivo `girado`), cada peso nas duas leituras (acima da binária reprova pelo limite `specs.peso_reprova_acima_da_leitura_binaria`; entre as duas avisa pelo `specs.peso_avisa_acima_da_leitura_decimal`; peso condicional reprova só com `--condicao` igual à dele, e sem ela avisa; peso divergente avisa com `fontes_divergentes_o_da_decide`), tipo contra os tipos aceitos, extensão que não bate com o tipo (aviso). Sem regra confirmada de dimensão, peso ou tipo (`sem_regra`), o resultado é no mínimo `aviso`, com o o que fazer de validação incompleta: o arquivo nunca sai aprovado sem regra. Área útil, faixas, área segura e borda ficam `nao_verificado` (pixel, na entrega do M6). Com `--job`, só valem valores confirmados (`specs/formatos-do-job.json`); com `--perfil`, a validação é diagnóstico (`contra_valor_nao_confirmado` 1). Códigos: 0 aprovado ou com aviso (`situacao` `ok`), 3 reprovado (`recusado`), 2 formato inexistente ou job sem as specs. O envelope leva só contagens (`ok`, `aviso`, `reprova`, `nao_verificado`, `sem_regra`), o sha256 e os números do arquivo.

### Biblioteca inicial (`plugins/desdobra/biblioteca-specs/`)

`eletromidia-pme-1.json` e `globo-ads-1.json` (`spec/1`, tipo `perfil`, versão 1; o registro sem valor fica implícito no arquivo, e `importar.perfil_da_biblioteca` o completa ao ler): os valores que o motor extrai das folhas públicas, com a citação (arquivo, sha256, página, seção e só os trechos citados, nunca a folha), mais a curadoria em `mapeamento` (qual trecho é ambiente, praça, área segura, borda, nome), na mesma regra das propostas: sem número. Os valores do perfil ficam em rascunho. Quando a mesma folha (mesmo sha256) entra num job, a importação usa o veiculador do perfil e aplica a curadoria (`mapeamento: biblioteca`). `dev/gerar_biblioteca_specs.py --pme <pdf> --globo <pasta>` refaz os perfis a partir das folhas, que ficam fora do repositório; o teste das folhas reais roda com `DESDOBRA_FOLHAS_SPECS` apontando para a pasta com `eletromidia-pme/` e `globo-ads/`.

### Limites novos

`specs.fator_abertura_max` (64), `specs.tempo_max_s` (120) e `specs.recorte_escala` (2), a calibrar, com fonte na arquitetura 7.1 e 4.8; `specs.fator_incoerencia_unidade` (10, a calibrar, só alerta); `specs.peso_reprova_acima_da_leitura_binaria` e `specs.peso_avisa_acima_da_leitura_decimal`, medidos (`pesquisa/v1-estatico-sintese.md` §5); `specs.trechos_max` (20000), `specs.trecho_caracteres_max` (4000) e `specs.pdf_trechos_por_pagina_max` (1000), a calibrar, tetos do filho.

A fase `specs` tem entradas de fora do job (`Fase.externas`): o sha256 de `biblioteca-specs/` e o dos limites `specs.*` e `isolador.*`. Perfil novo na biblioteca ou limite mudado invalida a fase como uma folha trocada.

### Doctor

Mais uma verificação: `pypdfium2`, a versão fixada do lock, só pelos metadados (o processo principal nunca importa o pypdfium2).

### Pendências da frente de specs

- Frase solta (a área segura, a borda, a qualidade de JPG) só vira valor por proposta de mapeamento (do Claude ou da curadoria da biblioteca); sozinho, o motor reconhece só rótulo seguido de valor.
- A borda condicional guarda a condição como o texto da folha: a validação no pixel (M6) ainda precisa decidir como ler "fundo da cor da página".
- Área útil, faixas, área segura e borda não são conferidas no `validar` deste marco (pixel, M6).

## M4: render da origem (`desdobra/render`)

Dono: frente de render do M4. Arquivos: `motor/desdobra/render/` (`contrato.py`, `texto.py`, `execucao.py`, `filho.py`, `filho_pilhas.py`, `gama.py`, `icc.py`, `linkados.py`, `autoteste.py`), a rota de várias páginas em `desdobra/chromium/servidor.py`, `navegador.imprimir` em `desdobra/chromium/navegador.py`, o parâmetro `entrada` da interface de plataforma, os esquemas `composicao-1.json`, `render-1.json` e `linkados-confirmados-1.json`, a imagem `motor/referencias/autoteste-render.png`, as entradas `render.*` de `motor/fontes-de-limites.json` e os testes `testes/test_render*`.

### Contrato `composicao/1` (`render/<formato>/contrato.json`)

O que o render desenha num formato, de baixo para cima. No M4 é o contrato da origem, na identidade (`origem.funcoes: identidade`), montado só de arquivos do job: a estrutura bruta do leitor (`laudo/bruto/<sha256>/estrutura.json`), a conferência de fontes (`fontes/conferencia.json` e as leituras de `fontes/bruto/`) e os linkados confirmados (`briefing/linkados-confirmados.json`). O M5 grava o mesmo formato para os outros formatos: muda `formato` (chave, largura, altura, escala) e a caixa de cada entrada, nunca a forma das entradas. `montar(pasta, funcoes=None)` aceita `{layer_id: funcao}`; camada `fora_da_peca` não entra em entrada nenhuma e vai para `fora_da_peca`.

Entradas (`entradas`, na ordem de desenho do PSD):
- `pilha`: as camadas sem texto entre duas camadas de texto (`indices` na ordem de `descendants()` e `layer_ids`), compostas juntas pelo compositor do psd-tools no filho das pilhas, com máscaras, mesclagens, ajustes e os efeitos que ele desenha, no espaço de cor do documento. A `chave` (sha256 do KV e dos índices) indexa o asset em `render/pilhas.json`; o asset fica em `render/assets/<sha256>.png`, recortado na caixa de tinta. Cache por hash: com a mesma chave e a mesma versão do psd-tools e do motor, o PSD não é aberto de novo;
- `texto`: uma camada de texto com a matriz, os trechos (texto, fonte, corpo, tracking, entrelinha, caixa, kerning, ligaduras), os parágrafos, a região da página (caixa e caixa de tinta com a margem `render.margem_regiao_px`, dentro do canvas), a opacidade (camada x preenchimento x grupos), as cores no espaço do documento (`cores`, `valores_cor`, `cores_por_trecho`), as faces (`{fonte_ps: face_id}`), o antialiasing e `sharp_pequeno` (Sharp até `render.corpo_sharp_pequeno_px` no dispositivo);
- `linkado`: smart object linkado com o arquivo de `entrada/campanha/` confirmado pelo DA (`arquivo`, `sha256`), colocado no quadrilátero da camada (`colocacao`) ou na caixa.

`faces`: as faces do job usadas (id, sha256, nomes PostScript, formato, peso declarado, coleção, métricas), nunca bytes nem caminho. `registros`: o que o render não desenha ou desenha aproximado, por código e camada (efeito de texto, faux bold, escala de trecho, caixa de parágrafo quebrada pelo motor na largura da caixa, warp, mesclagem de texto diferente da normal, texto em grupo com máscara, máscara e efeito de linkado, ColorOverlay normal e opaco usado como cor do texto).

Bloqueios (o render recusa): `composicao_acima_do_orcamento` (recusa da composição no laudo), `modo_de_cor_fora_da_v1` (só RGB de 8 bits), `sem_estrutura`, `fontes_nao_conferidas`, `conferencia_desatualizada`, `fonte_bloqueante` (motivo técnico da conferência numa camada de texto visível), `arquivo_de_fonte_fora_do_job`, `linkado_sem_confirmacao`, `linkado_confirmado_mudou`. Decisão do DA (pede confirmação no terminal): `largura_divergente`.

### `desdobra render --job <pasta> [--formato origem]`

Render protegido (decisões, arquitetura nº 2): recusa com código 3 sem console interativo (veja disparo humano, abaixo), e pergunta ao DA sem resposta padrão (Enter vazio repete; `nao` cancela). Quando o contrato pede decisão (`largura_divergente`, `efeito_sobre_texto_sem_aplicar`, `clipping_dividido_por_texto`), pergunta também se o DA aceita, e o aceite vai para o `render.json`. As perguntas rodam sem a trava; o render pega a trava e monta o contrato de novo. A tela (M7) vai disparar o render pelo clique do DA. Passos (`desdobra.render.execucao.renderizar`):
1. monta e grava o contrato;
2. resolve as pilhas pelo cache ou roda o filho das pilhas;
3. o servidor local serve uma página por camada de texto e cor (`/pagina/<id>`) e as faces (`/fonte/<id>`, `Cache-Control: no-store`), com o controle positivo do cache na primeira página; o Chromium fixado (escala 1, `--disable-lcd-text`, `--disable-gpu`, `--force-color-profile=srgb`, perfil temporário curto) carrega cada página, o CDP confere a face de cada trecho com tinta e `Page.printToPDF` com `transferMode: ReturnAsBase64` devolve os bytes do PDF na resposta (o `page.pdf()` do Playwright pede stream, e o Chromium grava o stream em `<guid>.tmp` na pasta temporária). Camada visível sem trecho conferido para o render (`texto_sem_trecho_conferido`). Caixa de parágrafo: uma página mede as linhas, `texto.quebras_da_caixa` quebra na última posição de espaço antes da largura da caixa do PSD, e a camada volta para a fila com essas quebras. Posições de caractere em unidades UTF-16 (caractere fora do plano básico conta duas); erro de layout vira `ErroRender` (`texto_layout`);
4. o perfil é varrido (cópia de fonte, assinatura `%PDF-`, controle) e apagado. CDP sem 100% de confirmação, face que não carregou, cópia de fonte ou PDF no perfil param o render;
5. o filho do render recebe os PDFs pela entrada padrão e grava `master.png`; o motor copia para `render/<formato>/master.png`, apaga `render/.trabalho`, varre a pasta do job (arquivo de fonte fora de `entrada/fontes/` e PDF fora de `entrada/`) e grava `render/<formato>/render.json` (`render/1`): disparo (usuário, máquina, meio, quando), versões (Chromium, Playwright, pypdfium2, PDFium, psd-tools, numpy, Pillow, LittleCMS, Python), parâmetros citados (G, supersample, corpo Sharp pequeno, margem, cor), sha256 do contrato e do master, faces (id, sha256, nome PostScript, formato), CDP, cache, varredura, assets (pilhas e linkados com o sha256), aceites, registros, curva do perfil, conversão de cor, tempos.

Códigos: 0 master gravado; 3 recusado (sem terminal, cancelado, bloqueio ou decisão pendente, com a situação `bloqueado`); 4 teto de memória ou tempo do filho (a calibrar: não reprova); 5 auditoria; 1 erro interno; 21 job ocupado. O envelope leva só contagens (textos, Sharp pequeno, páginas de PDF, trechos do CDP, assets, registros, cópias no cache, fontes fora da entrada, PDFs no job), o sha256 do master e o tempo.

### Processo filho das pilhas (`desdobra.render.filho_pilhas`)

```
python -I -B -m desdobra.render.filho_pilhas <kv> <pasta_saida> --orcamento-bytes N
```

Mesmo isolador, linha `iniciar` e gancho de auditoria do leitor; abre o documento do mesmo jeito (cabeçalho contra o orçamento, vista sem os blocos dos smart objects, limites de alocação e de parse) e nunca abre smart object. Lê `pedido.json` da pasta de saída (sha256 do KV e as pilhas), confere o sha256, compõe cada pilha em faixas com `layer_filter` (as camadas da pilha e os grupos acima delas), `apply_icc=False`, e grava `<sha256>.png` e `pilhas.json`. Orçamento: o do leitor (`desdobra.leitor.orcamento_bytes`); tempo `isolador.tempo_max_s`.

### Processo filho do render (`desdobra.render.filho`)

```
python -I -B -m desdobra.render.filho <contrato.json> <pasta_saida> --orcamento-bytes N
entrada padrão: iniciar + uma linha JSON de cabeçalho + os bytes dos PDFs
```

O cabeçalho traz a pasta do job, G (`cor.gama_mistura_texto`), o supersample (`render.supersample`), os parâmetros de cor do job, as pilhas (arquivo e caixa), o tamanho de cada PDF e as pastas que o filho pode ler (assets, `entrada/campanha`, a pasta do perfil do documento). O gancho de auditoria só deixa ler essas pastas e o contrato, e só gravar na pasta de saída. O PDFium abre os bytes na memória, rasteriza em escala 96/72 x S com `FPDF_NO_NATIVETEXT`, em tons de cinza sobre branco, em faixas (`PIXELS_BANDA`, sem efeito no resultado), e a cobertura é a média de blocos S x S. Composição em float64 pré-multiplicado, de baixo para cima: pilha e linkado em mesclagem normal; texto pela fórmula do Photoshop com G sobre a curva do perfil do documento (`desdobra.render.icc` lê `curv` e `para`; sem perfil, sRGB), com uma cobertura por cor somada. No fim, 8 bits no espaço do documento e conversão para sRGB pelo LittleCMS com o intent e a compensação do job; sem perfil, o documento já é sRGB. Grava `master.png` (RGB, ou RGBA quando o canvas tem transparência) e `saida.json`. Orçamento `(isolador.base_python_bytes + render.bytes_por_px_canvas x pixels + render.bytes_banda_pdfium + bytes dos PDFs) x isolador.margem_orcamento`; tempo `render.tempo_max_s`.

### `desdobra linkado confirmar --job <pasta>`

Só no terminal interativo (código 3 sem ele). Para cada smart object linkado do laudo, mostra o registro do PSD (nome, tamanho, data) e os candidatos de `entrada/campanha/` da proposta do leitor, e o DA escolhe o número do arquivo ou pula. Grava `briefing/linkados-confirmados.json` (`linkados-confirmados/1`) com o arquivo, o sha256 congelado em `estado.json`, quem confirmou, o meio e quando. No M7 a confirmação passa para o briefing confirmado.

### Autoteste do render no doctor (`desdobra.render.autoteste`)

Decisão nº 36: a fonte é gerada pelo motor num processo filho (fontBuilder, com retas, diagonais e curvas, datas fixas, a mesma byte a byte), nunca baixada nem posta pelo DA. A página de referência (quatro linhas: corpo pequeno, duas cores numa linha, corpo grande e uma linha girada, sobre fundo creme) passa pelo mesmo caminho do job (`texto_no_chromium` e `compor`) e é comparada com `motor/referencias/autoteste-render.png`, gravada na máquina de desenvolvimento com `python -m desdobra.render.autoteste --gravar-referencia`. Verificação `autoteste_render` do doctor: falha se o filho não gera a fonte, se o CDP não confirma a face ou se o perfil guarda cópia da fonte ou PDF; aviso se a diferença passa de `render.autoteste_media_max` ou `render.autoteste_max_abs` (a calibrar). O autoteste Arial de captura de tela da pesquisa não existe no motor: o render não usa captura de tela.

### Correção na conferência de fontes (M2)

A feature `cpsp` da caixa alta ia no atributo `style` entre aspas duplas e fechava o atributo: o Chromium perdia o `cpsp` (e, no render, o `fill`). A página de medição (`desdobra.fontes.medicao`) e a do render usam agora aspas simples. A largura medida das camadas em caixa alta muda; a conferência roda de novo no próximo `fontes conferir`.

### Limites novos

`render.supersample` (8, medido na pesquisa §8), `render.corpo_sharp_pequeno_px` (256, decidido), e a calibrar: `render.margem_regiao_px` (16), `render.pagina_multiplo_px` (32), `render.bytes_por_px_canvas` (192), `render.bytes_banda_pdfium` (256 MiB), `render.tempo_max_s` (600), `render.autoteste_media_max` (0,5), `render.autoteste_max_abs` (8), `render.tolerancia_borda_smooth` e `render.tolerancia_borda_sharp_pequeno` (sem valor até o Duda fixar). O G vem de `cor.gama_mistura_texto` (1,45, decidido), que já existia.

### Pendências da frente de render

- A tolerância de borda fica sem valor até o Duda fixar (pergunta 6); o M4 entregou a medição por camada e a proposta no relatório do marco.
- Caixa de parágrafo: a quebra é do motor, pela largura da caixa e pela palavra; hifenização e justificação completa do Photoshop não são refeitas.
- Faux bold, faux itálico, sublinhado, tachado, traço de texto, escala de trecho, deslocamento de linha de base, warp de texto e efeitos de texto (exceto ColorOverlay normal e opaco) não são desenhados (registro).
- Pilha acima de texto é composta isolada: ajuste ou mesclagem diferente da normal que cruza o texto de baixo vira decisão do DA (`efeito_sobre_texto_sem_aplicar`). Aplicar o ajuste global no formato inteiro com o texto é do M5.
- Smart object linkado: a máscara e os efeitos da camada não entram (registro).

### Revisão do M4: disparo humano, entradas e temporários

**Disparo humano (`desdobra.humano`).** `console_interativo()` recusa: modo envelope; processo com variável de ambiente que o Claude Code põe nos processos dele (`CLAUDECODE`, `CLAUDE_CODE_ENTRYPOINT`, `CLAUDE_CODE_SESSION_ID`, `CLAUDE_PID`, `AI_AGENT`); pela interface de plataforma (`Plataforma.console_interativo`), no Windows, entrada ou saída que não é console (`GetFileType` de caractere e `GetConsoleMode` que responde: o `NUL` tem `isatty()` verdadeiro e é recusado aqui) e processo sem janela de console; fora do Windows, `isatty` nos dois. `exigir(comando)` emite o `Disparo` (comando, meio, usuário, máquina, hora e um selo aleatório guardado no processo) só depois dessa conferência; `conferir(disparo, comando)` recusa qualquer outro objeto. `render`, `linkado confirmar` e `spec confirmar` não têm parâmetro que pule a conferência, e `execucao.renderizar`, `linkados.confirmar` e `confirmar.sessao` só gravam com o `Disparo` (o do render vale uma vez). Testes e a medição do corpus simulam só o console (`humano.console_interativo`). Risco residual: um processo do mesmo usuário, fora do Claude, que abre um console e escreve teclas nele (`WriteConsoleInputW`), passa pela conferência.

**Gancho PreToolUse** (`hooks/hooks.json`, `scripts/gancho_confirmacoes.py`, só biblioteca padrão, forma exec): nas ferramentas Bash e PowerShell, nega comando que chama `desdobra render`, `linkado confirmar`, `spec confirmar` ou `briefing confirmar` (com opções globais no meio), código Python do motor que chama `renderizar`, `linkados.confirmar`, `confirmar.sessao` ou mexe em `desdobra.humano`, e escrita em arquivo que só o DA grava; nas ferramentas Write, Edit, MultiEdit e NotebookEdit, nega `briefing/`, `specs/confirmacoes.json` e `render/<formato>/master.png`, `render.json` e `contrato.json`. A negação diz ao Claude que quem roda é o DA, num terminal próprio. No M6 o gancho passou a negar também `aprovar`, `entregar` e `parametros-entrega`, o subcomando numa variável, a escrita em `entrega/`, `manifesto-licenca.json`, `relatorio-entrega.json` e `parametros/entrega.json`, e confere o comando normalizado (sem aspas nem escapes, caminhos sem `./`, `//` e `segmento/..`); a lista completa e o limite do gancho estão na seção do M6.

**Entradas trocadas.** O contrato bloqueia com `fases_desatualizadas` (ler, fontes, laudo-fontes ou ds inválida contra as entradas atuais), `entrada_alterada_fora_do_motor`, `laudo_de_outro_kv` (o sha256 do KV em `entrada/` difere do do laudo), `trecho_sem_face` e `linkados_de_outro_laudo` (a confirmação guarda `laudo_sha256` e `kv_sha256`). A chave da pilha usa o sha256 do KV em `entrada/`. `job trocar-entrada` e `job remover-entrada` apagam `render/<formato>/master.png` e `render.json` (`nucleo.invalidar_render`). O cache das pilhas confere o sha256 do asset no disco.

**Linkado.** Só PNG e JPEG (`linkado_formato_sem_suporte` pelo cabeçalho, sem decodificar no processo principal); no filho, `Image.open` só com esses formatos, CMYK e cinza convertidos (com perfil do asset, para o perfil do documento ou sRGB; CMYK sem perfil, conversão simples com registro `linkado_cmyk_sem_perfil`); os pixels do linkado contam no orçamento do filho.

**Temporários.** `render/.trabalho/` sai em qualquer falha. O master e o `render.json` são gravados como `.tmp-*` e só trocam de nome depois da varredura; render que falha não deixa master novo. Na plataforma Windows, a entrada do filho é escrita numa thread, e o relógio de `tempo_s` conta durante a escrita. Perfil ICC com curva ilegível (truncado, gama zero, parâmetro que divide por zero) vira `ErroCurva`, e o filho cai para a curva sRGB com registro.

## M5: derivação determinística por família (`desdobra/briefing`, `desdobra/derivacao`, `desdobra/render/derivado.py`)

Dono: frente de derivação do M5. Arquivos: `motor/desdobra/briefing/` (`modelo.py` e a CLI), `motor/desdobra/derivacao/` (`escala.py`, `elementos.py`, `formatos.py`, `solver.py`, `validacao.py`, `nucleo.py` e a CLI), `motor/desdobra/render/derivado.py`, a pilha transformada em `render/filho.py` (`colocar_transformada`), `execucao.montar_contrato` e o parâmetro `formato` do render, os esquemas `briefing-1.json`, `derivacao-1.json` e `devolucoes-1.json`, os campos novos de `composicao-1.json` (`elemento`, `transformacao`, `origem.derivacao_sha256`) e de `render-1.json` (`derivacao`), as entradas `derivacao.*` de `motor/fontes-de-limites.json`, a verificação `kiwisolver` do doctor e os testes `testes/test_derivacao*.py`. O kiwisolver 1.5.1 (BSD de 3 cláusulas) entrou no lock de execução e no doctor; o solver da derivação usa o HiGHS do scipy, que já estava no lock (ver Solver, abaixo).

### Contrato `briefing/1` (`briefing/briefing-confirmado.json`)

Todo campo de decisão é `{valor, situacao, origem}` (situação `confirmado` ou `pendente`; origem `da`, `padrao_marca`, `decisao_10`, `folha` ou `fixture_de_teste`, com a referência). Cabeçalho: hashes do laudo, das specs (os formatos do job quando há formato confirmado, senão o rascunho), do design system e da conferência de fontes; origem (`da` ou `fixture_de_teste`), meio (`tela`, `terminal`, `importar_teste`), quem e quando. Campos: quadro, funções (por grupo ou por camada, com observação), cobertas (o DA aceita ou inverte a função da regra da decisão 10), regras de escala por função, regras das camadas indeterminado, âncoras por eixo (por função ou por elemento, sem padrão), lockup de governo, sujeitos, formatos (id, chave das specs, largura, altura, rotação, sufixos), famílias (faixa, base, número de mestres), mestres (a do KV e as próprias, com a caixa de cada elemento e as quebras aprovadas), opções de texto e modo de dados.

**Herança** (`modelo.resolver`): a função dada a uma camada vale sobre a do grupo mais próximo; a camada coberta no KV sem função própria pede a decisão do DA sobre a sugestão da decisão 10; camada desenhável sem função é erro. Só a função resolvida chega ao layout, à validação e aos testes. A camada fora do quadro escolhido e a invisível ficam de fora (contagem).

**Conferência** (`modelo.conferir`): recusa pendente obrigatório (quadro, modo de dados, famílias), indeterminado sem observação, camada sem função, coberta sem decisão, função sem regra de escala, elemento (com tinta no canvas da mestre) sem âncora, formato repetido e mestre própria de formato que não existe. Exceção, regra e âncora pendentes não valem (a falta é conferida pelo que elas resolvem).

### Comandos do briefing

- `briefing importar <arquivo> --teste --job <pasta>`: grava o briefing escrito à mão com o cabeçalho dos arquivos de agora e a origem `fixture_de_teste`, depois do esquema e da conferência; nunca grava por cima de briefing com origem `da` e guarda o anterior em `briefing/historico/<sha256>.json`. Sem `--teste`, recusa (código 3).
- `modelo.conferir_para_entrega(pasta)` é o que o `entregar` (M6) lê: recusa `briefing_de_fixture_de_teste`, `briefing_rascunho`, `briefing_sem_origem_do_da`, `sem_briefing`, `briefing_invalido`, `briefing_desatualizado` e `briefing_com_problema` (roda a conferência inteira). A prova de que o arquivo saiu de um disparo humano entra com a confirmação no terminal (M7); até lá, o gancho nega a escrita em `briefing/` e o portão confere origem, hashes e conteúdo.
- `briefing rascunho --job <pasta> [--saida <arquivo>]`: o briefing sem valor, um item por grupo e por camada desenhável (instrumento da rotulagem), com a origem `rascunho` (o `derivar` recusa com `briefing_rascunho`, e o portão de entrega também). Grava por padrão em `rotulagem/briefing-rascunho.json`; dentro da pasta do job, só em `rotulagem/` (o caminho é resolvido de verdade, com `..`, junção e link simbólico), e recusa qualquer outro lugar do job.
- `briefing funcoes --job <pasta>`: as contagens da herança.
- A confirmação do briefing no terminal interativo entra com a tela, no M7.

### `desdobra derivar --job <pasta> [--formato <id>]...`

Pega a trava, confere entradas, fases (`ler`, `fontes`, `laudo-fontes`, `ds`, `specs`), briefing (contrato, cabeçalho e conferência) e grava `derivacao/<id>.json` (`derivacao/1`) e `derivacao/devolucoes.json` (`devolucoes/1`). Recusa com código 3 e `recusa_<motivo>` nas contagens: `sem_briefing`, `briefing_rascunho`, `briefing_desatualizado`, `briefing_com_problema`, `briefing_invalido`, `fases_desatualizadas`, `entrada_alterada_fora_do_motor`, `formato_desconhecido`. Não renderiza.

- **Elementos** (`elementos.montar`): camadas que herdam a função do mesmo lugar (a raiz) andam juntas; a caixa é a união das caixas de tinta cortada no canvas da mestre (a prancheta escolhida, ou o documento). O lado que encosta na borda sangra. Elemento sem tinta no canvas sai com registro (`fora_do_canvas`). Bloco rígido (decisões 95 e 99): elementos de base que se sobrepõem na mestre (interseção de pelo menos `derivacao.bloco_sobreposicao_min` da caixa menor, sem contar o fundo de cena, que cobre `derivacao.bloco_fundo_fracao` do canvas), a camada de mesclagem diferente da normal com o que ela cobre embaixo, e as camadas sem tinta (ajuste, preenchimento, smart object sem caixa) com os elementos de base embaixo que a influência delas cobre (a máscara, ou o canvas inteiro) formam um elemento só, com uma escala e um deslocamento; o elemento leva id, raiz, função e âncora do maior membro, `membros` e `bloco`. Camada sem tinta que não cobre nenhum elemento de base vai para `sem_bloco` e o `conferir` recusa (`camada_sem_tinta_sem_bloco`); ajuste global que cobre também conteúdo vai para `ajuste_global_sobre_conteudo` e todo formato derivado devolve `ajuste_global_sem_aplicar` (decisão 99, enquanto o render não aplica o ajuste ao formato inteiro).
- **Família** (`formatos`): base do cálculo `arquivo`, `composicao` (girada em 90 e 270 graus) ou `area_util` (da folha); orientação horizontal, quadrado (|ln(L/A)| até `derivacao.quadrado_ln_max`) ou vertical. Troca de orientação contra todas as mestres devolve (`troca_forte_de_orientacao`, `troca_de_orientacao_quadrado`); mesma orientação fora da faixa (`derivacao.faixa_familia_razao_max`) devolve `fora_da_faixa_de_familia`. Faixa, base e número de mestres: briefing, depois `parametros/derivacao.json`, depois a proposta citada do registro.
- **Caminhos**: mesma proporção (diferença até `derivacao.mesma_proporcao_px`) vira transform de saída se passa nas validações obrigatórias; senão, ou com proporção diferente, o solver; a obrigatória que não fecha devolve `restricao_obrigatoria_nao_fecha` com nome, força e fonte. O formato de uma mestre própria sai das caixas do DA (contain na caixa; cover no elemento que sangra no KV, para o corte ficar fora); mestre própria sem caixa para todo elemento devolve `mestre_propria_incompleta`, e as quebras da origem num formato de outra orientação só valem com `quebras` aprovadas.
- **Solver** (`solver.resolver`): o problema do Cassowary (restrições com forças, obrigatórias duras e as outras em ordem estrita) resolvido pelo HiGHS (`scipy.optimize.linprog`), porque o kiwisolver 1.5.1 (e o 1.4.9) abortou o processo em parte das soluções do corpus e variava de um processo para outro. A obrigatória que não fecha é achada por bisseção, na ordem em que entrou. Variáveis x, y e s por elemento, em unidades do maior lado do formato. Obrigatórias com fonte (área útil, faixas e área segura da folha, esta para texto e marca; dentro do canvas; sangria; não sobrepor pelo eixo em que a mestre separa, só entre pares de conteúdo, isto é, texto, marca e sujeito, decisão 96; margem mínima de texto e marca até cada borda que não sangra, `derivacao.margem_minima_lado_curto` do lado curto, nunca acima da margem da mestre escalada, decisão 98), fortes (razão de corpo entre todos os textos, decisão 97, e entre elementos de mesma função e regra nas outras classes; margem até cada borda pelo menos a proporcional da mestre, decisão 98; alinhamentos de borda e centro da mestre, fora do eixo que sangra), médias (âncora por eixo, posição proporcional), fracas (regra de escala). As forças não obrigatórias entram em ordem estrita (lexicográfica: o ótimo da forte fica preso, depois o da média, depois o da fraca), com perturbação mínima para o ótimo ser único; o vértice é refeito pelas restrições ativas (mínimos quadrados) para sair igual em todo processo.
- **Validações** (`validacao.validar`): enquadramento, área útil e faixa, área segura, colisão nova contra a mestre do KV (só entre pares de conteúdo), inventário, regra por função (função e regra relidas do briefing, contra as do layout), resíduo da regra (registro) e folga de resolução (aviso). A primeira obrigatória que reprova devolve `validacao_obrigatoria_reprovou` com nome e fonte. Entre formatos, `inventario_entre_formatos` (igual ou diferente).
- Indeterminado sem regra devolve todo formato (`indeterminado_sem_regra`). Fora da peça não entra em elemento nenhum. Formato cuja chave está na folha com um valor que a derivação lê (dimensão, faixas, área útil ou área segura, do próprio formato ou herdado) ainda em rascunho em `specs/rascunho.json` devolve `spec_por_confirmar`, com qualquer arquivo de specs que valha: a derivação não usa o valor sem confirmação nem a spec sem ele, a tela não monta galeria para o formato, a família dele não pode ser confirmada e a lista do que falta leva o DA a Valores de spec, no passo 1. Enquanto o formato de uma mestre própria do DA está assim, a base da mestre não sai do valor sem confirmação, e todo formato que deriva dessa mestre devolve `mestre_por_confirmar` (medidas `mestre`, `formato_da_mestre`, `chave_da_mestre`), com o mesmo tratamento na tela: sem galeria, família sem confirmação, "Salvar e seguir" recusado e o item do que falta levando a Valores de spec, no passo 1. O formato da folha com a medida divergente (duas leituras, valor nulo) fica sem chave na importação até o DA escolher a leitura; a escolha monta a chave dele depois das ações (`specs.modelo.chaves_depois_das_escolhas`), sem mudar chave nenhuma que já existia (a repetida leva o sufixo `#<id>` e o alerta `chave_repetida` só no formato novo, também quando a chave igual já tinha sufixo). Até a escolha, a tela lista todos os valores do formato em Valores de spec pelas medidas da folha, o que falta leva ao passo 1, o botão "Salvar e seguir" fica desligado com a dica da medida e o salvar recusa com `formato_sem_medida`. Formato cuja chave não está nas specs devolve `formato_sem_folha`, salvo o marcado `sem_folha` no briefing (medição, teste), que deriva com registro; formato com largura e altura diferentes da dimensão da folha devolve `dimensao_diferente_da_folha`. Um formato que quebra devolve `erro_no_formato` sozinho, e os outros seguem. Texto e marca nunca sangram: encostar na borda do KV conta como dentro, e a área útil, as faixas e a área segura valem para eles. A base `arquivo` usa o arquivo na orientação da composição. Mestre sem elemento é recusada no `conferir` (`mestre_sem_elemento`). Ids de formato `devolucoes`, `origem` e os nomes reservados do Windows (con, prn, aux, nul, com1 a com9, lpt1 a lpt9) são recusados no esquema, no `conferir` (`formato_id_reservado`) e no `render --formato`. Com `--formato`, o `derivar` muda só a entrada daquele formato em `devolucoes.json` e refaz o inventário com todas as derivações deste briefing.
- Cada elemento derivado traz caixa, escala, âncora, quebras (`congeladas_da_mestre` ou as da mestre própria), corpo, a regra aplicada (função, regra, caminho, classe) e a transformação para o render (`s`, `origem_doc`, `destino`, `recorte_doc`, `sangra`), arredondadas para o resultado ser o mesmo em todo processo.

### Render de formato derivado

O render ganhou `--formato <id>` (padrão `origem`), com o mesmo disparo humano do M4 (terminal próprio, pergunta sem resposta padrão). `execucao.montar_contrato` monta pelo `render/derivado.py`: lê `derivacao/<id>.json` e refaz a derivação do formato (determinística) com o briefing, as specs, os parâmetros e os limites de agora; arquivo diferente bloqueia com `derivacao_desatualizada` (bloqueia também `formato_sem_derivacao`, `formato_devolvido`, `briefing_desatualizado`, `rotacao_sem_render`), monta o contrato da origem com fora da peça para toda camada sem elemento e transforma as entradas: a pilha da origem é separada pelo elemento de cada camada (camada clipada vai com o elemento da base), e cada pedaço leva a transformação; o texto leva a matriz escalada e deslocada (quebras e tracking da mestre) e a região transformada com a margem; o linkado leva o quadrilátero e a caixa transformados. Ajuste global sem aplicação no formato inteiro (`ajuste_global_sem_aplicar_no_formato`) e mesclagem diferente da normal que perde o fundo dos outros elementos (`mesclagem_sem_o_fundo_de_outro_elemento`) são decisões do DA. Com os blocos, a mesclagem só pede decisão quando é a primeira camada do seu pedaço e há outro elemento desenhado embaixo; dentro de um bloco ela compõe sobre o fundo do próprio bloco, numa pilha só, como no M4. No filho, `colocar_transformada` corta o asset no recorte da mestre e reamostra em alfa pré-multiplicado com LANCZOS, pela caixa de origem que corresponde ao destino em pixel inteiro, com folga transparente (repetida no lado que sangra). O `render.json` ganha `derivacao` (arquivo, sha256, caminho, mestre, briefing e a origem dele).

### Gancho PreToolUse (revisão do M5)

Os arquivos que só o motor ou o DA gravam passam a incluir todo `.json` de `derivacao/` (além dos de `briefing/`). Contam como escrita, além de redireção, cópia e movimento: `os.replace`, `os.rename`, `os.link`, `os.symlink`, `shutil.`, `Rename-Item`, `ren`, `rename`, `Move-Item`, `Copy-Item` e a opção `--saida` do motor. O motor chamado como `desdobra.cli` ou `desdobra.__main__` conta como `desdobra`. O código-fonte do plugin (`motor/desdobra/derivacao/*.py`, `briefing/*.py`, `schemas/derivacao-1.json`) continua editável.

### Revisão 2 do M5 e decisões 100 e 101

- **Bloco partido** (`bloco_partido_na_pilha`): se, na pilha do laudo, outro elemento, ou um texto ou linkado do próprio elemento (o render os desenha fora da pilha), fica entre um efeito do elemento (camada que atua embaixo, mesclagem ou camada clipada) e o que o efeito pega, todo formato derivado devolve, com `blocos` (elemento, separadores, efeitos; só ids). O render tem a mesma conta como defesa (`elemento_partido_no_render`, bloqueio): pedaço de efeito sozinho nunca sai em silêncio. Saiu o bloqueio morto `ajuste_global_sem_aplicar_no_formato`.
- **Ajuste global** nunca é elemento próprio: com tinta (cor sólida, preenchimento) ou sem, atua onde a tinta e a máscara dele atuam; sobre conteúdo devolve, só sobre cena entra no bloco.
- **Clipping e grupo**: a camada clipada anda com a base do clip (a camada de baixo mais perto, no mesmo pai, sem clipping), e a caixa dela é cortada pela da base; o ajuste e a mesclagem clipados atuam só na base. Num grupo com mesclagem própria (isolado), o efeito atua só dentro do grupo; em passagem, em tudo embaixo. O ajuste dentro de um elemento com tinta também junta a cena que ele cobre embaixo.
- **Membro inteiro**: o membro do bloco que é objeto (não só cor sólida ou preenchimento) e estava inteiro no canvas da mestre, e o membro texto ou marca, ganham obrigatórias `membro_dentro_do_canvas`, `membro_dentro_da_area_util` e `membro_dentro_da_area_segura` (estas para texto e marca), depois da sangria; quando não fecham, o formato devolve com o nome do membro e a fonte. A validação confere o mesmo pela caixa do membro no formato.
- **Regra do bloco (decisão 100)**: o `conferir` recusa bloco cujos membros têm regras de escala diferentes (`bloco_com_regras_diferentes`, com as camadas, os membros e as regras) e pede `regras_bloco` no briefing (layer_id de qualquer camada do bloco e a regra). Recusa também regra de bloco conflitante e regra de bloco para camada fora de bloco. A validação `regra_por_funcao` confere a função de cada membro (`funcoes_membros`).
- **Margem da mestre (decisão 101)**: média; o mínimo obrigatório de texto e marca continua.
- **Fundo ambíguo**: elemento de cena entre `derivacao.bloco_fundo_fracao` menos `derivacao.bloco_fundo_faixa_ambigua` e o limiar junta como cena comum, e cada formato avisa (`fundo_de_cena_ambiguo`).
- **Validações novas**: `cena_cobre_conteudo` (cena opaca acima de conteúdo na pilha que passa a cobrir mais que `derivacao.cobertura_nova_cena_sobre_conteudo_max` da caixa dele, reprova) e `corpo_minimo_do_legal` (abaixo de `derivacao.corpo_minimo_legal_px`, avisa). O indeterminado com tinta conta como conteúdo no "não sobrepor" e na colisão.
- **Maior membro**: o desenhado por si (não só clipado), depois a área, e no empate o de baixo na pilha; `origem_funcao` é a da raiz dele.
- **Preparo**: com pranchetas, os aglomerados são medidos por prancheta.

### Rodada 3 da fatia

- **Objeto solto** (base opaca que não sangra, sem véu nem sujeito) entra no "não sobrepor" e na colisão nova contra conteúdo (`solver.objeto_solto`, `par_que_nao_sobrepoe`).
- **Proximidade** (`derivacao.proximidade_max`): conteúdo e objeto solto empilhados e perto na mestre mantêm a distância na escala deles (forte, `proximidade_<eixo>`); entre textos não vale.
- **Grupo preso**: elementos ligados por alinhamento ou proximidade, num eixo, usam só a âncora do maior.
- **Alinhamento**: a diferença da mestre (dentro da tolerância) vai na escala média dos dois elementos.
- **Quebras por família** (`quebras_por_familia` no briefing/1): `layer_id`, `razao_min` e `razao_max` (largura / altura do formato) ou `formatos`, e `quebras` (decisão com os índices das quebras gravadas que ficam). O layout usa a caixa estimada pela contagem de caracteres (`derivacao/quebras.py`); o elemento derivado leva `quebras` (`aprovadas`, `juntadas`) e `quebras_camada`; o contrato do texto leva `quebras_juntadas`, e `render.texto.linhas_da_camada(..., juntar=...)` junta as linhas. O `conferir` recusa `quebra_aprovada_invalida`. Texto de mais de uma linha sem quebra aprovada avisa `quebras_sem_aprovacao` a partir de `derivacao.quebra_razao_aviso`.

### Revisão 3 do M5

- **Medida das linhas juntadas** (`derivacao/medida_quebras.py`): no `preparar` do job, quando o briefing tem `quebras_por_familia`, a pagina de medida da conferencia de fontes (`fontes.medicao`) mede no Chromium, com a fonte do job servida pelo motor, o texto da mestre e o texto juntado. A caixa nova (`derivacao.quebras.caixa_medida`) tem a largura na proporcao medida e a altura menos uma entrelinha por quebra tirada, e nunca e cortada no canvas da mestre. Sem medida, o formato volta com `quebra_sem_medida`. `nucleo.contexto(..., medidas_quebras=)` recebe a medida em memoria.
- **Envelope**: o elemento derivado leva `quebras: {'familia': [{layer_id, aprovadas, caixa_doc}]}` (so indices); o render calcula as posicoes (`render.derivado.quebras_da_entrada`), em cada texto do elemento. A lista de posicoes da mestre propria (`quebras_camada`, um texto so por elemento) chega ao render como `quebras_inseridas`.
- **Tinta contra a caixa validada**: o contrato do texto derivado leva `caixa_validada` e uma regiao que a cobre com folga; o filho do render devolve a caixa da tinta real e os lados em que ela encosta na regiao; `render.derivado.tinta_fora_da_caixa` reprova (`tinta_fora_da_caixa_validada`) acima de `render.tolerancia_tinta_texto` (5% do maior lado, minimo `render.tolerancia_tinta_texto_min_px`, 3 px) ou com corte na regiao.
- **Conferir**: recusa quebra por familia em caixa de paragrafo (`quebra_em_caixa_de_paragrafo`), formato inexistente, faixa invertida, faixas sobrepostas com valores diferentes e lista da mestre propria em elemento de mais de um texto. O formato vence a faixa.
- **Ancora do grupo**: a ancora dada ao proprio elemento vale sobre a da funcao; no grupo preso, o principal e o maior dos que tem ancora propria (senao o maior), e a restricao de registro `ancora_do_grupo_<eixo>` diz quais ancoras ficaram sem efeito.
- **Objeto solto**: exige uma camada em mesclagem normal com opacidade efetiva (camada, preenchimento e grupos) de pelo menos `derivacao.objeto_solto_opacidade_min` (0,9).

### Preparo do PSD (decisão 99)

`laudo.preparo.contar` conta, pelo laudo, ajustes com máscara, mesclagens, cores sólidas com máscara sobre imagem e aglomerados sobrepostos (três ou mais camadas desenháveis sem texto ligadas por sobreposição, sem a que cobre quase o canvas inteiro). Quando a soma das três primeiras chega a `laudo.preparo_minimo_camadas`, ou há aglomerado, a esteira mostra no fim do laudo a recomendação de preparar o PSD antes da rotulagem (juntar a cena num smart object ou num grupo). Só contagens; nenhum nome de camada.

### Limites novos

A calibrar, com fonte: `derivacao.faixa_familia_razao_max` (2,0), `derivacao.base_calculo` (`area_util`), `derivacao.mestres_max` (3), `derivacao.quadrado_ln_max` (0,05), `derivacao.mesma_proporcao_px` (1), `derivacao.alinhamento_tolerancia_px` (2), `derivacao.colisao_tolerancia_px` (1), `derivacao.enquadramento_tolerancia_px` (1), `derivacao.escala_min` (0,01), `derivacao.tolerancia_regra_escala` (0,001) e `derivacao.residuo_regra_aviso` (0,6931, fator 2; avisa). Das decisões 95 a 99: `derivacao.bloco_sobreposicao_min` (0,01), `derivacao.bloco_fundo_fracao` (0,95), `derivacao.margem_minima_lado_curto` (0,05, proposta do corpus: mínimo 0,050 e mediana 0,066 em 16 elementos de texto e marca) e `laudo.preparo_minimo_camadas` (3; avisa). Da revisão 2: `derivacao.bloco_fundo_faixa_ambigua` (0,05; avisa), `derivacao.cobertura_nova_cena_sobre_conteudo_max` (0,01) e `derivacao.corpo_minimo_legal_px` (8 px; avisa). Da rodada 3: `derivacao.proximidade_max` (0,05) e `derivacao.quebra_razao_aviso` (ln 1,5; avisa).

### Impressão por formato (M7b, A1 a A7)

- `derivacao/impressao.py`: `impressao(derivacao_formato, briefing_resolvido, fid)` devolve o sha256 (hex) de tudo o que alimenta o formato, para a cadeia derivação, render e aprovação cair só no formato que mudou. `briefing_resolvido` sai de `impressao.resolvido(briefing, resolvidas, specs)` (`resolvidas` de `briefing.modelo.resolver`). Entram: a `derivacao/1` do formato sem `gerado_em`, `briefing_sha256` e `inventario_entre_formatos`; as funções resolvidas das camadas no escopo (as dos elementos do formato e as `fora_da_peca`; o elemento apagado pelo DA fica fora); as regras de escala, do indeterminado e de bloco delas; as âncoras (a do elemento vale sobre a da função); as quebras aprovadas que valem no formato; o formato do briefing, a composição da família dele e os valores da folha (sem `id` e `fonte` do campo); a mestre própria usada, com o formato e a folha dela. Todo número com casas sai por `nucleo._q(v, CASAS_ESCALA)`. Função pura: não lê arquivo. Entram também, desde o A3, as camadas `fora_da_peca` de agora (a lista vai em toda derivação: a camada que sai da peça muda todo formato, inclusive o gravado antes) e fica fora a própria `impressao_formato`. Desde o A6, o carimbo `em` da confirmação da família fica fora, na composição do briefing e na `proposta` da derivação (`impressao.CARIMBO_DA_CONFIRMACAO`): a mudança do passo 2 pede nova confirmação de toda família (decisão 175), e confirmar de novo a mesma versão com as mesmas edições não muda o formato. A origem e o meio da confirmação continuam na conta. Ficam fora também o id da família (`impressao.ROTULOS_DA_FAMILIA`, na composição e na `proposta`), que até a revisão do id estável (abaixo) era a posição do grupo na tela e ainda pode mudar quando a família se divide ou se junta, e a lista dos formatos da composição, que só alimenta o formato pela derivação dele (o irmão novo que não muda a derivação não derruba o formato). A versão e as edições da família continuam na conta.
- Cadeia por formato (A2). A impressão substitui o sha do briefing inteiro em cada elo:
  - `derivacao/<f>.json` grava `impressao_formato` (fora do `required` do `derivacao/1`: o arquivo de antes lê e cai como desatualizado). `briefing_sha256` fica como registro de quando o formato foi derivado e não trava nada.
  - `nucleo.impressao_de_agora(pasta, d, briefing=None)` refaz a impressão da derivação gravada `d` com o briefing, o laudo e as folhas de agora (None quando o formato saiu do briefing ou falta o que ler).
  - A trava do derivado (`render/derivado.montar`) compara `impressao_formato` com `impressao_de_agora` no lugar do sha do briefing. O `_derivacao_confere` (rederivação em memória contra o arquivo) continua depois dela, sem o `briefing_sha256` na comparação e com a `proposta` passada por `impressao.sem_carimbo` (sem o carimbo `em` da confirmação e sem o id da família): o formato que o salvar seletivo guarda depois de confirmar a família de novo segue para o render.
  - O contrato (`composicao/1`) leva `origem.derivacao_impressao` no lugar de `origem.derivacao_sha256` (o sha do arquivo levava o carimbo: derivar de novo sem mudar o formato deixa o contrato igual). O `render.json` leva `derivacao.impressao_formato` (a do contrato); `derivacao.sha256` passa a ser o sha do arquivo lido no render, só registro.
  - O portão (`portao.impressao_do_formato`) mede a impressão de agora; `master_de_outro_briefing` vira `master_de_outra_impressao`. O `atual` de cada formato, `aprovacao.HASHES` e `relatorio.HASHES` trocam `briefing_sha256` por `impressao_formato`.
  - Mudar a função de uma camada que só está em f1 derruba o render e a aprovação de f1 (`aprovacao_caiu` com o campo `impressao_formato`) e deixa f2 e f3 passarem; mudar o briefing fora dos formatos (o carimbo do cabeçalho) não derruba nenhum (`testes/test_cadeia_por_formato.py`).
- Rederivação seletiva (A3). `nd.derivar(pasta, so=[...])` guarda no inventário e em `devolucoes.json` o formato gravado cuja `impressao_formato` ainda confere com o briefing de agora (antes, só o do mesmo sha do briefing). O `inventario_entre_formatos` dos formatos derivados agora sai do inventário com todos os guardados; o dos guardados fica o gravado, porque o arquivo deles não muda (mesmo sha). A derivação guardada que não confere mais sai da conta.
- Determinismo (A0): 30 derivações no mesmo processo e 30 em processos com `PYTHONHASHSEED` diferente deram o mesmo `derivacao/<f>.json` normalizado nos três caminhos (transformação 2 de 2, solver 6 de 6, galeria 5 de 5). O teste fica em `testes/test_determinismo_derivacao.py`.
- O apagado pelo DA numa família da galeria ainda alimenta os outros elementos: a versão da galeria sai com todos e o encaixe é refeito depois, e a mudança da função dele chega à impressão pela derivação.
- Histórico com índice encadeado (A4, `briefing/historico.py`, contrato `historico-indice/1`). Cada gravação do briefing (`briefing.modelo.gravar_com_historico`, que ganhou o argumento `afetados=None`) acrescenta uma entrada em `briefing/historico/indice.json`: `seq` (1, 2, 3...), `quando` (o carimbo da gravação), `origem` e `meio` do cabeçalho, `sha_anterior` (None na primeira) e `sha_novo` do arquivo do briefing, `formatos_afetados` (None quando quem grava não os calculou; o salvar seletivo do A6 os passa) e `sha_entrada_anterior` (sha256 da entrada anterior em JSON canônico, a cadeia). A versão anterior continua em `briefing/historico/<sha>.json`, como antes. `historico.conferir(pasta)` lê e confere: `indice_invalido`, `indice_reiniciado`, `sequencia_quebrada`, `cadeia_quebrada`, `versoes_desencadeadas` (o `sha_anterior` não é o `sha_novo` da entrada de antes) e `briefing_fora_do_indice` (o briefing gravado não é o da última entrada). `historico.avisos(pasta)` traduz em frases, e `tela.estado._avisos_do_job` as junta aos avisos de retomada na faixa de avisos da tela. A gravação nunca para por causa do índice mexido: ela encadeia na última entrada que há, e o índice ilegível fica guardado como `briefing/historico/indice-invalido-<sha>.json`, com o novo começando em `reiniciado_de`; o aviso continua nos dois casos. Job gravado antes do índice não tem o que conferir até a próxima gravação.
- O que a cadeia do A4 não resolve: o risco da nº177 continua. A cadeia mostra a ordem e pega a adulteração ingênua (entrada apagada, trocada ou fora de ordem, briefing trocado sem passar pelo gravador). Ela não prova quem gravou: o índice não tem segredo, e quem reescreve o índice inteiro com a cadeia refeita passa sem aviso. Histórico, rascunho e aprovação escritos à mão continuam sem se distinguir dos gravados pela tela; o que impede o Claude de escrevê-los é o gancho.
- Diferença por formato (A5, `derivacao/diferenca.py`). `impressao.corpo(d, briefing_resolvido, fid)` devolve o que a impressão resume, já normalizado (`impressao.do_corpo(c)` dá o sha; `impressao` é `do_corpo(corpo(...))`). `diferenca.diferencas(antes, depois)` compara dois corpos (None num lado: `formato_novo` ou `formato_saiu`) e `diferenca.do_formato(d_antes, br_antes, d_depois, br_depois, fid)` monta os corpos antes. Cada item é `{tipo, elemento, frase}` e, em `moveu` e `tamanho`, `antes` e `depois` com as caixas, para a tela desenhar a caixa velha. Tipos: `situacao`, `caminho`, `formato` (tamanho e giro, áreas, mestre, versão e edições da família, PSD, fontes, versão do desdobra), por elemento `entrou`, `saiu`, `apagado`, `fora_da_peca`, `funcao`, `moveu` (px e % do lado, pelo centro da caixa), `tamanho`, `escala`, `regra`, `ancora`, `quebra`, `texto`, `origem` (`origem_geometria`), `camadas`, `caixa_mestre` e `detalhe`; as camadas soltas que saíram da peça ou voltaram; os outros campos da derivação só quando nada acima saiu; e `entrada`, quando a derivação ficou igual e mudou só o que a alimenta (a frase termina em "e a peça ficou igual"). Impressão igual não dá item; impressão diferente dá pelo menos um (o que nenhum detector explica sai como detalhe). As frases seguem as regras de escrita da tela (sem travessão, com artigo, sem identificador do motor), por exemplo "O título desceu 24 px (8,0% da altura).", "O logo principal saiu da peça.", "Você apagou o texto legal nesta família.". Teste aleatório em `testes/test_diferenca_formato.py` (1500 mudanças).
- Salvar seletivo (A6, `briefing/salvar.py`, contrato `historico-mudancas/1`). Dentro da trava do job, antes de gravar, "Salvar e seguir" (e o "briefing confirmar" do terminal, o mesmo gravador) deriva em memória com o briefing novo (`nucleo.preparar(pasta, briefing=b)`, que confere e deriva o briefing dado no lugar do gravado, com `briefing_sha256` vazio no contexto) e compara a `impressao_formato` de cada formato com a da derivação gravada. Afetado é o formato cuja impressão mudou, o que não tinha derivação gravada (ou ela não se lê) e o que saiu do briefing. Depois, `gravar_com_historico(..., afetados=[...])` põe a lista na entrada do índice; `briefing/historico/mudancas/<seq>.json` guarda `seq`, `sha_anterior` e `sha_novo` (os da entrada) e, por formato afetado, a lista de A5 (`diferenca.do_formato` com a derivação gravada e o briefing gravado antes, resolvido; sem derivação ou sem briefing de antes do formato, `formato_novo`; formato que saiu, `formato_saiu`); e `nd.derivar(pasta, so=...)` regrava só os afetados que estão no briefing novo. Os outros ficam com o mesmo arquivo (mesmo sha) e entram no inventário e em `devolucoes.json` pelo A3. O evento `briefing_confirmado` leva `afetados`, e o retorno de `salvar` também. Quando a derivação em memória não roda (`ErroDerivacao`, `ErroFormatos` ou contrato ilegível), `afetados` fica None no índice e fora do evento, nenhum arquivo de mudanças é gravado e a derivação refaz todo formato, como antes. Testes em `testes/test_tela_salvar.py` (primeiro salvar com todos afetados, salvar sem mudança sem regravar nada, mudança da âncora do logo que regrava só `mesma` e `quadrado` e deixa intacta a família vertical depois da nova confirmação de todas as famílias, e a derivação em memória que falha).
- Render do texto editado (A7). O bloqueio `texto_editado_sem_render` saiu: o render desenha o texto que o DA editou no palco. Na derivação (`derivacao/proposta._derivacao`), o elemento com `texto_editado` leva `quebras: "do_texto_editado"` e nunca as quebras da proposta (antes, as quebras da família juntavam com as linhas do DA). No contrato (`render/derivado.texto_editado_na_entrada`), a entrada de texto do elemento editado vira um trecho só, com o estilo, a cor, a face e o parágrafo do primeiro trecho com tinta, e ganha `texto_editado: true` e `largura_quebra` (a largura da caixa de tinta da camada no formato, levada ao espaço do texto: a mesma largura da prévia). `render/texto.largura_da_quebra` faz a página de medida no Chromium também para essa entrada, e `quebras_da_caixa` quebra a linha no espaço nessa largura, como na caixa de parágrafo; as quebras de linha que o DA digitou ficam. O cmap da face do job é conferido no contrato como na edição da tela (`derivado.caracteres_fora_da_face`, a mesma `tela.edicao.caracteres_que_faltam`): caractere que falta dá o bloqueio `texto_editado_fora_da_fonte` com `elementos` e `caracteres`. O texto novo não tem caixa validada pela derivação: a região da página e `caixa_validada` são o formato inteiro, o contrato registra `texto_editado_desenhado`, e `tinta_fora_da_caixa` conta como corte qualquer tinta na borda do formato. O `render.json` leva em `textos.editados` as linhas que o render desenhou (`entrada`, `layer_id`, `elemento`, `linhas`). Na tela, o texto editado quebra só no espaço (sem `overflow-wrap: break-word`) e a linha que quebra desce uma entrelinha, como no render.
- Id estável da família (revisão da fase A). O id do grupo da tela é o id da família: o rascunho guarda as edições, a versão e a confirmação por ele, os atos e a prévia da edição o usam, e "Salvar e seguir" grava `composicoes[].familia` com ele. Até aqui era a posição do grupo na aba (`'<orientacao>-<n>'` pela proporção), e o formato que entrava, saía ou mudava de medida no passo 1 podia levar as edições de um grupo para outro. Agora `tela.estado.abas(laudo, briefing, formatos, variantes=None, conhecidas=None)` casa cada grupo com os ids que o job já conhece (`tela.estado.familias_conhecidas(pasta)`: `{id: [formatos] ou None}`, do rascunho da tela e das `composicoes` do briefing gravado, mesmo de outra versão dos arquivos; o rascunho vale sobre o briefing). Cada grupo fica com o id com que divide mais formatos; no empate, o de menos diferença, depois o grupo que vem antes nas abas e o id menor (`'<orientacao>-<n>'` pelo número). Um id vai a um grupo só, e o `'<outra orientacao>-<n>'` nunca vai ao grupo desta orientação (o id que não diz orientação, como os do briefing de teste, segue os formatos). O grupo sem formato em comum com id nenhum ganha o menor `'<orientacao>-<n>'` que nenhum id conhecido usa: o id que sumiu da tela fica reservado, e as edições dele nunca passam para outros formatos. Sem id conhecido (job novo), a numeração é a de antes. O id do rascunho de antes desta revisão, sem formato nenhum (`None`), fica com o grupo da mesma posição. A ordem das abas continua pela proporção. Divisão: a parte que divide mais formatos fica com o id e as edições, e a outra ganha id novo e parte da proposta. Junção: o id que fica guarda as edições, e as do outro id continuam no rascunho (a página as manda de volta a cada gravação), prontas para quando os formatos se separarem de novo.
  - Cada grupo leva `aviso` (e `conteudo['familias'][id]['aviso']`): a frase da tela quando a família ganhou ou perdeu formatos desde que o DA mexeu nela (`estado.aviso_da_familia`: o que entrou, o que saiu e, para o formato vindo de outra família conhecida com edição, que as edições de lá ficam guardadas e não valem aqui) ou quando ela é nova com formatos que estavam em outra família (`estado.aviso_de_familia_nova(de_outra, com_edicoes)`: "sem as edições de lá" só quando a família de lá tem edição), senão `''`. `abas(..., conhecidas=None, editadas=(), cedidos=None)` recebe as duas marcas de `estado.marcas_das_familias(pasta)`: `editadas` (ids com edição, o rascunho sobre o briefing) e `cedidos` (`{id: [formatos]}` do rascunho). O formato cedido que está de novo na família entrou de novo, mesmo estando na lista guardada dela. A página põe a frase em `#aviso-familia`, acima do palco, e marca a família na lista (`.mudou`, "Mudou, confirme de novo"). A confirmação não conta para outros formatos nem com formato cedido de volta (`rascunho.confirmada_para` com `confirmacao.formatos`, `cedidos` e a impressão das peças), e a lista do que falta pede a confirmação de novo.
  - A frase segue o rascunho de agora sem mudar os ids: `recarregar()` (depois de cada ato) refaz o `aviso` de cada grupo com `estado.avisos_das_familias(pasta, familias)`, no estado e em `conteudo['familias']`; a família confirmada deixa de dizer que mudou. A página troca a frase e a marca no lugar quando só ela mudou (sem redesenhar o passo 3) e, depois de cada estado novo, lê `/api/rascunho` de novo para tirar a confirmação que o servidor não conta mais (`sem_confirmacao_velha`): o botão "Confirmar família" volta, e "Salvar e seguir" espera.
  - `rascunho-tela/1`: cada família ganha `formatos` (opcional), os formatos da família na tela quando o DA mexeu nela pela última vez. Só o servidor grava: `rascunho.gravar(..., familias_da_tela=)` descarta o que a página manda e põe os formatos da tela na família nova ou com versão ou edições diferentes das gravadas; a que não mudou guarda os de antes (o aviso continua até o DA mexer nela ou confirmá-la), e a que a tela não mostra mais guarda os gravados. `rascunho.confirmar_familia` grava os formatos confirmados também ali. O rascunho de antes, sem `formatos`, usa `confirmacao.formatos` e depois as `composicoes` do briefing. E ganha `cedidos` (opcional, também só do servidor): quando o DA mexe numa família ou a confirma, cada outra família que ainda tem algum desses formatos na lista guarda ali os que foram levados (`rascunho._ceder`). O campo sai quando o DA mexe nela ou a confirma.
  - A impressão de cada formato continua sem o id e sem a lista dos formatos da família: o salvar depois de um id novo ou de uma família que mudou de formatos não derruba a derivação, o render nem a aprovação do formato que não mudou (`test_cadeia_por_formato.py`, `test_tela_familia_estavel.py`).

### Pendências da frente de derivação

- Confirmação do briefing no terminal e a tela (M7). Requebra que tira quebra da origem (hoje só acrescenta, ou mantém aprovada). Rotação no render (M6). Ajuste global aplicado ao formato inteiro (hoje devolve, decisão 99). Grupo com mesclagem própria sobre a cena (o grupo inteiro em tela, por exemplo) ainda não entra na conta do bloco. A caixa do elemento usa a caixa de tinta da camada, sem a máscara.

## M6: aprovação e entrega (`desdobra/entrega`)

Dono: frente de entrega do M6. Arquivos: `motor/desdobra/entrega/` (`__init__.py` com a CLI, `portao.py`, `codificar.py`, `aprovacao.py`, `parametros.py`, `validar.py` e `relatorio.py`), os esquemas `aprovacao-1.json` e `aprovacao-2.json`, `parametros-entrega-1.json`, `relatorio-entrega-1.json` e `manifesto-licenca-1.json`, as entradas `entrega.*` de `motor/fontes-de-limites.json` e os testes `testes/test_entrega*`.

### Arquivos do job

| Caminho | Contrato | Quem grava |
|---|---|---|
| `parametros/entrega.json` | `parametros-entrega/1` | `desdobra parametros-entrega`, pelo DA |
| `briefing/aprovacao.json` | `aprovacao/2` (lê a `aprovacao/1`) | `desdobra aprovar`, pelo DA |
| `entrega/previa/<formato>.<ext>` | arquivo final | `desdobra aprovar`, antes da pergunta, para o DA abrir |
| `entrega/aprovados/` | arquivos finais | `desdobra entregar`, pelo DA |
| `entrega/reprovados/` | arquivos finais com regra que reprova | `desdobra entregar`, pelo DA |
| `entrega/relatorio-entrega.json` | `relatorio-entrega/1` | `desdobra entregar`, pelo DA |
| `entrega/anteriores/<carimbo>/` | a entrega que saiu | `desdobra entregar` (troca) e o motor, quando uma entrada muda (`<carimbo>-invalidada/`) |
| `manifesto-licenca.json` (raiz do job) | `manifesto-licenca/1` | `desdobra entregar`, junto com a entrega |

O gancho PreToolUse nega a escrita de todos eles pelas ferramentas do Claude (os `.json` de `briefing/`, tudo em `entrega/`, `manifesto-licenca.json`, `relatorio-entrega.json` e `parametros/entrega.json`). Nada da entrega é apagado: a entrega que sai vai inteira para `entrega/anteriores/`. Nenhum desses arquivos entra no cabeçalho do briefing (`modelo.hashes_atuais`) nem nos padrões de fase, então gravar um deles não deixa briefing nem fase desatualizados (teste).

### Contratos

- `parametros-entrega/1`: `{esquema, formatos: {<id>: {rotacao_sentido?, condicao?, cor_de_achatamento?, borda_1px?}}}`. Cada campo é `{valor, confirmado_por}`, com `confirmado_por` do Disparo (meio `terminal`). `rotacao_sentido` é `horario` ou `anti_horario`, só em formato que o briefing gira 90 ou 270 graus (decisão 139); `condicao` é `hospedado`, `por_tag`, `tag_carga_inicial` ou `tag_carga_posterior`, e com teto condicional na folha confirmada só as condições dela (decisão 137); `cor_de_achatamento` é `#rrggbb` em minúsculas; `borda_1px` é booleano (sim: o fundo da peça é o da página).
- `aprovacao/2` (M7b, A2): `{esquema, job_id, formatos: {<id>: registro}}`. O registro leva `formato`, `job_id`, `impressao_formato`, `master_sha256`, `render_json_sha256`, `contrato_sha256`, `arquivo_entregue` (`sha256`, `bytes` e `extensao` do arquivo final), `parametros_encoder`, `aprovado_por` e `registro_sha256` (o selo do próprio registro). A `aprovacao/1` (com `briefing_sha256` no lugar da impressão) ainda lê (`aprovacao.ler`, `ESQUEMA_ANTIGO`): o portão conta cada registro dela como aprovação caída (`aprovacao_antiga`, "aprove o formato de novo"), e o `gravar` não a carrega para o arquivo novo. Mudar o que alimenta o formato (a impressão), o master, o render, o contrato, o arquivo final ou um parâmetro do encoder derruba a aprovação daquele formato (`aprovacao.diferencas` diz o campo). Os registros dos outros formatos ficam.
- `relatorio-entrega/1`: `esquema`, `job_id`, `gerado_em`, `carimbo`, `motor_versao`, `entregue_por`, `contagens` (`aprovados`, `reprovados`), `arquivos` (um por formato: `formato`, `nome`, `pasta`, `sha256`, `bytes`, `mime`, `largura`, `altura`, `extensao`, `parametros_encoder`, `medidas_encoder`, `verificacoes`, `regras`, `sugestoes`, `origem`, `aprovacao`, `mudou_desde_a_entrega_anterior`), `ambiente` (versões do encoder contra a build de referência e, por formato, as do render e o sha256 das fontes), `limites` (a citação de cada limite da entrega), `fontes_dos_campos`, `entrega_anterior`, `manifesto_sha256`, `resumo` e `relatorio_sha256`. O `resumo` traz `verificacoes` (`passou`, `avisou`, `so_registro`, `reprovou`), `aprovados_sem_aviso`, `avisos` e `registros` (contagem por regra). Sem texto de peça: só ids, hashes, contagens, códigos de regra e valores medidos. O relatório não é gravado com número sem fonte (`relatorio_com_numero_sem_fonte`).
- `manifesto-licenca/1`: `esquema`, `job_id`, `gerado_em`, `motor_versao`, `conferencia_fontes_sha256`, `responsabilidade` e `arquivos` (um por arquivo de `entrada/fontes/`: `nome`, `sha256`, `formato` e `faces`, com o nome PostScript e a versão da tabela name). Só registro, sem portão (decisão 19); fica na raiz do job, nunca em `entrega/aprovados`.

### Comandos

- `desdobra parametros-entrega --job <pasta> --formato <id> [--rotacao-sentido horario|anti_horario] [--condicao X] [--cor-de-achatamento #rrggbb] [--borda-1px sim|nao] [--limpar <campo> ...]`: só pelo DA (`humano.exigir('parametros-entrega')`). O `--limpar` aceita o nome do campo com hífen: `rotacao-sentido`, `condicao`, `cor-de-achatamento` ou `borda-1px`. Mostra o antes e o depois de cada campo e pede o sim digitado, sem resposta padrão; com o sim, confere de novo com a trava do job e grava. Recusa (código 3, `recusa_<motivo>`): `sem_briefing`, `briefing_invalido`, `formato_inexistente`, `rotacao_nao_decidida`, `rotacao_sem_quarto_de_volta`, `rotacao_sentido_divergente` (o briefing já diz o outro sentido), `condicao_fora_da_folha` (contam só os tetos confirmados com valor, como no encoder), `cor_invalida`, `parametros_de_entrega_invalidos` (o arquivo de agora não segue o contrato e não é sobrescrito), `gravacao_cancelada` e `mudou_durante_a_confirmacao`. Com o job ocupado por outro comando, sai com o código de job ocupado e não grava. Sem campo pedido, ou com o mesmo campo gravado e limpo, é um erro de uso (código 2). O mesmo valor de agora devolve `campos_mudados: 0` sem perguntar. Giro, achatamento e borda entram nos parâmetros do encoder, então mudar um deles derruba a aprovação do formato; a cor de achatamento só muda os bytes de master com transparência, e a condição só quando troca o teto que vale.
- `desdobra aprovar --job <pasta> --formato <id> [--formato <id> ...]`: só pelo DA. Confere cada formato pelo portão (sem a origem do briefing e sem a aprovação), gera o arquivo final (`codificar.arquivo_final`), grava a prévia em `entrega/previa/` e pede uma confirmação só, sem resposta padrão. Com o sim, confere tudo de novo com a trava e grava um registro por formato em `briefing/aprovacao.json`.
- `desdobra entregar --job <pasta>`: só pelo DA. Roda o portão inteiro em todos os formatos do briefing (`portao.conferir`: briefing de origem `da` com a conferência inteira, rotação decidida com o sentido nos 90 e 270 graus, master, render e contrato coerentes e do KV de agora, contrato refeito igual ao gravado e aprovação válida). Recusado, lista o código de cada formato e não grava nada. Com o portão aberto, valida cada arquivo final (`validar.validar`), mostra para onde vai cada formato e pede o sim digitado; com o sim, confere de novo com a trava e grava a entrega de uma vez (troca por `os.replace`, que volta inteira se um passo falha). O formato que o encoder recusa por decisão ou folha que falta (`validar.RECUSAS_ROTEADAS`) vai para reprovados com a regra e a sugestão, sem arquivo. Um arquivo aberto em outro programa recusa com `entrega_em_uso`, e a entrega anterior fica como estava. A saída termina com o resumo em português (`relatorio.linhas_do_resumo`): o que passou, o que avisou e o que ficou só como registro.
- `desdobra conferir-entrega --job <pasta>`: só lê e nunca pega a trava; roda sem o console do DA, o Claude inclusive, e o gancho não nega. Confere o relatório pelo selo, cada arquivo pelo sha256 e pelos bytes, que nada sobra em `aprovados/` e `reprovados/`, que nenhum arquivo com verificação que reprova está em `aprovados/`, que não há arquivo de fonte em `entrega/` e o manifesto da raiz contra o selo do relatório. Código 0 quando confere; código 3 com as contagens `divergem`, `faltam`, `sobram`, `reprovado_em_aprovados`, `aprovado_em_reprovados` e `arquivos_de_fonte` (e o motivo do relatório ou do manifesto, quando há) quando não confere.

`aprovar`, `entregar` e `parametros-entrega` estão em `humano.COMANDOS` e em `SUBCOMANDOS_HUMANOS` do gancho (teste de igualdade): recusam rodar com `--envelope`, sem console interativo ou em processo aberto pelo Claude, e o gancho também nega o código Python do motor que grava a aprovação, a entrega ou os parâmetros (`desdobra.entrega.aprovacao`, `validar`, `parametros` e os handlers).

O gancho confere só o texto do comando e o caminho do arquivo; o conteúdo de um script gravado antes e um caminho montado por partes ficam de fora. Ele barra o caminho direto e o engano. Um desvio feito de propósito passa: um comando que monta `parametros/entrega.json` por segmentos, que importa o motor com o nome partido ou que roda um `.py` gravado fora do job. `confirmado_por` é um dado do arquivo, sem segredo, e não prova quem gravou. Esse risco residual fica declarado aqui, junto com o do console.

### Validação final (`validar.validar`)

Cada verificação tem `nome`, `situacao` (`ok`, `reprova`, `avisa` ou `registra`), `regra`, `fonte` e `medidas`; a que reprova leva `sugestao`. Conferem: peso contra o teto estrito (leitura decimal, decisão 136; sem a condição, o teto mais estrito com `condicao_nao_decidida`), dimensão, tipo e extensão, alfa e perfil do arquivo (decisão 140), caminho de cor (os parâmetros de cor e a conversão do render são os do job agora, o job não pede perfil e o master não tem perfil embutido: `master_com_perfil_embutido`), parâmetros do arquivo contra as decisões de agora, o arquivo contra `transformar(master)` (PNG pelos pixels, JPEG pelo reencode), a borda de 1 px quando declarada e a área segura, a área útil e as faixas com tolerância de `entrega.tolerancia_area_px` (decisão 141). Um arquivo com alguma verificação que reprova vai para `entrega/reprovados`; os outros, para `entrega/aprovados` (`validar.destino`).

### Limites novos

Com fonte em `motor/fontes-de-limites.json`: `entrega.peso_reprova_acima_da_leitura_decimal`, `entrega.jpeg_qualidade_min`, `entrega.jpeg_qualidade_max`, `entrega.jpeg_qualidade_piso_aviso` (avisa), `entrega.jpeg_subamostragem`, `entrega.jpeg_progressivo`, `entrega.jpeg_optimize`, `entrega.jpeg_buffer_bytes`, `entrega.png_nivel_compressao`, `entrega.encoder_build_referencia` e `entrega.tolerancia_area_px`.
