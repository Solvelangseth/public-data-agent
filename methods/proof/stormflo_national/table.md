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
| 1000ymax | 2025 | annenbygning | 27305 |  |  |  | 100 | 2 |  | 26fe573be3bda8926044874739ea2c116474e3d4 | stormflo:national.json |
| 1000ymax | 2100 | annenbygning | 44816 |  |  | 0.6413111152 | 164.1311115 | 2 | 0 | 6a7db2138ab402e094fad64662ff9314e7d06d6a | stormflo:national.json |
| 1000ymax | 2025 | areal_total | 740687936 |  |  |  | 100 | 2 |  | d9b2ba9e0b775fe32375e23aaa2803ae9248b2c9 | stormflo:national.json |
| 1000ymax | 2100 | areal_total | 1087847016 |  |  | 0.4686981698 | 146.869817 | 2 | 0 | ba6314872e905c12f4507b7b53dd783cbb2ee287 | stormflo:national.json |
| 1000ymax | 2025 | bebyggelse | 11061378 |  |  |  | 100 | 2 |  | 5cedf8fbbaf8967ae06d0983f8e2ed75baa678a8 | stormflo:national.json |
| 1000ymax | 2100 | bebyggelse | 32820637 |  |  | 1.967138181 | 296.7138181 | 2 | 0 | 110e30037bf3ed50cb6b1bccc3e7ba5bd8e82303 | stormflo:national.json |
| 1000ymax | 2025 | bygning_total | 156907 |  |  |  | 100 | 2 |  | d51a7c256eed5714314008ef29371a06b1d7ae82 | stormflo:national.json |
| 1000ymax | 2100 | bygning_total | 225626 |  |  | 0.4379600655 | 143.7960066 | 2 | 0 | 4d9e66b78392ae7abc6cb482302a4855cfbad848 | stormflo:national.json |
| 1000ymax | 2025 | natur | 660932767 |  |  |  | 100 | 2 |  | 312b96dbd054d81858258e3e4959a5f248a346f1 | stormflo:national.json |
| 1000ymax | 2100 | natur | 929690026 |  |  | 0.4066332801 | 140.663328 | 2 | 0 | bde52ce52c431158cfc884b6783120b22f149ab7 | stormflo:national.json |
| 1000ymax | 2025 | offentlige_anlegg | 699674 |  |  |  | 100 | 2 |  | e5f06cd5236f46a925de9584588fbf3a62cd330b | stormflo:national.json |
| 1000ymax | 2100 | offentlige_anlegg | 1620984 |  |  | 1.316770382 | 231.6770382 | 2 | 0 | 66014bda3efbf92818e0bb528f8f9d7b9debad58 | stormflo:national.json |
| 1000ymax | 2025 | offentlige_bygg | 2119 |  |  |  | 100 | 2 |  | fe7c84ec8346164b8efb937976a1097e1fc03fd1 | stormflo:national.json |
| 1000ymax | 2100 | offentlige_bygg | 4595 |  |  | 1.168475696 | 216.8475696 | 2 | 0 | b6da4bcbf4671fda20192da0a05ed76e13ee8a82 | stormflo:national.json |
| 1000ymax | 2025 | primarnaering | 67994117 |  |  |  | 100 | 2 |  | 1930d30483df3b0f3e241c67cbdc5d446d686746 | stormflo:national.json |
| 1000ymax | 2100 | primarnaering | 123715369 |  |  | 0.8195010754 | 181.9501075 | 2 | 0 | 0025e6d0c438dc9e813303c5a068a0988d826573 | stormflo:national.json |
| 1000ymax | 2025 | privat_naering | 19787 |  |  |  | 100 | 2 |  | d78477d2221457494f54b5662b1d9831fe63390a | stormflo:national.json |
| 1000ymax | 2100 | privat_naering | 31918 |  |  | 0.6130792945 | 161.3079294 | 2 | 0 | d8dab33fbc22eced0d5242b5cb691aa4acb9aeb1 | stormflo:national.json |
| 1000ymax | 2025 | private_bygninger | 107657 |  |  |  | 100 | 2 |  | 44f13ee0c016b65cb6fbdb8797213c371774b25a | stormflo:national.json |
| 1000ymax | 2100 | private_bygninger | 144191 |  |  | 0.3393555459 | 133.9355546 | 2 | 0 | 04fcbab98194be1ad776000acb1ad14eff76ccc1 | stormflo:national.json |
| 1000ymax | 2025 | samfunnskritiske_bygg | 39 |  |  |  | 100 | 2 |  | fc42009992667e670a52298068829b9a47215ced | stormflo:national.json |
| 1000ymax | 2100 | samfunnskritiske_bygg | 106 |  |  | 1.717948718 | 271.7948718 | 2 | 0 | 8d4f189700e391f6cc83d32b96b2582de7097cd4 | stormflo:national.json |
| 1000ymax | 2025 | veilengde_offentlig | 567094 |  |  |  | 100 | 2 |  | f3e2a588ba9a71a546a96c66e4a793772b75833c | stormflo:national.json |
| 1000ymax | 2100 | veilengde_offentlig | 1493430 |  |  | 1.633478753 | 263.3478753 | 2 | 0 | 89b38448cab7f1dd4c7a768ac25686500719ea8d | stormflo:national.json |
| 1000ymax | 2025 | veilengde_privat | 479439 |  |  |  | 100 | 2 |  | 8267202f3c739f1eafd998a85d64570d921e1e4c | stormflo:national.json |
| 1000ymax | 2100 | veilengde_privat | 1256073 |  |  | 1.619880736 | 261.9880736 | 2 | 0 | d5734d4f0ae7e9df6de453ef835703620ef0d4d6 | stormflo:national.json |
| 1000ymax | 2025 | veilengde_total | 1046532 |  |  |  | 100 | 2 |  | d5e8cfb1db9ac8b6ba3290618f17dcc14878876d | stormflo:national.json |
| 1000ymax | 2100 | veilengde_total | 2749494 |  |  | 1.627243123 | 262.7243123 | 2 | 0 | 6540b84b935955d95b607a136abd2f6a33a72b00 | stormflo:national.json |
| 200ymax | 2025 | annenbygning | 24231 |  |  |  | 100 | 3 |  | e17ce833df8f4a81b2635457dff6682ce55d0019 | stormflo:national.json |
| 200ymax | 2100 | annenbygning | 41960 |  |  | 0.7316660476 | 173.1666048 | 3 | 0 | 62c11bd02d15313287fea0d830f3938e91edc40e | stormflo:national.json |
| 200ymax | 2025 | areal_total | 683550913 |  |  |  | 100 | 3 |  | 34216d0b817271856c50e2d264ed1ac76ec051a5 | stormflo:national.json |
| 200ymax | 2100 | areal_total | 1025167891 |  |  | 0.4997681541 | 149.9768154 | 3 | 0 | 5941d59d59637ae066e8dc145ba5d0d64fc52cc7 | stormflo:national.json |
| 200ymax | 2025 | bebyggelse | 8872199 |  |  |  | 100 | 3 |  | f6dcb4cd250e1f175efab4145c980ad73ed7b640 | stormflo:national.json |
| 200ymax | 2100 | bebyggelse | 28279393 |  |  | 2.187416445 | 318.7416445 | 3 | 0 | a9523e4bc28de3b30e80c8bf258d76a8a52a4837 | stormflo:national.json |
| 200ymax | 2025 | bygning_total | 143895 |  |  |  | 100 | 3 |  | b258d08c818379da280a616ff5c204aab946798d | stormflo:national.json |
| 200ymax | 2100 | bygning_total | 215202 |  |  | 0.4955488377 | 149.5548838 | 3 | 0 | f41dbd749c61f0194e0009d415acfc965600a0ff | stormflo:national.json |
| 200ymax | 2025 | natur | 615180385 |  |  |  | 100 | 3 |  | 37e7afbc5f0674dd377d8a5d956e61b638be91a4 | stormflo:national.json |
| 200ymax | 2100 | natur | 882975848 |  |  | 0.4353120963 | 143.5312096 | 3 | 0 | e452064616165e1a8c5e5124cdc1d3642616b3fd | stormflo:national.json |
| 200ymax | 2025 | offentlige_anlegg | 547976 |  |  |  | 100 | 3 |  | 87aec61d75b5e4318dd9a29d15e11299a5766e85 | stormflo:national.json |
| 200ymax | 2100 | offentlige_anlegg | 1453097 |  |  | 1.651752996 | 265.1752996 | 3 | 0 | 798b901cbad8f666089f04a26f77c3582252f3c6 | stormflo:national.json |
| 200ymax | 2025 | offentlige_bygg | 1810 |  |  |  | 100 | 3 |  | 0c5488dd0676fa3d79726a47f90ecc51922a3bf4 | stormflo:national.json |
| 200ymax | 2100 | offentlige_bygg | 4176 |  |  | 1.30718232 | 230.718232 | 3 | 0 | 09a1487bd391f14f079379c24fac90b8594ecfea | stormflo:national.json |
| 200ymax | 2025 | primarnaering | 58950353 |  |  |  | 100 | 3 |  | 580a1af00b58bc665894d9df5814bbf8e819fa85 | stormflo:national.json |
| 200ymax | 2100 | primarnaering | 112459553 |  |  | 0.9076993992 | 190.7699399 | 3 | 0 | d64723c6f01c8a2c7aba6347d055f6e230117673 | stormflo:national.json |
| 200ymax | 2025 | privat_naering | 17802 |  |  |  | 100 | 3 |  | db98f974eefd1560416389435f9c347c859a284f | stormflo:national.json |
| 200ymax | 2100 | privat_naering | 30190 |  |  | 0.6958768678 | 169.5876868 | 3 | 0 | 5984160290481c46e67b90061a077da205217c8e | stormflo:national.json |
| 200ymax | 2025 | private_bygninger | 100022 |  |  |  | 100 | 3 |  | 067e63d98301bee8765f0de0befd7f38a93a0887 | stormflo:national.json |
| 200ymax | 2100 | private_bygninger | 138781 |  |  | 0.387504749 | 138.7504749 | 3 | 0 | e69e168469d83517247a9720a5badbe807a35604 | stormflo:national.json |
| 200ymax | 2025 | samfunnskritiske_bygg | 30 |  |  |  | 100 | 3 |  | 65aeb4a62b35466a321a9c7551dd9cf04bc06f8a | stormflo:national.json |
| 200ymax | 2100 | samfunnskritiske_bygg | 95 |  |  | 2.166666667 | 316.6666667 | 3 | 0 | 03495e20ce0520f079911ebc14483d8176e2505d | stormflo:national.json |
| 200ymax | 2025 | veilengde_offentlig | 479792 |  |  |  | 100 | 3 |  | 56dece9644ad98435dafdde96f8567cd0e007934 | stormflo:national.json |
| 200ymax | 2100 | veilengde_offentlig | 1298841 |  |  | 1.707091823 | 270.7091823 | 3 | 0 | dc30b3c20a6877e52df767a7d289665a36a23e02 | stormflo:national.json |
| 200ymax | 2025 | veilengde_privat | 366781 |  |  |  | 100 | 3 |  | 0c91eea8a0e9c0217b05a96a8ddf5eab058783e0 | stormflo:national.json |
| 200ymax | 2100 | veilengde_privat | 1112713 |  |  | 2.033725847 | 303.3725847 | 3 | 0 | c68e22ea1728fecfd2b3364e5cedb343e0fb6b4c | stormflo:national.json |
| 200ymax | 2025 | veilengde_total | 846564 |  |  |  | 100 | 3 |  | 131ffaad7c3454a8efde5b7a0f2caee6e52df8e7 | stormflo:national.json |
| 200ymax | 2100 | veilengde_total | 2411542 |  |  | 1.848623376 | 284.8623376 | 3 | 0 | 4481b2150aeefb942f10ca4a1a9958d538b96683 | stormflo:national.json |
| 20ymax | 2025 | annenbygning | 19507 |  |  |  | 100 | 4 |  | 8dbd931d86f467a7b5ac99077377fbb5fea6a431 | stormflo:national.json |
| 20ymax | 2100 | annenbygning | 37140 |  |  | 0.9039319219 | 190.3931922 | 4 | 0 | 3687b56f10e083a2b4bf4aa0558547944c8d4853 | stormflo:national.json |
| 20ymax | 2025 | areal_total | 593299417 |  |  |  | 100 | 4 |  | 79c5c00846177bfa78d6d7586ca2d82640e7dc6e | stormflo:national.json |
| 20ymax | 2100 | areal_total | 924890799 |  |  | 0.5588938275 | 155.8893827 | 4 | 0 | 46059321d10015d9b282c6b6a642d439bc4090dd | stormflo:national.json |
| 20ymax | 2025 | bebyggelse | 6244073 |  |  |  | 100 | 4 |  | 07f117acf043f1deee0a5b10c48ca94da81efc40 | stormflo:national.json |
| 20ymax | 2100 | bebyggelse | 21505798 |  |  | 2.444193878 | 344.4193878 | 4 | 0 | ac6c52b66e66e9a3ebd4391148a2b5d1adf9b212 | stormflo:national.json |
| 20ymax | 2025 | bygning_total | 123060 |  |  |  | 100 | 4 |  | b17af09e91da91d708b010debc1d888099662cf1 | stormflo:national.json |
| 20ymax | 2100 | bygning_total | 197567 |  |  | 0.6054526247 | 160.5452625 | 4 | 0 | 97f5bb7b2835df81c49155d40637e9c6653b3faf | stormflo:national.json |
| 20ymax | 2025 | natur | 541179120 |  |  |  | 100 | 4 |  | f5a35625ce6609d4a210c07512eb767d51ccb6b1 | stormflo:national.json |
| 20ymax | 2100 | natur | 807129749 |  |  | 0.4914281042 | 149.1428104 | 4 | 0 | c20936ffba9d3fdc1349e68c1515721f69e073e9 | stormflo:national.json |
| 20ymax | 2025 | offentlige_anlegg | 324745 |  |  |  | 100 | 4 |  | eef5f8f1cb855c90d8afad686bd032684e72ca23 | stormflo:national.json |
| 20ymax | 2100 | offentlige_anlegg | 1188726 |  |  | 2.660490539 | 366.0490539 | 4 | 0 | b848527d2dd92bf78fa9ad24137125131d53b19c | stormflo:national.json |
| 20ymax | 2025 | offentlige_bygg | 1373 |  |  |  | 100 | 4 |  | 40c1d15dac88d63e13c48fef321f6867929e084a | stormflo:national.json |
| 20ymax | 2100 | offentlige_bygg | 3503 |  |  | 1.551347414 | 255.1347414 | 4 | 0 | f2968595ba2549bbaf9bbf31e8158198a05b435b | stormflo:national.json |
| 20ymax | 2025 | primarnaering | 45551479 |  |  |  | 100 | 4 |  | 1dc01f7d82e3ad4b681a4db9aeba635971da10dc | stormflo:national.json |
| 20ymax | 2100 | primarnaering | 95066526 |  |  | 1.087012938 | 208.7012938 | 4 | 0 | cfb93b2780dff758a7b7da09a78b8f65aa0b72b2 | stormflo:national.json |
| 20ymax | 2025 | privat_naering | 14949 |  |  |  | 100 | 4 |  | 07fcdacc678929d89be4611afc5b3bba810b9f92 | stormflo:national.json |
| 20ymax | 2100 | privat_naering | 27246 |  |  | 0.8225968292 | 182.2596829 | 4 | 0 | 3b61ff2e76279408506fe3c2ce0c2312112a55d8 | stormflo:national.json |
| 20ymax | 2025 | private_bygninger | 87213 |  |  |  | 100 | 4 |  | cb0c325ed0974a75f331680d546eb09192a32d41 | stormflo:national.json |
| 20ymax | 2100 | private_bygninger | 129598 |  |  | 0.4859940605 | 148.5994061 | 4 | 0 | 700950f003f07c9ee3bd40b1f16705d66acd2dfe | stormflo:national.json |
| 20ymax | 2025 | samfunnskritiske_bygg | 18 |  |  |  | 100 | 4 |  | fefe1e30e62bb749a3eb756f7a91e7e41377608b | stormflo:national.json |
| 20ymax | 2100 | samfunnskritiske_bygg | 80 |  |  | 3.444444444 | 444.4444444 | 4 | 0 | 3fbf9b3d2ec9cd772dbb85b37bce26c6d499c264 | stormflo:national.json |
| 20ymax | 2025 | veilengde_offentlig | 388821 |  |  |  | 100 | 4 |  | b889392fc67ec87d903a2b33dff9df08d930e2fc | stormflo:national.json |
| 20ymax | 2100 | veilengde_offentlig | 1007007 |  |  | 1.589898694 | 258.9898694 | 4 | 0 | 7636971f0cdd98e6ecad4fc54aeacd3f3044675f | stormflo:national.json |
| 20ymax | 2025 | veilengde_privat | 216400 |  |  |  | 100 | 4 |  | ff3d0cbf61c4a43139f4a3df5662107b55cd347a | stormflo:national.json |
| 20ymax | 2100 | veilengde_privat | 885928 |  |  | 3.093937153 | 409.3937153 | 4 | 0 | 782c3a000fb5a5ce39d4fc34319a1ae038ef5f15 | stormflo:national.json |
| 20ymax | 2025 | veilengde_total | 605220 |  |  |  | 100 | 4 |  | 7fa83308bdbecc9bb92959dbe88899dcb0e21964 | stormflo:national.json |
| 20ymax | 2100 | veilengde_total | 1892930 |  |  | 2.127672582 | 312.7672582 | 4 | 0 | 71c6d47e705e5b3779e03abe21e88924e4f449bb | stormflo:national.json |
| highendwl | 2025 | annenbygning | 42213 |  |  |  | 100 | 1 |  | 5cf656d7a0bac9c2a4c08f4d0f54009251a3ffbb | stormflo:national.json |
| highendwl | 2100 | annenbygning | 57753 |  |  | 0.3681330396 | 136.813304 | 1 | 0 | 5aaa6f83f53eaf28e136d9ce7d25a3baa38cdc4e | stormflo:national.json |
| highendwl | 2150 | annenbygning | 68346 |  |  | 0.1834190432 | 161.9074693 | 1 | 0 | 50143f97cec9e5d2bcb032f153097da699eeee9f | stormflo:national.json |
| highendwl | 2025 | areal_total | 1049239234 |  |  |  | 100 | 1 |  | ba95c385078387df5c55961100c29837080543c9 | stormflo:national.json |
| highendwl | 2100 | areal_total | 1404067311 |  |  | 0.338176524 | 133.8176524 | 1 | 0 | 49737a0560fe153912e3037f11ec9d0f62919cab | stormflo:national.json |
| highendwl | 2150 | areal_total | 1657342560 |  |  | 0.1803868283 | 157.9565943 | 1 | 0 | c814d4888031020cdae5df3e43db58d582c000c3 | stormflo:national.json |
| highendwl | 2025 | bebyggelse | 29644840 |  |  |  | 100 | 1 |  | 615867959a8a607170773c138cfc53d5ec0eb317 | stormflo:national.json |
| highendwl | 2100 | bebyggelse | 56891578 |  |  | 0.9191055846 | 191.9105585 | 1 | 0 | f36145486bb8ebf64d19b6c748d5e58657b23fea | stormflo:national.json |
| highendwl | 2150 | bebyggelse | 73437867 |  |  | 0.2908389885 | 247.7256312 | 1 | 0 | f4be94bfc1589d42e02e2fa0d71390e2411e4a61 | stormflo:national.json |
| highendwl | 2025 | bygning_total | 215887 |  |  |  | 100 | 1 |  | 81c7b71919fc17108e8b95c836f78a2a588bab58 | stormflo:national.json |
| highendwl | 2100 | bygning_total | 272065 |  |  | 0.2602194667 | 126.0219467 | 1 | 0 | 4b2e3c13110d3870c0b478dba95c143414a4311f | stormflo:national.json |
| highendwl | 2150 | bygning_total | 309130 |  |  | 0.136235826 | 143.1906507 | 1 | 0 | 09d4791e6881a87f85df34e1b64d24449af2795c | stormflo:national.json |
| highendwl | 2025 | natur | 898289790 |  |  |  | 100 | 1 |  | 08f1d0f749f785151f93f364fad76e4d92cf41a3 | stormflo:national.json |
| highendwl | 2100 | natur | 1160883205 |  |  | 0.2923259486 | 129.2325949 | 1 | 0 | 89b711f158a47f6bea51e9f38eff82b17d41b2ac | stormflo:national.json |
| highendwl | 2150 | natur | 1347124963 |  |  | 0.1604310901 | 149.9655209 | 1 | 0 | 0ea1c1aa595ccb041d60f4d7dea5a99753ed9c47 | stormflo:national.json |
| highendwl | 2025 | offentlige_anlegg | 1493639 |  |  |  | 100 | 1 |  | 3c8ea97f85bcb9e628051536e10695df327d1ae9 | stormflo:national.json |
| highendwl | 2100 | offentlige_anlegg | 2502009 |  |  | 0.6751095814 | 167.5109581 | 1 | 0 | 71da7989c8b2de3035ce0b1020bd76c564c87999 | stormflo:national.json |
| highendwl | 2150 | offentlige_anlegg | 3257178 |  |  | 0.3018250534 | 218.069962 | 1 | 0 | d39de87ba56cdeb8d66444f390eca48b6d1615cb | stormflo:national.json |
| highendwl | 2025 | offentlige_bygg | 4197 |  |  |  | 100 | 1 |  | 6006a9312fb90b37967dc34e0c939f5a54dc592f | stormflo:national.json |
| highendwl | 2100 | offentlige_bygg | 6312 |  |  | 0.5039313796 | 150.393138 | 1 | 0 | 424326dbdab468befa6ce4e3c9dbf09f1502e7f8 | stormflo:national.json |
| highendwl | 2150 | offentlige_bygg | 7497 |  |  | 0.1877376426 | 178.6275911 | 1 | 0 | 5f4db0c96c5f517a458de71917e3912b4d6e36df | stormflo:national.json |
| highendwl | 2025 | primarnaering | 119810965 |  |  |  | 100 | 1 |  | 78d041584842b694e6ed78b9ec88f21c9bacddbc | stormflo:national.json |
| highendwl | 2100 | primarnaering | 183790519 |  |  | 0.5340041623 | 153.4004162 | 1 | 0 | 6478328955d116951bf46f391bd5d0f9c3cca526 | stormflo:national.json |
| highendwl | 2150 | primarnaering | 233522552 |  |  | 0.2705908513 | 194.9091655 | 1 | 0 | 563196d0bf31842833cfe779a7d72c5c54f04f30 | stormflo:national.json |
| highendwl | 2025 | privat_naering | 30379 |  |  |  | 100 | 1 |  | d28fd39c51a32af3dbb076d60d729d78f8fb3d9e | stormflo:national.json |
| highendwl | 2100 | privat_naering | 39551 |  |  | 0.3019190888 | 130.1919089 | 1 | 0 | 222490318e6ea55bf4fb8967d000f75d940975c4 | stormflo:national.json |
| highendwl | 2150 | privat_naering | 44346 |  |  | 0.1212358727 | 145.9758386 | 1 | 0 | 255ced77c81f48b21f918645378b2b88f078e0bd | stormflo:national.json |
| highendwl | 2025 | private_bygninger | 138984 |  |  |  | 100 | 1 |  | a63dfe463379d64b2673ffeac354fb9294fbc32a | stormflo:national.json |
| highendwl | 2100 | private_bygninger | 168255 |  |  | 0.2106069763 | 121.0606976 | 1 | 0 | 05f7723b0189db5422514febd0d12abded389e1c | stormflo:national.json |
| highendwl | 2150 | private_bygninger | 188694 |  |  | 0.1214763306 | 135.766707 | 1 | 0 | 6239e5017dbe29df582e51d8248d9560e18ba796 | stormflo:national.json |
| highendwl | 2025 | samfunnskritiske_bygg | 114 |  |  |  | 100 | 1 |  | 0af9f30571be6d375400813dd8d58ae970e138e3 | stormflo:national.json |
| highendwl | 2100 | samfunnskritiske_bygg | 194 |  |  | 0.701754386 | 170.1754386 | 1 | 0 | dbc46e159bc87298d03ea614a9398338d509d00d | stormflo:national.json |
| highendwl | 2150 | samfunnskritiske_bygg | 247 |  |  | 0.2731958763 | 216.6666667 | 1 | 0 | 4bae2f31f31756ebc310a006b46ee50a4f843fc6 | stormflo:national.json |
| highendwl | 2025 | veilengde_offentlig | 1378016 |  |  |  | 100 | 1 |  | a0501e4a99a92b4bc806208118d88b98b317fe1d | stormflo:national.json |
| highendwl | 2100 | veilengde_offentlig | 2614253 |  |  | 0.8971136765 | 189.7113676 | 1 | 0 | 4de2625bfa7a8699f0a54b957e6efad25e66ca9b | stormflo:national.json |
| highendwl | 2150 | veilengde_offentlig | 3556514 |  |  | 0.3604322152 | 258.0894561 | 1 | 0 | 8d4870beddba3bafd44d2ddf2fe5b79d97907bb6 | stormflo:national.json |
| highendwl | 2025 | veilengde_privat | 1166024 |  |  |  | 100 | 1 |  | 93d36d2fcbf13ab5dfc325a0bfaed322878788e5 | stormflo:national.json |
| highendwl | 2100 | veilengde_privat | 1918536 |  |  | 0.6453657901 | 164.536579 | 1 | 0 | c2bf072b299d1f2731f045dcd0ae3b101479b6fe | stormflo:national.json |
| highendwl | 2150 | veilengde_privat | 2422691 |  |  | 0.2627810998 | 207.7736822 | 1 | 0 | fc1bab7e40179102e3ca963694b6dc036bc78344 | stormflo:national.json |
| highendwl | 2025 | veilengde_total | 2544056 |  |  |  | 100 | 1 |  | 5857d4918d476bcf54ee39d14be115e708aa12d7 | stormflo:national.json |
| highendwl | 2100 | veilengde_total | 4532790 |  |  | 0.7817178553 | 178.1717855 | 1 | 0 | 7081d0c7d4971cb85751bf669381502bc541b966 | stormflo:national.json |
| highendwl | 2150 | veilengde_total | 5979209 |  |  | 0.3191012599 | 235.0266268 | 1 | 0 | fb0557e5955f8132c99585eb92b3953ef3fdf9a3 | stormflo:national.json |
| mhw | 2025 | annenbygning | 6842 |  |  |  | 100 | 5 |  | cc2e70dd4714694d051cafd19780a7614f40483f | stormflo:national.json |
| mhw | 2100 | annenbygning | 12680 |  |  | 0.8532592809 | 185.3259281 | 5 | 0 | 59aac374d64333d3b762f46c23c63682f07f9644 | stormflo:national.json |
| mhw | 2150 | annenbygning | 22033 |  |  | 0.7376182965 | 322.0257235 | 2 | 3 | 9e038d5b8ea91ba8dbcdcbced8eb34540bd4feca | stormflo:national.json |
| mhw | 2025 | areal_total | 165790969 |  |  |  | 100 | 5 |  | 24330f4a48bd590057422a50ad8a618e647cbbc0 | stormflo:national.json |
| mhw | 2100 | areal_total | 380157740 |  |  | 1.292994258 | 229.2994258 | 5 | 0 | 0cd1fc9659ee6bfdbc5b97c04b3e0415d55c13b1 | stormflo:national.json |
| mhw | 2150 | areal_total | 592640736 |  |  | 0.5589337626 | 357.4626167 | 2 | 3 | 1dd5951f7e182f95799c1248175ee74036422f06 | stormflo:national.json |
| mhw | 2025 | bebyggelse | 1882913 |  |  |  | 100 | 5 |  | d7a5ce822af766e71f17f07a1093cc325d1649aa | stormflo:national.json |
| mhw | 2100 | bebyggelse | 3713827 |  |  | 0.9723837479 | 197.2383748 | 5 | 0 | b91072a95bdf89b2cb7a9901180c28b7b9320cbe | stormflo:national.json |
| mhw | 2150 | bebyggelse | 8763816 |  |  | 1.359780356 | 465.4392423 | 2 | 3 | 20b679d407652881458884df4b773db15c86dd3a | stormflo:national.json |
| mhw | 2025 | bygning_total | 49293 |  |  |  | 100 | 5 |  | 8e45754fbfcd98eb48dd8a3fcd451608903e271f | stormflo:national.json |
| mhw | 2100 | bygning_total | 89417 |  |  | 0.813989816 | 181.3989816 | 5 | 0 | 48f134be0b509a9d27a0d167deda116cec5ea034 | stormflo:national.json |
| mhw | 2150 | bygning_total | 136408 |  |  | 0.5255264659 | 276.7289473 | 2 | 3 | 8b2161ee87b905a2abd1da3340c4c3ca002710e3 | stormflo:national.json |
| mhw | 2025 | natur | 158823394 |  |  |  | 100 | 5 |  | c2a763d8b1b64fe14d208dd6b39ed4fb00a461c0 | stormflo:national.json |
| mhw | 2100 | natur | 357212970 |  |  | 1.249120618 | 224.9120618 | 5 | 0 | 291b4d8d9fdf50672617474e75ce30c03275f3fe | stormflo:national.json |
| mhw | 2150 | natur | 539275028 |  |  | 0.5096737053 | 339.5438256 | 2 | 3 | 164c8cd881e2bdce6d786104551a5e0ff708dee0 | stormflo:national.json |
| mhw | 2025 | offentlige_anlegg | 14392 |  |  |  | 100 | 5 |  | b34d79d2d4f63bba54647385e1e4577bc8874eef | stormflo:national.json |
| mhw | 2100 | offentlige_anlegg | 81286 |  |  | 4.647998888 | 564.7998888 | 5 | 0 | 2ddbad10b22f357f1334e046908e90169b94c6cd | stormflo:national.json |
| mhw | 2150 | offentlige_anlegg | 358459 |  |  | 3.409849175 | 2490.682324 | 2 | 3 | 5e0a62d35f8835838c8896856b1a5a71ce6c55fe | stormflo:national.json |
| mhw | 2025 | offentlige_bygg | 583 |  |  |  | 100 | 5 |  | 360272fc6a35c951be9eb3599f1794a0e95f3071 | stormflo:national.json |
| mhw | 2100 | offentlige_bygg | 956 |  |  | 0.6397941681 | 163.9794168 | 5 | 0 | 20679198b7f9390ec137c9dcad25fffe93b9436b | stormflo:national.json |
| mhw | 2150 | offentlige_bygg | 1844 |  |  | 0.9288702929 | 316.2950257 | 2 | 3 | b5288a366a93afccda8dc7af0e7e89009526b7be | stormflo:national.json |
| mhw | 2025 | primarnaering | 5070270 |  |  |  | 100 | 5 |  | c9247aa6f1ebb6edb305cbe1bd6b95a9d4806448 | stormflo:national.json |
| mhw | 2100 | primarnaering | 19149657 |  |  | 2.776851529 | 377.6851529 | 5 | 0 | 656e722f7eecdd6093f295a5a38cb86c284fe720 | stormflo:national.json |
| mhw | 2150 | primarnaering | 44243433 |  |  | 1.310403419 | 872.6050684 | 2 | 3 | 4bf6fd70e168d547026e91d21151ce2256398814 | stormflo:national.json |
| mhw | 2025 | privat_naering | 7789 |  |  |  | 100 | 5 |  | d6f4bb41b5c0864b4ed0c5315f0dede3e5b5cf18 | stormflo:national.json |
| mhw | 2100 | privat_naering | 11613 |  |  | 0.4909487739 | 149.0948774 | 5 | 0 | f1cfab08b050f30111f25b21a0b042f68aa58319 | stormflo:national.json |
| mhw | 2150 | privat_naering | 17757 |  |  | 0.5290622578 | 227.9753499 | 2 | 3 | b7ad97909de0c2cceb71f99f64d6587268fbd669 | stormflo:national.json |
| mhw | 2025 | private_bygninger | 34074 |  |  |  | 100 | 5 |  | 8d122f7b17c8f12caf7e0df8f1f9bd2f841f864c | stormflo:national.json |
| mhw | 2100 | private_bygninger | 64157 |  |  | 0.8828725715 | 188.2872571 | 5 | 0 | b4f3827975887edab179d2beb6cb0295d539e665 | stormflo:national.json |
| mhw | 2150 | private_bygninger | 94744 |  |  | 0.4767523419 | 278.0536479 | 2 | 3 | 923b86cba65aea18a58bd4be4627288eac22c2d7 | stormflo:national.json |
| mhw | 2025 | samfunnskritiske_bygg | 5 |  |  |  | 100 | 5 |  | 5c2ab6a00b278e62574b51066599e6e55fe2ece4 | stormflo:national.json |
| mhw | 2100 | samfunnskritiske_bygg | 11 |  |  | 1.2 | 220 | 5 | 0 | 595cebafd92b9561bdd268bf99d8d28f2b21188a | stormflo:national.json |
| mhw | 2150 | samfunnskritiske_bygg | 30 |  |  | 1.727272727 | 600 | 2 | 3 | 2f21ac390c38d0f799130e4c2824825c70d66e25 | stormflo:national.json |
| mhw | 2025 | veilengde_offentlig | 299674 |  |  |  | 100 | 5 |  | 6047c0810f156147fea648c6b212e2f6bef106be | stormflo:national.json |
| mhw | 2100 | veilengde_offentlig | 328053 |  |  | 0.09469957354 | 109.4699574 | 5 | 0 | a08a2e90be504ddabb15a8cd9d1d8221005f3b4d | stormflo:national.json |
| mhw | 2150 | veilengde_offentlig | 495773 |  |  | 0.5112588515 | 165.437442 | 2 | 3 | eda3ef1818a837d34400ed084ae2a323a81425c1 | stormflo:national.json |
| mhw | 2025 | veilengde_privat | 16423 |  |  |  | 100 | 5 |  | b5de8bdca42f85bacf2588160fa85b35e8c91058 | stormflo:national.json |
| mhw | 2100 | veilengde_privat | 62592 |  |  | 2.811240334 | 381.1240334 | 5 | 0 | d41e150d5308eccf7fd1a62d27cafc0ee8e362e0 | stormflo:national.json |
| mhw | 2150 | veilengde_privat | 309807 |  |  | 3.94962615 | 1886.421482 | 2 | 3 | 16a89675555ec33dc3af69d346e6c01fffcef8a2 | stormflo:national.json |
| mhw | 2025 | veilengde_total | 316091 |  |  |  | 100 | 5 |  | f1adfc6bbadee1f7479b1166d559df0916c041a8 | stormflo:national.json |
| mhw | 2100 | veilengde_total | 390648 |  |  | 0.2358719483 | 123.5871948 | 5 | 0 | bcd6a66ef73c5c3088d187b31f54f48ae5e8ed86 | stormflo:national.json |
| mhw | 2150 | veilengde_total | 805577 |  |  | 1.0621557 | 254.8560383 | 2 | 3 | ada6beaa17bada0d69fbe1e0d3d9b0be35645ece | stormflo:national.json |
