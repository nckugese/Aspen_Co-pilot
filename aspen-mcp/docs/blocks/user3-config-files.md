# USER3: configuration files

A `.cfg` file is plain text, one `keyword = value` per line; `!` starts a comment. Components are the flowsheet's IDs, separated by commas (a line ending in a comma goes on). Name it `<CFGNAM>.cfg`; where it goes: [user3.md](user3.md).

## Mixer (`SUBMODEL` = `EOMIXER`)

```
Title = 'BTX mixer'
Model type = Mixer
Inlet streams = 2
Outlet Phase = Mixed
Report Format = Full
Stream components = BENZENE, TOLUENE
```

`Inlet streams` is the number of feeds; `Stream components` lists the components of every stream; `Outlet Phase = Mixed` lets the outlet split into vapor and liquid. The run: 190 kmol/hr out, 80 kmol/hr benzene.

## Component splitter (`SUBMODEL` = `EOCSPLIT`)

```
Title = 'BTX component splitter'
Model type = csplitter
Outlet Streams = 2
Report Format = Full
Inlet stream components = BENZENE, TOLUENE
Outlet stream 1 components = BENZENE
Outlet stream 2 components = TOLUENE
```

Each `Outlet stream <n> components` line lists the components that leave by outlet n; in the run all benzene leaves by outlet 1 and all toluene by outlet 2.

## Splitter (`SUBMODEL` = `EOSPLIT`)

```
Title = 'BTX splitter'
Model type = splitter
Outlet Streams = 2
Report Format = Full
Stream components = BENZENE, TOLUENE
```

`Outlet Streams` is the number of outlets, each with the inlet's composition. Run as is, the flow is shared equally (50 and 50 kmol/hr).
