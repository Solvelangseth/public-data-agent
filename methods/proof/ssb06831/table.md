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
| 16-19 år / Kvinner / Samboere | 2021 | 06831: Andel personer (prosent), etter samlivsform, kjønn, alder, statistikkvariabel og år | 3 |  |  | 100 | 2 |  | 81e014346d5be156e8604196c87611b17cc05229 | ssb:06831 |
| 16-19 år / Kvinner / Samboere | 2022 | 06831: Andel personer (prosent), etter samlivsform, kjønn, alder, statistikkvariabel og år | 2 | -0.3333333333 | -33.33 | 66.66666667 | 2 | 0 | 48ddb1a78ce5bd1c41a1321568f95a818b545be9 | ssb:06831 |
| 20-24 år / Kvinner / Samboere | 2021 | 06831: Andel personer (prosent), etter samlivsform, kjønn, alder, statistikkvariabel og år | 23 |  |  | 100 | 1 |  | fdf49768b007ae1f825fa117b97616134503ad85 | ssb:06831 |
| 20-24 år / Kvinner / Samboere | 2022 | 06831: Andel personer (prosent), etter samlivsform, kjønn, alder, statistikkvariabel og år | 23 | 0 | 0 | 100 | 1 | 0 | 5aa6ecf9688fb152016f02db8a249993787abbbf | ssb:06831 |
