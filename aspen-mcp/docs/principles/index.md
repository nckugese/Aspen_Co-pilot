# Principle cards

A fixed library of chemical-engineering ideas, one card per key (`<key>.md`), in English and
Traditional Chinese. In learning mode a workbench group carries keys with
`"principle": ["<key>"]` (at most 2) on its heading or on its steps; its line then shows a
Principle chip that opens the card. The card shows only the library text; what the idea means
for this change goes in the group's `why`. A key not listed below is not shown (warn
`principle_unknown`).

Card text is our own, written for this project and reviewed by a chemical engineer. No vendor
or textbook wording; `ref` names a book chapter and quotes nothing.

## Keys

Each line: key -- 中文名 / English -- attach when -- what the group's `why` should say.

- `mass_balance` -- 質量平衡 / Mass balance -- a change to a split, a product rate or a
  stream's flow that others must make up for -- name the boundary and which stream takes up
  the difference.
- `energy_balance` -- 能量平衡 / Energy balance -- a heater, cooler or flash duty or outlet
  temperature changes -- name the stream heated or cooled and whether a phase change is part
  of the duty.
- `flash_vle` -- 閃蒸與槓桿法則 / Flash and the lever rule -- a flash drum's temperature,
  pressure or vapour fraction changes -- say which way the split moves and which component
  follows the vapour.
- `relative_volatility` -- 相對揮發度 / Relative volatility -- choosing what a column can
  separate, or a column pressure change -- name the two key components and whether they are
  easy or hard to split.
- `reflux_vs_duty` -- 迴流比與再沸器負荷 / Reflux ratio and reboiler duty -- a column's
  reflux or boilup changes -- say what purity is bought and that the duty rises with it.
- `stages_separation` -- 板數與分離程度 / Stages and separation -- a column's stage count or
  feed stage changes, or a key recovery is set -- say which product gets purer and what the
  extra stages trade against.
- `azeotrope` -- 共沸 / Azeotrope -- a distillation target near an azeotrope, or a step added
  to cross one -- name the pair and why the plain column stops short.
- `absorption_factor` -- 吸收因子 / Absorption factor -- an absorber or scrubber is added, or
  its wash flow or stages change -- name the wash and the gas, and whether the wash is large
  enough to clean the gas.
- `henry_law` -- 亨利定律 / Henry's law -- a dissolved gas, or an absorber's temperature or
  pressure, matters to the change -- name the gas and the solvent and which way the change
  moves its solubility.
- `conversion_selectivity` -- 轉化率與選擇率 / Conversion and selectivity -- a reactor's
  conversion, temperature, volume or residence time changes -- name the key reactant and the
  side product it competes with.
- `recycle_purge` -- 循環與排放的累積 / Recycle and purge build-up -- a recycle or purge is
  added, or a purge split changes -- name what builds up in the loop and where it leaves.
- `heat_recovery` -- 熱回收與最小溫差 / Heat recovery and minimum approach -- a feed/effluent
  or process-to-process exchanger is added, or its approach changes -- name the hot and the
  cold stream and the utility saved.

A group with no key may get one from the block type and the field a step sets:
[rules.md](rules.md).

## Card format

```text
---
key: <key, same as the file name>
title_en: <English name, same as in the key line above>
title_zh: <中文名, same as in the key line above>
related: <key>, <key>          (0-3 keys of this library)
ref: <book> · <book>           (0-2 books)
---
## zh
idea: <one paragraph>
eq: <one equation>
sym: <one line: symbol meaning · symbol meaning>
## en
idea: ...
eq: ...
sym: ...
```

| Field | Rule |
|---|---|
| `idea` | Plain text, no marks. At most 120 characters in zh, 260 in en. Typical design values go here. |
| `eq` | Plain text. `_` makes the run of letters and digits after it a subscript, `^` a superscript (`c_p`, `ΔT_lm`). Single Latin or Greek letters are set in italics; Σ, Δ, Π, ∂, ∇ stay upright. No HTML. |
| `sym` | One line, symbols separated by ` · `, same marks as `eq`. Only the single letters that `eq` uses are set in italics. |
| `ref` | One line for both languages, at most 160 characters. Each book `Authors, Title, Nth ed.[, Ch. N]`; the field before the edition is the title (set in italics). A chapter only where checked against the book. |
| `related` | Keys of this library, not the card's own; more than 3 are cut. |

The key line's two names feed the chips and the related links (`catalog.principles`); the card's
`title_en` / `title_zh` head the open card. Keep them the same.
