# `analysis/` · SQL de verificación del tablero y de la gobernanza

Todos los archivos usan nombres completos `cienciadatos-509301.gold.*`, se ejecutan tal cual con
`bq query --use_legacy_sql=false --location=us-central1 < analysis/<archivo>.sql` y llevan al final un comentario con el
resultado principal, el tiempo del job (`endTime − startTime` de `bq show -j --location=us-central1 --format=prettyjson <job_id>`),
los slot-ms, los bytes procesados y el tiempo total medido con `time` desde la CLI. Mediciones del 2026-09-20 con
`--nouse_cache` (dos rondas; se reporta la última, la anterior está en el comentario de cada archivo).

| Hoja | SQL | Cifra principal | Tiempo del job (ms) | Slot-ms | Bytes procesados | CLI (s) |
|---|---|---|---:|---:|---:|---:|
| H1 Demanda por modo y hora | `h1_demanda_modo_hora.sql` | hora pico = 906 950 abordajes (55,05 %); 07:00 = 197 491 (11,99 %) | 230 | 372 | 0,79 MB | 1,64 |
| H2 Demanda por zona | `h2_demanda_zona.sql` | Zona 17 = 148 554 (9,02 %); top 5 = 43,68 % | 1 367 | 22 263 | 0,81 MB | 3,65 |
| H3 Cobertura | `h3_cobertura.sql` | 11 zonas sin servicio de 26; Santa Catarina Pinula con 1 261 residentes del padrón | 203 | 107 | 8,18 MB | 1,55 |
| H4 Transbordo | `h4_transbordo.sql` | 41 485 de 56 848 personas multimodales = 72,98 % | 190 | 33 | 1,32 MB | 1,43 |
| H5 Caso MetroRiel | `h5_caso_metroriel.sql` | 5 zonas del trazado = puestos 1–5, 719 607 abordajes (43,68 %) | 267 | 306 | 0,30 MB | 1,54 |
| H6 KPIs | `h6_kpis.sql` | viajes junio 1 093 235 · usuarios activos 53 820 personas (110 762 tarjetas) · 11 zonas sin servicio · 72,98 % | 1 173 | 23 587 | 157,74 MB | 2,51 |
| H7 Linaje | `h7_linaje_de_una_cifra.sql` | 725 abordajes (TM, Z17, 2026-06-01) = 388 + 337 en 2 objetos jsonl de Bronze | 173 | 41 | 4,23 MB | 1,42 |
| H8 Estación candidata | `h8_transbordo_estacion_candidata.sql` | Zona 17: 23 704 personas usan ≥ 2 modos en la zona; MR 22 y Aerómetro Eje 1 - Torre 6 | 4 118 | 45 711 | 256,46 MB | 6,17 |
| Gobernanza (camino A) | `viajes_del_mes_a.sql` | viajes junio 2026 = 1 093 235 | 662 | 5 735 | 168,1 MB | 1,85 |
| Gobernanza (camino B) | `viajes_del_mes_b.sql` | viajes junio 2026 = 1 093 235 | 345 | 2 924 | 93,2 MB | 1,52 |

Notas:
- Los `agg_*` responden en < 0,3 s con < 10 MB; las consultas que leen `fct_abordaje` completa (H6, H8) suben a
  1–4 s y 150–260 MB. H7 lee solo 4,2 MB de `fct_abordaje` gracias a la partición por `fecha` y al cluster por
  `modo_id, zona_id`.
- H2 tarda más que H1 con los mismos bytes por la ventana acumulada (`SUM(SUM()) OVER (ORDER BY …)`) y el RANK.
- Las cifras coinciden con `docs/evidence/gold_resumen.md` (§4–§7) y con las pruebas de dbt (`assert_viajes_del_mes_dos_caminos`).
