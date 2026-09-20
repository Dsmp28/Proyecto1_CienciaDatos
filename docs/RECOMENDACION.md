# Recomendación 2.2 · ¿Los cuatro modos integrados resuelven la movilidad metropolitana?

*Agencia Metropolitana de Transporte · operación del 2026-06-01 al 2026-07-15 (45 días), capa Gold
`cienciadatos-509301.gold`. Cada cifra cita el SQL de `analysis/` que la produce; tiempos en `docs/evidence/tablero_resumen.md`.*

## Contexto

La Agencia integró por primera vez las validaciones de Transmetro (BRT), Transurbano (bus), MetroRiel (tren ligero)
y Aerómetro (teleférico) bajo una sola definición de viaje (un abordaje válido) y un seudónimo de persona que permite
ver transbordos entre sistemas (ADR-008). En 45 días hubo **1 647 569 viajes** (`h6_kpis.sql`): Transurbano 786 398
(47,7 %), Transmetro 362 106, MetroRiel 295 511 y Aerómetro 203 554 (`h1_demanda_modo_hora.sql`). El tablero 2.1
responde dónde y cuándo se concentra la demanda, qué zonas no tienen servicio, cuántas personas combinan sistemas y si
el trazado de MetroRiel pasa por donde hace falta; este documento convierte esas respuestas en una recomendación.

## Qué dicen los datos

1. **La demanda se concentra en dos picos y en cinco zonas.** El 55,05 % de los viajes (906 950) ocurre en las ocho
   horas pico (05–08 y 16–19); las 07:00 solas concentran el 11,99 % (197 491) y el valle 09–15 es plano en ≈ 58 500
   viajes/hora (`h1_demanda_modo_hora.sql`). Las cinco zonas con más demanda (17, 12, 8, 6 y 1: 148 554 … 137 170
   viajes) acumulan el 43,68 % y son exactamente las del trazado de MetroRiel (`h2_demanda_zona.sql`, `h5_caso_metroriel.sql`).
2. **Once de 26 zonas no tienen estación ni parada de ningún modo** (Zonas 2, 3, 5, 14, 15, 16, 19, 21, 24, 25 y
   Santa Catarina Pinula). Diez no aparecen en el padrón; la excepción es **Santa Catarina Pinula: 1 261 personas del
   padrón (2 677 tarjetas) residen ahí sin servicio**, población comparable a la de cualquier zona atendida
   (1 208 en Mixco … 1 320 en Zona 12) (`h3_cobertura.sql`).
3. **El 72,98 % de las personas usa más de un sistema**: 41 485 de 56 848 (25 048 usan dos modos, 14 004 tres y
   2 433 los cuatro). La combinación más frecuente es Transmetro + Transurbano (12 477 personas); las personas de
   cuatro modos hacen 57,09 viajes cada una (`h4_transbordo.sql`). La integración no es un extra: es el uso mayoritario.
4. **Aerómetro es el modo de menor alcance y uso**: 9 zonas, 12,35 % de los viajes y solo 964 personas lo usan en
   exclusiva; la mitad de su demanda está en Mixco (57 907) y Zona 7 (43 808), y en sus otras siete zonas mueve
   ≈ 14 500 viajes cada una frente a ≈ 50 000 de Transurbano en las mismas zonas (`h2_demanda_zona.sql`,
   `h4_transbordo.sql`). MetroRiel, en cambio, opera como corredor: el 83,54 % de sus 295 511 viajes cambia de zona
   (`h5_caso_metroriel.sql`).

## ¿Resuelven el problema? Dónde sí y dónde no

**Sí en el corredor central.** Las zonas 17, 12 y 1 tienen los cuatro modos y las zonas 8 y 6 tres; ahí está el
43,68 % de la demanda y MetroRiel aporta entre el 36 % y el 48 % de los viajes de cada una: el trazado propuesto
atiende donde más se necesita (`h5_caso_metroriel.sql`). La integración también funciona en el uso: tres de cada
cuatro personas ya combinan sistemas (`h4_transbordo.sql`).

**No en tres frentes.** (a) *Cobertura:* 11 zonas sin servicio, una con 1 261 residentes del padrón
(`h3_cobertura.sql`). (b) *Profundidad de red:* las zonas 4, 9, 10 y 11 solo tienen Transmetro y Transurbano; suman
315 528 viajes (19,15 %) y son las cuatro últimas del ranking, lo que apunta a oferta insuficiente más que a falta
de necesidad (`h2_demanda_zona.sql`). (c) *Hora pico:* la red absorbe en 8 horas el 55 % de los viajes; ningún modo
adicional cambia esa saturación sin gestión de la demanda (`h1_demanda_modo_hora.sql`).

## Recomendación

**1. Construir la estación de transbordo integrada en la Zona 17, sobre la estación MR 22 de MetroRiel y la torre
Aerómetro Eje 1 - Torre 6.** Es la zona con más demanda (148 554 viajes, 9,02 %), una de las tres con los cuatro
modos y la primera en transbordo local: **23 704 personas usan dos o más sistemas dentro de la misma zona** y los
usuarios multimodales generan el 88,46 % de sus viajes (131 404). Las estaciones más cargadas por ellos son MR 22
(12 517 viajes) y Aerómetro Eje 1 - Torre 6 (13 380), con Transmetro Centra Sur - Centro 10 (2 936) y la parada 7 de
la ruta R-110 de Transurbano (2 188) como alimentadores (`h8_transbordo_estacion_candidata.sql`). La Zona 12
(23 004 personas; MR 03 y Eje 1 - Torre 4) es la segunda opción.

**2. Corredor descubierto: Santa Catarina Pinula.** Única zona sin servicio con demanda demostrable (1 261 personas
del padrón, `h3_cobertura.sql`). Se propone extender una ruta de Transurbano (el modo más barato de desplegar) desde
la Zona 10, la zona con servicio colindante en la geografía real, y medir su uso a los 30 días con las mismas
tablas Gold.

**3. Modo subutilizado: Aerómetro.** Antes de ampliarlo, concentrar frecuencia en los ejes de Mixco y Zona 7, donde
está la mitad de su demanda, e integrarlo tarifariamente con Transurbano, con el que comparte 1 546 usuarios de dos
modos y 3 928 de tres (`h4_transbordo.sql`); fuera de esos ejes cada torre mueve ≈ 320 viajes/día.

**4. Hora pico.** Reforzar frecuencias entre 06:00–08:00 y 17:00–18:00, cinco horas que concentran el 44,6 % de
los viajes (735 172), y promover horarios escalonados con los grandes empleadores (`h1_demanda_modo_hora.sql`).

## Límites de la evidencia

- Datos sintéticos (`docs/generar_red_metropolitana.py`, 45 días, escala 0,08): las distribuciones son más uniformes
  que en una red real (≈ 1 250 residentes del padrón por zona), así que diferencias pequeñas entre zonas (17 vs 12:
  651 viajes) no son significativas; las de orden (4 modos vs 2, pico vs valle, 11 zonas sin servicio) sí.
- La identidad de persona entre modos depende del vínculo determinista de ADR-008 (identificador base compartido e
  inversión del hash sin sal de Aerómetro); sin él, el 72,98 % no sería medible.
- Aerómetro no tuvo filas en cuarentena (0 de 203 554, `docs/evidence/calidad_resumen.md`): su bajo volumen es
  demanda real, no pérdida de datos. Transurbano sí perdió 5 003 filas (0,6 %: paradas nulas y fechas futuras).
- "Usuario activo" (53 820 personas (110 762 tarjetas) tarjetas) se calcula a `fecha_referencia = 2026-07-16`, no a la fecha del sistema.
- Gold no tiene geometrías ni distancias entre estaciones: la ubicación exacta de la estación de transbordo dentro
  de la Zona 17 requiere un estudio de sitio.
