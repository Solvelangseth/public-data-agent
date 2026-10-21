"""Reading what an OPeNDAP grid holds without moving any of it.

151 datasets resolve to thredds.met.no and they are 1 km climate-projection
grids. The registry holds only their titles, so a search for "fordampning"
cannot find them. Two requests per dataset -- .dds and .das -- give the
variable list, and no data moves.

The fixtures are trimmed copies of the live `change-evap` dataset from
Klima i Norge 2025.
"""

from __future__ import annotations

import pytest

from public_data_agent.opendap import (
    attributes_from_das,
    measured_variables,
    variables_from_dds,
)

DDS = """Dataset {
    Int32 time[time = 2];
    Grid {
     ARRAY:
        Float64 lon[Yc = 1550][Xc = 1195];
     MAPS:
        Float64 Yc[Yc = 1550];
        Float64 Xc[Xc = 1195];
    } lon;
    Float64 Xc[Xc = 1195];
    Float64 Yc[Yc = 1550];
    Int32 projection_utm;
    Grid {
     ARRAY:
        Float32 change-evap_annual[time = 2][Yc = 1550][Xc = 1195];
     MAPS:
        Int32 time[time = 2];
    } change-evap_annual;
} ensemble-mean.nc;
"""

DAS = """Attributes {
    time {
        String standard_name "time";
        String long_name "time";
        String units "days since 2056-01-01";
        String axis "T";
    }
    lat {
        String standard_name "latitude";
        String units "degrees_north";
    }
    lon {
        String standard_name "longitude";
        String units "degrees_east";
    }
    change-evap_annual {
        String long_name "change in mean evapotranspiration";
        String units "%";
        Float32 _FillValue -999.0;
    }
    NC_GLOBAL {
        String title "Klima i Norge 2025";
    }
}
"""


def test_a_hyphenated_variable_name_is_read() -> None:
    """`change-evap_annual` is not `\\w+`, and it is the variable that matters."""

    names = [v["name"] for v in variables_from_dds(DDS)]
    assert "change-evap_annual" in names


def test_every_declaration_is_found_including_the_grid_maps() -> None:
    variables = {v["name"]: v for v in variables_from_dds(DDS)}
    assert set(variables) == {
        "time", "lon", "Yc", "Xc", "projection_utm", "change-evap_annual",
    }
    assert variables["change-evap_annual"]["dimensions"] == [
        {"name": "time", "size": 2},
        {"name": "Yc", "size": 1550},
        {"name": "Xc", "size": 1195},
    ]
    assert variables["projection_utm"]["dimensions"] == [], "a scalar has no dimensions"


def test_a_dds_that_parses_to_nothing_raises() -> None:
    """"No variables" and "the parser failed" are different answers."""

    with pytest.raises(ValueError, match="no Dataset declaration"):
        variables_from_dds("<html>404</html>")
    with pytest.raises(ValueError, match="parsing failure"):
        variables_from_dds("Dataset {\n} empty.nc;\n")


def test_attributes_are_kept_under_their_own_variable() -> None:
    attributes = attributes_from_das(DAS)
    assert attributes["change-evap_annual"]["units"] == "%"
    assert attributes["change-evap_annual"]["long_name"] == "change in mean evapotranspiration"
    assert attributes["time"]["axis"] == "T"
    assert "title" not in attributes.get("change-evap_annual", {}), (
        "NC_GLOBAL's title must not become the variable's"
    )
    assert attributes["NC_GLOBAL"]["title"] == "Klima i Norge 2025"


def test_a_quoted_value_loses_its_quotes_and_a_number_stays_as_printed() -> None:
    attributes = attributes_from_das(DAS)
    assert attributes["change-evap_annual"]["units"] == "%"
    assert attributes["change-evap_annual"]["_FillValue"] == "-999.0"


def test_a_das_that_is_not_one_raises() -> None:
    with pytest.raises(ValueError, match="no Attributes declaration"):
        attributes_from_das("<html>400</html>")


def test_coordinate_axes_are_not_measurements() -> None:
    """time, lat, lon, Xc and Yc say where a value sits, not what was measured.

    Each is excluded for a different reason, and all four reasons are live in
    one real dataset: `time` and `lon` declare it in their own attributes,
    `Xc` and `Yc` are indexed only by themselves, and `projection_utm` holds
    the CRS and has no dimensions at all.
    """

    measured = measured_variables(variables_from_dds(DDS), attributes_from_das(DAS))
    assert [m["name"] for m in measured] == ["change-evap_annual"]
    only = measured[0]
    assert only["units"] == "%"
    assert only["long_name"] == "change in mean evapotranspiration"
    assert only["shape"] == "time=2, Yc=1550, Xc=1195"


def test_a_variable_with_no_unit_comes_back_without_one() -> None:
    """No unit is supplied and nothing is renamed."""

    dds = "Dataset {\n    Float32 snow[time = 1][Yc = 2][Xc = 2];\n} x.nc;\n"
    das = 'Attributes {\n    snow {\n        String long_name "snow";\n    }\n}\n'
    (measured,) = measured_variables(variables_from_dds(dds), attributes_from_das(das))
    assert measured["name"] == "snow"
    assert "units" not in measured
    assert measured["long_name"] == "snow"
