# EP0010253 HIDiC Simulation - Parameters & Results

## Patent Reference
- **Patent**: EP 0010253 A1
- **Title**: Continuous Distillation Apparatus and Method of Operation
- **Inventor**: Seader, Junior DeVere (University of Utah)
- **Figure**: 2 (Heat-Integrated Distillation Column)
- **System**: Ethylene / Ethane separation

---

## Components
| Component | Alias | Databank Name |
|-----------|-------|---------------|
| Ethylene  | C2H4  | ETHYLENE      |
| Ethane    | C2H6  | ETHANE        |

## Property Method
- **PENG-ROB** (Peng-Robinson EOS, appropriate for light hydrocarbons)

---

## Feed Stream (FEED)
| Parameter | Value | Unit |
|-----------|-------|------|
| Temperature | -100 | °C |
| Pressure | 304 | kPa |
| Total Flow | 453.6 | kmol/hr |
| Ethylene Flow | 226.8 | kmol/hr |
| Ethane Flow | 226.8 | kmol/hr |
| Composition | 50/50 equimolar | mol% |

*Note: 0.126 kgmol/s = 453.6 kmol/hr (patent value)*

---

## Block Specifications

### STRIP (RadFrac - Stripping Section)
| Parameter | Value | Unit |
|-----------|-------|------|
| Number of Stages | 15 | - |
| Condenser | NONE | - |
| Reboiler | KETTLE | - |
| Top Stage Pressure | 304 | kPa |
| Bottoms Rate (BASIS_B) | 226.8 | kmol/hr |
| Feed Stage (FEED) | 1 (top) | - |
| Feed Stage (VALVOUT) | 1 (top) | - |
| Product Stage (STRVAP) | 1, Vapor | - |
| Product Stage (ETHANE) | 15, Liquid | - |
| Side Duties (stages 2-14) | +30,000 each | cal/sec |
| Total Side Duty | +390,000 (~1,632 kW) | cal/sec |

### RECT (RadFrac - Rectifying Section)
| Parameter | Value | Unit |
|-----------|-------|------|
| Number of Stages | 15 | - |
| Condenser | TOTAL | - |
| Reboiler | NONE | - |
| Condenser Pressure | 911 | kPa |
| Reflux Ratio (BASIS_RR) | 1.5 | - |
| Feed Stage (COMPOUT) | 15 (bottom) | - |
| Feed Convention | ON-STAGE | - |
| Product Stage (ETHLNE) | 1, Liquid | - |
| Product Stage (RECTLIQ) | 15, Liquid | - |
| Side Duties (stages 2-14) | -30,000 each | cal/sec |
| Total Side Duty | -390,000 (~-1,632 kW) | cal/sec |

### COMP (Compr - Compressor)
| Parameter | Value | Unit |
|-----------|-------|------|
| Type | ISENTROPIC | - |
| Discharge Pressure | 911 | kPa |
| Isentropic Efficiency | 0.72 | - |

### VALVE (Valve - Constriction Valve)
| Parameter | Value | Unit |
|-----------|-------|------|
| Outlet Pressure | 304 | kPa |

---

## Stream Connections (Flowsheet Topology)
```
FEED ──► STRIP (F, stage 1)
         STRIP ──► STRVAP (VD, stage 1, vapor)
         STRIP ──► ETHANE (B, stage 15, liquid) ──► Ethane Product
STRVAP ──► COMP (F)
            COMP ──► COMPOUT (P)
COMPOUT ──► RECT (F, stage 15, on-stage)
            RECT ──► ETHLNE (LD, stage 1, liquid) ──► Ethylene Product
            RECT ──► RECTLIQ (B, stage 15, liquid)
RECTLIQ ──► VALVE (F)
             VALVE ──► VALVOUT (P)
VALVOUT ──► STRIP (F, stage 1) ──► [recycle]
```

---

## Simulation Results (With Heat Pipe Integration)

### Key Performance
| Parameter | Patent (HIDiC) | Simulation | Unit |
|-----------|----------------|------------|------|
| Rectifier Pressure | 911.9 | 911 | kPa |
| Stripper Pressure | 304.0 | 304 | kPa |
| Condenser Temperature | -54.3 (218.9 K) | -54.3 | °C |
| Reboiler Temperature | — | -66.0 | °C |
| Reboiler Duty | 1,495 | 1,455 | kW |
| Condenser Duty | 1,070 | 1,754 | kW |
| Compressor Duty | 509 | 651 | kW |
| External Reflux Ratio | 1.500 | 1.500 | - |

### Product Purities
| Stream | Ethylene (kmol/hr) | Ethane (kmol/hr) | Purity (mol%) |
|--------|-------------------|------------------|---------------|
| ETHLNE (overhead) | 222.0 | 4.82 | 97.9% C2H4 |
| ETHANE (bottoms) | 4.81 | 222.0 | 97.9% C2H6 |

*Patent target: 99 mol% pure products*

### Comparison Without Heat Pipes (reference run, 16 stages)
| Parameter | Without Heat Pipes | With Heat Pipes |
|-----------|-------------------|-----------------|
| Reboiler Duty | 1,787 kW | 1,455 kW |
| Condenser Duty | 1,781 kW | 1,754 kW |
| Compressor Duty | 342 kW | 651 kW |
| Product Purity | ~84% | ~98% |

---

## Patent Table I (Reference Data)
| Parameter | Conventional | HIDiC (Patent) | Unit |
|-----------|-------------|----------------|------|
| Rectifier Pressure | 304.0 | 911.9 | kPa |
| Stripper Pressure | 304.0 | 304.0 | kPa |
| Condenser Temperature | 191.2 | 218.9 | K |
| Reboiler Duty | 207.7 | 207.7 | kW (?) |
| Reboiler Duty | 2,482 | 1,495 | kW |
| Condenser Duty | 2,150 | 1,070 | kW |
| Compressor Duty | — | 509 | kW |
| External Reflux Ratio | 2.652 | 1.500 | - |
| Total Steam Req. | 19.42 | 8.46 | kg/s |
| Total Cooling Water | 132.19 | 32.62 | kg/s |

---

## Notes
1. **30 total stages** in patent: 15 per section. STRIP has 15 stages (14 trays + reboiler), RECT has 15 stages (condenser + 14 trays). Total = 30 stages.
2. **Heat pipe integration** modeled as uniform side duties (+/-30,000 cal/sec) on stages 2-14 of both columns. The patent uses 4 discrete heat pipes (84-87) connecting specific rectifying stages (36,38,40,42) to stripping stages (25,27,29,31). A non-uniform duty distribution could improve accuracy.
3. **Purity gap** (98% vs 99%): Could be closed by fine-tuning side duty magnitude, using non-uniform distribution, or adding stages.
4. **Condenser duty mismatch**: The patent's lower condenser duty (1,070 kW) suggests more effective heat removal via heat pipes than our uniform approximation achieves.
5. **File**: `EP0010253_HIDiC.bkp` in the same folder.
