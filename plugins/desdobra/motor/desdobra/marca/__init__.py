# -*- coding: utf-8 -*-
"""Marca e perfil de marca (M7c; arquitetura-v1.md, 4.14 e 5.7; decisoes-v1.md, 190).

  - perfil.py: o perfil de marca da biblioteca da agencia, <biblioteca>/marcas/<id>/perfil-marca.json
    (perfil-marca/1), com versao e historico.

Gravar no perfil e ato so do DA, pelo registro do padrao da marca na tela (passo M5). O gancho do plugin nega ao Claude
a leitura e a escrita em <biblioteca>/marcas/ e o codigo que chama desdobra.marca.perfil ou desdobra.marca.registrar.
"""
