"""Read what an OPeNDAP dataset holds, without transferring any of it.

151 datasets in the registry resolve to `thredds.met.no`, and they are 1 km
climate-projection grids -- `change-evap_annual[time = 2][Yc = 1550][Xc = 1195]`
is 1.85M cells per time step. Ingesting them would be wrong twice over: wrong
shape for `observations`, and a projection is not a measurement.

What is worth having is the variable list. A search for "fordampning" or
"snømengde" cannot find these today because the only thing the registry holds
about them is a title. Two requests per dataset -- `.dds` for the variables
and their dimensions, `.das` for units and names -- and no data moves.

THREDDS serves neither as JSON. `.ncml`, `.iso` and `.dods.json` all answer
HTTP 400 on this server, so these two custom formats are the only way in and
this module parses them. Both parsers are deliberately shallow: they read the
declarations they understand and ignore the rest rather than failing, because
a `.das` carries free-form attribute blocks that no fixed grammar will cover
and a variable list is still worth having when one attribute is unparseable.

What they will not do is guess. A `.dds` that declares nothing recognisable
raises rather than returning an empty list, because "this dataset has no
variables" and "this parser did not understand the file" are different
answers and only one of them is ever true here.
"""

from __future__ import annotations

import re

# `Float32 change-evap_annual[time = 2][Yc = 1550][Xc = 1195];`
# A name may carry a hyphen, which is why this is not `\w+`.
_DECLARATION = re.compile(
    r"^\s*(?P<type>Byte|Int16|UInt16|Int32|UInt32|Float32|Float64|String|Url)\s+"
    r"(?P<name>[A-Za-z_][A-Za-z0-9_.\-]*)\s*(?P<dims>(?:\[[^\]]*\]\s*)*);",
    re.MULTILINE,
)
_DIMENSION = re.compile(r"\[\s*(?P<name>[A-Za-z_][A-Za-z0-9_.\-]*)\s*=\s*(?P<size>\d+)\s*\]")
# `String units "mm";` / `Float64 _FillValue -999;`
_ATTRIBUTE = re.compile(
    r"^\s*(?:Byte|Int16|UInt16|Int32|UInt32|Float32|Float64|String|Url)\s+"
    r"(?P<key>[A-Za-z_][A-Za-z0-9_.\-]*)\s+(?P<value>.+?);\s*$",
    re.MULTILINE,
)
_BLOCK_OPEN = re.compile(r"^\s*(?P<name>[A-Za-z_][A-Za-z0-9_.\-]*)\s*\{\s*$", re.MULTILINE)


def variables_from_dds(text: str) -> list[dict[str, object]]:
    """Every variable a `.dds` declares, with its dimensions.

    A `Grid` wraps an ARRAY and its MAPS, and the MAPS repeat the coordinate
    variables that are already declared at the top level. Both are returned:
    deduplicating them would mean deciding which declaration is canonical, and
    the caller can see that `Yc` appears as both an array and a map.
    """

    if not isinstance(text, str) or "Dataset" not in text:
        raise ValueError("not an OPeNDAP .dds document: no Dataset declaration")
    found: list[dict[str, object]] = []
    seen: set[str] = set()
    for match in _DECLARATION.finditer(text):
        name = match.group("name")
        if name in seen:
            continue
        seen.add(name)
        dims = [
            {"name": dim.group("name"), "size": int(dim.group("size"))}
            for dim in _DIMENSION.finditer(match.group("dims") or "")
        ]
        found.append({"name": name, "type": match.group("type"), "dimensions": dims})
    if not found:
        raise ValueError(
            "OPeNDAP .dds declared no variable this parser recognises; "
            "that is a parsing failure, not an empty dataset"
        )
    return found


def attributes_from_das(text: str) -> dict[str, dict[str, str]]:
    """Per-variable attributes from a `.das`, as far as they parse.

    Returns `{variable: {key: value}}`. A nested block inside a variable's
    block is flattened under its own name rather than merged into the parent,
    because `change-evap_annual` and its `CoordinateAxes` sub-block are
    different things and merging them invents attributes on the variable.
    """

    if not isinstance(text, str) or "Attributes" not in text:
        raise ValueError("not an OPeNDAP .das document: no Attributes declaration")
    out: dict[str, dict[str, str]] = {}
    stack: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped == "}":
            if stack:
                stack.pop()
            continue
        opened = _BLOCK_OPEN.match(line)
        if opened:
            name = opened.group("name")
            if name != "Attributes":
                stack.append(name)
            continue
        if stripped.startswith("Attributes"):
            continue
        attribute = _ATTRIBUTE.match(line)
        if attribute and stack:
            value = attribute.group("value").strip()
            if value.startswith('"') and value.endswith('"') and len(value) >= 2:
                value = value[1:-1]
            out.setdefault(stack[-1], {})[attribute.group("key")] = value
    return out


def measured_variables(
    variables: list[dict[str, object]],
    attributes: dict[str, dict[str, str]],
) -> list[dict[str, str]]:
    """The variables that carry a quantity, with the publisher's unit and name.

    A coordinate axis is excluded: `time`, `Xc`, `Yc`, `lat` and `lon` say
    where and when a value sits, not what was measured, and a dataset's
    `axis` attribute or its appearance as its own single dimension is the
    publisher saying so. `projection_utm` is a scalar holding the CRS and has
    no dimensions at all.

    Nothing is renamed and no unit is supplied. A variable whose `.das` block
    gives no `units` comes back without one.
    """

    axes = {
        name
        for name, attrs in attributes.items()
        if attrs.get("axis") or attrs.get("standard_name") in ("time", "latitude", "longitude")
    }
    measured: list[dict[str, str]] = []
    for variable in variables:
        name = str(variable["name"])
        dims = variable.get("dimensions") or []
        if name in axes:
            continue
        # A variable indexed only by itself is its own coordinate.
        if len(dims) == 1 and isinstance(dims[0], dict) and dims[0].get("name") == name:
            continue
        if not dims:
            continue
        attrs = attributes.get(name) or {}
        entry = {"name": name, "type": str(variable["type"])}
        for key in ("units", "long_name", "standard_name"):
            if attrs.get(key):
                entry[key] = attrs[key]
        entry["shape"] = ", ".join(
            f"{d['name']}={d['size']}" for d in dims if isinstance(d, dict)
        )
        measured.append(entry)
    return measured
