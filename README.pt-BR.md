# Aspen Co-pilot

[English](README.md) · [繁體中文](README.zh-TW.md) · [简体中文](README.zh-CN.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [Español](README.es.md) · **Português** · [Deutsch](README.de.md) · [Français](README.fr.md) · [Русский](README.ru.md)

*Esta é uma tradução; se houver divergência, prevalece a [versão em inglês](README.md).*

**Deixe um agente de IA projetar, simular e otimizar processos químicos no seu próprio Aspen Plus,
enquanto você acompanha cada passo e mantém o controle.**

O Aspen Co-pilot conecta o Aspen Plus a agentes de IA como Claude Code e Codex por meio do
Model Context Protocol (MCP). Você descreve o processo em linguagem natural; o agente faz o
trabalho no Aspen, e você revisa.

Somente Windows. Você precisa ter sua própria licença do Aspen Plus; este projeto não a inclui.
Desenvolvido pelo NCKU GESE Lab.

## O que ele faz

**Construir e alterar processos.** Crie um fluxograma a partir de uma descrição — componentes, métodos
de propriedades, reações, operações unitárias e correntes —, defina e ajuste qualquer parâmetro, rode a
simulação e leia os resultados. A maioria das funções do Aspen Plus está disponível.

**Da literatura a um modelo que funciona.** Com as ferramentas de pesquisa do seu cliente de IA, o agente pode
reunir cinética, condições de operação e rotas de processo de artigos e patentes e, em seguida,
transformá-las em um modelo do Aspen que você pode conferir com as fontes.

**Descobrir por que uma simulação falha.** Ele verifica o que ainda falta ao Aspen antes de rodar, explica simulações
com falha e avisos, e os corrige. As correções que funcionaram ficam salvas na sua máquina para a próxima vez.

**Otimizar o processo.** Nove algoritmos em uma única ferramenta — NSGA-II, NSGA-III, PSO, DE/GDE3,
gradiente (SLSQP), busca em grade e três métodos bayesianos (BO, CBO, AFM-CBO) — para problemas mono ou
multiobjetivo com restrições, além de análise pinch e sugestões de pareamento de trocadores de calor
para integração energética.

**Consultar em vez de adivinhar.** Uma referência para cada bloco, corrente e configuração
([aspen-mcp/docs](aspen-mcp/docs/aspen.md)) que o agente consulta antes de alterar um campo.

## Feito para trabalhar com pessoas

É difícil confiar em um agente LLM que opera software sozinho: você não vê o que ele
mudou nem por quê, nem consegue barrar um erro antes que ele chegue ao modelo. O Aspen Co-pilot resolve isso
com o **Aspen Workbench**, uma janela de desktop ao lado do Aspen Plus.

- **Veja o que a IA faz.** O fluxograma, os resultados e cada alteração feita pela IA, com o
  motivo, são atualizados ao vivo. Desfaça qualquer alteração ou volte a um ponto de restauração.
- **Mantenha o controle.** No modo de revisão, as alterações da IA aguardam sua aprovação; alterações maiores
  chegam como propostas que só você pode executar.
- **Defina você mesmo o trabalho com programas de blocos.** Monte varreduras de parâmetros, cálculos,
  tabelas, gráficos e estudos de otimização — com suas próprias variáveis, objetivos e restrições —
  a partir de blocos de arrastar e soltar, sem código. A IA pode escrever um programa para você editar, ou rodar
  o seu.
- **Trabalhem juntos.** Clique em qualquer corrente ou bloco e use **Ask AI** para perguntar sobre ele. No modo de aprendizado, a IA
  explica o princípio de processo por trás de cada alteração.

O workbench tem interface em inglês e em chinês (não em português) e também funciona sem um cliente de IA
(`%USERPROFILE%\.aspen-mcp\aspen-workbench.cmd`: sem rede, sem tokens).

## Instalação

Você precisa de **Windows**, uma licença do **Aspen Plus** e do **[uv](https://docs.astral.sh/uv/)**
(`winget install --id=astral-sh.uv -e`; ele traz o próprio Python).

**Claude Code:**

```bash
claude plugin marketplace add nckugese/Aspen_Co-pilot
claude plugin install aspen-plus@aspen-mcp
```

**Codex:** `codex plugin marketplace add nckugese/Aspen_Co-pilot`, depois ative o **Aspen Plus** em
`/plugins` e confie nos hooks dele em `/hooks`.

Em seguida, reinicie o cliente. Na primeira sessão ele oferece concluir a configuração (cerca de 200 MB: Python,
o servidor e as bibliotecas do otimizador); aceite e reinicie mais uma vez. `/aspen-doctor`
verifica o resultado.

O plugin fixa uma versão, então nada muda até você atualizá-lo
(`claude plugin update aspen-plus@aspen-mcp`); ele avisa quando existe uma versão mais nova.

Outros clientes MCP (Claude Desktop, Gemini CLI, Codex sem o plugin), a versão passo a passo
com verificações e a solução de problemas: **[INSTALL.md](INSTALL.md)** (em inglês).

## Privacidade

Tudo o que o servidor guarda fica na sua máquina, em `~/.aspen-mcp/`: o log, o histórico
de alterações, os pontos de restauração (cópias dos seus modelos) e o seu histórico de erros. Este projeto nunca envia
seus modelos, resultados ou conversas para lugar nenhum. Os únicos acessos à rede são:

- a verificação de atualizações do plugin, no máximo uma vez por dia (`git ls-remote` contra este repositório);
- a primeira chamada a `pinch_analysis`, que baixa o Python 3.14 e o OpenPinch via uv;
- a instalação e a atualização, que baixam o servidor e suas dependências via uv.

O que o seu cliente de IA envia ao próprio provedor é regido por esse cliente.

## Feedback

Dúvidas e relatos de bugs: [GitHub Issues](https://github.com/nckugese/Aspen_Co-pilot/issues). Relatos de segurança: [SECURITY.md](SECURITY.md) (em inglês).

## Licença

MIT — veja [LICENSE](LICENSE). Copyright (c) 2026 NCKU GESE Lab.

Se você usar este software em trabalhos acadêmicos, cite este repositório.

## Aviso legal

Aspen Plus® e AspenTech® são marcas comerciais da Aspen Technology, Inc. Este projeto é uma
integração independente e não oficial, e não é afiliado, endossado nem patrocinado
pela Aspen Technology, Inc. Ele não inclui nem distribui o Aspen Plus; ele controla uma
instalação separada, fornecida pelo usuário, e você precisa ter sua própria licença válida do Aspen Plus.
