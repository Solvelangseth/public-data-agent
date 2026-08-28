# Methods table

Derived column `yoy_growth` uses `(v_t - v_{t-1}) / v_{t-1}` for adjacent calendar years.
Derived column `period_change` uses `(v_t - v_prev) / v_prev` for other stored steps.
`period_change` describes the stored step. It is not a one-year rate.
Derived column `index` uses `100 * v_t / v_base`. The base row is exactly 100.
Derived column `rank` uses `1 + count(peers in (period, measure) with value > v_t)`. 1 is the highest value in `(period, measure)`.
Ties share the minimum (competition) rank; the next rank skips.
Derived column `rank_change` uses `rank_{t-1} - rank_t`. Positive means moved up.
The first period has no prior-period rate and no rank_change. A missing or zero base leaves index undefined.
Values are stored observations, not guesses.
Percent next to yoy_growth is display-only: `100 × yoy_growth`.

| entity | period | measure | value | yoy_growth (ratio) | yoy_growth × 100 | period_change (ratio) | index | rank | rank_change | observation_id | source |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| 200ymax | 2025 | offentlige_bygg | 1810 |  |  |  | 100 | 1 |  | 0c5488dd0676fa3d79726a47f90ecc51922a3bf4 | stormflo:national.json |
| 200ymax | 2025 | privat_naering | 17802 |  |  |  | 100 | 1 |  | db98f974eefd1560416389435f9c347c859a284f | stormflo:national.json |
