# Aspen Co-pilot

[English](README.md) · [繁體中文](README.zh-TW.md) · [简体中文](README.zh-CN.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [Español](README.es.md) · [Português](README.pt-BR.md) · [Deutsch](README.de.md) · **Français** · [Русский](README.ru.md)

Ceci est une traduction ; en cas de divergence, la [version anglaise](README.md) fait foi.

**Confiez à un agent d'IA la conception, la simulation et l'optimisation de procédés chimiques
dans votre propre Aspen Plus — vous voyez chaque étape et gardez la main.**

Aspen Co-pilot relie Aspen Plus à des agents d'IA tels que Claude Code et Codex via le Model
Context Protocol (MCP). Vous décrivez le procédé en langage courant ; l'agent fait le travail
dans Aspen, et vous le vérifiez.

Windows uniquement. Vous avez besoin de votre propre licence Aspen Plus ; ce projet ne l'inclut
pas. Développé par le NCKU GESE Lab.

## Ce qu'il sait faire

**Construire et modifier des procédés.** Créez un schéma de procédé (flowsheet) à partir d'une
description — constituants, méthodes thermodynamiques, réactions, opérations unitaires et
courants —, réglez et ajustez n'importe quel paramètre, lancez la simulation et lisez les
résultats. La plupart des fonctions d'Aspen Plus sont disponibles.

**Passer de la littérature à un modèle qui tourne.** Grâce aux outils de recherche de votre
client d'IA, l'agent peut rassembler cinétiques, conditions opératoires et voies de procédé à
partir d'articles et de brevets, puis les intégrer dans un modèle Aspen que vous pouvez
confronter aux sources.

**Comprendre pourquoi une simulation échoue.** Il vérifie ce qui manque encore à Aspen avant un
calcul, explique les échecs et les avertissements, et les corrige. Les corrections qui ont
fonctionné sont conservées sur votre machine pour la prochaine fois.

**Optimiser le procédé.** Neuf algorithmes derrière un seul outil — NSGA-II, NSGA-III, PSO,
DE/GDE3, gradient (SLSQP), recherche sur grille et trois méthodes bayésiennes (BO, CBO,
AFM-CBO) — pour des problèmes mono- ou multi-objectifs sous contraintes, ainsi qu'une analyse
pincement (pinch) et des suggestions d'appariement d'échangeurs de chaleur pour l'intégration
thermique.

**Vérifier plutôt que deviner.** Une référence pour chaque bloc, courant et paramètre
([aspen-mcp/docs](aspen-mcp/docs/aspen.md)), que l'agent consulte avant de modifier un champ.

## Conçu pour travailler avec des humains

Un agent LLM qui pilote un logiciel seul est difficile à croire sur parole : vous ne voyez ni ce
qu'il a modifié ni pourquoi, et vous ne pouvez pas arrêter une erreur avant qu'elle n'atteigne
le modèle. Aspen Co-pilot comble ce manque avec l'**Aspen Workbench**, une fenêtre de bureau à
côté d'Aspen Plus.

- **Voir ce que fait l'IA.** Le schéma de procédé, les résultats et chaque modification de
  l'IA, avec sa justification, se mettent à jour en direct. Annulez n'importe quelle
  modification, ou revenez à un point de restauration.
- **Garder le contrôle.** En mode révision, les modifications de l'IA attendent votre
  approbation ; les changements plus importants arrivent sous forme de propositions que vous
  seul pouvez exécuter.
- **Définir vous-même le travail avec des programmes à blocs.** Assemblez balayages de
  paramètres, calculs, tableaux, graphiques et études d'optimisation — avec vos propres
  variables, objectifs et contraintes — à partir de blocs à glisser-déposer, sans écrire de
  code. L'IA peut écrire un programme que vous modifierez, ou exécuter le vôtre.
- **Travailler ensemble.** Cliquez sur n'importe quel courant ou bloc et posez-lui une question
  avec **Ask AI**. En mode apprentissage, l'IA explique le principe de génie des procédés
  derrière chaque modification.

L'interface de la Workbench existe en anglais et en chinois (pas en français), et elle
fonctionne aussi sans client d'IA (`%USERPROFILE%\.aspen-mcp\aspen-workbench.cmd` : sans réseau,
sans jetons).

## Installation

Il vous faut **Windows**, une licence **Aspen Plus** et **[uv](https://docs.astral.sh/uv/)**
(`winget install --id=astral-sh.uv -e` ; il apporte son propre Python).

**Claude Code :**

```bash
claude plugin marketplace add nckugese/Aspen_Co-pilot
claude plugin install aspen-plus@aspen-mcp
```

**Codex :** `codex plugin marketplace add nckugese/Aspen_Co-pilot`, puis activez **Aspen Plus**
dans `/plugins` et accordez votre confiance à ses hooks dans `/hooks`.

Redémarrez ensuite le client. Lors de la première session, il propose de terminer
l'installation (environ 200 Mo : Python, le serveur et les bibliothèques d'optimisation) ;
acceptez, puis redémarrez encore une fois. `/aspen-doctor` vérifie le résultat.

Le plugin est figé sur une version, donc rien ne change tant que vous ne le mettez pas à jour
(`claude plugin update aspen-plus@aspen-mcp`) ; il vous prévient lorsqu'une version plus récente
existe.

Autres clients MCP (Claude Desktop, Gemini CLI, Codex sans le plugin), version pas à pas avec
vérifications, et dépannage : **[INSTALL.md](INSTALL.md)** (en anglais).

## Confidentialité

Tout ce que le serveur conserve reste sur votre machine, dans `~/.aspen-mcp/` : son journal, le
journal des modifications, les points de restauration (copies de vos modèles) et votre
historique d'erreurs. Vos modèles, résultats et conversations ne sont jamais envoyés nulle part
par ce projet. Les seuls accès réseau sont :

- la vérification des mises à jour du plugin, au plus une fois par jour (`git ls-remote` sur ce dépôt) ;
- le premier appel à `pinch_analysis`, qui télécharge Python 3.14 et OpenPinch via uv ;
- l'installation et la mise à jour, qui récupèrent le serveur et ses dépendances via uv.

Ce que votre client d'IA envoie à son propre fournisseur relève de ce client.

## Retours

Questions et rapports de bogues : [GitHub Issues](https://github.com/nckugese/Aspen_Co-pilot/issues). Signalements de sécurité : [SECURITY.md](SECURITY.md) (en anglais).

## Licence

MIT — voir [LICENSE](LICENSE). Copyright (c) 2026 NCKU GESE Lab.

Si vous utilisez ce logiciel dans un travail universitaire, merci de citer ce dépôt.

## Avertissement

Aspen Plus® et AspenTech® sont des marques d'Aspen Technology, Inc. Ce projet est une
intégration indépendante et non officielle ; il n'est ni affilié à Aspen Technology, Inc., ni
approuvé ou parrainé par elle. Il n'inclut ni ne distribue Aspen Plus ; il pilote une
installation distincte fournie par l'utilisateur, et vous devez disposer de votre propre licence
Aspen Plus valide.
