# Aspen Co-pilot

[English](README.md) · [繁體中文](README.zh-TW.md) · [简体中文](README.zh-CN.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · **Español** · [Português](README.pt-BR.md) · [Deutsch](README.de.md) · [Français](README.fr.md) · [Русский](README.ru.md)

*Esta es una traducción; si difiere de la [versión en inglés](README.md), prevalece esta última.*

**Deje que un agente de IA diseñe, simule y optimice procesos químicos en su propio Aspen Plus,
mientras usted ve cada paso y conserva el control.**

Aspen Co-pilot conecta Aspen Plus con agentes de IA como Claude Code y Codex mediante el
Model Context Protocol (MCP). Usted describe el proceso en lenguaje natural; el agente hace el
trabajo en Aspen y usted lo revisa.

Solo para Windows. Necesita su propia licencia de Aspen Plus; este proyecto no la incluye.
Desarrollado por NCKU GESE Lab.

## Qué puede hacer

**Construir y modificar procesos.** Cree un diagrama de flujo (flowsheet) a partir de una descripción —componentes,
métodos de propiedades, reacciones, operaciones unitarias y corrientes—, defina y ajuste cualquier parámetro, ejecute la
simulación y lea los resultados. La mayoría de las funciones de Aspen Plus están disponibles.

**Pasar de la literatura a un modelo que funciona.** Con las herramientas de investigación de su cliente de IA, el agente puede
recopilar cinética, condiciones de operación y rutas de proceso de artículos y patentes, y luego
convertirlas en un modelo de Aspen que usted puede contrastar con las fuentes.

**Averiguar por qué falla una simulación.** Revisa qué le falta a Aspen antes de ejecutar, explica las ejecuciones
fallidas y las advertencias, y las corrige. Las correcciones que funcionaron se guardan en su equipo para la próxima vez.

**Optimizar el proceso.** Nueve algoritmos en una sola herramienta —NSGA-II, NSGA-III, PSO, DE/GDE3,
gradiente (SLSQP), búsqueda en malla y tres métodos bayesianos (BO, CBO, AFM-CBO)— para problemas mono- o
multiobjetivo con restricciones, además de análisis pinch y sugerencias de emparejamiento de intercambiadores de calor
para la integración energética.

**Consultar en lugar de adivinar.** Una referencia para cada bloque, corriente y ajuste
([aspen-mcp/docs](aspen-mcp/docs/aspen.md)) que el agente consulta antes de cambiar un campo.

## Hecho para trabajar con personas

Es difícil confiar en un agente LLM que opera software por su cuenta: no se ve qué
cambió ni por qué, ni se puede detener un error antes de que llegue al modelo. Aspen Co-pilot cierra esa brecha
con el **Aspen Workbench**, una ventana de escritorio junto a Aspen Plus.

- **Vea lo que hace la IA.** El diagrama de flujo, los resultados y cada cambio que hizo la IA, con su
  motivo, se actualizan en vivo. Deshaga cualquier cambio o vuelva a un punto de restauración.
- **Mantenga el control.** En el modo de revisión, los cambios de la IA esperan su aprobación; los cambios mayores
  llegan como propuestas que solo usted puede ejecutar.
- **Defina el trabajo usted mismo con programas de bloques.** Arme barridos de parámetros, cálculos,
  tablas, gráficos y estudios de optimización —con sus propias variables, objetivos y restricciones—
  a partir de bloques que se arrastran y sueltan, sin código. La IA puede escribirle un programa para que lo edite, o ejecutar
  el suyo.
- **Trabajen juntos.** Haga clic en cualquier corriente o bloque y use **Ask AI** para preguntar sobre él. En el modo de aprendizaje, la IA
  explica el principio de proceso detrás de cada cambio.

El workbench tiene interfaz en inglés y en chino (no en español), y también funciona sin un cliente de IA
(`%USERPROFILE%\.aspen-mcp\aspen-workbench.cmd`: sin red, sin tokens).

## Instalación

Necesita **Windows**, una licencia de **Aspen Plus** y **[uv](https://docs.astral.sh/uv/)**
(`winget install --id=astral-sh.uv -e`; trae su propio Python).

**Claude Code:**

```bash
claude plugin marketplace add nckugese/Aspen_Co-pilot
claude plugin install aspen-plus@aspen-mcp
```

**Codex:** `codex plugin marketplace add nckugese/Aspen_Co-pilot`, luego habilite **Aspen Plus** en
`/plugins` y confíe en sus hooks en `/hooks`.

Después reinicie el cliente. En la primera sesión ofrece terminar la configuración (unos 200 MB: Python,
el servidor y las bibliotecas del optimizador); acepte y reinicie una vez más. `/aspen-doctor`
comprueba el resultado.

El plugin fija una versión, así que nada cambia hasta que usted lo actualice
(`claude plugin update aspen-plus@aspen-mcp`); le avisa cuando hay una versión más reciente.

Otros clientes MCP (Claude Desktop, Gemini CLI, Codex sin el plugin), la versión paso a paso
con verificaciones y la solución de problemas: **[INSTALL.md](INSTALL.md)** (en inglés).

## Privacidad

Todo lo que guarda el servidor permanece en su equipo, en `~/.aspen-mcp/`: su registro, el
historial de cambios, los puntos de restauración (copias de sus modelos) y su historial de errores. Este proyecto nunca envía
a ningún lado sus modelos, resultados ni conversaciones. Los únicos accesos a la red son:

- la comprobación de actualizaciones del plugin, como máximo una vez al día (`git ls-remote` contra este repositorio);
- la primera llamada a `pinch_analysis`, que descarga Python 3.14 y OpenPinch mediante uv;
- la instalación y la actualización, que obtienen el servidor y sus dependencias mediante uv.

Lo que su cliente de IA envía a su propio proveedor se rige por ese cliente.

## Comentarios

Preguntas y reportes de errores: [GitHub Issues](https://github.com/nckugese/Aspen_Co-pilot/issues). Reportes de seguridad: [SECURITY.md](SECURITY.md) (en inglés).

## Licencia

MIT — consulte [LICENSE](LICENSE). Copyright (c) 2026 NCKU GESE Lab.

Si usa este software en trabajos académicos, cite este repositorio.

## Aviso legal

Aspen Plus® y AspenTech® son marcas comerciales de Aspen Technology, Inc. Este proyecto es una
integración independiente y no oficial, y no está afiliado, respaldado ni patrocinado
por Aspen Technology, Inc. No incluye ni distribuye Aspen Plus; controla una
instalación independiente proporcionada por el usuario, y usted necesita su propia licencia válida de Aspen Plus.
