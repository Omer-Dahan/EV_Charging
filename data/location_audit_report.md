# Location Audit Report — 2026-09-28 20:10

Read-only audit. **No station was changed, merged or deleted.** Every fix below is a proposal for manual review.

## Summary

| Metric | Count |
|--------|------:|
| Total stations in dataset | 3360 |
| Stations scanned | 3360 |
| **Outside Israel (foreign/test)** | **23** ⚠️ high |
| **Water coordinates (coastal)** | **0** ⚠️ high |
| Coastal suspects not verified (lookup failed) | 0 |
| **Far from city (>25 km)** | **82** ⚠️ high |
| Far from city (12–25 km) | 34 ⚡ medium |
| Duplicate pairs with divergent coords | 97 |
| Stations without a city (distance check skipped) | 83 |
| Stations whose city could not be geocoded (skipped) | 129 |
| Nominatim requests made | 69 |
| Nominatim 429 responses | 0 |
| Nominatim failed lookups | 0 |
| Elapsed time | 76s |

## Outside Israel (foreign / test stations)

| id | name | city | lat | lng | source | g | reason |
|---:|------|------|----:|----:|--------|:-:|---|
| 1484 | Gnrgy ES Office | Barcelona | 41.378115 | 2.133519 | cello,auto_coil | 0 | Outside Israel bbox (lat=41.3781, lng=2.1335) |
| 1518 | Demo site | city | 21.000000 | 20.000000 | cello | 0 | Outside Israel bbox (lat=21.0000, lng=20.0000) |
| 1520 | בנגלור 1 | בנגלור | 12.908742 | 77.650445 | cello,auto_coil | 0 | Outside Israel bbox (lat=12.9087, lng=77.6504) |
| 1524 | Adgar Wave Public | Warszawa | 52.177042 | 21.001314 | cello,auto_coil | 0 | Outside Israel bbox (lat=52.1770, lng=21.0013) |
| 1525 | Adgar Park West | Warszawa | 52.210151 | 20.953259 | cello,auto_coil | 0 | Outside Israel bbox (lat=52.2102, lng=20.9533) |
| 1527 | Adgar Plaza Public | Warszawa | 52.181012 | 20.996208 | cello,auto_coil | 0 | Outside Israel bbox (lat=52.1810, lng=20.9962) |
| 1529 | Heron’s Hill | toronto | 43.775021 | -79.338340 | cello,auto_coil | 0 | Outside Israel bbox (lat=43.7750, lng=-79.3383) |
| 1531 | Adgar Theater Public | Antwerpen | 51.220050 | 4.415620 | cello,auto_coil | 0 | Outside Israel bbox (lat=51.2201, lng=4.4156) |
| 1532 | Adgar Renaissance Tower | Warszawa | 52.230130 | 20.970950 | cello,auto_coil | 0 | Outside Israel bbox (lat=52.2301, lng=20.9709) |
| 1534 | Adgar Plaza High Speed | Warszawa | 52.180733 | 20.996094 | cello,auto_coil | 0 | Outside Israel bbox (lat=52.1807, lng=20.9961) |
| 1535 | 9050 Yonge St | Richmond Hill, ON | 43.846844 | -79.431998 | cello,auto_coil | 0 | Outside Israel bbox (lat=43.8468, lng=-79.4320) |
| 1536 | Adgar Plantin | Antwerpen | 51.210928 | 4.418498 | cello,auto_coil | 0 | Outside Israel bbox (lat=51.2109, lng=4.4185) |
| 1545 | Adgar 120 Bloor | Toronto | 43.671213 | -79.383809 | cello,auto_coil | 0 | Outside Israel bbox (lat=43.6712, lng=-79.3838) |
| 1561 | 111 Gordon Baker Rd | Toronto | 43.802029 | -79.343367 | cello | 0 | Outside Israel bbox (lat=43.8020, lng=-79.3434) |
| 1562 | 40 Eglinton Ave E | Toronto | 43.706876 | -79.398617 | cello,auto_coil | 0 | Outside Israel bbox (lat=43.7069, lng=-79.3986) |
| 1578 | 1270-1300 Central | Mississauga | 43.567596 | -79.664159 | cello,auto_coil | 0 | Outside Israel bbox (lat=43.5676, lng=-79.6642) |
| 1606 | Adgar 302 Town Centre Blvd | Markham | 43.859820 | -79.340186 | cello,auto_coil | 0 | Outside Israel bbox (lat=43.8598, lng=-79.3402) |
| 1620 | Adgar 350 Burnhamthorpe | Mississauga | 43.585301 | -79.643339 | cello,auto_coil | 0 | Outside Israel bbox (lat=43.5853, lng=-79.6433) |
| 1626 | 5000 | Kraków | 50.048278 | 19.943406 | cello | 0 | Outside Israel bbox (lat=50.0483, lng=19.9434) |
| 3196 | Gnrgyאבגדהוזחטיכלמנסעפצקרש |  | 12.919809 | 77.650814 | auto_coil | 0 | Outside Israel bbox (lat=12.9198, lng=77.6508) |
| 3197 | , ישראל |  | 77.000000 | 12.000000 | auto_coil | 0 | Outside Israel bbox (lat=77.0000, lng=12.0000) |
| 3198 | Charging station test |  | 12.950000 | 77.651598 | auto_coil | 0 | Outside Israel bbox (lat=12.9500, lng=77.6516) |
| 3199 | בנגלור 2 |  | 12.923473 | 77.651469 | auto_coil | 0 | Outside Israel bbox (lat=12.9235, lng=77.6515) |

## Water Coordinates (Mediterranean coast)

None found.


- City distance > 25 km: city center suspect = 29, station outlier = 12, unconfirmed = 41
- City distance 12–25 km: city center suspect = 5, station outlier = 12, unconfirmed = 17

"city center suspect" rows most likely point at a wrong Nominatim geocode of the city name (e.g. a same-named neighbourhood elsewhere), not a wrong station. "station outlier" rows are the real candidates.

## Far from City Center (>25 km) — High Severity

| id | name | city | lat | lng | source | g | distance_km | verdict |
|---:|------|------|----:|----:|--------|:-:|---|---|
| 1531 | Adgar Theater Public | Antwerpen | 51.220050 | 4.415620 | cello,auto_coil | 0 | 3215.1 | unconfirmed: only 2 station(s) in this city |
| 1536 | Adgar Plantin | Antwerpen | 51.210928 | 4.418498 | cello,auto_coil | 0 | 3214.5 | unconfirmed: only 2 station(s) in this city |
| 1626 | 5000 | Kraków | 50.048278 | 19.943406 | cello | 0 | 2342.6 | unconfirmed: only 1 station(s) in this city |
| 3027 | מחסן מלאי | בית רימון | 31.046051 | 34.851612 | cello,auto_coil,data_gov | 1 | 198.2 | unconfirmed: only 1 station(s) in this city |
| 464 | דור אלון צומת הגומא | הגומא | 33.170044 | 35.570974 | cello,auto_coil,evm,data_gov,afcon | 1 | 163.4 | unconfirmed: only 1 station(s) in this city |
| 1752 | אלרום | אלרום | 33.178548 | 35.771916 | cello,data_gov | 1 | 151.1 | unconfirmed: only 1 station(s) in this city |
| 1490 | קניון צים סנטר מעלות | מעלות | 33.021167 | 35.280394 | cello,evm,data_gov | 1 | 140.3 | unconfirmed: only 1 station(s) in this city |
| 229 | כפר הנופש רמות , כנרת | רמות | 32.859332 | 35.659963 | cello,data_gov,afcon | 1 | 124.0 | unconfirmed: only 1 station(s) in this city |
| 551 | דור אלון-חצור הגלילית | חצור | 32.980749 | 35.555218 | cello,afcon,zen | 0 | 118.3 | unconfirmed: only 1 station(s) in this city |
| 2173 | Mechinat otzem | Neve | 31.163300 | 34.334600 | cello,data_gov | 1 | 114.5 | unconfirmed: only 1 station(s) in this city |
| 1939 | Ar Bracha-kindergarten | Bracha | 32.194712 | 35.267404 | cello,data_gov,interev | 1 | 113.1 | unconfirmed: only 2 station(s) in this city |
| 1917 | Ar Bracha-Kashti | Bracha | 32.191895 | 35.264433 | cello,data_gov,interev | 1 | 112.7 | unconfirmed: only 2 station(s) in this city |
| 2324 | TEN Ashkelon - HaMetakhnen 10 | South District | 31.635131 | 34.553519 | cello,auto_coil,data_gov | 1 | 110.5 | unconfirmed: only 2 station(s) in this city |
| 2333 | TEN Zavdiel | South District | 31.652614 | 34.762759 | cello,auto_coil,data_gov | 1 | 108.5 | unconfirmed: only 2 station(s) in this city |
| 1497 | קיבוץ תל קציר | תל | 32.705753 | 35.619317 | cello,auto_coil,data_gov | 1 | 104.6 | unconfirmed: only 1 station(s) in this city |
| 1203 | Commercial Complex Bitans \|  Bitan Aharon | Beit Aharon | 32.361358 | 34.868017 | cello,auto_coil | 0 | 104.0 | unconfirmed: only 1 station(s) in this city |
| 581 | פז - עין חצבה - עמדה מהירה 2 | כביש הערבה | 30.798883 | 35.244076 | cello,auto_coil,evm,paz | 0 | 103.6 | city center suspect: station is with the other 2 stations of this city; geocoded center is 104 km away |
| 582 | עין חצבה - עמדה מהירה 1 | כביש הערבה | 30.798883 | 35.244076 | cello | 0 | 103.6 | city center suspect: station is with the other 2 stations of this city; geocoded center is 104 km away |
| 2671 | מפעלי ים המלח סדום חניה | סדום | 31.029189 | 35.363469 | cello,data_gov | 1 | 103.1 | unconfirmed: only 1 station(s) in this city |
| 3174 | חניית הנהלה מתחם שורק למורשים בלבד | ראשון לציון | 31.046051 | 34.851612 | cello | 0 | 102.1 | station outlier: far from the other 68 stations of this city too |
| 3012 | סונול שפיה | כביש 67 | 32.587326 | 34.980289 | cello,auto_coil | 0 | 99.4 | unconfirmed: only 1 station(s) in this city |
| 561 | דור אלון-פארק אפק, ראש העין | ראש עין | 32.085878 | 34.980432 | cello,auto_coil,afcon | 0 | 99.3 | unconfirmed: only 1 station(s) in this city |
| 1311 | Isrotel Kayma Hotel \| dead sea | Unknown | 31.193318 | 35.362394 | cello,auto_coil | 0 | 94.4 | station outlier: far from the other 2 stations of this city too |
| 2722 | חניה שכונה מערבית | קיבוץ גבת | 32.676940 | 35.210326 | cello,data_gov | 1 | 91.1 | city center suspect: station is with the other 3 stations of this city; geocoded center is 91 km away |
| 2746 | חניון הכלבו | קיבוץ גבת | 32.675953 | 35.212555 | cello,data_gov | 1 | 91.1 | city center suspect: station is with the other 3 stations of this city; geocoded center is 91 km away |
| 2725 | חניון כרם דרום | קיבוץ גבת | 32.673338 | 35.211440 | cello,data_gov | 1 | 90.8 | city center suspect: station is with the other 3 stations of this city; geocoded center is 91 km away |
| 2764 | חניון אשטרומים | קיבוץ גבת | 32.673755 | 35.211990 | cello,data_gov | 1 | 90.8 | city center suspect: station is with the other 3 stations of this city; geocoded center is 91 km away |
| 2939 | אולם מופעים אפיקים | קיבוץ אפיקים | 32.682312 | 35.580032 | cello,auto_coil,data_gov | 1 | 87.0 | city center suspect: station is with the other 3 stations of this city; geocoded center is 87 km away |
| 2587 | קיבוץ אפיקים | קיבוץ אפיקים | 32.679845 | 35.578389 | cello,auto_coil,data_gov | 1 | 86.7 | city center suspect: station is with the other 3 stations of this city; geocoded center is 87 km away |
| 2662 | קיבוץ אפיקים - חניה פרבר | קיבוץ אפיקים | 32.680564 | 35.577730 | cello,auto_coil,data_gov | 1 | 86.7 | city center suspect: station is with the other 3 stations of this city; geocoded center is 87 km away |
| 2938 | חניה שכונת כוח אפיקים | קיבוץ אפיקים | 32.680832 | 35.574417 | cello,auto_coil,data_gov | 1 | 86.5 | city center suspect: station is with the other 3 stations of this city; geocoded center is 87 km away |
| 3063 | אשדוד DC - ברק בן אבינועם 6 | אשדוד | 31.046051 | 34.851612 | cello | 0 | 85.7 | station outlier: far from the other 61 stations of this city too |
| 743 | The Israeli addiction Center | Unknown | 31.794683 | 35.241035 | cello,auto_coil,data_gov | 1 | 81.3 | city center suspect: station is with the other 2 stations of this city; geocoded center is 81 km away |
| 3272 | מודיעין הראל | המכונאי 2 | 31.895316 | 34.959504 | evm | 0 | 76.2 | unconfirmed: only 1 station(s) in this city |
| 1864 | בית השותפויות | אכזיב | 33.056934 | 35.104928 | cello | 0 | 72.0 | unconfirmed: only 1 station(s) in this city |
| 1487 | המרכז של קרסו אבן יהודה | אבן יהודה | 32.269877 | 34.888621 | cello,evm,data_gov | 1 | 62.5 | unconfirmed: only 2 station(s) in this city |
| 3128 | דלק דרור (זקס) אבן יהודה | אבן יהודה | 32.256170 | 34.877440 | cello,auto_coil,evm,data_gov,zen | 1 | 61.8 | unconfirmed: only 2 station(s) in this city |
| 3182 | דלק שדי תרומות (בכורה) | כביש 90 | 32.448380 | 35.483040 | cello,auto_coil | 0 | 60.7 | unconfirmed: only 1 station(s) in this city |
| 2271 | Scala office | Neve Yamin | 32.169665 | 34.933477 | cello,data_gov | 1 | 56.7 | unconfirmed: only 1 station(s) in this city |
| 641 | קריית צאנז נתניה עמדת AC כפולה | נתניה | 32.820125 | 34.999321 | cello | 0 | 56.3 | station outlier: far from the other 63 stations of this city too |
| 105 | צומת גוש ציון | גוש עציון | 31.644813 | 35.130882 | cello,auto_coil,data_gov,afcon | 1 | 55.3 | unconfirmed: only 2 station(s) in this city |
| 721 | Rami Levy_Gush Etzion Branch | גוש עציון | 31.644691 | 35.130758 | cello,auto_coil | 0 | 55.3 | unconfirmed: only 2 station(s) in this city |
| 1814 | יקבי גוש עציון | צומת | 31.648277 | 35.129976 | cello,auto_coil,data_gov | 1 | 54.6 | unconfirmed: only 1 station(s) in this city |
| 1351 | Shufersal ltd \| Rehovot HaHadasha \| DC charge | Unknown | 31.880520 | 34.812311 | cello | 0 | 53.1 | station outlier: far from the other 2 stations of this city too |
| 2758 | חניה-בית מוסדות | קיבוץ דליה | 32.590879 | 35.075777 | cello,auto_coil,data_gov | 1 | 52.6 | unconfirmed: only 2 station(s) in this city |
| 2653 | קיבוץ דליה - חניה שכונה כב | קיבוץ דליה | 32.588037 | 35.070318 | cello,auto_coil,data_gov | 1 | 52.1 | unconfirmed: only 2 station(s) in this city |
| 3502 | דלק פונדק הרים | נווה אילן | 31.804448 | 35.095034 | zen | 0 | 51.2 | unconfirmed: only 2 station(s) in this city |
| 1479 | כפר מנחם | כפר | 31.729733 | 34.838861 | cello,auto_coil,data_gov | 1 | 50.2 | unconfirmed: only 1 station(s) in this city |
| 1509 | חדשות 12 (לעובדים ואורחים בלבד) | נווה אילן | 31.808323 | 35.080879 | cello,auto_coil,data_gov | 1 | 50.0 | unconfirmed: only 2 station(s) in this city |
| 626 | הרואה בקפה - DC 40 | חיפה | 32.393116 | 34.915413 | cello,auto_coil | 0 | 48.0 | station outlier: far from the other 97 stations of this city too |
| 1471 | פונדק כושי הק"מ 101 | כביש הערבה | 30.306744 | 35.134586 | cello,evm,data_gov,zen | 1 | 47.9 | station outlier: far from the other 2 stations of this city too |
| 1436 | Mirage Parking Lot \| Dimona Municipality | מחוז הדרום | 31.067568 | 35.037286 | cello | 0 | 45.3 | city center suspect: station is with the other 2 stations of this city; geocoded center is 45 km away |
| 1437 | The Post Office Parking Lot \| Dimona Municipa | מחוז הדרום | 31.066557 | 35.034154 | cello | 0 | 45.1 | city center suspect: station is with the other 2 stations of this city; geocoded center is 45 km away |
| 1435 | The Hamtens parking lot \| Dimona Municipality | מחוז הדרום | 31.064381 | 35.032085 | cello | 0 | 44.8 | city center suspect: station is with the other 2 stations of this city; geocoded center is 45 km away |
| 1115 | Leonardo Club Hotel - Fattal Hotels ltd \| Dea | Dead Sea | 31.164185 | 35.367479 | cello,auto_coil | 0 | 43.4 | city center suspect: station is with the other 3 stations of this city; geocoded center is 40 km away |
| 1234 | Megiddo Junction \| Commercial Center Terminal | North District | 32.571526 | 35.184288 | cello,evm | 0 | 42.2 | city center suspect: station is with the other 7 stations of this city; geocoded center is 35 km away |
| 3104 | דלק מסמיה | מלאכי | 31.758350 | 34.783680 | cello,auto_coil,data_gov,zen | 1 | 41.1 | unconfirmed: only 1 station(s) in this city |
| 2312 | Kochav Yokneam business center | North District | 32.662569 | 35.105113 | cello,auto_coil,evm,data_gov | 1 | 41.0 | city center suspect: station is with the other 7 stations of this city; geocoded center is 35 km away |
| 837 | Nevo Hotel - Isrotel ltd \| Dead Sea | Dead Sea | 31.192989 | 35.361064 | cello,auto_coil,data_gov | 1 | 40.4 | city center suspect: station is with the other 3 stations of this city; geocoded center is 40 km away |
| 271 | אואזיס ים המלח-לאורחי המלון | ים המלח | 31.195378 | 35.361268 | cello,data_gov,afcon | 1 | 40.2 | city center suspect: station is with the other 4 stations of this city; geocoded center is 39 km away |
| 854 | Isrotel Noga Hotel \| Dead Sea | Dead Sea | 31.198361 | 35.361836 | cello,auto_coil,data_gov | 1 | 39.9 | city center suspect: station is with the other 3 stations of this city; geocoded center is 40 km away |
| 301 | מלון לוט-לאורחי המלון | ים המלח | 31.200025 | 35.364468 | cello,data_gov,afcon | 1 | 39.6 | city center suspect: station is with the other 4 stations of this city; geocoded center is 39 km away |
| 2328 | Nir David - Movement World | North District | 32.505952 | 35.457530 | cello,data_gov | 1 | 39.6 | station outlier: far from the other 7 stations of this city too |
| 3489 | Narkisim Tzuva | Tzova | 31.781381 | 35.120214 | interev | 0 | 39.6 | unconfirmed: only 1 station(s) in this city |
| 212 | מילוס-ים המלח -לאורחי המלון | ים המלח | 31.201437 | 35.364503 | cello,auto_coil,evm,data_gov,afcon | 1 | 39.5 | city center suspect: station is with the other 4 stations of this city; geocoded center is 39 km away |
| 1162 | Vert Hotel \| Dead Sea | Dead Sea | 31.200606 | 35.365269 | cello | 0 | 39.5 | city center suspect: station is with the other 3 stations of this city; geocoded center is 40 km away |
| 2329 | Nir David - Laundry | North District | 32.506612 | 35.456425 | cello,auto_coil,data_gov | 1 | 39.5 | station outlier: far from the other 7 stations of this city too |
| 251 | הוד-ים מלח -לאורחי המלון | ים המלח | 31.201942 | 35.363640 | cello,evm,data_gov,afcon | 1 | 39.4 | city center suspect: station is with the other 4 stations of this city; geocoded center is 39 km away |
| 1484 | Gnrgy ES Office | Barcelona | 41.378115 | 2.133519 | cello,auto_coil | 0 | 38.6 | unconfirmed: only 1 station(s) in this city |
| 1109 | Hevel Eilot \| Eilot | Eilot | 29.894524 | 35.065298 | cello,auto_coil | 0 | 36.2 | city center suspect: station is with the other 3 stations of this city; geocoded center is 36 km away |
| 1101 | Eilot Council Square \| Eilot | Eilot | 29.892948 | 35.064030 | cello,auto_coil | 0 | 36.0 | city center suspect: station is with the other 3 stations of this city; geocoded center is 36 km away |
| 556 | דור אלון -ג'ת | דור אלון | 32.388923 | 35.042966 | cello,auto_coil,afcon | 0 | 34.9 | unconfirmed: only 1 station(s) in this city |
| 2302 | Givat Haim Ihud - Hot Spot | Center District | 32.399125 | 34.929527 | cello,auto_coil,data_gov | 1 | 34.8 | station outlier: far from the other 4 stations of this city too |
| 2499 | Alonim - Old Laundry | North District | 32.720819 | 35.142512 | cello,auto_coil | 0 | 34.7 | city center suspect: station is with the other 7 stations of this city; geocoded center is 35 km away |
| 2500 | Alonim - Ceramic Studio | North District | 32.721376 | 35.143585 | cello,auto_coil | 0 | 34.6 | city center suspect: station is with the other 7 stations of this city; geocoded center is 35 km away |
| 3449 | פז אשכול | באר שבע | 31.290845 | 34.432284 | paz | 0 | 34.6 | station outlier: far from the other 56 stations of this city too |
| 2501 | Alonim - Tennis Court | North District | 32.721992 | 35.146274 | cello,auto_coil | 0 | 34.4 | city center suspect: station is with the other 7 stations of this city; geocoded center is 35 km away |
| 635 | החברה לפיתוח דרום הר חברון - חניה מוסך | הר חברון | 31.373868 | 35.006090 | cello,auto_coil | 0 | 34.2 | unconfirmed: only 2 station(s) in this city |
| 636 | החברה לפיתוח דרום הר חברון - חניה ראשית | הר חברון | 31.375197 | 35.006424 | cello | 0 | 34.1 | unconfirmed: only 2 station(s) in this city |
| 668 | Haemek hospital | North District | 32.619060 | 35.312586 | cello,auto_coil,evm,data_gov | 1 | 30.9 | station outlier: far from the other 7 stations of this city too |
| 504 | מפגש הבקעה-כביש 90 | בקעת הירדן | 32.055919 | 35.470586 | cello,auto_coil,evm,data_gov,afcon | 1 | 30.3 | unconfirmed: only 1 station(s) in this city |
| 3278 | עמק שרה באר שבע | צאלים | 31.230479 | 34.818978 | evm | 0 | 27.3 | unconfirmed: only 1 station(s) in this city |

## Far from City Center (12–25 km) — Medium Severity

| id | name | city | lat | lng | source | g | distance_km | verdict |
|---:|------|------|----:|----:|--------|:-:|---|---|
| 1971 | חוף ביאנקיני בים המלח | ים המלח | 31.761088 | 35.500980 | cello,data_gov | 1 | 24.4 | station outlier: far from the other 4 stations of this city too |
| 2716 | מועצה בני שמעון חניה | בני שמעון | 31.442056 | 34.761263 | cello,auto_coil,data_gov | 1 | 23.5 | unconfirmed: only 1 station(s) in this city |
| 1137 | Timna Lake - Mevoa \| Eilot | Eilot | 29.787809 | 34.989183 | cello,auto_coil | 0 | 23.1 | station outlier: far from the other 3 stations of this city too |
| 2314 | Piano Center - South | Center District | 32.277692 | 34.841963 | cello,auto_coil,evm,data_gov | 1 | 22.4 | city center suspect: station is with the other 4 stations of this city; geocoded center is 14 km away |
| 3132 | ישיבת הגולן - חיספין | רמת הגולן | 32.845630 | 35.792990 | cello,auto_coil,evm | 0 | 22.3 | station outlier: far from the other 3 stations of this city too |
| 1854 | מדרשת רמת הגולן | רמת הגולן | 32.850071 | 35.797567 | cello,auto_coil,data_gov | 1 | 21.9 | station outlier: far from the other 3 stations of this city too |
| 3496 | Panora Seeds - Ilan Yaar | אליעד | 32.806583 | 35.736575 | interev | 0 | 21.0 | unconfirmed: only 1 station(s) in this city |
| 2301 | Beit Mai Parking - Haifa | Haifa District | 32.814305 | 34.998055 | cello,auto_coil,data_gov | 1 | 20.9 | city center suspect: station is with the other 2 stations of this city; geocoded center is 20 km away |
| 3181 | דלק מעבר מכמש | כביש 60 | 31.872692 | 35.259869 | cello,auto_coil,zen | 0 | 20.7 | unconfirmed: only 1 station(s) in this city |
| 3086 | דלק גל הערבה | גל הערבה | 30.985280 | 35.307430 | cello,auto_coil,data_gov,zen | 1 | 20.6 | unconfirmed: only 1 station(s) in this city |
| 2330 | TEN Haifa - Oil Coast | Haifa District | 32.807432 | 35.015821 | cello,data_gov | 1 | 20.4 | city center suspect: station is with the other 2 stations of this city; geocoded center is 20 km away |
| 3283 | גראנד קניון- חיפה | חיפה | 32.999574 | 34.967197 | evm | 0 | 20.3 | station outlier: far from the other 97 stations of this city too |
| 1132 | Timna Lake \| Eilot | Eilot | 29.760262 | 34.969255 | cello,auto_coil | 0 | 19.9 | station outlier: far from the other 3 stations of this city too |
| 3273 | פז - שער הגיא ירושלים | ירושלים | 31.815733 | 35.024154 | evm,paz | 0 | 19.5 | station outlier: far from the other 132 stations of this city too |
| 1952 | Hacal Golan - Hispin Pool | חספין | 32.844496 | 35.794385 | cello,auto_coil,interev,zen | 0 | 19.2 | unconfirmed: only 1 station(s) in this city |
| 628 | בית מלון Oaks | רמת הגולן | 33.201393 | 35.773195 | cello,auto_coil | 0 | 18.1 | station outlier: far from the other 3 stations of this city too |
| 1889 | כניסה משרדי רכש | מרום גליל | 32.997070 | 35.440621 | cello | 0 | 18.0 | unconfirmed: only 2 station(s) in this city |
| 1888 | חניית רכש | מרום גליל | 32.997285 | 35.440831 | cello,auto_coil | 0 | 17.9 | unconfirmed: only 2 station(s) in this city |
| 558 | מרכז קהילתי מיר"ב חוף הכרמל | חוף הכרמל | 32.646544 | 34.965045 | cello,auto_coil,afcon | 0 | 17.7 | unconfirmed: only 1 station(s) in this city |
| 2319 | TEN Nesher - Tel Hanan shopping center | Haifa District | 32.777664 | 35.039791 | cello,auto_coil,evm,data_gov | 1 | 17.7 | city center suspect: station is with the other 2 stations of this city; geocoded center is 20 km away |
| 1633 | חניון מועצה רמת הנגב | רמת הנגב | 31.003910 | 34.771460 | cello,auto_coil,data_gov | 1 | 17.2 | unconfirmed: only 1 station(s) in this city |
| 499 | דור אלון -פארק חדרה כביש 4 | דרום חדרה | 32.413900 | 34.904164 | cello,auto_coil,data_gov,afcon | 1 | 17.0 | unconfirmed: only 1 station(s) in this city |
| 3240 | מלון סטאי - חוף צאלון | כנרת | 32.650552 | 35.562281 | evm,data_gov | 1 | 16.9 | unconfirmed: only 2 station(s) in this city |
| 2303 | Rishpon | Center District | 32.201468 | 34.820055 | cello,auto_coil,evm,data_gov | 1 | 15.7 | city center suspect: station is with the other 4 stations of this city; geocoded center is 14 km away |
| 2683 | סונול עירון | צומת חנה | 32.459003 | 34.987716 | cello,auto_coil,evm,data_gov | 1 | 14.9 | unconfirmed: only 1 station(s) in this city |
| 667 | Kfar Kara _Local Council | מחוז חיפה | 32.505808 | 35.047237 | cello,auto_coil,data_gov | 1 | 14.8 | unconfirmed: only 1 station(s) in this city |
| 671 | Kibbutz Nachshon_Factory | לוד | 31.829089 | 34.955177 | cello,auto_coil,data_gov | 1 | 14.7 | station outlier: far from the other 16 stations of this city too |
| 3467 | פז נטופה | מצפה נטופה | 32.764188 | 35.244715 | paz | 0 | 13.6 | unconfirmed: only 2 station(s) in this city |
| 2586 | כינר | טבריה | 32.862060 | 35.645630 | cello,data_gov | 1 | 13.0 | station outlier: far from the other 17 stations of this city too |
| 889 | Nof Hasadot \| Kibbutz Negba - Yoav Regional C | Yoav Regional Counci | 31.658169 | 34.684525 | cello,auto_coil | 0 | 12.7 | station outlier: far from the other 2 stations of this city too |
| 3284 | גראנד קניון ב"ש- חניון צפוני | באר שבע | 31.358888 | 34.780752 | evm | 0 | 12.6 | station outlier: far from the other 56 stations of this city too |
| 2993 | שיח מדבר (מרחבעם) | מרחב עם | 30.809577 | 34.741866 | cello,auto_coil | 0 | 12.1 | unconfirmed: only 1 station(s) in this city |
| 1553 | 1309 - E (פרטי) | נופים | 32.158066 | 34.973009 | cello,data_gov | 1 | 12.0 | unconfirmed: only 1 station(s) in this city |
| 1976 | בית הברכה | חברון | 31.632412 | 35.132047 | cello,data_gov | 1 | 12.0 | unconfirmed: only 1 station(s) in this city |

## Stations without a city (skipped city-distance check) — 83

These stations have no declared city (`c` is null or empty), so there is no center to measure against. They are **not** flagged as suspicious and no city was assigned. A suggestion is shown only when the address/name contains a city already used in the dataset, or a geocoded city center is within 5 km (marked "hint only").

- With a suggestion: 78 (exact text match: 12, nearest center: 66)
- Without a suggestion: 5

| id | name | city | lat | lng | source | g | address | suggested city | basis |
|---:|------|------|----:|----:|--------|:-:|---|---|---|
| 30 | טירת כרמל, ישראל |  | 32.762127 | 34.972980 | cello | 0 | טירת כרמל, ישראל | טירת כרמל | exact match in address |
| 31 | מלון ירמיהו 33, ירמיהו, ירושלים, ישראל |  | 31.790782 | 35.202891 | cello,auto_coil | 0 | מלון ירמיהו 33, ירמיהו, ירושלים, ישראל | ירושלים | exact match in address |
| 33 | אדרים חקלאות ובניה בע"מ, גבעתי, ישראל |  | 31.734881 | 34.678179 | cello,auto_coil | 0 | אדרים חקלאות ובניה בע"מ, גבעתי, ישראל | Emunim | nearest city center, 1.2 km (hint only) |
| 64 | טירת כרמל, ישראל |  | 32.762127 | 34.972980 | cello | 0 | טירת כרמל, ישראל | טירת כרמל | exact match in address |
| 65 | מלון ירמיהו 33, ירמיהו, ירושלים, ישראל |  | 31.790782 | 35.202891 | cello | 0 | מלון ירמיהו 33, ירמיהו, ירושלים, ישראל | ירושלים | exact match in address |
| 66 | אדרים חקלאות ובניה בע"מ, גבעתי, ישראל |  | 31.734881 | 34.678179 | cello | 0 | אדרים חקלאות ובניה בע"מ, גבעתי, ישראל | Emunim | nearest city center, 1.2 km (hint only) |
| 588 | Gat Center DC |  | 31.624256 | 34.773966 | cello | 0 |  | הר חברון | nearest city center, 1.4 km (hint only) |
| 602 | Usha Public 01 |  | 32.796820 | 35.115015 | cello,auto_coil | 0 |  | Usha | nearest city center, 0.2 km (hint only) |
| 603 | Usha Public 02 |  | 32.796630 | 35.112264 | cello,auto_coil | 0 |  | Usha | nearest city center, 0.2 km (hint only) |
| 604 | Usha Public 03 |  | 32.795270 | 35.115665 | cello,auto_coil | 0 |  | Usha | nearest city center, 0.1 km (hint only) |
| 606 | Beit Alfa Public 02 |  | 32.516030 | 35.428326 | cello,auto_coil | 0 |  | Beit Alfa | nearest city center, 0.3 km (hint only) |
| 607 | Beit Alfa Public 04 |  | 32.516379 | 35.426386 | cello,auto_coil | 0 |  | Beit Alfa | nearest city center, 0.5 km (hint only) |
| 608 | Beit Alfa Public 05 |  | 32.516502 | 35.431348 | cello,auto_coil | 0 |  | Beit Alfa | nearest city center, 0.1 km (hint only) |
| 609 | Reshafim Public 01 |  | 32.480980 | 35.476797 | cello,auto_coil | 0 |  | Reshafim | nearest city center, 0.1 km (hint only) |
| 610 | Reshafim Public 02 |  | 32.479690 | 35.475041 | cello,auto_coil | 0 |  | Reshafim | nearest city center, 0.3 km (hint only) |
| 611 | Reshafim Public 03 |  | 32.482625 | 35.478037 | cello,auto_coil | 0 |  | Reshafim | nearest city center, 0.1 km (hint only) |
| 612 | Yahel Public 01 |  | 30.082675 | 35.128761 | cello,auto_coil | 0 |  | Yahel | nearest city center, 0.1 km (hint only) |
| 614 | Yahel Public 02 |  | 30.082675 | 35.128761 | cello | 0 |  | Yahel | nearest city center, 0.1 km (hint only) |
| 615 | Beit Berl Public 01 |  | 32.200325 | 34.923401 | cello | 0 |  | Beit Berl | nearest city center, 0.4 km (hint only) |
| 617 | Meirav Public 02 |  | 32.450968 | 35.423440 | cello,auto_coil | 0 |  | Meirav | nearest city center, 0.3 km (hint only) |
| 618 | Meirav Public 01 |  | 32.451693 | 35.421968 | cello,auto_coil | 0 |  | Meirav | nearest city center, 0.2 km (hint only) |
| 619 | Meirav Public 03 |  | 32.452812 | 35.421648 | cello,auto_coil | 0 |  | Meirav | nearest city center, 0.1 km (hint only) |
| 1518 | Demo site | city | 21.000000 | 20.000000 | cello | 0 | street house name |  | no confident suggestion |
| 2024 | פארן |  | 30.366100 | 35.151920 | cello,auto_coil,data_gov | 1 |  | פארן | exact match in name |
| 2025 | בקתה בשומרה |  | 33.087080 | 35.292230 | cello,data_gov | 1 |  | שומרה | nearest city center, 1.0 km (hint only) |
| 2034 | הרוח הגלילית - גורן |  | 33.054480 | 35.238860 | cello,auto_coil,data_gov | 1 |  | גרנות הגליל | nearest city center, 1.2 km (hint only) |
| 2040 | חדנס מזכירות |  | 32.928200 | 35.641160 | cello | 0 |  | חד נס | nearest city center, 0.2 km (hint only) |
| 2043 | הרוח הגלילית |  | 33.054450 | 35.238850 | cello,auto_coil | 0 |  | גרנות הגליל | nearest city center, 1.2 km (hint only) |
| 2045 | חדנס בריכה |  | 32.928480 | 35.640820 | cello,auto_coil | 0 |  | חד נס | nearest city center, 0.2 km (hint only) |
| 2047 | אירוח פארן |  | 30.363900 | 35.158670 | cello,auto_coil | 0 |  | פארן | nearest city center, 0.5 km (hint only) |
| 2048 | צרפתי אשדוד |  | 31.812420 | 34.658250 | cello | 0 |  | אשדוד | nearest city center, 1.7 km (hint only) |
| 2050 | פארן בקתות קלם |  | 30.366100 | 35.151920 | cello | 0 |  | פארן | nearest city center, 0.4 km (hint only) |
| 2053 | שופינג עד הלום - מתחם מקס סטוק |  | 31.757536 | 34.663953 | cello,auto_coil | 0 |  | Emunim | nearest city center, 1.8 km (hint only) |
| 2054 | אלעזר |  | 31.661195 | 35.145053 | cello,auto_coil | 0 |  | אפרת | nearest city center, 1.0 km (hint only) |
| 2084 | באר שבע, ישראל |  | 31.252102 | 34.786769 | cello | 0 | באר שבע, ישראל | באר שבע | exact match in address |
| 2532 | עמי סנטר -פתח תקווה |  | 32.103332 | 34.882197 | cello,auto_coil,data_gov | 1 |  | פתח | nearest city center, 1.8 km (hint only) |
| 2533 | מרכז מסחרי אלמוג-באר יעקב |  | 31.941867 | 34.843379 | cello,data_gov | 1 |  | באר יעקב | nearest city center, 0.4 km (hint only) |
| 2536 | דיזינגוף סנטר |  | 32.075108 | 34.774942 | cello,data_gov,zen | 1 |  | תל אביב-יפו | nearest city center, 1.3 km (hint only) |
| 2539 | כפר חסידים |  | 32.752332 | 35.094315 | cello,auto_coil,data_gov | 1 |  | כפר חסידים | exact match in name |
| 2540 | אור עקיבא-נוף ים סנטר |  | 32.504353 | 34.917956 | cello,data_gov | 1 |  | אור עקיבא | nearest city center, 0.5 km (hint only) |
| 2543 | חצבה- חאן |  | 30.781835 | 35.250476 | cello,auto_coil,data_gov | 1 |  | חצבה | nearest city center, 3.2 km (hint only) |
| 2547 | מרכז מינקין-מודיעין |  | 31.892243 | 35.008740 | cello,auto_coil,data_gov | 1 |  | Modi'in-Maccabim-Re'ut | nearest city center, 1.8 km (hint only) |
| 2553 | עפולה אדיר הום -DC |  | 32.584913 | 35.293941 | cello,auto_coil,data_gov | 1 |  | עפולה | nearest city center, 2.6 km (hint only) |
| 2554 | אולם אירועים- אמרה |  | 31.916100 | 34.777889 | cello,data_gov | 1 |  | נס ציונה | nearest city center, 1.9 km (hint only) |
| 2561 | מתחם ספיר קצרין -DC |  | 32.992696 | 35.680481 | cello | 0 |  | חספין | nearest city center, 0.4 km (hint only) |
| 2563 | בדיקות עמדות ציבוריות |  | 31.588423 | 34.564015 | cello,data_gov | 1 |  | יד מרדכי | nearest city center, 0.5 km (hint only) |
| 2564 | עמי סנטר אור יהודה MINI DC60KW |  | 32.025076 | 34.870430 | cello,data_gov | 1 |  | אור יהודה | nearest city center, 0.7 km (hint only) |
| 2572 | קיבוץ כיסופים |  | 31.374766 | 34.396850 | cello,auto_coil | 0 |  | Ein HaShlosha | nearest city center, 2.6 km (hint only) |
| 2573 | כיסופים-עמדה מס' 1 |  | 31.376020 | 34.399521 | cello | 0 |  | Ein HaShlosha | nearest city center, 2.7 km (hint only) |
| 2574 | עמדה מס' 2 - כיסופים |  | 31.374766 | 34.396850 | cello | 0 |  | Ein HaShlosha | nearest city center, 2.6 km (hint only) |
| 2575 | כיסופים-עמדה מס' 3 |  | 31.375650 | 34.397060 | cello,auto_coil | 0 |  | Ein HaShlosha | nearest city center, 2.7 km (hint only) |
| 2578 | אוניברסיטת בן גוריון עמדה ימנית |  | 31.261438 | 34.799559 | cello,auto_coil | 0 |  | באר שבע | nearest city center, 1.9 km (hint only) |
| 2579 | אוניברסיטת בן גוריון עמדה שמאלית |  | 31.261438 | 34.799559 | cello | 0 |  | באר שבע | nearest city center, 1.9 km (hint only) |
| 3033 | הרודס ים המלח - פתאל |  | 31.171270 | 35.367839 | cello,auto_coil,data_gov | 1 | undefined undefined | נווה זוהר | nearest city center, 2.1 km (hint only) |
| 3036 | הרודס ים המלח - פתאל |  | 31.171270 | 35.367839 | cello,data_gov | 1 | undefined undefined | נווה זוהר | nearest city center, 2.1 km (hint only) |
| 3196 | Gnrgyאבגדהוזחטיכלמנסעפצקרש |  | 12.919809 | 77.650814 | auto_coil | 0 | 7th Cross Road 24 |  | no confident suggestion |
| 3197 | , ישראל |  | 77.000000 | 12.000000 | auto_coil | 0 |  |  | no confident suggestion |
| 3198 | Charging station test |  | 12.950000 | 77.651598 | auto_coil | 0 | Wind Tunnel Road | בנגלור | nearest city center, 4.7 km (hint only) |
| 3199 | בנגלור 2 |  | 12.923473 | 77.651469 | auto_coil | 0 | 27th Main Road |  | no confident suggestion |
| 3210 | WIX Complex \| Glilot Junction |  | 32.142258 | 34.799929 | auto_coil | 0 | יוניצמן 5 | קיבוץ גליל ים | nearest city center, 2.1 km (hint only) |
| 3215 | Kibbutz Ginegar - Secretariat Parking |  | 32.662843 | 35.259488 | auto_coil | 0 | דרך הרפת 1 | Migdal HaEmek | nearest city center, 2.3 km (hint only) |
| 3216 | Private \| Amdocs Israel ltd \| Nazareth |  | 32.680650 | 35.292579 | auto_coil | 0 | רח' 2024 | Kfar Hahoresh | nearest city center, 2.9 km (hint only) |
| 3225 | דור אלון- פארק חדרה כביש 4 |  | 32.465490 | 34.919293 | evm,data_gov | 1 | חדרה | חדרה | exact match in address |
| 3230 | DC רמות, רמות |  | 32.850912 | 35.666042 | evm | 0 | מושב רמות | רמות | exact match in name |
| 3231 | יער טמרה |  | 32.855913 | 35.187059 | evm | 0 | טמרה | טמרה | exact match in address |
| 3234 | מועצה אזורית יואב צומת אולטרה DC |  | 31.601096 | 34.900043 | evm | 0 | מועצה אזורית יואב 12345 | Beit Guvrin | nearest city center, 0.4 km (hint only) |
| 3236 | רמת הנגב עמדה מהירה |  | 31.020621 | 34.766052 | evm | 0 | חניון מועצה אזורית רמת הנגב | משאבי שדה | nearest city center, 2.7 km (hint only) |
| 3237 | נווה אטיב- חניה מרכזית |  | 33.310346 | 35.744274 | evm,data_gov | 1 | נווה אטי"ב |  | no confident suggestion |
| 3242 | חמי עין גדי |  | 31.417561 | 35.379054 | evm,data_gov | 1 | עין גדי | Ein Gedi | nearest city center, 3.9 km (hint only) |
| 3245 | דור כימיכלים חיפה |  | 32.820503 | 35.044564 | evm | 0 | דור כימיכלים חיפה | עוקף קריות | nearest city center, 2.4 km (hint only) |
| 3252 | דרך יצחק בן צבי ראשון לציון |  | 31.983012 | 34.792928 | evm | 0 | דרך יצחק בן צבי 1 ראשון לציון | Tzova | nearest city center, 2.7 km (hint only) |
| 3253 | פז מפגש ארבל |  | 32.830837 | 35.503044 | evm,paz | 0 | מגדל | מגדל | exact match in address |
| 3254 | פז - מצפה טורען |  | 32.795426 | 35.404041 | evm,paz | 0 | מצפה טורען כביש 65 לכיוון צומת גולני | מצפה נטופה | nearest city center, 2.1 km (hint only) |
| 3257 | פז - בחן בת חפר כביש 5714 |  | 32.350511 | 35.013710 | evm,paz | 0 | בת חפר | בחן | nearest city center, 0.5 km (hint only) |
| 3258 | פז - עוקף נצרת |  | 32.692015 | 35.297678 | evm,paz | 0 | כביש עוקף נצרת | נצרת | nearest city center, 1.8 km (hint only) |
| 3263 | תלפיות |  | 31.749349 | 35.213483 | evm | 0 | אזור תעשייה תלפיות ירושלים | מעלות | nearest city center, 1.9 km (hint only) |
| 3264 | פז - אצטדיון כפר סבא |  | 32.178778 | 34.928455 | evm,paz | 0 | כפר סבא | כפר סבא | exact match in address |
| 3265 | טופז רמת השרון |  | 32.130303 | 34.829799 | evm,paz | 0 | טופז רמת השרון | רמת השרון | nearest city center, 1.6 km (hint only) |
| 3271 | פז - קואופ רמלה |  | 31.937928 | 34.885977 | evm,paz | 0 | שד' ירושלים רמלה | רמלה דוכיפת | nearest city center, 0.5 km (hint only) |
| 3274 | ברורים כביש 40 |  | 31.761680 | 34.784892 | evm | 0 | כביש 4 צומת ראם | בני ראם | nearest city center, 1.1 km (hint only) |
| 3285 | חניון פונדק יטבתה |  | 29.898647 | 35.059495 | evm,data_gov | 1 | יטבתה | Yotvata | nearest city center, 0.3 km (hint only) |
| 3287 | פז - שיאונה הירקונים פתח תקווה |  | 32.115328 | 34.906336 | evm,paz | 0 | שיאונה הירקונים בכניסה לכפר הבטיסטים פתח תקוו | דור אלון | nearest city center, 2.0 km (hint only) |
| 3288 | פז - מסילת ציון |  | 31.808395 | 35.017855 | evm,paz | 0 | מסילת ציון כביש בית שמש שער הגיא | Eshtaol | nearest city center, 3.2 km (hint only) |

## Declared city not geocodable (skipped) — 129

| city | stations | reason |
|------|---------:|--------|
| קיבוץ זיקים | 7 | Nominatim found no match |
| קיבוץ מזרע | 5 | Nominatim found no match |
| קיבוץ יגור | 5 | Nominatim found no match |
| קיבוץ רוחמה | 4 | Nominatim found no match |
| קיבוץ נצר סרני | 4 | Nominatim found no match |
| קיבוץ מלכיה | 3 | Nominatim found no match |
| קיבוץ בית אורן | 3 | Nominatim found no match |
| קיבוץ גזית | 3 | Nominatim found no match |
| יישוב אלעזר | 2 | Nominatim found no match |
| South Sharon Regional Council | 2 | Nominatim found no match |
| קריית שדה התעופה | 2 | Nominatim found no match |
| Mississauga | 2 | Nominatim found no match |
| מושב חוסן | 2 | Nominatim found no match |
| Maanita | 2 | Nominatim found no match |
| Merkaz Kah | 2 | Nominatim found no match |
| Undefined | 2 | Nominatim found no match |
| קיבוץ מגל | 2 | Nominatim found no match |
| קיבוץ עין השלושה | 2 | Nominatim found no match |
| קיבוץ צאלים | 2 | Nominatim found no match |
| מושב שורש | 2 | Nominatim found no match |
| צוומת מחניים | 1 | Nominatim found no match |
| קיבוץ עין חרוד מאוחד | 1 | Nominatim found no match |
| קיבוץ עינת | 1 | Nominatim found no match |
| דור אלון-ציפורית | 1 | Nominatim found no match |
| עין כרמל \ עתלית | 1 | Nominatim found no match |
| קיבוץ יפעת | 1 | Nominatim found no match |
| יישובי יבנה | 1 | Nominatim found no match |
| דייר אל-אסד | 1 | Nominatim found no match |
| צומת האון | 1 | Nominatim found no match |
| דור אלון חמד/ברכיה | 1 | Nominatim found no match |
| עוקף חדרה | 1 | Nominatim found no match |
| דור אלון רמת רחל | 1 | Nominatim found no match |
| רעננה מגדל אלון | 1 | Nominatim found no match |
| David’s Harp Galilee Resort | 1 | Nominatim found no match |
| משק מלמד - לול אורגני, חנות המשק, HaEla Street, Kfar HaNagid, Israel | 1 | Nominatim found no match |
| מושב חצבה | 1 | Nominatim found no match |
| קיבוץ רביבים | 1 | Nominatim found no match |
| אזור תעשייה שח״ק | 1 | Nominatim found no match |
| Bar-Lev Hi-Tech Park | 1 | Nominatim found no match |
| Beit HaMaks | 1 | Nominatim found no match |
| קיבוץ בית הערבה | 1 | Nominatim found no match |
| קרייית גת | 1 | Nominatim found no match |
| קיבוץ הרדוף | 1 | Nominatim found no match |
| רמת גן ישראל | 1 | Nominatim found no match |
| קרית שדה תהעופה | 1 | Nominatim found no match |
| בינמינה | 1 | Nominatim found no match |
| Markham | 1 | Nominatim found no match |
| קיבוץ כפר גלעדי | 1 | Nominatim found no match |
| מושב מנות | 1 | Nominatim found no match |
| מושב יערה | 1 | Nominatim found no match |
| מושב עמקה | 1 | Nominatim found no match |
| מושב כרם בן זמרה | 1 | Nominatim found no match |
| מושב אמנון | 1 | Nominatim found no match |
| תנובות-נירים | 1 | Nominatim found no match |
| Pnei Hever | 1 | Nominatim found no match |
| Kfar Ezion | 1 | Nominatim found no match |
| Mezer | 1 | Nominatim found no match |
| Natzrat Eilit | 1 | Nominatim found no match |
| Giv'at Haim Me'uhad Cemetery | 1 | Nominatim found no match |
| Hemek Hefer | 1 | Nominatim found no match |
| Yikon Community Center | 1 | Nominatim found no match |
| Beit Yitshak Sha'ar Hefer | 1 | Nominatim found no match |
| קיבוץ בארי | 1 | Nominatim found no match |
| כפר נופש מעגן | 1 | Nominatim found no match |
| קיבוץ ניר אליהו | 1 | Nominatim found no match |
| קיבוץ יקום | 1 | Nominatim found no match |
| קיבוץ נחשונים | 1 | Nominatim found no match |
| קיבוץ גשור | 1 | Nominatim found no match |
| מלון פסטורל כפר בלום | 1 | Nominatim found no match |
| קיבוץ שובל | 1 | Nominatim found no match |
| קיבוץ אפיק | 1 | Nominatim found no match |
| כפר נוקדים | 1 | Nominatim found no match |
| סונול אלמוג | 1 | Nominatim found no match |
| קיבוץ רמת הכובש | 1 | Nominatim found no match |
| סונול עיר אובות | 1 | Nominatim found no match |
| מושב רגבה | 1 | Nominatim found no match |
| קיבוץ געש | 1 | Nominatim found no match |
| צומת אליקים | 1 | Nominatim found no match |
| קיבוץ שריד | 1 | Nominatim found no match |
| ראשון לציוןן | 1 | Nominatim found no match |
| מפעל דודאים | 1 | Nominatim found no match |
| נין התבור | 1 | Nominatim found no match |
| פארק ציפורי | 1 | Nominatim found no match |
| ביתר עלית | 1 | Nominatim found no match |
| מפגש צביקה | 1 | Nominatim found no match |
| אזה״ת הדרומי | 1 | Nominatim found no match |
| עפר קרע | 1 | Nominatim found no match |
| בית שמש כביש הכניסה | 1 | Nominatim found no match |
| כביש ב"ש-מצפה רמון | 1 | Nominatim found no match |
| קיבוץ יטבתה | 1 | Nominatim found no match |
| קיבוץ ברור חיל | 1 | Nominatim found no match |

## Duplicate Pairs with Divergent Coordinates

| id_a | name_a | id_b | name_b | distance_m | match | recommended_keep | reason |
|-----:|--------|-----:|--------|----------:|-------|-----------------|--------|
| 3174 | חניית הנהלה מתחם שורק למורשים  | 3175 | חניה גדולה מתחם שורק למורשים ב | 100426 | same address + city | id=3175 | B has more sources (2 vs 1); B has higher power (5 |
| 626 | הרואה בקפה - DC 40 | 1891 | וילאר מבוא כרמל | 48056 | fuzzy address (sim=1.00) | manual review needed | A has higher power (80kW); B has price info |
| 626 | הרואה בקפה - DC 40 | 630 | עיר תחתית AC | 48040 | same address + city | id=626 | A has higher power (80kW) |
| 623 | עמדת טעינה DC חניון | 626 | הרואה בקפה - DC 40 | 48024 | same address + city | manual review needed | no clear winner |
| 219 | מלון סטאי - חוף צאלון | 3240 | מלון סטאי - חוף צאלון | 22218 | same normalized name + ci | id=219 | A has more sources (4 vs 2); A has price info |
| 3177 | תפוז עפולה | 3508 | תפוז עפולה | 10884 | same normalized name + ci | id=3177 | A has more sources (2 vs 1); A has higher power (2 |
| 2816 | ראשונים סנטר | 2884 | פז - סונול ראשונים | 4493 | fuzzy name (sim=1.00) | id=2884 | B has more sources (4 vs 2); B has higher power (1 |
| 1144 | Machsanei Hashuk \| Neighborhoo | 1150 | Machsanei Hashuk \| Ramot neigh | 4491 | fuzzy name (sim=0.60) | manual review needed | no clear winner |
| 2610 | קניון עזריאלי ראשונים | 2816 | ראשונים סנטר | 4336 | fuzzy name (sim=1.00) | id=2610 | A has more sources (3 vs 2); A has higher power (5 |
| 2816 | ראשונים סנטר | 2956 | קניון עזריאלי ראשונים עמדה מהי | 4332 | fuzzy name (sim=1.00) | id=2956 | B has higher power (150kW) |
| 1296 | Menachem Begin Parking Lot \| P | 3226 | פתח תקווה Supercharger | 4174 | fuzzy address (sim=0.67) | manual review needed | B has higher power (250kW); A has price info |
| 3035 | לאונרדו פלאזה טבריה- פתאל | 3459 | פז טבריה עילית | 3691 | fuzzy name (sim=1.00) | id=3035 | A is gov-verified; A has more sources (2 vs 1); B  |
| 3043 | לאונרדו פלאזה טבריה - פתאל | 3459 | פז טבריה עילית | 3691 | fuzzy name (sim=1.00) | id=3043 | A is gov-verified; A has more sources (2 vs 1); B  |
| 1132 | Timna Lake \| Eilot | 1137 | Timna Lake - Mevoa \| Eilot | 3617 | fuzzy name (sim=0.75) | manual review needed | no clear winner |
| 3126 | רני צים - רהט seven | 3499 | SEVEN רהט | 3355 | fuzzy name (sim=0.67) | id=3126 | A is gov-verified; A has more sources (3 vs 1); A  |
| 789 | תחנת דלק יעד פתח תקווה | 2369 | Pango Office | 3299 | fuzzy address (sim=0.67) | id=2369 | B has more sources (4 vs 3); A has higher power (1 |
| 837 | Nevo Hotel - Isrotel ltd \| Dea | 1115 | Leonardo Club Hotel - Fattal H | 3260 | same address + city | id=837 | A is gov-verified; A has more sources (3 vs 2) |
| 3092 | צים אורבן כפר סבא | 3282 | אורבן צים כפר סבא | 2872 | fuzzy name (sim=1.00) | id=3092 | A is gov-verified; A has more sources (3 vs 1); A  |
| 544 | דור אלון-עכו | 2626 | קניון עזריאלי עכו | 2727 | fuzzy name (sim=1.00) | id=2626 | B is gov-verified; A has higher power (150kW) |
| 2771 | מול זכרון | 3180 | דלק זכרון יעקב | 2391 | fuzzy name (sim=1.00) | id=2771 | A is gov-verified; A has more sources (4 vs 2); B  |
| 370 | דור אלון-זכרון יעקב | 3180 | דלק זכרון יעקב | 2301 | fuzzy name (sim=1.00) | id=370 | A is gov-verified; A has more sources (5 vs 2); B  |
| 1202 | Jumbo City of the Kings Southe | 2495 | GT Center - Eilat | 2128 | fuzzy address (sim=1.00) | id=1202 | A has higher power (180kW) |
| 2608 | קניון עזריאלי חולון | 2827 | מרכז עזריאלי חולון | 2105 | fuzzy name (sim=1.00) | id=2827 | B has more sources (4 vs 3); B has higher power (2 |
| 325 | דור אלון-בית קשת | 3136 | קיבוץ בית קשת | 2046 | fuzzy name (sim=1.00) | id=325 | A has more sources (5 vs 4); A has higher power (1 |
| 1207 | Jumbo City of the Kings Northe | 2495 | GT Center - Eilat | 2042 | fuzzy address (sim=1.00) | id=1207 | A has higher power (180kW) |
| 1296 | Menachem Begin Parking Lot \| P | 1306 | Aharonovich Yosef \| Petah Tikv | 2012 | fuzzy address (sim=0.67) | id=1296 | A has more sources (2 vs 1); A has higher power (5 |
| 3491 | Batei Zikuk Ahazaka | 3492 | Batey Zikuk Ashdod | 1880 | fuzzy address (sim=1.00) | manual review needed | no clear winner |
| 406 | מלונות דן-דן בוטיק ירושלים | 3025 | לאונרדו בוטיק ירושלים - פתאל | 1864 | fuzzy name (sim=1.00) | id=406 | A has more sources (4 vs 3) |
| 1232 | Ofer Mall \| Hadera | 2371 | TEN Hadera | 1825 | fuzzy name (sim=1.00) | id=2371 | B is gov-verified; A has more sources (3 vs 2); B  |
| 358 | דור אלון - מצפה רמון | 1589 | 2898 - מצפה רמון - פרטי | 1729 | fuzzy name (sim=0.67) | id=358 | A has more sources (4 vs 2); A has higher power (2 |
| 358 | דור אלון - מצפה רמון | 3084 | דלק מצפה רמון | 1683 | fuzzy name (sim=1.00) | id=3084 | B has higher power (280kW) |
| 642 | קניון לב הרמה בית שמש \| NH Ene | 3223 | תחמש | 1682 | fuzzy address (sim=0.67) | id=642 | A has more sources (2 vs 1) |
| 1059 | Kedem Hotel \| Tirat Carmel | 2402 | TEN - Tirat Carmel | 1658 | fuzzy name (sim=0.67) | id=2402 | B is gov-verified; B has more sources (4 vs 1); B  |
| 783 | דלק עפולה | 3202 | סונול עפולה | 1619 | fuzzy name (sim=1.00) | id=783 | A is gov-verified; A has more sources (3 vs 2); A  |
| 553 | דור אלון -מתחם אלון קריית השרו | 2628 | סונול צומת השרון | 1572 | fuzzy name (sim=1.00) | id=2628 | B is gov-verified |
| 2073 | בר אילן צפת | 2714 | סונול צפת | 1481 | fuzzy name (sim=1.00) | id=2714 | B has more sources (4 vs 3); B has higher power (6 |
| 482 | דור אלון -אורים | 3201 | אורים | 1447 | fuzzy name (sim=1.00) | id=482 | A is gov-verified; A has more sources (4 vs 1); A  |
| 2855 | סונול עד הלום | 3115 | פז - תחנת דלק תפוז עד הלום | 1445 | fuzzy name (sim=0.67) | id=3115 | B has more sources (6 vs 4); B has higher power (1 |
| 1327 | Gordonia Hotels \| Elma Hotel Z | 1343 | Gordonia Hotels \| Gordonia hot | 1388 | fuzzy name (sim=0.67) | id=1327 | A has more sources (3 vs 2) |
| 2551 | עמי סנטר -נס ציונה | 3161 | דלק נס ציונה | 1378 | fuzzy name (sim=0.67) | id=2551 | A is gov-verified; B has higher power (150kW) |
| 1240 | Ofer Park \| East Petah Tikva | 2345 | Ofer Big Mall - Outdoor Parkin | 1326 | same address + city | id=2345 | B is gov-verified; A has higher power (184kW) |
| 135 | פז מגדל העמק | 2780 | סונול מגדל העמק | 1216 | fuzzy name (sim=1.00) | id=135 | A has more sources (6 vs 4) |
| 2591 | מרכז מסחרי חוצות יגור | 2664 | משרדי רכב-יגור | 1174 | same address + city | manual review needed | no clear winner |
| 2988 | קבוצת טרייסטמן ציבורי | 3203 | קבוצת טרייסטמן | 1168 | fuzzy name (sim=1.00) | id=2988 | A has more sources (2 vs 1); A has higher power (5 |
| 2856 | 2231_גילה_חניון צביה ויצחק פינ | 2860 | 2230 גילה_חניון צביה ויצחק 6 כ | 1063 | fuzzy address (sim=0.67) | manual review needed | no clear winner |
| 263 | מלונות דן - נצרת | 3145 | נצרת נצרת | 1034 | fuzzy name (sim=1.00) | id=263 | A has more sources (4 vs 2) |
| 1494 | מתחם צים סנטר ערד | 3165 | דלק ערד | 1017 | fuzzy name (sim=1.00) | id=1494 | A is gov-verified; A has more sources (4 vs 2); B  |
| 202 | דור אלון-ערד | 1494 | מתחם צים סנטר ערד | 1007 | fuzzy name (sim=1.00) | id=202 | A has higher power (180kW); A has price info |
| 1772 | לישנסקי 4 | 2965 | עיריית ראשון לציון- חניון נאפי | 927 | fuzzy address (sim=1.00) | id=2965 | B has more sources (4 vs 3); B has higher power (5 |
| 1223 | Harel Mall Parking Lot \| Mevas | 1309 | 10 Harel st \| Mevaseret Zion | 924 | fuzzy name (sim=1.00) | id=1223 | A has higher power (180kW) |
| 569 | גיבורי ישראל | 2869 | סונול גיבורי ישראל | 907 | fuzzy name (sim=1.00) | id=2869 | B is gov-verified; B has more sources (3 vs 2); A  |
| 2367 | More Mall City - Harish | 2368 | More Mall - Harish | 883 | fuzzy name (sim=1.00) | id=2368 | B has more sources (4 vs 3) |
| 2660 | הפרחים | 2692 | רעננה - תיכון אביב | 858 | fuzzy address (sim=1.00) | id=2692 | B has more sources (3 vs 2); B has higher power (5 |
| 1040 | Gav-Yam Management Services an | 1051 | Gav-Yam Management Services an | 854 | fuzzy name (sim=0.80) | id=1040 | A has more sources (2 vs 1); A has higher power (5 |
| 1094 | Leonardo Club Hotel - Fattal H | 1098 | Leonardo Plaza Hotel - Fattal  | 837 | fuzzy name (sim=0.67) | manual review needed | no clear winner |
| 2714 | סונול צפת | 3475 | פז צפת | 837 | fuzzy name (sim=1.00) | id=2714 | A is gov-verified; A has more sources (4 vs 1); B  |
| 1365 | Hill Mall Parking Lot \| Giv'at | 1366 | HaGefen \| Giv'at Shmuel Munici | 829 | fuzzy name (sim=0.60) | id=1365 | A is gov-verified; A has more sources (3 vs 2) |
| 185 | דב גור 9, אשדוד | 186 | ביאליק 15,אשדוד | 826 | same address + city | id=185 | A has more sources (4 vs 3); A has higher power (5 |
| 100 | מנחם בגין 53, גדרה | 152 | מנחם בגין 11 גדרה | 826 | fuzzy name (sim=0.67) | manual review needed | no clear winner |
| 1 | עתיר ידע 16, כפר סבא, ישראל | 675 | O-TECH | 823 | fuzzy address (sim=1.00) | id=675 | B has more sources (4 vs 3); A has higher power (3 |
| 15 | עתיר ידע 16, כפר סבא, ישראל | 675 | O-TECH | 823 | fuzzy address (sim=1.00) | id=675 | B has more sources (4 vs 2); B has higher power (9 |
| 41 | עתיר ידע 16, כפר סבא, ישראל | 675 | O-TECH | 823 | fuzzy address (sim=1.00) | id=675 | B has more sources (4 vs 2); A has higher power (3 |
| 49 | עתיר ידע 16, כפר סבא, ישראל | 675 | O-TECH | 823 | fuzzy address (sim=1.00) | id=675 | B has more sources (4 vs 2); B has higher power (9 |
| 580 | ecorgy test | 675 | O-TECH | 811 | fuzzy address (sim=1.00) | id=675 | B is gov-verified; B has more sources (4 vs 1); B  |
| 2073 | בר אילן צפת | 3475 | פז צפת | 790 | fuzzy name (sim=1.00) | id=2073 | A is gov-verified; A has more sources (3 vs 1); B  |
| 2871 | שד' גולדה מאיר 21 | 2872 | שד' גולדה מאיר 3 | 787 | fuzzy address (sim=1.00) | id=2871 | A has higher power (160kW) |
| 2650 | בית מכבי | 2872 | שד' גולדה מאיר 3 | 783 | fuzzy address (sim=1.00) | id=2872 | B has higher power (150kW) |
| 251 | הוד-ים מלח -לאורחי המלון | 271 | אואזיס ים המלח-לאורחי המלון | 764 | same address + city | id=251 | A has more sources (4 vs 3); A has higher power (2 |
| 107 | אופק1 קיסריה-מורשים בלבד | 146 | האשל 40 | 745 | fuzzy address (sim=1.00) | manual review needed | no clear winner |
| 212 | מילוס-ים המלח -לאורחי המלון | 271 | אואזיס ים המלח-לאורחי המלון | 741 | same address + city | id=212 | A has more sources (5 vs 3); A has higher power (5 |
| 138 | האשל 1 | 146 | האשל 40 | 738 | fuzzy address (sim=1.00) | manual review needed | no clear winner |
| 922 | Ulpanat Giv'at Shmue \| Giv'at  | 1365 | Hill Mall Parking Lot \| Giv'at | 738 | fuzzy address (sim=0.67) | id=1365 | B has more sources (3 vs 2); B has higher power (5 |
| 1309 | 10 Harel st \| Mevaseret Zion | 2450 | Ofer Harel Mall | 712 | fuzzy name (sim=1.00) | id=2450 | B is gov-verified; B has more sources (5 vs 1); B  |
| 2239 | פז - אושילנד כפר סבא | 2559 | סבן בדיקות | 709 | fuzzy address (sim=1.00) | id=2239 | A has more sources (4 vs 2); A has higher power (1 |
| 137 | סנטר - נתניה (מפלס עליון) (Y)  | 569 | גיבורי ישראל | 704 | fuzzy address (sim=1.00) | id=137 | A is gov-verified; A has more sources (4 vs 2); B  |
| 1264 | Azrieli Mall \| Tel Aviv | 2311 | The Young Towers - Tel Aviv | 700 | fuzzy address (sim=0.67) | id=2311 | B is gov-verified; B has more sources (3 vs 2); A  |
| 98 | פז - שופינה ראש פינה | 2880 | סונול ראש פינה | 689 | fuzzy name (sim=0.67) | id=98 | A has more sources (5 vs 3); A has higher power (1 |
| 1220 | Municipality Herzliya - Alterm | 1221 | Municipality Herzliya - Alterm | 681 | fuzzy address (sim=1.00) | id=1221 | B has more sources (2 vs 1); B has higher power (5 |
| 1856 | רויאל פארק | 2963 | אייסמול אילת אולטרה | 677 | fuzzy address (sim=1.00) | id=2963 | B is gov-verified; B has more sources (3 vs 1); B  |
| 1146 | פז - Machsanei Hashuk \| Kiryat | 2568 | איי סלומון קריית גת | 673 | fuzzy address (sim=1.00) | id=2568 | B is gov-verified; A has more sources (4 vs 2) |
| 285 | בניין פיזיקה, מכון ויצמן | 1474 | מכון וייצמן | 671 | same address + city | id=285 | A has more sources (4 vs 3); A has price info |
| 2293 | Givat Haim ihud - Swimming poo | 2442 | Givat Haim ihud - Kindergarden | 666 | same address + city | id=2442 | B has more sources (3 vs 2) |
| 2779 | שכונה א' - נצר סרני | 2874 | שכונה ג' - נצר סרני | 658 | fuzzy address (sim=0.75) | manual review needed | no clear winner |
| 458 | דור אלון-כפר עזה | 2841 | כפר עזה - חניה מזכירות | 642 | fuzzy name (sim=1.00) | id=458 | A has more sources (4 vs 3); A has higher power (1 |
| 306 | מכון לביוכימיה, מכון ויצמן | 1474 | מכון וייצמן | 607 | same address + city | id=306 | A has more sources (4 vs 3); A has price info |
| 285 | בניין פיזיקה, מכון ויצמן | 290 | בניין ידע,מכון ויצמן | 597 | same address + city | manual review needed | no clear winner |
| 1856 | רויאל פארק | 2961 | אייסמול אילת מהירות | 581 | fuzzy address (sim=1.00) | id=2961 | B is gov-verified; B has more sources (5 vs 1); B  |
| 2280 | Givat Haim ihud - Lev hapardes | 2293 | Givat Haim ihud - Swimming poo | 566 | same address + city | id=2280 | A has more sources (3 vs 2) |
| 1591 | 2834 - רמות מנשה - קומותיים | 1592 | 2834 - רמות מנשה - השדות | 564 | fuzzy name (sim=0.60) | id=1591 | A has more sources (2 vs 1); A has higher power (2 |
| 1560 | 2834 - רמות מנשה - נופים | 1591 | 2834 - רמות מנשה - קומותיים | 550 | fuzzy name (sim=0.60) | id=1560 | A is gov-verified |
| 1589 | 2898 - מצפה רמון - פרטי | 3084 | דלק מצפה רמון | 541 | fuzzy name (sim=0.67) | id=3084 | B has more sources (4 vs 2); B has higher power (2 |
| 2280 | Givat Haim ihud - Lev hapardes | 2442 | Givat Haim ihud - Kindergarden | 539 | same address + city | manual review needed | no clear winner |
| 971 | Sheba Medical Center Tel Hasho | 1179 | Sheba Medical Center Tel Hasho | 535 | fuzzy name (sim=0.75) | manual review needed | no clear winner |
| 971 | Sheba Medical Center Tel Hasho | 983 | Sheba Medical Center Tel Hasho | 516 | same address + city | manual review needed | no clear winner |
| 150 | בניין לופאטי, מכון ויצמן | 306 | מכון לביוכימיה, מכון ויצמן | 506 | same address + city | id=306 | B has higher power (50kW) |
| 3152 | אורבן צים נוף הגליל | 3509 | צים אורבן נוף הגליל | 504 | fuzzy name (sim=1.00) | id=3152 | A is gov-verified; A has more sources (2 vs 1); A  |
| 1250 | Reit 1 ltd - Office Building \| | 1299 | EV-Edge \| Company Offices \| Te | 503 | fuzzy address (sim=1.00) | id=1250 | A has more sources (2 vs 1); A has higher power (5 |

### Duplicate Pair Details (top 30 by distance)

**Pair 1** — distance: 100426m, match: same address + city
- **A**: id=3174 `חניית הנהלה מתחם שורק למורשים בלבד` | lat=31.046051, lng=34.851612 | g=0 | source=cello | provider=Zen Energy | price=2.21 | power=22kW
- **B**: id=3175 `חניה גדולה מתחם שורק למורשים בלבד` | lat=31.943524, lng=34.732995 | g=0 | source=cello,auto_coil | provider=Zen Energy | price=2.21 | power=50kW
- **Recommendation**: keep id=3175 — B has more sources (2 vs 1); B has higher power (50kW)

**Pair 2** — distance: 48056m, match: fuzzy address (sim=1.00)
- **A**: id=626 `הרואה בקפה - DC 40` | lat=32.393116, lng=34.915413 | g=0 | source=cello,auto_coil | provider=EvLink | price=None | power=80kW
- **B**: id=1891 `וילאר מבוא כרמל` | lat=32.819327, lng=35.000361 | g=0 | source=cello,auto_coil | provider=Greenspot | price=1.79 | power=50kW
- **Recommendation**: keep manual review needed — A has higher power (80kW); B has price info

**Pair 3** — distance: 48040m, match: same address + city
- **A**: id=626 `הרואה בקפה - DC 40` | lat=32.393116, lng=34.915413 | g=0 | source=cello,auto_coil | provider=EvLink | price=None | power=80kW
- **B**: id=630 `עיר תחתית AC` | lat=32.819083, lng=35.001058 | g=0 | source=cello,auto_coil | provider=EvLink | price=None | power=22kW
- **Recommendation**: keep id=626 — A has higher power (80kW)

**Pair 4** — distance: 48024m, match: same address + city
- **A**: id=623 `עמדת טעינה DC חניון` | lat=32.818957, lng=35.000953 | g=0 | source=cello,auto_coil | provider=EvLink | price=None | power=80kW
- **B**: id=626 `הרואה בקפה - DC 40` | lat=32.393116, lng=34.915413 | g=0 | source=cello,auto_coil | provider=EvLink | price=None | power=80kW
- **Recommendation**: keep manual review needed — no clear winner

**Pair 5** — distance: 22218m, match: same normalized name + city
- **A**: id=219 `מלון סטאי - חוף צאלון` | lat=32.836658, lng=35.648744 | g=1 | source=cello,auto_coil,data_gov,afcon | provider=ON-EV | price=2.04 | power=50kW
- **B**: id=3240 `מלון סטאי - חוף צאלון` | lat=32.650552, lng=35.562281 | g=1 | source=evm,data_gov | provider=ON EV | price=None | power=50kW
- **Recommendation**: keep id=219 — A has more sources (4 vs 2); A has price info

**Pair 6** — distance: 10884m, match: same normalized name + city
- **A**: id=3177 `תפוז עפולה` | lat=32.599548, lng=35.294717 | g=0 | source=cello,auto_coil | provider=Zen Energy | price=2.6 | power=210kW
- **B**: id=3508 `תפוז עפולה` | lat=32.593946, lng=35.410708 | g=0 | source=zen | provider=Zen Energy | price=None | power=50kW
- **Recommendation**: keep id=3177 — A has more sources (2 vs 1); A has higher power (210kW); A has price info

**Pair 7** — distance: 4493m, match: fuzzy name (sim=1.00)
- **A**: id=2816 `ראשונים סנטר` | lat=31.983859, lng=34.78247 | g=1 | source=cello,data_gov | provider=SonolEvi | price=1.6 | power=22kW
- **B**: id=2884 `פז - סונול ראשונים` | lat=31.946938, lng=34.801812 | g=1 | source=cello,evm,data_gov,paz | provider=Yellow | price=1.6 | power=150kW
- **Recommendation**: keep id=2884 — B has more sources (4 vs 2); B has higher power (150kW)

**Pair 8** — distance: 4491m, match: fuzzy name (sim=0.60)
- **A**: id=1144 `Machsanei Hashuk | Neighborhood T - Beer Sheva` | lat=31.245868, lng=34.780204 | g=0 | source=cello | provider=EvEdge | price=2.19 | power=22kW
- **B**: id=1150 `Machsanei Hashuk | Ramot neighborhood  - Beer Sheva` | lat=31.280451, lng=34.80461 | g=0 | source=cello | provider=EvEdge | price=2.19 | power=22kW
- **Recommendation**: keep manual review needed — no clear winner

**Pair 9** — distance: 4336m, match: fuzzy name (sim=1.00)
- **A**: id=2610 `קניון עזריאלי ראשונים` | lat=31.949438, lng=34.804063 | g=1 | source=cello,auto_coil,data_gov | provider=SonolEvi | price=1.6 | power=50kW
- **B**: id=2816 `ראשונים סנטר` | lat=31.983859, lng=34.78247 | g=1 | source=cello,data_gov | provider=SonolEvi | price=1.6 | power=22kW
- **Recommendation**: keep id=2610 — A has more sources (3 vs 2); A has higher power (50kW)

**Pair 10** — distance: 4332m, match: fuzzy name (sim=1.00)
- **A**: id=2816 `ראשונים סנטר` | lat=31.983859, lng=34.78247 | g=1 | source=cello,data_gov | provider=SonolEvi | price=1.6 | power=22kW
- **B**: id=2956 `קניון עזריאלי ראשונים עמדה מהירה` | lat=31.949409, lng=34.803924 | g=1 | source=cello,data_gov | provider=SonolEvi | price=2.6 | power=150kW
- **Recommendation**: keep id=2956 — B has higher power (150kW)

**Pair 11** — distance: 4174m, match: fuzzy address (sim=0.67)
- **A**: id=1296 `Menachem Begin Parking Lot | Petah Tikva` | lat=32.078054, lng=34.905885 | g=0 | source=cello,auto_coil | provider=EvEdge | price=1.99 | power=50kW
- **B**: id=3226 `פתח תקווה Supercharger` | lat=32.09692, lng=34.867583 | g=0 | source=evm,tesla | provider=Tesla | price=None | power=250kW
- **Recommendation**: keep manual review needed — B has higher power (250kW); A has price info

**Pair 12** — distance: 3691m, match: fuzzy name (sim=1.00)
- **A**: id=3035 `לאונרדו פלאזה טבריה- פתאל` | lat=32.785915, lng=35.542883 | g=1 | source=cello,data_gov | provider=ViMore | price=1.59 | power=22kW
- **B**: id=3459 `פז טבריה עילית` | lat=32.780054, lng=35.504024 | g=0 | source=paz | provider=Yellow | price=None | power=150kW
- **Recommendation**: keep id=3035 — A is gov-verified; A has more sources (2 vs 1); B has higher power (150kW); A has price info

**Pair 13** — distance: 3691m, match: fuzzy name (sim=1.00)
- **A**: id=3043 `לאונרדו פלאזה טבריה - פתאל` | lat=32.785915, lng=35.542883 | g=1 | source=cello,data_gov | provider=ViMore | price=1.59 | power=22kW
- **B**: id=3459 `פז טבריה עילית` | lat=32.780054, lng=35.504024 | g=0 | source=paz | provider=Yellow | price=None | power=150kW
- **Recommendation**: keep id=3043 — A is gov-verified; A has more sources (2 vs 1); B has higher power (150kW); A has price info

**Pair 14** — distance: 3617m, match: fuzzy name (sim=0.75)
- **A**: id=1132 `Timna Lake | Eilot` | lat=29.760262, lng=34.969255 | g=0 | source=cello,auto_coil | provider=EvEdge | price=0.51 | power=50kW
- **B**: id=1137 `Timna Lake - Mevoa | Eilot` | lat=29.787809, lng=34.989183 | g=0 | source=cello,auto_coil | provider=EvEdge | price=0.51 | power=50kW
- **Recommendation**: keep manual review needed — no clear winner

**Pair 15** — distance: 3355m, match: fuzzy name (sim=0.67)
- **A**: id=3126 `רני צים - רהט seven` | lat=31.37365, lng=34.77943 | g=1 | source=cello,auto_coil,data_gov | provider=Zen Energy | price=4.77 | power=160kW
- **B**: id=3499 `SEVEN רהט` | lat=31.394591, lng=34.753979 | g=0 | source=zen | provider=Zen Energy | price=None | power=50kW
- **Recommendation**: keep id=3126 — A is gov-verified; A has more sources (3 vs 1); A has higher power (160kW); A has price info

**Pair 16** — distance: 3299m, match: fuzzy address (sim=0.67)
- **A**: id=789 `תחנת דלק יעד פתח תקווה` | lat=32.106, lng=34.89 | g=1 | source=cello,auto_coil,data_gov | provider=Enova | price=3.02 | power=180kW
- **B**: id=2369 `Pango Office` | lat=32.090826, lng=34.859903 | g=1 | source=cello,auto_coil,data_gov,zen | provider=Scala Energy | price=1.81 | power=50kW
- **Recommendation**: keep id=2369 — B has more sources (4 vs 3); A has higher power (180kW)

**Pair 17** — distance: 3260m, match: same address + city
- **A**: id=837 `Nevo Hotel - Isrotel ltd | Dead Sea` | lat=31.192989, lng=35.361064 | g=1 | source=cello,auto_coil,data_gov | provider=EvEdge | price=2.19 | power=50kW
- **B**: id=1115 `Leonardo Club Hotel - Fattal Hotels ltd | Dead Sea` | lat=31.164185, lng=35.367479 | g=0 | source=cello,auto_coil | provider=EvEdge | price=2.19 | power=50kW
- **Recommendation**: keep id=837 — A is gov-verified; A has more sources (3 vs 2)

**Pair 18** — distance: 2872m, match: fuzzy name (sim=1.00)
- **A**: id=3092 `צים אורבן כפר סבא` | lat=32.18522, lng=34.95368 | g=1 | source=cello,auto_coil,data_gov | provider=Zen Energy | price=4.77 | power=150kW
- **B**: id=3282 `אורבן צים כפר סבא` | lat=32.179131, lng=34.924022 | g=0 | source=evm | provider=ZEN Energy | price=None | power=50kW
- **Recommendation**: keep id=3092 — A is gov-verified; A has more sources (3 vs 1); A has higher power (150kW); A has price info

**Pair 19** — distance: 2727m, match: fuzzy name (sim=1.00)
- **A**: id=544 `דור אלון-עכו` | lat=32.89983, lng=35.091107 | g=0 | source=cello,auto_coil,afcon | provider=ON-EV | price=2.75 | power=150kW
- **B**: id=2626 `קניון עזריאלי עכו` | lat=32.922938, lng=35.081313 | g=1 | source=cello,auto_coil,data_gov | provider=SonolEvi | price=1.6 | power=50kW
- **Recommendation**: keep id=2626 — B is gov-verified; A has higher power (150kW)

**Pair 20** — distance: 2391m, match: fuzzy name (sim=1.00)
- **A**: id=2771 `מול זכרון` | lat=32.56879, lng=34.933523 | g=1 | source=cello,auto_coil,evm,data_gov | provider=SonolEvi | price=1.6 | power=50kW
- **B**: id=3180 `דלק זכרון יעקב` | lat=32.59021, lng=34.93573 | g=0 | source=cello,auto_coil | provider=Zen Energy | price=2.6 | power=240kW
- **Recommendation**: keep id=2771 — A is gov-verified; A has more sources (4 vs 2); B has higher power (240kW)

**Pair 21** — distance: 2301m, match: fuzzy name (sim=1.00)
- **A**: id=370 `דור אלון-זכרון יעקב` | lat=32.569519, lng=34.936172 | g=1 | source=cello,auto_coil,evm,data_gov,afcon | provider=ON-EV | price=2.75 | power=180kW
- **B**: id=3180 `דלק זכרון יעקב` | lat=32.59021, lng=34.93573 | g=0 | source=cello,auto_coil | provider=Zen Energy | price=2.6 | power=240kW
- **Recommendation**: keep id=370 — A is gov-verified; A has more sources (5 vs 2); B has higher power (240kW)

**Pair 22** — distance: 2128m, match: fuzzy address (sim=1.00)
- **A**: id=1202 `Jumbo City of the Kings Southern Complex | Eilat` | lat=29.550181, lng=34.966114 | g=0 | source=cello,auto_coil | provider=EvEdge | price=1.68 | power=180kW
- **B**: id=2495 `GT Center - Eilat` | lat=29.569005, lng=34.962149 | g=0 | source=cello,auto_coil | provider=Scala Energy | price=2.71 | power=160kW
- **Recommendation**: keep id=1202 — A has higher power (180kW)

**Pair 23** — distance: 2105m, match: fuzzy name (sim=1.00)
- **A**: id=2608 `קניון עזריאלי חולון` | lat=32.012313, lng=34.779438 | g=1 | source=cello,auto_coil,data_gov | provider=SonolEvi | price=1.6 | power=50kW
- **B**: id=2827 `מרכז עזריאלי חולון` | lat=32.00761, lng=34.801058 | g=1 | source=cello,auto_coil,evm,data_gov | provider=SonolEvi | price=1.6 | power=250kW
- **Recommendation**: keep id=2827 — B has more sources (4 vs 3); B has higher power (250kW)

**Pair 24** — distance: 2046m, match: fuzzy name (sim=1.00)
- **A**: id=325 `דור אלון-בית קשת` | lat=32.705314, lng=35.410267 | g=1 | source=cello,auto_coil,evm,data_gov,afcon | provider=ON-EV | price=2.75 | power=180kW
- **B**: id=3136 `קיבוץ בית קשת` | lat=32.718446, lng=35.394952 | g=1 | source=cello,auto_coil,data_gov,zen | provider=Zen Energy | price=4.42 | power=50kW
- **Recommendation**: keep id=325 — A has more sources (5 vs 4); A has higher power (180kW)

**Pair 25** — distance: 2042m, match: fuzzy address (sim=1.00)
- **A**: id=1207 `Jumbo City of the Kings Northern Complex | Eilat` | lat=29.551114, lng=34.966927 | g=0 | source=cello,auto_coil | provider=EvEdge | price=1.68 | power=180kW
- **B**: id=2495 `GT Center - Eilat` | lat=29.569005, lng=34.962149 | g=0 | source=cello,auto_coil | provider=Scala Energy | price=2.71 | power=160kW
- **Recommendation**: keep id=1207 — A has higher power (180kW)

**Pair 26** — distance: 2012m, match: fuzzy address (sim=0.67)
- **A**: id=1296 `Menachem Begin Parking Lot | Petah Tikva` | lat=32.078054, lng=34.905885 | g=0 | source=cello,auto_coil | provider=EvEdge | price=1.99 | power=50kW
- **B**: id=1306 `Aharonovich Yosef | Petah Tikva` | lat=32.093463, lng=34.894691 | g=0 | source=cello | provider=EvEdge | price=1.99 | power=22kW
- **Recommendation**: keep id=1296 — A has more sources (2 vs 1); A has higher power (50kW)

**Pair 27** — distance: 1880m, match: fuzzy address (sim=1.00)
- **A**: id=3491 `Batei Zikuk Ahazaka` | lat=31.836504, lng=34.700684 | g=0 | source=interev | provider=InterEV | price=None | power=0kW
- **B**: id=3492 `Batey Zikuk Ashdod` | lat=31.84137, lng=34.681628 | g=0 | source=interev | provider=InterEV | price=None | power=0kW
- **Recommendation**: keep manual review needed — no clear winner

**Pair 28** — distance: 1864m, match: fuzzy name (sim=1.00)
- **A**: id=406 `מלונות דן-דן בוטיק ירושלים` | lat=31.76661, lng=35.225915 | g=1 | source=cello,auto_coil,data_gov,afcon | provider=ON-EV | price=2.04 | power=22kW
- **B**: id=3025 `לאונרדו בוטיק ירושלים - פתאל` | lat=31.783135, lng=35.222617 | g=1 | source=cello,auto_coil,data_gov | provider=ViMore | price=1.59 | power=22kW
- **Recommendation**: keep id=406 — A has more sources (4 vs 3)

**Pair 29** — distance: 1825m, match: fuzzy name (sim=1.00)
- **A**: id=1232 `Ofer Mall | Hadera` | lat=32.437894, lng=34.921999 | g=0 | source=cello,auto_coil,evm | provider=EvEdge | price=2.19 | power=50kW
- **B**: id=2371 `TEN Hadera` | lat=32.450597, lng=34.909685 | g=1 | source=cello,data_gov | provider=Scala Energy | price=5.44 | power=160kW
- **Recommendation**: keep id=2371 — B is gov-verified; A has more sources (3 vs 2); B has higher power (160kW)

**Pair 30** — distance: 1729m, match: fuzzy name (sim=0.67)
- **A**: id=358 `דור אלון - מצפה רמון` | lat=30.627637, lng=34.805916 | g=1 | source=cello,auto_coil,data_gov,afcon | provider=ON-EV | price=2.75 | power=200kW
- **B**: id=1589 `2898 - מצפה רמון - פרטי` | lat=30.613227, lng=34.79912 | g=1 | source=cello,data_gov | provider=Greems | price=1.1 | power=22kW
- **Recommendation**: keep id=358 — A has more sources (4 vs 2); A has higher power (200kW)


## Recommendations (not executed)

### High Priority

- **Review 23 stations outside Israel's bounding box** — likely test/demo data or foreign locations; candidates for removal.

- **Review 82 stations >25 km from their declared city** — either the coordinates or the city label is wrong.

### Medium Priority

- **Review 34 stations 12–25 km from city center** — many are legitimate (highway, industrial zones, regional councils).

- **Review 97 duplicate pairs** — decide per pair; the `recommended_keep` column is a heuristic (g=1, more sources, power, price).

- **Fill the city for 78 stations** from the suggestions above, after checking each one.

### Systemic

- The existing dedup (`data/dedup_db.py`) matches within 50 m or identical names; pairs above show duplicates it cannot catch when one copy has wrong coordinates.

- Add a coastline / bounding-box check to the import pipeline.


## Method & Limitations

### Water Detection

1. **Bounding box**: outside lat 29.4–33.4, lng 34.2–35.95 → 'outside Israel'.

2. **Coastline threshold + reverse geocoding**: inside the bbox, a latitude-banded longitude threshold approximates the Mediterranean coast. Points west of it are reverse-geocoded; no local address component (road, city, suburb, …) → 'water'. Failed lookups are listed separately as unverified, never counted as water.

**Potential false positives**: beaches, marinas, ports, and new areas missing from OSM. The Sea of Galilee, Dead Sea and Eilat bay are not checked.

### City Distance

- City centers from Nominatim search (cached in city_centers_cache.json). Haversine distance station → center.

- **Potential false positives**: highway stations, industrial zones, regional councils / moshavim labelled with a council name whose geocoded point is arbitrary, large municipalities, and ambiguous city names that Nominatim resolved to the wrong place.

### Duplicate Detection

- Exact normalized address + city; exact normalized name + city; fuzzy name or address (Jaccard ≥ 0.6) within the same city. Fuzzy matching ignores tokens shared by more than 10 stations (chain names, 'parking lot', city names). Only pairs >500 m apart.

- **Potential false positives**: different sites sharing a generic name (e.g. a chain's name only) or a generic address (a mall, a street without number) in the same city.
