# ORC — Orçamentos de Reparos Construtivos

Aplicativo desktop para elaboração de orçamentos de reparos de vícios construtivos, com base nos preços do **SINAPI** (Sistema Nacional de Preços e Índices da Construção Civil).

Desenvolvido em **Python** com interface **Tkinter**, voltado ao uso em perícias e laudos de vícios construtivos.

## Funcionalidades

### Hub principal

Tela inicial com acesso aos módulos:


| Módulo              | Status     | Descrição                                  |
| ------------------- | ---------- | ------------------------------------------ |
| **Área Privativa**  | Disponível | Orçamento de reparos em unidades autônomas |
| **Área Comum**      | Em breve   | Orçamento de reparos em áreas comuns       |
| **Consulta SINAPI** | Disponível | Pesquisa de composições e preços da base   |


### Área Privativa

- Cadastro de metragens por cômodo (piso, revestimento argamassado e cerâmico)
- Seleção de anomalias mapeadas em `vicios_construtivos.json`
- Cálculo automático de quantidades e valores com base nas composições SINAPI
- Agrupamento por tipo de reparo (pisos cerâmicos, azulejos, trincas, esquadrias, umidade, DR etc.)
- Aplicação de **BDI** e opção de **eventuais** (10%)
- Exportação do orçamento para **Excel** (.xlsx)

### Consulta SINAPI

- Busca por insumo ou composição com debounce
- Filtro por **estado** (UF) e **unidade** de medida
- Abre em tela cheia para facilitar a consulta

### Atualização automática da base SINAPI

Na inicialização, o app verifica no site da Caixa se há uma referência SINAPI mais recente. Os arquivos são baixados, processados e armazenados em `sinapi/sinapi_processado/`. Se o servidor estiver indisponível, utiliza a base local mais recente.

### Atualização do aplicativo

O app consulta o arquivo `[version.json](version.json)` no repositório GitHub e oferece download do instalador quando há uma versão mais nova.

## Requisitos

- **Windows** 10 ou superior
- **Python** 3.10+ (para desenvolvimento)
- Conexão com a internet (atualização SINAPI e verificação de versão do app)

## Instalação (usuário final)

Baixe o instalador mais recente na [página de releases](https://github.com/leosans-eng/orcamento-reparos-construtivos/releases) ou pelo link em `version.json`.

Execute `ORC_Instalador_X.Y.Z.exe` e siga o assistente. O app será instalado em `C:\ORC` por padrão.

## Estrutura do projeto

```
orcamento-reparos-construtivos/
├── app.py                     # Ponto de entrada e navegação entre módulos
├── app_paths.py               # Caminhos (dev vs. executável PyInstaller)
├── atualizacao.py             # Verificação de atualização do app via GitHub
├── vicios_construtivos.json   # Mapeamento anomalia → composições SINAPI
├── version.json               # Versão e link do instalador (publicado no GitHub)
├── core/
│   ├── app_state.py           # Estado global, callbacks SINAPI, rodapé
│   ├── sinapi_loader.py       # Carregamento e recarga da base SINAPI
│   └── sinapi_busca.py        # Pesquisa na base SINAPI
├── ui/
│   ├── hub.py                 # Tela inicial com cartões dos módulos
│   ├── area_privativa.py      # Módulo de orçamento (área privativa)
│   ├── consulta_sinapi.py     # Módulo de consulta SINAPI
│   └── widgets.py             # Componentes visuais reutilizáveis
├── sinapi/
│   ├── atualizador_sinapi.py  # Download e gestão de versões SINAPI
│   └── extrair_sinapi.py      # Processamento do arquivo de referência
├── setup/
│   ├── orc_installer.bat      # Script de build (PyInstaller + Inno Setup)
│   ├── orc_installer.iss      # Definição do instalador Windows
│   └── read_app_version.py    # Lê a versão de core/app_state.py
└── ORC.spec                   # Configuração PyInstaller
```

## Base SINAPI


| Pasta / arquivo             | Descrição                                            |
| --------------------------- | ---------------------------------------------------- |
| `sinapi/sinapi_referencia/` | Arquivos ZIP/CSV baixados da Caixa                   |
| `sinapi/sinapi_processado/` | CSVs processados prontos para uso                    |
| `sinapi/status.json`        | Status da última verificação (gerado em runtime)     |
| `sinapi_precos.csv`         | Fallback local na raiz (opcional, ignorado pelo git) |


A referência SINAPI em uso aparece no rodapé da interface (ex.: `03/2026`).

## Versão atual

**1.0.0** — definida em `core/app_state.py` e `version.json`.

## Autor

Léo Santos — [leosans-eng/orcamento-reparos-construtivos](https://github.com/leosans-eng/orcamento-reparos-construtivos)