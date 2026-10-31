# desdobra

Plugin do Claude Code que desdobra peças de mídia estática (OOH, DOOH e banner digital em JPG ou PNG) a partir do PSD do KV. O motor em Python faz toda a leitura e todo o cálculo, e roda também sem o Claude, pela linha de comando. O diretor de arte confirma cada decisão.

Repositório privado da Trezion. A raiz é o marketplace, e o plugin fica em `plugins/desdobra`.

## Instalação

No Claude Code 2.1.275 ou mais novo, numa sessão Local, com a credencial do GitHub já guardada no git:

```
/plugin marketplace add https://github.com/egrandelle/desdobra.git
/plugin install desdobra@desdobra
```

O passo a passo completo, com o que conferir depois, está em `docs/instalacao-teste.md`.

## Linha de comando do motor

```
desdobra job criar <pasta> --kv <arquivo.psd> --modo-dados {a,b,c} [--fontes <arquivos ou pasta>] [--licencas <arquivo.json>]
desdobra job proxima <pasta>
desdobra ler <arquivo.psd> --saida <pasta>
desdobra fontes conferir --job <pasta>
desdobra fontes laudo --job <pasta>
desdobra regressao --corpus <pasta> --linha-de-base <pasta> --saida <pasta>
desdobra doctor
```

Com `--envelope` antes do subcomando, o motor imprime só uma linha JSON (contrato `envelope/1`), filtrada pelo modo de dados do job e pelo detector de segredos. É assim que as skills chamam o motor.

## Pastas

| Pasta | Conteúdo |
|---|---|
| `.claude-plugin/marketplace.json` | O marketplace, com o plugin `desdobra` |
| `plugins/desdobra/motor` | O motor Python (pacote `desdobra`), os esquemas dos contratos, o registro de limites e os locks |
| `plugins/desdobra/skills`, `hooks`, `tela` | Skills, gancho de início de sessão e tela de briefing local |
| `plugins/desdobra/biblioteca-specs` | Perfis públicos de veículo |
| `plugins/desdobra/testes` | Testes, só com material sintético gerado na hora |
| `dev/` | Ferramentas só de desenvolvimento |
| `docs/` | Documentação técnica, com o contrato entre as partes em `docs/m1-interfaces.md` |

## Desenvolvimento

```
python -m venv .venv
.venv/Scripts/python.exe -m pip install --require-hashes --no-deps --only-binary=:all: -r plugins/desdobra/motor/requirements-dev.lock
.venv/Scripts/python.exe -m pip install --no-deps --no-build-isolation -e plugins/desdobra/motor
.venv/Scripts/python.exe -m pytest plugins/desdobra/testes
```

Regras do repositório: nada de material de cliente (PSD, imagem, nome de camada, texto de peça, nome de marca), nada de arquivo de fonte e nada de segredo. Os testes geram os PSDs e as fontes sintéticas na hora. As fontes de um job entram só por `--fontes`, ficam em `entrada/fontes/` da pasta do job e nunca vão para o repositório.

Dois testes dependem de material que fica fora do repositório e só rodam quando a variável de ambiente aponta para ele:
- `DESDOBRA_PALAVRAS_PROIBIDAS`: arquivo com as palavras que nunca podem aparecer no repositório (nomes de cliente, marca e fonte do material de teste), uma por linha; a linha que começa com `sigla:` conta só em maiúsculas e como palavra inteira. A lista nunca entra no repositório, nem codificada;
- `DESDOBRA_LINHA_DE_BASE`: pasta com a linha de base da regressão.
