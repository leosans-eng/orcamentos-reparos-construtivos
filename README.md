# ORC — Orçamentos de Reparos Construtivos

Aplicativo desktop para elaboração de orçamentos de reparos de vícios construtivos, com base nos preços do **SINAPI** (Sistema Nacional de Preços e Índices da Construção Civil).

Desenvolvido em **Python** com interface **Tkinter**, voltado ao uso em perícias e laudos de vícios construtivos.

**Versão atual: 1.2.0**

## Funcionalidades

### Hub principal

Tela inicial com acesso aos módulos:

| Módulo | Status | Descrição |
|--------|--------|-----------|
| **Área Privativa** | Disponível | Orçamento de reparos em unidades autônomas |
| **Área Comum** | Em breve | Orçamento de reparos em áreas comuns |
| **Consulta SINAPI** | Disponível | Pesquisa de composições e preços da base |
| **Orçamento Customizado** | Disponível | Montagem livre do orçamento com etapas e itens |
| **Composições Próprias** | Disponível | Cadastro de composições com insumos SINAPI ou de mercado |
| **Etapas pré-definidas** | Disponível | Modelos de etapas com itens SINAPI e composições próprias |

### Área Privativa

- Cadastro de metragens por cômodo (piso, revestimento argamassado e cerâmico)
- Seleção de anomalias mapeadas em `vicios_construtivos.json`
- Cálculo automático de quantidades e valores com base nas composições SINAPI
- Agrupamento por tipo de reparo (pisos cerâmicos, azulejos, trincas, esquadrias, umidade, DR etc.)
- Aplicação de **BDI** e opção de **eventuais** (10%)
- Exportação do orçamento para **Excel** (.xlsx)

### Orçamento Customizado

- Múltiplos orçamentos salvos localmente (criar, renomear, excluir e alternar entre eles)
- Estrutura em **etapas** (grupos) com itens **SINAPI** ou **composições próprias**
- Inserção por busca, por código rápido, a partir do catálogo de composições ou de **etapas pré-definidas**
- Reordenação de etapas e itens; edição de quantidades e custos
- **BDI** configurável e seleção de **estado** de referência para preços
- **Importação** de planilhas sintéticas exportadas pelo sistema **i9**
- **Exportação** para Excel em quatro modelos:
  - **Atualização** (+ documento Word)
  - **Enviar ao Perito** (planilha com fórmulas)
  - **Parecer Inicial** (+ documento Word)
  - **Orçamentos Customizados** (layout dedicado)

### Composições Próprias

- Catálogo persistente de composições com código, nome, unidade e custo estimado
- Componentes vindos da base **SINAPI** ou cadastrados como **mercado** (preço manual)
- Prévia de custo por estado (UF) selecionado
- Composições cadastradas ficam disponíveis no módulo **Orçamento Customizado**

### Etapas pré-definidas

- Cadastro de modelos de etapa com itens **SINAPI** e **composições próprias** já incluídos
- Modelos reutilizáveis no **Orçamento Customizado** (inserção rápida de etapas completas)
- Persistência local junto aos demais dados do usuário

### Consulta SINAPI

- Busca por insumo ou composição com debounce
- Filtro por **estado** (UF) e **unidade** de medida
- Abre em tela cheia para facilitar a consulta

### Atualização automática da base SINAPI

Na inicialização, o app verifica no site da Caixa se há uma referência SINAPI mais recente. Os arquivos são baixados, processados e armazenados em `sinapi/sinapi_processado/`. Se o servidor estiver indisponível, utiliza a base local mais recente.

### Atualização do aplicativo

O app consulta o arquivo [`version.json`](version.json) no repositório GitHub e oferece download do instalador quando há uma versão mais nova.

### Configurações

No hub, o botão **Configurações** abre um diálogo para **reverificar a base SINAPI** manualmente e acompanhar o status do servidor (HTTP e situação da última consulta).

### API compartilhada

Composições próprias, etapas pré-definidas e orçamentos customizados usam **API FastAPI + PostgreSQL**.

O backend autossuficiente (o que a TI sobe no servidor) está em [`api/`](api/) — ver [`api/README.md`](api/README.md) e [`api/MENSAGEM-TI.md`](api/MENSAGEM-TI.md).

```bat
cd api
copy .env.example .env
run_dev.bat
```

No desktop ORC, informe a URL `http://IP_DO_SERVIDOR:8000` na tela de login.

## Requisitos

- **Windows** 10 ou superior
- **Python** 3.10+ (para desenvolvimento)
- Conexão com a internet (atualização SINAPI e verificação de versão do app)

## Instalação (usuário final)

Baixe o instalador mais recente na [página de releases](https://github.com/leosans-eng/orcamento-reparos-construtivos/releases) ou pelo link em `version.json`.

Execute `ORC_Instalador_1.2.0.exe` (ou o instalador indicado em `version.json`) e siga o assistente. O app será instalado em `C:\ORC` por padrão.

## Desenvolvimento

### 1. Clonar o repositório

```bash
git clone https://github.com/leosans-eng/orcamento-reparos-construtivos.git
cd orcamento-reparos-construtivos
```

### 2. Criar ambiente virtual e instalar dependências

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Executar em modo desenvolvimento

```bash
python app.py
```

> **Nota:** na primeira execução, o app tentará baixar a base SINAPI. Se não houver conexão, coloque manualmente um CSV processado em `sinapi/sinapi_processado/` ou um arquivo `sinapi_precos.csv` na raiz do projeto como fallback. Para pular a verificação de atualização do app durante o desenvolvimento: `$env:SKIP_UPDATE_CHECK = "1"`. Para pular a verificação de atualização do app durante o desenvolvimento: `$env:SKIP_UPDATE_CHECK = "1"`.

## Dados do usuário

Orçamentos customizados, composições próprias e etapas pré-definidas são gravados fora do pacote de instalação:

| Ambiente | Pasta |
|----------|-------|
| Instalador (produção) | `%LOCALAPPDATA%\ORC\` |
| Desenvolvimento | `dados_usuario/` |

| Arquivo | Conteúdo |
|---------|----------|
| `orcamentos_customizados.json` | Orçamentos salvos do módulo customizado |
| `composicoes_proprias.json` | Catálogo de composições próprias |
| `etapas_predefinidas.json` | Modelos de etapas pré-definidas |

## Estrutura do projeto

```
orcamento-reparos-construtivos/
├── app.py                          # Ponto de entrada e navegação entre módulos
├── app_paths.py                    # Caminhos (dev, executável e dados do usuário)
├── atualizacao.py                  # Verificação de atualização do app via GitHub
├── vicios_construtivos.json        # Mapeamento anomalia → composições SINAPI
├── version.json                    # Versão e link do instalador (publicado no GitHub)
├── assets/                         # Ícones e modelos de planilha/Word para exportação
├── core/
│   ├── app_state.py                # Estado global, APP_VERSION, callbacks SINAPI, rodapé
│   ├── sinapi_loader.py            # Carregamento e recarga da base SINAPI
│   ├── sinapi_busca.py             # Pesquisa na base SINAPI
│   ├── orcamento_customizado.py    # Modelo de dados do orçamento customizado
│   ├── orcamento_storage.py        # Persistência dos orçamentos salvos
│   ├── composicoes_proprias.py     # Modelo de composições e componentes
│   ├── composicoes_proprias_storage.py
│   ├── etapas_predefinidas.py      # Modelo de etapas pré-definidas
│   ├── etapas_predefinidas_storage.py
│   ├── exportacao_planilha_orcamento.py
│   ├── importacao_i9.py            # Importação de planilhas do sistema i9
│   ├── planilha_sintetica.py
│   └── formatador_sinapi/          # Formatação dos modelos de exportação (1–4)
├── docs/
│   └── SISTEMA-ATUALIZACAO.md      # Documentação técnica do atualizador
├── ui/
│   ├── hub.py                      # Tela inicial com cartões dos módulos
│   ├── area_privativa.py           # Módulo de orçamento (área privativa)
│   ├── orcamento_customizado.py    # Módulo de orçamento livre
│   ├── composicoes_proprias.py     # Cadastro de composições próprias
│   ├── etapas_predefinidas.py      # Cadastro de etapas pré-definidas
│   ├── consulta_sinapi.py          # Módulo de consulta SINAPI
│   ├── dialogo_configuracoes.py    # Diálogo de configurações (SINAPI)
│   ├── grade_orcamento.py          # Grade hierárquica etapas/itens
│   ├── icones.py                   # Ícones SVG (tksvg) para botões e cartões
│   ├── dialogo_importar_i9.py
│   ├── dialogo_selecionar_modelo_planilha.py
│   └── widgets.py                  # Componentes visuais reutilizáveis
├── sinapi/
│   ├── atualizador_sinapi.py       # Download e gestão de versões SINAPI
│   └── extrair_sinapi.py           # Processamento do arquivo de referência
└── setup/
    ├── create_exe.bat              # Gera dist\ORC\ORC.exe (PyInstaller)
    ├── orc_installer.bat           # create_exe.bat + Inno Setup
    ├── orc_installer.iss           # Definição do instalador Windows
    └── read_app_version.py         # Lê a versão de core/app_state.py
```

## Gerar executável e instalador

Pré-requisitos adicionais:

- [Inno Setup 6](https://jrsoftware.org/isinfo.php)

Com o ambiente virtual ativo:

```bash
setup\orc_installer.bat
```

Saídas:

- `dist\ORC\ORC.exe` — executável portátil
- `setup\output\ORC_Instalador_1.1.0.exe` — instalador Windows

Após publicar uma nova versão, atualize `version.json` no GitHub com a versão e o link do instalador correspondente.

## Base SINAPI

| Pasta / arquivo | Descrição |
|-----------------|-----------|
| `sinapi/sinapi_referencia/` | Arquivos ZIP/CSV baixados da Caixa |
| `sinapi/sinapi_processado/` | CSVs processados prontos para uso |
| `sinapi/status.json` | Status da última verificação (gerado em runtime) |
| `sinapi_precos.csv` | Fallback local na raiz (opcional, ignorado pelo git) |

A referência SINAPI em uso aparece no rodapé da interface (ex.: `03/2026`).

## Novidades da versão 1.2.0

- Corrigido bug onde os valores de uma planilha importada do i9 não eram atualizados automaticamente até que o Estado fosse trocado. Agora, assim que a planilha é importada, a atualização já é feita automaticamente.
- Composições próprias deprecadas agora são mantidas ao importar do i9, para facilitar a edição do item e manter seu quantitativo. O aviso pop-up ainda aparece.
- Correção de vírgulas em separadores de milhares para números com casas decimais (Diversos ajustes para evitar possíveis erros futuros).
- Botões 'Editar item' e 'Editar nome da etapa' foram removidos, pois agora é possível dar duas cliques em um item ou etapa para abrir a caixa de edição.
- Cores na tabela de Orçamento Customizado ajustadas para maiores contrastes.
- Correção de orçamentos gerados pularem as linhas vazias (Etapas sem itens). São etapas que devem aparecer normalmente na tabela gerada com "A ORÇAR" escrito no lugar do valor. - Correção de Modelos 1 e 3 não seguirem o número da Estrutura do orçamento, sempre começava com 0.
- Novo botão 'Trocar ordem da etapa'.
- Ajustes na interface de 'Nova composição' para facilitar a inserção de dados.
- A prévia de custos na configuração de composições próprias agora é, por padrão, SP. Mantém o estado usado por último pelo usuário.
- Ao editar um item para sua substituição em 'Orçamento Customizado', aparecerá um rodapé de comparação entre o antigo e o novo, para facilitar a diferenciação.
- Corrigido bug visual de 'flash' na tela antes de abrir alguma caixa de preenchimento ou janela de busca da SINAPI.
- Nova função de configurar etapas pré-definidas que já vem com itens da SINAPI. Pode ser acessada pelo Hub.
- 3 botões de reordenar etapas removidos. Agora essa ação pode ser feita ao dar um duplo clique no número do item.
- Acrescenta diversos ícones para facilitar a identificação das opções e criar memória muscular.
- "Inserir itens" agora fica no centro da tela.
- Criado menu de Configurações. Atualmente, a única opção é a de verificar novamente alguma atualização da SINAPI, essencial para momentos de instabilidade do servidor da Caixa.

## Autor

Léo Santos — [leosans-eng/orcamento-reparos-construtivos](https://github.com/leosans-eng/orcamento-reparos-construtivos)
