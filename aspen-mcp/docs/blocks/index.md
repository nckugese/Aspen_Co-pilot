# Aspen Plus blocks

One general file per block (ports, what it needs to run, the main specs, key results), plus short files for its advanced GUI forms. Rules shared by every block -- paths, writes, list rows, subobjects, running, Block Options -- are in [common.md](common.md).

Blocks are grouped as on the Aspen model palette. Each was checked live on Aspen Plus V15.

These pages are generated; to correct one, open an issue.

## Mixers/Splitters

| Block | General | Advanced |
|---|---|---|
| Mixer | [mixer.md](mixer.md) | -- |
| FSplit | [fsplit.md](fsplit.md) | [flash options](fsplit-flash-options.md), [key components](fsplit-key-components.md) |
| SSplit | [ssplit.md](ssplit.md) | [flash options](ssplit-flash-options.md), [key components](ssplit-key-components.md) |

## Separators

| Block | General | Advanced |
|---|---|---|
| Flash2 | [flash2.md](flash2.md) | [entrainment](flash2-entrainment.md), [free water](flash2-free-water.md), [heating curves](flash2-hcurves.md) |
| Flash3 | [flash3.md](flash3.md) | [entrainment](flash3-entrainment.md), [heating curves](flash3-hcurves.md), [key components](flash3-key-components.md) |
| Decanter | [decanter.md](decanter.md) | [efficiencies](decanter-efficiencies.md), [entrainment](decanter-entrainment.md), [flash options](decanter-flash-options.md), [heating curves](decanter-hcurves.md), [phase properties](decanter-phase-properties.md) |
| Sep | [sep.md](sep.md) | [feed flash](sep-feed-flash.md), [outlet flash](sep-outlet-flash.md) |
| Sep2 | [sep2.md](sep2.md) | [feed flash](sep2-feed-flash.md), [outlet flash](sep2-outlet-flash.md) |

## Exchangers

| Block | General | Advanced |
|---|---|---|
| Heater | [heater.md](heater.md) | [flash options](heater-flash-options.md), [heating curves](heater-hcurves.md), [phases](heater-phases.md) |
| HeatX | [heatx.md](heatx.md) | [baffles, nozzles](heatx-baffles-nozzles.md), [convergence](heatx-convergence.md), [geometry](heatx-geometry.md), [heating curves](heatx-hcurves.md), [LMTD](heatx-lmtd.md), [pressure drop](heatx-pressure-drop.md), [properties](heatx-properties.md), [TQ curve](heatx-tq-curve.md), [U methods](heatx-u-methods.md), [utilities](heatx-utilities.md) |
| MHeatX | [mheatx.md](mheatx.md) | [heating curves](mheatx-hcurves.md), [options](mheatx-options.md), [properties](mheatx-properties.md), [zone analysis](mheatx-zone-analysis.md) |
| HXFlux | [hxflux.md](hxflux.md) | [immersed bundle](hxflux-immersed-bundle.md), [radiant](hxflux-radiant.md), [streams](hxflux-streams.md) |

## Columns

| Block | General | Advanced |
|---|---|---|
| DSTWU | [dstwu.md](dstwu.md) | [calculation](dstwu-calculation.md), [convergence](dstwu-convergence.md) |
| DISTL | [distl.md](distl.md) | [convergence](distl-convergence.md) |
| RadFrac | [radfrac.md](radfrac.md) | [analysis](radfrac-analysis.md), [convergence](radfrac-convergence.md), [design specs](radfrac-design-specs.md), [efficiencies](radfrac-efficiencies.md), [heating curves](radfrac-hcurves.md), [heaters](radfrac-heaters.md), [internals](radfrac-internals.md), [properties](radfrac-properties.md), [pumparounds](radfrac-pumparounds.md), [rate based](radfrac-rate-based.md), [reactions](radfrac-reactions.md), [three phase](radfrac-three-phase.md) |
| Extract | [extract.md](extract.md) | [convergence](extract-convergence.md), [efficiencies](extract-efficiencies.md), [heat streams](extract-heat-streams.md), [KLL](extract-kll.md), [report](extract-report.md) |
| MultiFrac | [multifrac.md](multifrac.md) | [analysis](multifrac-analysis.md), [condenser](multifrac-condenser.md), [convergence](multifrac-convergence.md), [design specs](multifrac-design-specs.md), [efficiencies](multifrac-efficiencies.md), [flow specs](multifrac-flow-specs.md), [heating curves](multifrac-hcurves.md), [heaters](multifrac-heaters.md), [properties](multifrac-properties.md), [sizing](multifrac-sizing.md) |
| SCFrac | [scfrac.md](scfrac.md) | [convergence](scfrac-convergence.md), [property specs](scfrac-property-specs.md), [steam](scfrac-steam.md) |
| PetroFrac | [petrofrac.md](petrofrac.md) | [analysis](petrofrac-analysis.md), [condenser](petrofrac-condenser.md), [convergence](petrofrac-convergence.md), [design specs](petrofrac-design-specs.md), [efficiencies](petrofrac-efficiencies.md), [furnace](petrofrac-furnace.md), [heating curves](petrofrac-hcurves.md), [heaters](petrofrac-heaters.md), [properties](petrofrac-properties.md), [pumparounds](petrofrac-pumparounds.md), [sizing](petrofrac-sizing.md), [strippers](petrofrac-strippers.md) |
| ConSep | [consep.md](consep.md) | [advanced options](consep-advanced-options.md), [component map](consep-component-map.md), [decanter](consep-decanter.md) |

## Reactors

| Block | General | Advanced |
|---|---|---|
| RStoic | [rstoic.md](rstoic.md) | [combustion](rstoic-combustion.md), [heat of reaction](rstoic-heat-of-reaction.md), [selectivity](rstoic-selectivity.md), [streams flash](rstoic-streams-flash.md) |
| RYield | [ryield.md](ryield.md) | [component mapping](ryield-component-mapping.md), [streams flash](ryield-streams-flash.md) |
| REquil | [requil.md](requil.md) | [convergence](requil-convergence.md), [reactions](requil-reactions.md) |
| RGibbs | [rgibbs.md](rgibbs.md) | [convergence](rgibbs-convergence.md), [products](rgibbs-products.md), [restricted](rgibbs-restricted.md) |
| RCSTR | [rcstr.md](rcstr.md) | [catalyst](rcstr-catalyst.md), [convergence](rcstr-convergence.md), [equipment](rcstr-equipment.md), [heat transfer](rcstr-heat-transfer.md), [mass transfer](rcstr-mass-transfer.md), [phases](rcstr-phases.md) |
| RPlug | [rplug.md](rplug.md) | [catalyst](rplug-catalyst.md), [convergence](rplug-convergence.md), [pressure drop](rplug-pressure-drop.md), [profiles](rplug-profiles.md), [report](rplug-report.md), [thermal fluid](rplug-thermal-fluid.md) |
| RBatch | [rbatch.md](rbatch.md) | [continuous feed](rbatch-continuous-feed.md), [convergence](rbatch-convergence.md), [operating spec](rbatch-operating-spec.md), [pressure vent](rbatch-pressure-vent.md), [report](rbatch-report.md) |
| Electrolyzer | [electrolyzer.md](electrolyzer.md) | [curves](electrolyzer-curves.md), [module](electrolyzer-module.md), [rigorous](electrolyzer-rigorous.md), [shortcut](electrolyzer-shortcut.md) |

## Pressure Changers

| Block | General | Advanced |
|---|---|---|
| Pump | [pump.md](pump.md) | [curves](pump-curves.md), [flash options](pump-flash-options.md), [NPSH](pump-npsh.md), [speed](pump-speed.md) |
| Compr | [compr.md](compr.md) | [calculation](compr-calculation.md), [convergence](compr-convergence.md), [curve adjust](compr-curve-adjust.md), [curves](compr-curves.md), [integration](compr-integration.md), [power loss](compr-power-loss.md) |
| MCompr | [mcompr.md](mcompr.md) | [convergence](mcompr-convergence.md), [curves](mcompr-curves.md), [feeds knockout](mcompr-feeds-knockout.md), [heating curves](mcompr-hcurves.md) |
| Valve | [valve.md](valve.md) | [calculation options](valve-calculation-options.md), [parameters](valve-parameters.md), [phases](valve-phases.md), [pipe fittings](valve-pipe-fittings.md) |
| Pipe | [pipe.md](pipe.md) | [fittings](pipe-fittings.md), [methods](pipe-methods.md), [properties](pipe-properties.md), [solids](pipe-solids.md) |
| Pipeline | [pipeline.md](pipeline.md) | [convergence](pipeline-convergence.md), [heat transfer](pipeline-heat-transfer.md), [methods](pipeline-methods.md), [properties](pipeline-properties.md), [solids](pipeline-solids.md) |

## Manipulators

| Block | General | Advanced |
|---|---|---|
| Mult | [mult.md](mult.md) | -- |
| Dupl | [dupl.md](dupl.md) | -- |
| ClChng | [clchng.md](clchng.md) | -- |
| Selector | [selector.md](selector.md) | -- |
| QTVec | [qtvec.md](qtvec.md) | -- |
| Analyzer | [analyzer.md](analyzer.md) | [property sets](analyzer-property-sets.md) |
| Charge Balance (ChgBal) | [chargebal.md](chargebal.md) | -- |
| Makeup | [makeup.md](makeup.md) | [flash options](makeup-flash-options.md) |

## Solids

| Block | General | Advanced |
|---|---|---|
| Crystallizer | [crystallizer.md](crystallizer.md) | [convergence](crystallizer-convergence.md), [growth](crystallizer-growth.md), [PSD](crystallizer-psd.md), [recirculation](crystallizer-recirculation.md), [solubility](crystallizer-solubility.md) |
| Crusher | [crusher.md](crusher.md) | [BOM tables](crusher-bom-tables.md), [grindability](crusher-grindability.md), [impact mills](crusher-impact-mills.md), [jaw, cone](crusher-jaw-cone.md), [outlet PSD](crusher-outlet-psd.md), [power](crusher-power.md) |
| Screen | [screen.md](screen.md) | [fluid](screen-fluid.md), [selection function](screen-selection-function.md), [separation strength](screen-separation-strength.md) |
| FluidBed (fluidized bed) | [fluidbed.md](fluidbed.md) | [convergence](fluidbed-convergence.md), [distributor](fluidbed-distributor.md), [elutriation](fluidbed-elutriation.md), [geometry](fluidbed-geometry.md), [heat exchanger](fluidbed-heat-exchanger.md), [operation](fluidbed-operation.md), [PSD](fluidbed-psd.md) |
| Granulator | [granulator.md](granulator.md) | [agglomeration](granulator-agglomeration.md), [convergence](granulator-convergence.md), [outlet PSD](granulator-outlet-psd.md), [outlet](granulator-outlet.md) |
| Classifier | [classifier.md](classifier.md) | [curves](classifier-curves.md), [impeller](classifier-impeller.md), [outlet](classifier-outlet.md), [sifter](classifier-sifter.md) |
| Dryer | [dryer.md](dryer.md) | [contact](dryer-contact.md), [convective](dryer-convective.md), [convergence](dryer-convergence.md), [curve](dryer-curve.md), [spray](dryer-spray.md), [transfer](dryer-transfer.md) |
| SWASH (one-stage solids wash) | [swash.md](swash.md) | [calculation](swash-calculation.md) |
| CCD (counter-current decanter) | [ccd.md](ccd.md) | [heat](ccd-heat.md), [side streams](ccd-side-streams.md) |

## Solids Separators

| Block | General | Advanced |
|---|---|---|
| Cyclone | [cyclone.md](cyclone.md) | [efficiency](cyclone-efficiency.md), [geometry](cyclone-geometry.md), [Muschelknautz](cyclone-muschelknautz.md), [solids separator](cyclone-solids-separator.md) |
| VScrub (wet scrubber) | [vscrub.md](vscrub.md) | [design](vscrub-design.md), [operating options](vscrub-operating-options.md), [solids separator](vscrub-solids-separator.md), [spray](vscrub-spray.md), [venturi throat](vscrub-venturi-throat.md) |
| CfFilter (crossflow filter) | [cffilter.md](cffilter.md) | [solids separator](cffilter-solids-separator.md) |
| ESP (electrostatic precipitator) | [esp.md](esp.md) | [design](esp-design.md), [operation](esp-operation.md), [solids separator](esp-solids-separator.md) |
| FabFl (fabric filter, baghouse) | [fabfl.md](fabfl.md) | [coefficient model](fabfl-coefficient-model.md), [design](fabfl-design.md), [efficiency](fabfl-efficiency.md), [pressure drop](fabfl-pressure-drop.md), [solids separator](fabfl-solids-separator.md) |
| HyCyc (hydrocyclone) | [hycyc.md](hycyc.md) | [correlations](hycyc-correlations.md), [geometry](hycyc-geometry.md), [solids separator](hycyc-solids-separator.md), [user efficiency](hycyc-user-efficiency.md) |
| CFuge (centrifuge) | [cfuge.md](cfuge.md) | [basket](cfuge-basket.md), [decanter](cfuge-decanter.md), [disc](cfuge-disc.md), [pusher](cfuge-pusher.md) |
| Filter | [filter.md](filter.md) | [cake](filter-cake.md), [convergence](filter-convergence.md), [deliquoring](filter-deliquoring.md), [design](filter-design.md), [simulation](filter-simulation.md), [solids separator](filter-solids-separator.md), [washing](filter-washing.md) |

## Batch

| Block | General | Advanced |
|---|---|---|
| BatchProcess (BatchOp) | [batchop.md](batchop.md) | [convergence](batchop-convergence.md), [filtration](batchop-filtration.md), [geometry](batchop-geometry.md), [heat transfer](batchop-heat-transfer.md), [reactions](batchop-reactions.md), [report](batchop-report.md), [streams](batchop-streams.md), [vent pressure](batchop-vent-pressure.md) |
| BatchSep | [batchsep.md](batchsep.md) | [condenser](batchsep-condenser.md), [controllers](batchsep-controllers.md), [convergence](batchsep-convergence.md), [efficiencies](batchsep-efficiencies.md), [heat transfer](batchsep-heat-transfer.md), [holdups](batchsep-holdups.md), [initial, final](batchsep-initial-final.md), [internals](batchsep-internals.md), [operating steps](batchsep-operating-steps.md) |

## User Models

| Block | General | Advanced |
|---|---|---|
| USER | [user.md](user.md) | [property settings](user-property-settings.md), [stream flash](user-stream-flash.md) |
| USER2 | [user2.md](user2.md) | [Excel](user2-excel.md), [stream flash](user2-stream-flash.md), [streams](user2-streams.md) |
| USER3 | [user3.md](user3.md) | [config files](user3-config-files.md), [EO options](user3-eo-options.md), [solver](user3-solver.md), [variables](user3-variables.md) |

## Placing a block

`place_block(session, block_name='B1', block_type='RadFrac')`, or `add_element(session, '\Data\Blocks', 'B1!RADFRAC')`. Block IDs: at most 8 characters: letters, digits and `-` (Aspen also takes `+`, `#` and `$`) ([IDs](../setup/setup.md#ids)).
