# Methods table

Derived column `yoy_growth` uses `(v_t - v_{t-1}) / v_{t-1}`.
Derived column `index` uses `100 * v_t / v_base`. The base row is exactly 100.
The first period has no YoY rate. A missing or zero base leaves index undefined.
Values are stored observations, not guesses.
Percent next to yoy_growth is display-only: `100 × yoy_growth`.

| entity | period | measure | value | yoy_growth (ratio) | yoy_growth × 100 | index | observation_id | source |
| --- | --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| Oslo (Kristiania og Aker) i alt | 2020 | Folkemengden i alt (antall personer) | 693494 |  |  | 100 | 4bbaaebeedb1184d6ea24978291da4644ff24d18 | datanorge:fc22c19b-5347-3b20-aa1b-ae534f178f57 |
| Oslo (Kristiania og Aker) i alt | 2021 | Folkemengden i alt (antall personer) | 697010 | 0.005069978976 | 0.507 | 100.5069979 | 5a1e6107fc5046770b1f0d8b2eaf3c137ee235ec | datanorge:fc22c19b-5347-3b20-aa1b-ae534f178f57 |
| Oslo (Kristiania og Aker) i alt | 2022 | Folkemengden i alt (antall personer) | 699827 | 0.004041548902 | 0.4042 | 100.9132018 | 0e3f55d28c9e888bfc2011fa6f4605636e9534a0 | datanorge:fc22c19b-5347-3b20-aa1b-ae534f178f57 |
| Oslo (Kristiania og Aker) i alt | 2023 | Folkemengden i alt (antall personer) | 709037 | 0.01316039535 | 1.316 | 102.2412595 | 128650ba035ef623f99ee12a4051b7a28e0f8d21 | datanorge:fc22c19b-5347-3b20-aa1b-ae534f178f57 |
| Oslo (Kristiania og Aker) i alt | 2024 | Folkemengden i alt (antall personer) | 717710 | 0.0122320838 | 1.223 | 103.4918831 | 298b094b34d6c98d4a9c188e3b466e1ab7a3cbe2 | datanorge:fc22c19b-5347-3b20-aa1b-ae534f178f57 |
| Oslo (Kristiania og Aker) i alt | 2025 | Folkemengden i alt (antall personer) | 724290 | 0.009168048376 | 0.9168 | 104.4407017 | 9a9a8db31b374047c6b1b792cf12d54efe1db81d | datanorge:fc22c19b-5347-3b20-aa1b-ae534f178f57 |
| Oslo (Kristiania og Aker) i alt | 2026 | Folkemengden i alt (antall personer) | 728714 | 0.006108050643 | 0.6108 | 105.0786308 | 01a055cacd3c3acbfa39465d6c33b6fee49e8a43 | datanorge:fc22c19b-5347-3b20-aa1b-ae534f178f57 |
