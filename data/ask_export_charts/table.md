# Methods table

Derived column `yoy_growth` uses `(v_t - v_{t-1}) / v_{t-1}`.
Derived column `index` uses `100 * v_t / v_base`. The base row is exactly 100.
The first period has no YoY rate. A missing or zero base leaves index undefined.
Values are stored observations, not guesses.
Percent next to yoy_growth is display-only: `100 × yoy_growth`.

| entity | period | measure | value | yoy_growth (ratio) | yoy_growth × 100 | index | observation_id | source |
| --- | --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| 030108 | 2024 | Personer (antall) | 55987 |  |  | 100 | 030108:2024 | ssb:11763 |
| 030108 | 2025 | Personer (antall) | 57017 | 0.0183971279 | 1.84 | 101.8397128 | 030108:2025 | ssb:11763 |
