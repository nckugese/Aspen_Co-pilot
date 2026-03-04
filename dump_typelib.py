"""Dump all methods/properties from Aspen Plus COM Type Libraries."""
import pythoncom

DLL_PATHS = [
    (r"C:\Program Files\AspenTech\AprSystem V15.0\GUI\XEQ\happ.dll", "Aspen Plus GUI 41.0"),
]

INVKIND = {1: "METHOD", 2: "GET", 4: "PUT", 8: "PUTREF"}
TYPEKIND = {0: "ENUM", 1: "RECORD", 2: "MODULE", 3: "INTERFACE",
            4: "DISPATCH", 5: "COCLASS", 6: "ALIAS", 7: "UNION"}

for dll_path, label in DLL_PATHS:
    try:
        tlb = pythoncom.LoadTypeLib(dll_path)
    except Exception as e:
        print(f"\n!!! Cannot load {label}: {e}")
        continue

    count = tlb.GetTypeInfoCount()
    print(f"\n{'='*60}")
    print(f"{label}  ({count} items)")
    print('='*60)

    for i in range(count):
        try:
            name, doc, _, _ = tlb.GetDocumentation(i)
            ti = tlb.GetTypeInfo(i)
            ta = ti.GetTypeAttr()
            kind = TYPEKIND.get(ta.typekind, "?")
            header = f"[{kind}] {name}"
            if doc and doc != name:
                header += f"  -- {doc}"
            print(f"\n{header}")

            if ta.typekind == 4:  # DISPATCH
                for j in range(ta.cFuncs):
                    fd = ti.GetFuncDesc(j)
                    names = ti.GetNames(fd.memid)
                    inv = INVKIND.get(fd.invkind, "?")
                    func_name = names[0] if names else "?"
                    params = ", ".join(names[1:]) if len(names) > 1 else ""
                    print(f"    [{inv:6s}] {func_name}({params})")

            if ta.typekind == 0:  # ENUM
                for j in range(ta.cVars):
                    vd = ti.GetVarDesc(j)
                    vnames = ti.GetNames(vd.memid)
                    vname = vnames[0] if vnames else "?"
                    print(f"    {vname} = {vd.value}")
        except Exception:
            pass
