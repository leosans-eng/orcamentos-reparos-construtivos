# ORC — Orçamentos de Reparos Construtivos

Aplicativo desktop para elaboração de orçamentos de reparos de vícios construtivos, com base nos preços do **SINAPI** (Sistema Nacional de Preços e Índices da Construção Civil).

Desenvolvido em **Python** com interface **Tkinter**, voltado ao uso em perícias e laudos de vícios construtivos.

**Versão atual: 1.4.0**

## Destaques da 1.4.0

- **UF por item**: é possível alterar o estado de um único item SINAPI, permitindo usá-lo com preço de qualquer UF
- **Substituição automática** de itens que existem em um estado e não em outro, ao trocar a UF de referência
- **Etapa modelo** com filtro por digitação na barra de seleção
- **Busca por código SINAPI** ordenada por relevância (código exato → prefixo → substring)
- **Expressões nos quantitativos**, para contas rápidas direto no campo de quantidade
- **Calculadora** no Orçamento Customizado
- **Edição inline** do nome das etapas (sem janela pop-up)

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

- Múltiplos orçamentos salvos no **banco compartilhado** (criar, renomear, excluir e alternar entre eles)
- Estrutura em **etapas** (grupos) com itens **SINAPI** ou **composições próprias**
- Inserção por busca, por código rápido, a partir do catálogo de composições ou de **etapas pré-definidas** (com filtro por digitação)
- Busca SINAPI por código com ordenação por relevância (exato, prefixo, substring)
- Reordenação de etapas e itens; edição de quantidades (com **expressões**) e custos
- Edição do nome da etapa **no local** (sem pop-up)
- **UF por item** e **substituição automática** ao trocar o estado de referência
- **Calculadora** integrada ao módulo
- **BDI** configurável e seleção de **estado** de referência para preços
- **Importação** de planilhas sintéticas exportadas pelo sistema **i9**
- **Exportação** para Excel em quatro modelos:
  - **Atualização** (+ documento Word)
  - **Enviar ao Perito** (planilha com fórmulas)
  - **Parecer Inicial** (+ documento Word)
  - **Orçamentos Customizados** (layout dedicado)

### Composições Próprias

- Catálogo compartilhado de composições com código, nome, unidade e custo estimado
- Componentes vindos da base **SINAPI** ou cadastrados como **mercado** (preço manual)
- Prévia de custo por estado (UF) selecionado
- Composições cadastradas ficam disponíveis no módulo **Orçamento Customizado** em qualquer máquina conectada à mesma API

### Etapas pré-definidas

- Cadastro de modelos de etapa com itens **SINAPI** e **composições próprias** já incluídos
- Modelos reutilizáveis no **Orçamento Customizado** (inserção rápida de etapas completas)
- Persistência no **banco compartilhado**, visível para todos os usuários do servidor

### Consulta SINAPI

- Busca por insumo ou composição com debounce
- Filtro por **estado** (UF) e **unidade** de medida
- Abre em tela cheia para facilitar a consulta

### Atualização automática da base SINAPI

Na inicialização, o app verifica no site da Caixa se há uma referência SINAPI mais recente. Os arquivos são baixados, processados e armazenados em `sinapi/sinapi_processado/` (no PC local). Se o servidor estiver indisponível, utiliza a base local mais recente.

### Atualização do aplicativo

O app consulta o arquivo [`version.json`](version.json) no repositório GitHub e oferece download do instalador quando há uma versão mais nova. A verificação pode ocorrer já na **tela de login**, sem necessidade de autenticar.

### Configurações

No hub, o botão **Configurações** abre um diálogo para **reverificar a base SINAPI** manualmente e acompanhar o status do servidor (HTTP e situação da última consulta).

### API e banco compartilhados

A partir da **1.3.0**, composições próprias, etapas pré-definidas e orçamentos customizados não ficam mais apenas em arquivos JSON locais: são lidos e gravados por meio de uma **API FastAPI** com **PostgreSQL** (ou banco configurado no servidor).

Assim, qualquer computador com o ORC instalado e autenticado na mesma URL de API enxerga e atualiza o **mesmo conjunto de dados**.

## Requisitos

- **Windows** 10 ou superior
- **Python** 3.10+ (para desenvolvimento)
- Conexão com a internet (atualização SINAPI, conexão com a API e verificação de versão do app)

## Instalação (usuário final)

1. Baixe o instalador mais recente na [página de releases](https://github.com/leosans-eng/orcamento-reparos-construtivos/releases) ou pelo link em `version.json`.
2. Execute `ORC_Instalador_1.4.0.exe` (ou o instalador indicado em `version.json`) e siga o assistente. O app será instalado em `C:\ORC` por padrão.
3. Abra o ORC e faça **login** com seu usuário.

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

## Dados: o que é compartilhado e o que fica no PC

| Tipo de dado | Onde fica | Compartilhado? |
|--------------|-----------|----------------|
| Orçamentos customizados | Banco via API | Sim |
| Composições próprias | Banco via API | Sim |
| Etapas pré-definidas | Banco via API | Sim |
| Base SINAPI processada | `sinapi/` na pasta do programa | Não (por máquina) |
| Preferências de login (URL / usuário / senha salvos) | Configuração local do desktop | Não (por máquina) |

Arquivos JSON em `%LOCALAPPDATA%\ORC\` ou `dados_usuario/` podem existir no **modo offline** / legado de testes; no fluxo normal com login, a fonte da verdade é o **banco no servidor**.

## Estrutura do projeto

```
orcamento-reparos-construtivos/
├── app.py                          # Ponto de entrada, login e navegação
├── app_offline.py                  # Modo offline (testes, sem API)
├── app_paths.py                    # Caminhos (dev, executável e dados locais)
├── atualizacao.py                  # Verificação de atualização do app via GitHub
├── vicios_construtivos.json        # Mapeamento anomalia → composições SINAPI
├── version.json                    # Versão e link do instalador (publicado no GitHub)
├── assets/                         # Ícones e modelos de planilha/Word para exportação
├── api/                            # Backend FastAPI + banco (dados compartilhados)
├── core/
│   ├── app_state.py                # Estado global, APP_VERSION, callbacks SINAPI
│   ├── api_client.py               # Cliente HTTP da API / autenticação
│   ├── sinapi_loader.py            # Carregamento e recarga da base SINAPI
│   ├── sinapi_busca.py             # Pesquisa na base SINAPI
│   ├── orcamento_customizado.py    # Modelo de dados do orçamento customizado
│   ├── orcamento_storage.py        # Persistência dos orçamentos (API)
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
│   ├── dialogo_login.py            # Tela de login (URL, usuário, senha)
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
- `setup\output\ORC_Instalador_1.4.0.exe` — instalador Windows

Após publicar uma nova versão, atualize `version.json` no GitHub com a versão e o link do instalador correspondente.

## Base SINAPI

| Pasta / arquivo | Descrição |
|-----------------|-----------|
| `sinapi/sinapi_referencia/` | Arquivos ZIP/CSV baixados da Caixa |
| `sinapi/sinapi_processado/` | CSVs processados prontos para uso |
| `sinapi/status.json` | Status da última verificação (gerado em runtime) |
| `sinapi_precos.csv` | Fallback local na raiz (opcional, ignorado pelo git) |

A referência SINAPI em uso aparece no rodapé da interface (ex.: `05/2026`).

## Histórico de versões

### 1.4.0

- É possível alterar a **UF de um único item**, para permitir que um item da SINAPI seja utilizado em qualquer estado
- **Substituição automática** de itens que existem em um estado, mas não em outro
- Melhorias na barra de seleção de **Etapa Modelo**, permitindo digitar para filtrar
- Melhoria na busca de item SINAPI por código: ordenação por relevância (código exato → prefixo → substring). Exemplo: ao buscar `142`, o item `142` aparece no topo
- Função de **expressões nos quantitativos**, para contas rápidas no campo de quantidade
- **Calculadora** no Orçamento Customizado
- Removida a janela pop-up para troca de nome de etapas; a edição passa a ser feita **no local**

### 1.3.0

- **Tela de login** com URL da API, usuário e senha (opção de salvar credenciais neste computador)
- **Armazenamento compartilhado** em banco de dados via API: orçamentos customizados, composições próprias e etapas pré-definidas passam a ser comuns a todos os PCs que acessam o mesmo servidor
- **Logout** no hub para encerrar a sessão e autenticar outro usuário

### 1.2.0

- Corrigido bug onde os valores de uma planilha importada do i9 não eram atualizados automaticamente até que o Estado fosse trocado. Agora, assim que a planilha é importada, a atualização já é feita automaticamente.
- Composições próprias deprecadas agora são mantidas ao importar do i9, para facilitar a edição do item e manter seu quantitativo. O aviso pop-up ainda aparece.
- Correção de vírgulas em separadores de milhares para números com casas decimais (diversos ajustes para evitar possíveis erros futuros).
- Botões 'Editar item' e 'Editar nome da etapa' foram removidos, pois agora é possível dar dois cliques em um item ou etapa para abrir a caixa de edição.
- Cores na tabela de Orçamento Customizado ajustadas para maiores contrastes.
- Correção de orçamentos gerados pularem as linhas vazias (etapas sem itens). São etapas que devem aparecer normalmente na tabela gerada com "A ORÇAR" escrito no lugar do valor. 
- Correção de Modelos 1 e 3 não seguirem o número da estrutura do orçamento (sempre começava com 0).
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
