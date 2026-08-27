# Methods table

Derived column `yoy_growth` uses `(v_t - v_{t-1}) / v_{t-1}`.
Derived column `index` uses `100 * v_t / v_base`. The base row is exactly 100.
Derived column `rank` uses `1 + count(peers in (period, measure) with value > v_t)`. 1 is the highest value in `(period, measure)`.
Ties share the minimum (competition) rank; the next rank skips.
Derived column `rank_change` uses `rank_{t-1} - rank_t`. Positive means moved up.
The first period has no YoY rate and no rank_change. A missing or zero base leaves index undefined.
Values are stored observations, not guesses.
Percent next to yoy_growth is display-only: `100 × yoy_growth`.

| entity | period | measure | value | yoy_growth (ratio) | yoy_growth × 100 | index | rank | rank_change | observation_id | source |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| Stebarn | 2023 | 06683: Adopsjoner, etter adopsjonstype, statistikkvariabel og år | 202 |  |  | 100 | 1 |  | c35149585e883145d3077abbfed744ee27d3d817 | ssb:06683 |
| Stebarn | 2024 | 06683: Adopsjoner, etter adopsjonstype, statistikkvariabel og år | 236 | 0.1683168317 | 16.83 | 116.8316832 | 1 | 0 | 791144f3b481c6e10f48bdd66ed649797d89118b | ssb:06683 |
| Utenlandsadopsjoner | 2023 | 06683: Adopsjoner, etter adopsjonstype, statistikkvariabel og år | 34 |  |  | 100 | 2 |  | 9dfbb0c4a931647520d856a3a81447e5e330e01f | ssb:06683 |
| Utenlandsadopsjoner | 2024 | 06683: Adopsjoner, etter adopsjonstype, statistikkvariabel og år | 24 | -0.2941176471 | -29.41 | 70.58823529 | 2 | 0 | 9cd3cc377bd311258bb7f1b88e582a50bcd7b30c | ssb:06683 |
