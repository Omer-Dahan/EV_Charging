# Location Verification Report — 2026-09-29 01:05

Read-only verification. **No station was changed, merged or deleted.** All verdicts are proposals for manual review.

## Summary

| Metric | Count |
|--------|------:|
| Stations verified (individual) | 213 |
| Duplicate pairs verified | 80 |
| Verdict: CONFIRMED_FOREIGN_OR_TEST (stations) | 23 |
| Verdict: CONFIRMED_OK (stations) | 78 |
| Verdict: CONFIRMED_WRONG_CITY (stations) | 75 |
| Verdict: CONFIRMED_WRONG_COORDS (stations) | 34 |
| Verdict: UNVERIFIED (stations) | 3 |
| Verdict: CONFIRMED_DUPLICATE (dup pairs) | 65 |
| Verdict: NOT_DUPLICATE (dup pairs) | 15 |
| Nominatim requests | 333 |
| Cache hits | 105 |
| 429 errors | 4 |
| Failed requests | 0 |
| Elapsed time | 836s |

## Foreign / Test Stations

| id | name | city | lat | lng | verdict | evidence |
|---:|------|------|----:|----:|---------|----------|
| 1484 | Gnrgy ES Office | Barcelona | 41.3781 | 2.1335 | CONFIRMED_FOREIGN_OR_TEST | Test/demo station. Coords (41.378115, 2.133519) are outside Israel. Reverse: roa |
| 1518 | Demo site | city | 21.0000 | 20.0000 | CONFIRMED_FOREIGN_OR_TEST | Test/demo station. Coords (21.0, 20.0) are outside Israel. Reverse: no local add |
| 1520 | בנגלור 1 | בנגלור | 12.9087 | 77.6504 | CONFIRMED_FOREIGN_OR_TEST | Located in הודו. Coords (12.908742, 77.650445). Operator data likely imported fr |
| 1524 | Adgar Wave Public | Warszawa | 52.1770 | 21.0013 | CONFIRMED_FOREIGN_OR_TEST | Located in פולין. Coords (52.177042, 21.001314). Operator data likely imported f |
| 1525 | Adgar Park West | Warszawa | 52.2102 | 20.9533 | CONFIRMED_FOREIGN_OR_TEST | Located in פולין. Coords (52.210151, 20.953259). Operator data likely imported f |
| 1527 | Adgar Plaza Public | Warszawa | 52.1810 | 20.9962 | CONFIRMED_FOREIGN_OR_TEST | Located in פולין. Coords (52.181012, 20.996208). Operator data likely imported f |
| 1529 | Heron’s Hill | toronto | 43.7750 | -79.3383 | CONFIRMED_FOREIGN_OR_TEST | Located in קנדה. Coords (43.775021, -79.33834). Operator data likely imported fr |
| 1531 | Adgar Theater Public | Antwerpen | 51.2201 | 4.4156 | CONFIRMED_FOREIGN_OR_TEST | Located in בֶּלְגְיָה. Coords (51.22005, 4.41562). Operator data likely imported |
| 1532 | Adgar Renaissance Tower | Warszawa | 52.2301 | 20.9709 | CONFIRMED_FOREIGN_OR_TEST | Located in פולין. Coords (52.23013, 20.97095). Operator data likely imported fro |
| 1534 | Adgar Plaza High Speed | Warszawa | 52.1807 | 20.9961 | CONFIRMED_FOREIGN_OR_TEST | Located in פולין. Coords (52.180733, 20.996094). Operator data likely imported f |
| 1535 | 9050 Yonge St | Richmond Hill,  | 43.8468 | -79.4320 | CONFIRMED_FOREIGN_OR_TEST | Located in קנדה. Coords (43.846844, -79.431998). Operator data likely imported f |
| 1536 | Adgar Plantin | Antwerpen | 51.2109 | 4.4185 | CONFIRMED_FOREIGN_OR_TEST | Located in בֶּלְגְיָה. Coords (51.210928, 4.418498). Operator data likely import |
| 1545 | Adgar 120 Bloor | Toronto | 43.6712 | -79.3838 | CONFIRMED_FOREIGN_OR_TEST | Located in קנדה. Coords (43.671213, -79.383809). Operator data likely imported f |
| 1561 | 111 Gordon Baker Rd | Toronto | 43.8020 | -79.3434 | CONFIRMED_FOREIGN_OR_TEST | Located in קנדה. Coords (43.802029, -79.343367). Operator data likely imported f |
| 1562 | 40 Eglinton Ave E | Toronto | 43.7069 | -79.3986 | CONFIRMED_FOREIGN_OR_TEST | Located in קנדה. Coords (43.706876, -79.398617). Operator data likely imported f |
| 1578 | 1270-1300 Central | Mississauga | 43.5676 | -79.6642 | CONFIRMED_FOREIGN_OR_TEST | Located in קנדה. Coords (43.567596, -79.664159). Operator data likely imported f |
| 1606 | Adgar 302 Town Centre Blvd | Markham | 43.8598 | -79.3402 | CONFIRMED_FOREIGN_OR_TEST | Located in קנדה. Coords (43.85982, -79.340186). Operator data likely imported fr |
| 1620 | Adgar 350 Burnhamthorpe | Mississauga | 43.5853 | -79.6433 | CONFIRMED_FOREIGN_OR_TEST | Located in קנדה. Coords (43.585301, -79.643339). Operator data likely imported f |
| 1626 | 5000 | Kraków | 50.0483 | 19.9434 | CONFIRMED_FOREIGN_OR_TEST | Located in פולין. Coords (50.048278, 19.943406). Operator data likely imported f |
| 3196 | Gnrgyאבגדהוזחטיכלמנסעפצקרש |  | 12.9198 | 77.6508 | CONFIRMED_FOREIGN_OR_TEST | Test/demo station. Coords (12.919809, 77.650814) are outside Israel. Reverse: ro |
| 3197 | , ישראל |  | 77.0000 | 12.0000 | CONFIRMED_FOREIGN_OR_TEST | Test/demo station. Coords (77.0, 12.0) are outside Israel. Reverse: unable to ge |
| 3198 | Charging station test |  | 12.9500 | 77.6516 | CONFIRMED_FOREIGN_OR_TEST | Test/demo station. Coords (12.95, 77.651598) are outside Israel. Reverse: road=W |
| 3199 | בנגלור 2 |  | 12.9235 | 77.6515 | CONFIRMED_FOREIGN_OR_TEST | Located in הודו. Coords (12.923473, 77.651469). Operator data likely imported fr |

## The Reported Cases (id=3283, id=3284)

### Station id=3283: גראנד קניון- חיפה

- **Address**: דרך שמחה גולן 54, חיפה
- **City**: חיפה
- **Coordinates**: (32.999574, 34.967197)
- **Sources**: evm
- **Gov-verified (g)**: 0
- **Verdict**: **CONFIRMED_WRONG_COORDS**
- **Evidence**: Coordinates are in water/void. country-level only (rank=4): type=administrative, class=boundary, display=ישראל. Address 'דרך שמחה גולן 54, חיפה' should be in חיפה. Suggested coords: (32.789015, 35.011632)
- **Suggested coordinates**: (32.789015, 35.011632)
- **Distance from geocoded address**: 23.78 km
- **Methods used**: reverse: country-level only (rank=4): type=administrative, class=boundary, display=ישראל; forward: geocoded to (32.789015, 35.011632), 23.8 km from current. Display: יוחנן רטנר/דרך שמחה גולן, יוחנן ר

### Station id=3284: גראנד קניון ב"ש- חניון צפוני

- **Address**: שדרות דוד טוביהו 125, באר שבע
- **City**: באר שבע
- **Coordinates**: (31.358888, 34.780752)
- **Sources**: evm
- **Gov-verified (g)**: 0
- **Verdict**: **CONFIRMED_WRONG_COORDS**
- **Evidence**: Current coords are 12.1 km from geocoded address. At current coords: road=, city=מועצה אזורית בני שמעון, suburb=, country=ישראל. Geocoded: (31.250298, 34.771804)
- **Suggested coordinates**: (31.250298, 34.771804)
- **Distance from geocoded address**: 12.1 km
- **Methods used**: reverse: road=, city=מועצה אזורית בני שמעון, suburb=, country=ישראל; forward: geocoded to (31.250298, 34.771804), 12.1 km from current. Display: גרנד קניון באר שבע, 125, שדרות דו

## Far from City

| id | name | city | verdict | old lat | old lng | suggested lat | suggested lng | geocode dist km | evidence |
|---:|------|------|---------|--------:|--------:|--------------:|--------------:|----------------:|----------|
| 105 | צומת גוש ציון | גוש עציון | CONFIRMED_WRONG_CITY | 31.644813 | 35.130882 |  |  |  | Reverse says 'מועצה אזורית גוש עציון', declared city is 'גוש עציון'. r |
| 212 | מילוס-ים המלח -לאורחי המלון | ים המלח | CONFIRMED_WRONG_CITY | 31.201437 | 35.364503 | 31.201383 | 35.363884 | 0.06 | Coords match address (0.1 km), but reverse says city is 'מועצה אזורית  |
| 229 | כפר הנופש רמות , כנרת | רמות | CONFIRMED_WRONG_CITY | 32.859332 | 35.659963 |  |  |  | Reverse says 'מועצה אזורית גולן', declared city is 'רמות'. road=אל על, |
| 251 | הוד-ים מלח -לאורחי המלון | ים המלח | CONFIRMED_WRONG_CITY | 31.201942 | 35.363640 | 31.201383 | 35.363884 | 0.07 | Coords match address (0.1 km), but reverse says city is 'מועצה אזורית  |
| 271 | אואזיס ים המלח-לאורחי המלון | ים המלח | CONFIRMED_WRONG_CITY | 31.195378 | 35.361268 | 31.201383 | 35.363884 | 0.71 | Coords match address (0.7 km), but reverse says city is 'מועצה אזורית  |
| 301 | מלון לוט-לאורחי המלון | ים המלח | CONFIRMED_WRONG_CITY | 31.200025 | 35.364468 | 31.201383 | 35.363884 | 0.16 | Coords match address (0.2 km), but reverse says city is 'מועצה אזורית  |
| 464 | דור אלון צומת הגומא | הגומא | CONFIRMED_WRONG_CITY | 33.170044 | 35.570974 |  |  |  | Reverse says 'מועצה אזורית גליל עליון', declared city is 'הגומא'. road |
| 499 | דור אלון -פארק חדרה כביש 4 | דרום חדרה | CONFIRMED_WRONG_CITY | 32.413900 | 34.904164 |  |  |  | Reverse says 'חדרה', declared city is 'דרום חדרה'. road=כביש חיפה רעננ |
| 504 | מפגש הבקעה-כביש 90 | בקעת הירדן | UNVERIFIED | 32.055919 | 35.470586 |  |  |  | Could not determine. Reverse: road=גנדי(זאבי), city=, suburb=, country |
| 551 | דור אלון-חצור הגלילית | חצור | CONFIRMED_WRONG_CITY | 32.980749 | 35.555218 | 32.980733 | 35.555270 | 0.01 | Coords match address (0.0 km), but reverse says city is 'חצור הגלילית' |
| 556 | דור אלון -ג'ת | דור אלון | CONFIRMED_WRONG_CITY | 32.388923 | 35.042966 |  |  |  | Reverse says 'ג'ת', declared city is 'דור אלון'. road=574, city=ג'ת, s |
| 558 | מרכז קהילתי מיר"ב חוף הכרמל | חוף הכרמל | CONFIRMED_WRONG_CITY | 32.646544 | 34.965045 |  |  |  | Reverse says 'מועצה אזורית חוף הכרמל', declared city is 'חוף הכרמל'. r |
| 561 | דור אלון-פארק אפק, ראש העין | ראש עין | CONFIRMED_WRONG_CITY | 32.085878 | 34.980432 |  |  |  | Reverse says 'ראש העין', declared city is 'ראש עין'. road=, city=ראש ה |
| 581 | פז - עין חצבה - עמדה מהירה 2 | כביש הערבה | CONFIRMED_WRONG_COORDS | 30.798883 | 35.244076 | 31.248332 | 35.197941 | 50.17 | Current coords are 50.2 km from geocoded address. At current coords: r |
| 582 | עין חצבה - עמדה מהירה 1 | כביש הערבה | CONFIRMED_WRONG_COORDS | 30.798883 | 35.244076 | 31.248332 | 35.197941 | 50.17 | Current coords are 50.2 km from geocoded address. At current coords: r |
| 626 | הרואה בקפה - DC 40 | חיפה | CONFIRMED_WRONG_COORDS | 32.393116 | 34.915413 | 32.818807 | 35.001096 | 48.01 | Current coords are 48.0 km from geocoded address. At current coords: r |
| 628 | בית מלון Oaks | רמת הגולן | CONFIRMED_WRONG_CITY | 33.201393 | 35.773195 |  |  |  | Reverse says 'בוקעאתא', declared city is 'רמת הגולן'. road=98, city=בו |
| 635 | החברה לפיתוח דרום הר חברון - חניה מ | הר חברון | CONFIRMED_WRONG_CITY | 31.373868 | 35.006090 |  |  |  | Reverse says 'מועצה אזורית הר חברון', declared city is 'הר חברון'. roa |
| 636 | החברה לפיתוח דרום הר חברון - חניה ר | הר חברון | CONFIRMED_WRONG_CITY | 31.375197 | 35.006424 |  |  |  | Reverse says 'מועצה אזורית הר חברון', declared city is 'הר חברון'. roa |
| 641 | קריית צאנז נתניה עמדת AC כפולה | נתניה | CONFIRMED_WRONG_COORDS | 32.820125 | 34.999321 | 32.344519 | 34.855661 | 54.57 | Current coords are 54.6 km from geocoded address. At current coords: r |
| 667 | Kfar Kara _Local Council | מחוז חיפה | CONFIRMED_WRONG_CITY | 32.505808 | 35.047237 | 32.502991 | 35.050500 | 0.44 | Coords match address (0.4 km), but reverse says city is 'כפר קרע', not |
| 668 | Haemek hospital | North District | CONFIRMED_WRONG_CITY | 32.619060 | 35.312586 | 32.621325 | 35.313845 | 0.28 | Coords match address (0.3 km), but reverse says city is 'עפולה', not ' |
| 671 | Kibbutz Nachshon_Factory | לוד | CONFIRMED_WRONG_CITY | 31.829089 | 34.955177 |  |  |  | Reverse says 'מועצה אזורית מטה יהודה', declared city is 'לוד'. road=42 |
| 721 | Rami Levy_Gush Etzion Branch | גוש עציון | CONFIRMED_WRONG_CITY | 31.644691 | 35.130758 |  |  |  | Reverse says 'מועצה אזורית גוש עציון', declared city is 'גוש עציון'. r |
| 743 | The Israeli addiction Center | Unknown | CONFIRMED_WRONG_CITY | 31.794683 | 35.241035 |  |  |  | Reverse says 'ירושלים', declared city is 'Unknown'. road=זלמן שוקן, ci |
| 837 | Nevo Hotel - Isrotel ltd \| Dead Sea | Dead Sea | CONFIRMED_WRONG_CITY | 31.192989 | 35.361064 | 31.201383 | 35.363884 | 0.97 | Coords match address (1.0 km), but reverse says city is 'מועצה אזורית  |
| 854 | Isrotel Noga Hotel \| Dead Sea | Dead Sea | CONFIRMED_WRONG_CITY | 31.198361 | 35.361836 |  |  |  | Reverse says 'מועצה אזורית תמר', declared city is 'Dead Sea'. road=דרך |
| 889 | Nof Hasadot \| Kibbutz Negba - Yoav  | Yoav Regional C | CONFIRMED_WRONG_COORDS | 31.658169 | 34.684525 | 31.763304 | 35.211982 | 51.25 | Current coords are 51.2 km from geocoded address. At current coords: r |
| 1101 | Eilot Council Square \| Eilot | Eilot | CONFIRMED_WRONG_CITY | 29.892948 | 35.064030 |  |  |  | Reverse says 'מועצה אזורית חבל אילות', declared city is 'Eilot'. road= |
| 1109 | Hevel Eilot \| Eilot | Eilot | CONFIRMED_WRONG_COORDS | 29.894524 | 35.065298 | 32.062951 | 34.769329 | 242.76 | Current coords are 242.8 km from geocoded address. At current coords:  |
| 1115 | Leonardo Club Hotel - Fattal Hotels | Dead Sea | CONFIRMED_WRONG_COORDS | 31.164185 | 35.367479 | 31.201383 | 35.363884 | 4.15 | Coords 4.2 km from geocoded address. Reverse city: 'מועצה אזורית תמר', |
| 1132 | Timna Lake \| Eilot | Eilot | CONFIRMED_WRONG_COORDS | 29.760262 | 34.969255 | 32.788192 | 35.638211 | 342.64 | Current coords are 342.6 km from geocoded address. At current coords:  |
| 1137 | Timna Lake - Mevoa \| Eilot | Eilot | CONFIRMED_WRONG_CITY | 29.787809 | 34.989183 |  |  |  | Reverse says 'מועצה אזורית חבל אילות', declared city is 'Eilot'. road= |
| 1162 | Vert Hotel \| Dead Sea | Dead Sea | CONFIRMED_WRONG_CITY | 31.200606 | 35.365269 | 31.201383 | 35.363884 | 0.16 | Coords match address (0.2 km), but reverse says city is 'מועצה אזורית  |
| 1203 | Commercial Complex Bitans \|  Bitan  | Beit Aharon | UNVERIFIED | 32.361358 | 34.868017 |  |  |  | Could not determine. Reverse: road=5710, city=, suburb=, country=ישראל |
| 1234 | Megiddo Junction \| Commercial Cente | North District | CONFIRMED_WRONG_CITY | 32.571526 | 35.184288 |  |  |  | Reverse says 'מועצה אזורית מגידו', declared city is 'North District'.  |
| 1311 | Isrotel Kayma Hotel \| dead sea | Unknown | CONFIRMED_WRONG_CITY | 31.193318 | 35.362394 | 31.201383 | 35.363884 | 0.91 | Coords match address (0.9 km), but reverse says city is 'מועצה אזורית  |
| 1351 | Shufersal ltd \| Rehovot HaHadasha \| | Unknown | CONFIRMED_WRONG_CITY | 31.880520 | 34.812311 | 31.903055 | 34.812437 | 2.51 | Coords match address (2.5 km), but reverse says city is 'רחובות', not  |
| 1435 | The Hamtens parking lot \| Dimona Mu | מחוז הדרום | CONFIRMED_WRONG_CITY | 31.064381 | 35.032085 | 31.068661 | 35.036648 | 0.64 | Coords match address (0.6 km), but reverse says city is 'דימונה', not  |
| 1436 | Mirage Parking Lot \| Dimona Municip | מחוז הדרום | CONFIRMED_WRONG_CITY | 31.067568 | 35.037286 | 31.065451 | 35.023610 | 1.32 | Coords match address (1.3 km), but reverse says city is 'דימונה', not  |
| 1437 | The Post Office Parking Lot \| Dimon | מחוז הדרום | CONFIRMED_WRONG_CITY | 31.066557 | 35.034154 | 31.065658 | 35.034543 | 0.11 | Coords match address (0.1 km), but reverse says city is 'דימונה', not  |
| 1471 | פונדק כושי הק"מ 101 | כביש הערבה | CONFIRMED_WRONG_CITY | 30.306744 | 35.134586 |  |  |  | Reverse says 'מועצה אזורית הערבה התיכונה', declared city is 'כביש הערב |
| 1479 | כפר מנחם | כפר | CONFIRMED_WRONG_COORDS | 31.729733 | 34.838861 | 31.788339 | 35.213930 | 36.05 | Current coords are 36.1 km from geocoded address. At current coords: r |
| 1487 | המרכז של קרסו אבן יהודה | אבן יהודה | CONFIRMED_WRONG_COORDS | 32.269877 | 34.888621 | 32.574525 | 34.954112 | 34.43 | Current coords are 34.4 km from geocoded address. At current coords: r |
| 1490 | קניון צים סנטר מעלות | מעלות | CONFIRMED_WRONG_CITY | 33.021167 | 35.280394 | 33.019899 | 35.283323 | 0.31 | Coords match address (0.3 km), but reverse says city is 'מעלות תרשיחא' |
| 1497 | קיבוץ תל קציר | תל | CONFIRMED_WRONG_COORDS | 32.705753 | 35.619317 | 32.488630 | 35.101689 | 54.17 | Current coords are 54.2 km from geocoded address. At current coords: r |
| 1509 | חדשות 12 (לעובדים ואורחים בלבד) | נווה אילן | CONFIRMED_WRONG_COORDS | 31.808323 | 35.080879 | 31.667790 | 34.578546 | 50.01 | Current coords are 50.0 km from geocoded address. At current coords: r |
| 1553 | 1309 - E (פרטי) | נופים | CONFIRMED_WRONG_COORDS | 32.158066 | 34.973009 | 32.157882 | 34.881840 | 8.58 | Current coords are 8.6 km from geocoded address. At current coords: ro |
| 1633 | חניון מועצה רמת הנגב | רמת הנגב | CONFIRMED_WRONG_COORDS | 31.003910 | 34.771460 | 33.221143 | 35.630069 | 259.46 | Current coords are 259.5 km from geocoded address. At current coords:  |
| 1752 | אלרום | אלרום | CONFIRMED_WRONG_COORDS | 33.178548 | 35.771916 | 32.069113 | 34.840217 | 151.1 | Current coords are 151.1 km from geocoded address. At current coords:  |
| 1814 | יקבי גוש עציון | צומת | CONFIRMED_WRONG_CITY | 31.648277 | 35.129976 |  |  |  | Reverse says 'מועצה אזורית גוש עציון', declared city is 'צומת'. road=, |
| 1854 | מדרשת רמת הגולן | רמת הגולן | CONFIRMED_WRONG_COORDS | 32.850071 | 35.797567 | 32.988882 | 35.681834 | 18.84 | Current coords are 18.8 km from geocoded address. At current coords: r |
| 1864 | בית השותפויות | אכזיב | CONFIRMED_WRONG_COORDS | 33.056934 | 35.104928 | 32.427106 | 34.927261 | 71.98 | Current coords are 72.0 km from geocoded address. At current coords: r |
| 1888 | חניית רכש | מרום גליל | CONFIRMED_WRONG_COORDS | 32.997285 | 35.440831 | 32.937578 | 35.454301 | 6.76 | Current coords are 6.8 km from geocoded address. At current coords: ro |
| 1889 | כניסה משרדי רכש | מרום גליל | CONFIRMED_WRONG_COORDS | 32.997070 | 35.440621 | 32.937578 | 35.454301 | 6.74 | Current coords are 6.7 km from geocoded address. At current coords: ro |
| 1917 | Ar Bracha-Kashti | Bracha | CONFIRMED_WRONG_COORDS | 32.191895 | 35.264433 | 32.089479 | 34.858705 | 39.86 | Current coords are 39.9 km from geocoded address. At current coords: r |
| 1939 | Ar Bracha-kindergarten | Bracha | CONFIRMED_WRONG_COORDS | 32.194712 | 35.267404 | 32.095925 | 34.878732 | 38.21 | Current coords are 38.2 km from geocoded address. At current coords: r |
| 1952 | Hacal Golan - Hispin Pool | חספין | CONFIRMED_WRONG_CITY | 32.844496 | 35.794385 |  |  |  | Reverse says 'מועצה אזורית גולן', declared city is 'חספין'. road=טיילת |
| 1971 | חוף ביאנקיני בים המלח | ים המלח | CONFIRMED_WRONG_CITY | 31.761088 | 35.500980 |  |  |  | Reverse says 'מועצה אזורית מגילות ים המלח', declared city is 'ים המלח' |
| 1976 | בית הברכה | חברון | CONFIRMED_WRONG_CITY | 31.632412 | 35.132047 |  |  |  | Reverse says 'מועצה אזורית גוש עציון', declared city is 'חברון'. road= |
| 2173 | Mechinat otzem | Neve | CONFIRMED_WRONG_COORDS | 31.163300 | 34.334600 | 31.842212 | 35.242060 | 114.46 | Current coords are 114.5 km from geocoded address. At current coords:  |
| 2271 | Scala office | Neve Yamin | CONFIRMED_WRONG_CITY | 32.169665 | 34.933477 | 32.169743 | 34.934084 | 0.06 | Coords match address (0.1 km), but reverse says city is 'מועצה אזורית  |
| 2301 | Beit Mai Parking - Haifa | Haifa District | CONFIRMED_WRONG_CITY | 32.814305 | 34.998055 |  |  |  | Reverse says 'חיפה', declared city is 'Haifa District'. road=חסן שוקרי |
| 2302 | Givat Haim Ihud - Hot Spot | Center District | CONFIRMED_WRONG_CITY | 32.399125 | 34.929527 | 32.400277 | 34.933050 | 0.35 | Coords match address (0.4 km), but reverse says city is 'גבעת חיים (אי |
| 2303 | Rishpon | Center District | CONFIRMED_WRONG_CITY | 32.201468 | 34.820055 | 32.198838 | 34.829453 | 0.93 | Coords match address (0.9 km), but reverse says city is 'רשפון', not ' |
| 2312 | Kochav Yokneam business center | North District | CONFIRMED_WRONG_COORDS | 32.662569 | 35.105113 | 33.018562 | 35.097379 | 39.59 | Current coords are 39.6 km from geocoded address. At current coords: r |
| 2314 | Piano Center - South | Center District | CONFIRMED_WRONG_CITY | 32.277692 | 34.841963 | 32.278218 | 34.842195 | 0.06 | Coords match address (0.1 km), but reverse says city is 'נתניה', not ' |
| 2319 | TEN Nesher - Tel Hanan shopping cen | Haifa District | CONFIRMED_WRONG_CITY | 32.777664 | 35.039791 |  |  |  | Reverse says 'נשר', declared city is 'Haifa District'. road=דרך בר יהו |
| 2324 | TEN Ashkelon - HaMetakhnen 10 | South District | CONFIRMED_WRONG_CITY | 31.635131 | 34.553519 |  |  |  | Reverse says 'אשקלון', declared city is 'South District'. road=המתכנן, |
| 2328 | Nir David - Movement World | North District | CONFIRMED_WRONG_CITY | 32.505952 | 35.457530 | 32.502737 | 35.456750 | 0.36 | Coords match address (0.4 km), but reverse says city is 'מועצה אזורית  |
| 2329 | Nir David - Laundry | North District | CONFIRMED_WRONG_CITY | 32.506612 | 35.456425 | 32.502737 | 35.456750 | 0.43 | Coords match address (0.4 km), but reverse says city is 'מועצה אזורית  |
| 2330 | TEN Haifa - Oil Coast | Haifa District | CONFIRMED_WRONG_CITY | 32.807432 | 35.015821 | 32.807547 | 35.015179 | 0.06 | Coords match address (0.1 km), but reverse says city is 'חיפה', not 'H |
| 2333 | TEN Zavdiel | South District | CONFIRMED_WRONG_CITY | 31.652614 | 34.762759 | 31.658429 | 34.759748 | 0.71 | Coords match address (0.7 km), but reverse says city is 'מועצה אזורית  |
| 2499 | Alonim - Old Laundry | North District | CONFIRMED_WRONG_CITY | 32.720819 | 35.142512 | 32.719909 | 35.144694 | 0.23 | Coords match address (0.2 km), but reverse says city is 'מועצה אזורית  |
| 2500 | Alonim - Ceramic Studio | North District | CONFIRMED_WRONG_CITY | 32.721376 | 35.143585 | 32.719909 | 35.144694 | 0.19 | Coords match address (0.2 km), but reverse says city is 'מועצה אזורית  |
| 2501 | Alonim - Tennis Court | North District | CONFIRMED_WRONG_CITY | 32.721992 | 35.146274 | 32.719909 | 35.144694 | 0.27 | Coords match address (0.3 km), but reverse says city is 'מועצה אזורית  |
| 2586 | כינר | טבריה | CONFIRMED_WRONG_CITY | 32.862060 | 35.645630 |  |  |  | Reverse says 'מועצה אזורית גולן', declared city is 'טבריה'. road=92, c |
| 2587 | קיבוץ אפיקים | קיבוץ אפיקים | CONFIRMED_WRONG_COORDS | 32.679845 | 35.578389 | 32.093311 | 34.969990 | 86.7 | Current coords are 86.7 km from geocoded address. At current coords: r |
| 2653 | קיבוץ דליה - חניה שכונה כב | קיבוץ דליה | CONFIRMED_WRONG_COORDS | 32.588037 | 35.070318 | 32.146625 | 34.883788 | 52.12 | Current coords are 52.1 km from geocoded address. At current coords: r |
| 2662 | קיבוץ אפיקים - חניה פרבר | קיבוץ אפיקים | CONFIRMED_WRONG_COORDS | 32.680564 | 35.577730 | 32.093311 | 34.969990 | 86.72 | Current coords are 86.7 km from geocoded address. At current coords: r |
| 2671 | מפעלי ים המלח סדום חניה | סדום | CONFIRMED_WRONG_CITY | 31.029189 | 35.363469 | 31.033615 | 35.366420 | 0.57 | Coords match address (0.6 km), but reverse says city is 'מועצה אזורית  |
| 2683 | סונול עירון | צומת חנה | CONFIRMED_WRONG_CITY | 32.459003 | 34.987716 |  |  |  | Reverse says 'פרדס חנה - כרכור', declared city is 'צומת חנה'. road=65, |
| 2716 | מועצה בני שמעון חניה | בני שמעון | CONFIRMED_WRONG_COORDS | 31.442056 | 34.761263 | 31.330693 | 34.776955 | 12.47 | Current coords are 12.5 km from geocoded address. At current coords: r |
| 2722 | חניה שכונה מערבית | קיבוץ גבת | CONFIRMED_WRONG_CITY | 32.676940 | 35.210326 |  |  |  | Reverse says 'מועצה אזורית עמק יזרעאל', declared city is 'קיבוץ גבת'.  |
| 2725 | חניון כרם דרום | קיבוץ גבת | CONFIRMED_WRONG_CITY | 32.673338 | 35.211440 |  |  |  | Reverse says 'מועצה אזורית עמק יזרעאל', declared city is 'קיבוץ גבת'.  |
| 2746 | חניון הכלבו | קיבוץ גבת | CONFIRMED_WRONG_CITY | 32.675953 | 35.212555 |  |  |  | Reverse says 'מועצה אזורית עמק יזרעאל', declared city is 'קיבוץ גבת'.  |
| 2758 | חניה-בית מוסדות | קיבוץ דליה | CONFIRMED_WRONG_COORDS | 32.590879 | 35.075777 | 32.146625 | 34.883788 | 52.59 | Current coords are 52.6 km from geocoded address. At current coords: r |
| 2764 | חניון אשטרומים | קיבוץ גבת | CONFIRMED_WRONG_CITY | 32.673755 | 35.211990 |  |  |  | Reverse says 'מועצה אזורית עמק יזרעאל', declared city is 'קיבוץ גבת'.  |
| 2938 | חניה שכונת כוח אפיקים | קיבוץ אפיקים | CONFIRMED_WRONG_COORDS | 32.680832 | 35.574417 | 32.093311 | 34.969990 | 86.54 | Current coords are 86.5 km from geocoded address. At current coords: r |
| 2939 | אולם מופעים אפיקים | קיבוץ אפיקים | CONFIRMED_WRONG_COORDS | 32.682312 | 35.580032 | 32.093311 | 34.969990 | 87.01 | Current coords are 87.0 km from geocoded address. At current coords: r |
| 2993 | שיח מדבר (מרחבעם) | מרחב עם | CONFIRMED_WRONG_COORDS | 30.809577 | 34.741866 | 30.888619 | 34.828885 | 12.09 | Current coords are 12.1 km from geocoded address. At current coords: r |
| 3012 | סונול שפיה | כביש 67 | CONFIRMED_WRONG_CITY | 32.587326 | 34.980289 |  |  |  | Reverse says 'זכרון יעקב', declared city is 'כביש 67'. road=ואדי מילק, |
| 3027 | מחסן מלאי | בית רימון | CONFIRMED_WRONG_CITY | 31.046051 | 34.851612 |  |  |  | Reverse says 'מועצה אזורית רמת נגב', declared city is 'בית רימון'. roa |
| 3063 | אשדוד DC - ברק בן אבינועם 6 | אשדוד | CONFIRMED_WRONG_COORDS | 31.046051 | 34.851612 | 32.333539 | 34.868207 | 143.17 | Current coords are 143.2 km from geocoded address. At current coords:  |
| 3086 | דלק גל הערבה | גל הערבה | CONFIRMED_WRONG_CITY | 30.985280 | 35.307430 | 30.987586 | 35.308952 | 0.29 | Coords match address (0.3 km), but reverse says city is 'מועצה אזורית  |
| 3104 | דלק מסמיה | מלאכי | CONFIRMED_WRONG_CITY | 31.758350 | 34.783680 | 31.759910 | 34.784064 | 0.18 | Coords match address (0.2 km), but reverse says city is 'מועצה אזורית  |
| 3128 | דלק דרור (זקס) אבן יהודה | אבן יהודה | CONFIRMED_OK | 32.256170 | 34.877440 |  |  |  | Reverse geocode confirms city 'אבן יהודה'. road=553, city=אבן יהודה, s |
| 3132 | ישיבת הגולן - חיספין | רמת הגולן | CONFIRMED_WRONG_CITY | 32.845630 | 35.792990 | 32.845073 | 35.792836 | 0.06 | Coords match address (0.1 km), but reverse says city is 'מועצה אזורית  |
| 3174 | חניית הנהלה מתחם שורק למורשים בלבד | ראשון לציון | CONFIRMED_WRONG_CITY | 31.046051 | 34.851612 |  |  |  | Reverse says 'מועצה אזורית רמת נגב', declared city is 'ראשון לציון'. r |
| 3181 | דלק מעבר מכמש | כביש 60 | CONFIRMED_WRONG_CITY | 31.872692 | 35.259869 |  |  |  | Reverse says 'מועצה אזורית מטה בנימין', declared city is 'כביש 60'. ro |
| 3182 | דלק שדי תרומות (בכורה) | כביש 90 | CONFIRMED_WRONG_CITY | 32.448380 | 35.483040 |  |  |  | Reverse says 'מועצה אזורית עמק המעיינות', declared city is 'כביש 90'.  |
| 3240 | מלון סטאי - חוף צאלון | כנרת | CONFIRMED_WRONG_CITY | 32.650552 | 35.562281 |  |  |  | Reverse says 'מועצה אזורית עמק המעיינות', declared city is 'כנרת'. roa |
| 3272 | מודיעין הראל | המכונאי 2 | CONFIRMED_WRONG_CITY | 31.895316 | 34.959504 |  |  |  | Reverse says 'מודיעין-מכבים-רעות', declared city is 'המכונאי 2'. road= |
| 3273 | פז - שער הגיא ירושלים | ירושלים | CONFIRMED_WRONG_CITY | 31.815733 | 35.024154 | 31.822324 | 35.016179 | 1.05 | Coords match address (1.1 km), but reverse says city is 'מועצה אזורית  |
| 3278 | עמק שרה באר שבע | צאלים | CONFIRMED_WRONG_CITY | 31.230479 | 34.818978 |  |  |  | Reverse says 'באר-שבע', declared city is 'צאלים'. road=נחל חבר, city=ב |
| 3449 | פז אשכול | באר שבע | CONFIRMED_WRONG_CITY | 31.290845 | 34.432284 |  |  |  | Reverse says 'מועצה אזורית אשכול', declared city is 'באר שבע'. road=23 |
| 3467 | פז נטופה | מצפה נטופה | CONFIRMED_WRONG_CITY | 32.764188 | 35.244715 |  |  |  | Reverse says 'מועצה אזורית עמק יזרעאל', declared city is 'מצפה נטופה'. |
| 3489 | Narkisim Tzuva | Tzova | CONFIRMED_WRONG_CITY | 31.781381 | 35.120214 |  |  |  | Reverse says 'מועצה אזורית מטה יהודה', declared city is 'Tzova'. road= |
| 3496 | Panora Seeds - Ilan Yaar | אליעד | CONFIRMED_WRONG_CITY | 32.806583 | 35.736575 |  |  |  | Reverse says 'מועצה אזורית גולן', declared city is 'אליעד'. road=, cit |
| 3502 | דלק פונדק הרים | נווה אילן | CONFIRMED_WRONG_CITY | 31.804448 | 35.095034 |  |  |  | Reverse says 'מועצה אזורית מטה יהודה', declared city is 'נווה אילן'. r |

## Duplicate Pairs

| id_a | name_a | id_b | name_b | dist_m | verdict | keep | reason | evidence |
|-----:|--------|-----:|--------|-------:|---------|------|--------|----------|
| 3174 | חניית הנהלה מתחם שורק למו | 3175 | חניה גדולה מתחם שורק למור | 100426 | CONFIRMED_DUPLICATE | manual review n | No geocode result, cannot determine corr | Same/similar name, 100426m apart. |
| 626 | הרואה בקפה - DC 40 | 1891 | וילאר מבוא כרמל | 48056 | NOT_DUPLICATE | both | Different physical locations | Different locations 48056m apart. A at: road=שבטי  |
| 626 | הרואה בקפה - DC 40 | 630 | עיר תחתית AC | 48040 | CONFIRMED_DUPLICATE | manual review n | No geocode result, cannot determine corr | Same/similar name, 48040m apart. |
| 623 | עמדת טעינה DC חניון | 626 | הרואה בקפה - DC 40 | 48024 | CONFIRMED_DUPLICATE | manual review n | No geocode result, cannot determine corr | Same/similar name, 48024m apart. |
| 219 | מלון סטאי - חוף צאלון | 3240 | מלון סטאי - חוף צאלון | 22218 | CONFIRMED_DUPLICATE | id=219 | More sources (4 vs 2) | Both far from geocode (100.5/81.1km). Likely same  |
| 3177 | תפוז עפולה | 3508 | תפוז עפולה | 10884 | CONFIRMED_DUPLICATE | manual review n | No geocode result, cannot determine corr | Same/similar name, 10884m apart. |
| 2816 | ראשונים סנטר | 2884 | פז - סונול ראשונים | 4493 | NOT_DUPLICATE | both | Different locations | Different streets (הנחשול vs 412), 4493m apart. |
| 2610 | קניון עזריאלי ראשונים | 2816 | ראשונים סנטר | 4336 | NOT_DUPLICATE | both | Different locations | Different streets (שדרות נים vs הנחשול), 4336m apa |
| 2816 | ראשונים סנטר | 2956 | קניון עזריאלי ראשונים עמד | 4332 | NOT_DUPLICATE | both | Different locations | Different streets (הנחשול vs שדרות נים), 4332m apa |
| 3035 | לאונרדו פלאזה טבריה- פתאל | 3459 | פז טבריה עילית | 3691 | NOT_DUPLICATE | both | Different locations | Different streets (הבנים vs הנשיא ויצמן), 3691m ap |
| 3043 | לאונרדו פלאזה טבריה - פתא | 3459 | פז טבריה עילית | 3691 | NOT_DUPLICATE | both | Different locations | Different streets (הבנים vs הנשיא ויצמן), 3691m ap |
| 3126 | רני צים - רהט seven | 3499 | SEVEN רהט | 3355 | CONFIRMED_DUPLICATE | id=3126 | Gov-verified (g=1) | Same area, 3355m apart. A: road=, city=רהט, suburb |
| 789 | תחנת דלק יעד פתח תקווה | 2369 | Pango Office | 3299 | NOT_DUPLICATE | both | Different locations | Different streets (בן ציון גליס vs השחם), 3299m ap |
| 3092 | צים אורבן כפר סבא | 3282 | אורבן צים כפר סבא | 2872 | NOT_DUPLICATE | both | Different locations | Different streets (דרך אפק vs הר תבור), 2872m apar |
| 544 | דור אלון-עכו | 2626 | קניון עזריאלי עכו | 2727 | NOT_DUPLICATE | both | Different locations | Different streets (בלטימור vs דוד רמז), 2727m apar |
| 2771 | מול זכרון | 3180 | דלק זכרון יעקב | 2391 | NOT_DUPLICATE | both | Different locations | Different streets (כביש החוף הישן vs 67), 2391m ap |
| 370 | דור אלון-זכרון יעקב | 3180 | דלק זכרון יעקב | 2301 | NOT_DUPLICATE | both | Different locations | Different streets (כביש החוף הישן vs 67), 2301m ap |
| 1202 | Jumbo City of the Kings S | 2495 | GT Center - Eilat | 2128 | NOT_DUPLICATE | both | Different locations | Different streets (פישטאני vs HaBalan), 2128m apar |
| 2608 | קניון עזריאלי חולון | 2827 | מרכז עזריאלי חולון | 2105 | NOT_DUPLICATE | both | Different locations | Different streets (גולדה מאיר vs הרוקמים), 2105m a |
| 325 | דור אלון-בית קשת | 3136 | קיבוץ בית קשת | 2046 | NOT_DUPLICATE | both | Different locations | Different streets (766 vs Scenic road 'Beit-Keshet |
| 1207 | Jumbo City of the Kings N | 2495 | GT Center - Eilat | 2042 | NOT_DUPLICATE | both | Different locations | Different streets (90 vs HaBalan), 2042m apart. |
| 3491 | Batei Zikuk Ahazaka | 3492 | Batey Zikuk Ashdod | 1880 | CONFIRMED_DUPLICATE | manual review n | Equal sources, no clear winner | Close together (1880m), likely same site |
| 406 | מלונות דן-דן בוטיק ירושלי | 3025 | לאונרדו בוטיק ירושלים - פ | 1864 | CONFIRMED_DUPLICATE | id=406 | More sources (4 vs 3) | Close together (1864m), likely same site |
| 358 | דור אלון - מצפה רמון | 1589 | 2898 - מצפה רמון - פרטי | 1729 | CONFIRMED_DUPLICATE | id=358 | More sources (4 vs 2) | Close together (1729m), likely same site |
| 358 | דור אלון - מצפה רמון | 3084 | דלק מצפה רמון | 1683 | CONFIRMED_DUPLICATE | manual review n | Equal sources, no clear winner | Close together (1683m), likely same site |
| 783 | דלק עפולה | 3202 | סונול עפולה | 1619 | CONFIRMED_DUPLICATE | id=783 | Gov-verified (g=1) | Close together (1619m), likely same site |
| 553 | דור אלון -מתחם אלון קריית | 2628 | סונול צומת השרון | 1572 | CONFIRMED_DUPLICATE | id=2628 | Gov-verified (g=1) | Close together (1572m), likely same site |
| 2073 | בר אילן צפת | 2714 | סונול צפת | 1481 | CONFIRMED_DUPLICATE | id=2714 | More sources (4 vs 3) | Close together (1481m), likely same site |
| 482 | דור אלון -אורים | 3201 | אורים | 1447 | CONFIRMED_DUPLICATE | id=482 | Gov-verified (g=1) | Close together (1447m), likely same site |
| 2855 | סונול עד הלום | 3115 | פז - תחנת דלק תפוז עד הלו | 1445 | CONFIRMED_DUPLICATE | id=3115 | More sources (6 vs 4) | Close together (1445m), likely same site |
| 2551 | עמי סנטר -נס ציונה | 3161 | דלק נס ציונה | 1378 | CONFIRMED_DUPLICATE | id=2551 | Gov-verified (g=1) | Close together (1378m), likely same site |
| 135 | פז מגדל העמק | 2780 | סונול מגדל העמק | 1216 | CONFIRMED_DUPLICATE | id=135 | More sources (6 vs 4) | Close together (1216m), likely same site |
| 2591 | מרכז מסחרי חוצות יגור | 2664 | משרדי רכב-יגור | 1174 | CONFIRMED_DUPLICATE | manual review n | Equal sources, no clear winner | Close together (1174m), likely same site |
| 2988 | קבוצת טרייסטמן ציבורי | 3203 | קבוצת טרייסטמן | 1168 | CONFIRMED_DUPLICATE | id=2988 | More sources (2 vs 1) | Close together (1168m), likely same site |
| 2856 | 2231_גילה_חניון צביה ויצח | 2860 | 2230 גילה_חניון צביה ויצח | 1063 | CONFIRMED_DUPLICATE | manual review n | Equal sources, no clear winner | Close together (1063m), likely same site |
| 263 | מלונות דן - נצרת | 3145 | נצרת נצרת | 1034 | CONFIRMED_DUPLICATE | id=263 | More sources (4 vs 2) | Close together (1034m), likely same site |
| 1494 | מתחם צים סנטר ערד | 3165 | דלק ערד | 1017 | CONFIRMED_DUPLICATE | id=1494 | Gov-verified (g=1) | Close together (1017m), likely same site |
| 202 | דור אלון-ערד | 1494 | מתחם צים סנטר ערד | 1007 | CONFIRMED_DUPLICATE | manual review n | Equal sources, no clear winner | Close together (1007m), likely same site |
| 1772 | לישנסקי 4 | 2965 | עיריית ראשון לציון- חניון | 927 | CONFIRMED_DUPLICATE | id=2965 | More sources (4 vs 3) | Close together (927m), likely same site |
| 569 | גיבורי ישראל | 2869 | סונול גיבורי ישראל | 907 | CONFIRMED_DUPLICATE | id=2869 | Gov-verified (g=1) | Close together (907m), likely same site |
| 2367 | More Mall City - Harish | 2368 | More Mall - Harish | 883 | CONFIRMED_DUPLICATE | id=2368 | More sources (4 vs 3) | Close together (883m), likely same site |
| 2660 | הפרחים | 2692 | רעננה - תיכון אביב | 858 | CONFIRMED_DUPLICATE | id=2692 | More sources (3 vs 2) | Close together (858m), likely same site |
| 1040 | Gav-Yam Management Servic | 1051 | Gav-Yam Management Servic | 854 | CONFIRMED_DUPLICATE | id=1040 | More sources (2 vs 1) | Close together (854m), likely same site |
| 1094 | Leonardo Club Hotel - Fat | 1098 | Leonardo Plaza Hotel - Fa | 837 | CONFIRMED_DUPLICATE | manual review n | Equal sources, no clear winner | Close together (837m), likely same site |
| 2714 | סונול צפת | 3475 | פז צפת | 837 | CONFIRMED_DUPLICATE | id=2714 | Gov-verified (g=1) | Close together (837m), likely same site |
| 185 | דב גור 9, אשדוד | 186 | ביאליק 15,אשדוד | 826 | CONFIRMED_DUPLICATE | id=185 | More sources (4 vs 3) | Close together (826m), likely same site |
| 100 | מנחם בגין 53, גדרה | 152 | מנחם בגין 11 גדרה | 826 | CONFIRMED_DUPLICATE | manual review n | Equal sources, no clear winner | Close together (826m), likely same site |
| 1 | עתיר ידע 16, כפר סבא, ישר | 675 | O-TECH | 823 | CONFIRMED_DUPLICATE | id=675 | More sources (4 vs 3) | Close together (823m), likely same site |
| 15 | עתיר ידע 16, כפר סבא, ישר | 675 | O-TECH | 823 | CONFIRMED_DUPLICATE | id=675 | More sources (4 vs 2) | Close together (823m), likely same site |
| 41 | עתיר ידע 16, כפר סבא, ישר | 675 | O-TECH | 823 | CONFIRMED_DUPLICATE | id=675 | More sources (4 vs 2) | Close together (823m), likely same site |
| 49 | עתיר ידע 16, כפר סבא, ישר | 675 | O-TECH | 823 | CONFIRMED_DUPLICATE | id=675 | More sources (4 vs 2) | Close together (823m), likely same site |
| 580 | ecorgy test | 675 | O-TECH | 811 | CONFIRMED_DUPLICATE | id=675 | Gov-verified (g=1) | Close together (811m), likely same site |
| 2073 | בר אילן צפת | 3475 | פז צפת | 790 | CONFIRMED_DUPLICATE | id=2073 | Gov-verified (g=1) | Close together (790m), likely same site |
| 2871 | שד' גולדה מאיר 21 | 2872 | שד' גולדה מאיר 3 | 787 | CONFIRMED_DUPLICATE | manual review n | Equal sources, no clear winner | Close together (787m), likely same site |
| 2650 | בית מכבי | 2872 | שד' גולדה מאיר 3 | 783 | CONFIRMED_DUPLICATE | manual review n | Equal sources, no clear winner | Close together (783m), likely same site |
| 251 | הוד-ים מלח -לאורחי המלון | 271 | אואזיס ים המלח-לאורחי המל | 764 | CONFIRMED_DUPLICATE | id=251 | More sources (4 vs 3) | Close together (764m), likely same site |
| 107 | אופק1 קיסריה-מורשים בלבד | 146 | האשל 40 | 745 | CONFIRMED_DUPLICATE | manual review n | Equal sources, no clear winner | Close together (745m), likely same site |
| 212 | מילוס-ים המלח -לאורחי המל | 271 | אואזיס ים המלח-לאורחי המל | 741 | CONFIRMED_DUPLICATE | id=212 | More sources (5 vs 3) | Close together (741m), likely same site |
| 138 | האשל 1 | 146 | האשל 40 | 738 | CONFIRMED_DUPLICATE | manual review n | Equal sources, no clear winner | Close together (738m), likely same site |
| 2239 | פז - אושילנד כפר סבא | 2559 | סבן בדיקות | 709 | CONFIRMED_DUPLICATE | id=2239 | More sources (4 vs 2) | Close together (709m), likely same site |
| 137 | סנטר - נתניה (מפלס עליון) | 569 | גיבורי ישראל | 704 | CONFIRMED_DUPLICATE | id=137 | Gov-verified (g=1) | Close together (704m), likely same site |
| 98 | פז - שופינה ראש פינה | 2880 | סונול ראש פינה | 689 | CONFIRMED_DUPLICATE | id=98 | More sources (5 vs 3) | Close together (689m), likely same site |
| 1220 | Municipality Herzliya - A | 1221 | Municipality Herzliya - A | 681 | CONFIRMED_DUPLICATE | id=1221 | More sources (2 vs 1) | Close together (681m), likely same site |
| 1856 | רויאל פארק | 2963 | אייסמול אילת אולטרה | 677 | CONFIRMED_DUPLICATE | id=2963 | Gov-verified (g=1) | Close together (677m), likely same site |
| 285 | בניין פיזיקה, מכון ויצמן | 1474 | מכון וייצמן | 671 | CONFIRMED_DUPLICATE | id=285 | More sources (4 vs 3) | Close together (671m), likely same site |
| 2293 | Givat Haim ihud - Swimmin | 2442 | Givat Haim ihud - Kinderg | 666 | CONFIRMED_DUPLICATE | id=2442 | More sources (3 vs 2) | Close together (666m), likely same site |
| 2779 | שכונה א' - נצר סרני | 2874 | שכונה ג' - נצר סרני | 658 | CONFIRMED_DUPLICATE | manual review n | Equal sources, no clear winner | Close together (658m), likely same site |
| 458 | דור אלון-כפר עזה | 2841 | כפר עזה - חניה מזכירות | 642 | CONFIRMED_DUPLICATE | id=458 | More sources (4 vs 3) | Close together (642m), likely same site |
| 306 | מכון לביוכימיה, מכון ויצמ | 1474 | מכון וייצמן | 607 | CONFIRMED_DUPLICATE | id=306 | More sources (4 vs 3) | Close together (607m), likely same site |
| 285 | בניין פיזיקה, מכון ויצמן | 290 | בניין ידע,מכון ויצמן | 597 | CONFIRMED_DUPLICATE | manual review n | Equal sources, no clear winner | Close together (597m), likely same site |
| 1856 | רויאל פארק | 2961 | אייסמול אילת מהירות | 581 | CONFIRMED_DUPLICATE | id=2961 | Gov-verified (g=1) | Close together (581m), likely same site |
| 2280 | Givat Haim ihud - Lev hap | 2293 | Givat Haim ihud - Swimmin | 566 | CONFIRMED_DUPLICATE | id=2280 | More sources (3 vs 2) | Close together (566m), likely same site |
| 1591 | 2834 - רמות מנשה - קומותי | 1592 | 2834 - רמות מנשה - השדות | 564 | CONFIRMED_DUPLICATE | id=1591 | More sources (2 vs 1) | Close together (564m), likely same site |
| 1560 | 2834 - רמות מנשה - נופים | 1591 | 2834 - רמות מנשה - קומותי | 550 | CONFIRMED_DUPLICATE | id=1560 | Gov-verified (g=1) | Close together (550m), likely same site |
| 1589 | 2898 - מצפה רמון - פרטי | 3084 | דלק מצפה רמון | 541 | CONFIRMED_DUPLICATE | id=3084 | More sources (4 vs 2) | Close together (541m), likely same site |
| 2280 | Givat Haim ihud - Lev hap | 2442 | Givat Haim ihud - Kinderg | 539 | CONFIRMED_DUPLICATE | manual review n | Equal sources, no clear winner | Close together (539m), likely same site |
| 971 | Sheba Medical Center Tel  | 1179 | Sheba Medical Center Tel  | 535 | CONFIRMED_DUPLICATE | manual review n | Equal sources, no clear winner | Close together (535m), likely same site |
| 971 | Sheba Medical Center Tel  | 983 | Sheba Medical Center Tel  | 516 | CONFIRMED_DUPLICATE | manual review n | Equal sources, no clear winner | Close together (516m), likely same site |
| 150 | בניין לופאטי, מכון ויצמן | 306 | מכון לביוכימיה, מכון ויצמ | 506 | CONFIRMED_DUPLICATE | manual review n | Equal sources, no clear winner | Close together (506m), likely same site |
| 3152 | אורבן צים נוף הגליל | 3509 | צים אורבן נוף הגליל | 504 | CONFIRMED_DUPLICATE | id=3152 | Gov-verified (g=1) | Close together (504m), likely same site |

## Stations Without a City

| id | name | suggested city | verdict | evidence |
|---:|------|---------------|---------|----------|
| 30 | טירת כרמל, ישראל | טירת הכרמל | CONFIRMED_OK | Reverse geocode suggests city: 'טירת הכרמל'. road=הרצל, city=טירת הכרמ |
| 31 | מלון ירמיהו 33, ירמיהו, ירושלים, יש | ירושלים | CONFIRMED_OK | Reverse geocode suggests city: 'ירושלים'. road=ירמיהו, city=ירושלים, s |
| 33 | אדרים חקלאות ובניה בע"מ, גבעתי, ישר | מועצה אזורית באר טוב | CONFIRMED_OK | Reverse geocode suggests city: 'מועצה אזורית באר טוביה'. road=גדוד שקד |
| 64 | טירת כרמל, ישראל | טירת הכרמל | CONFIRMED_OK | Reverse geocode suggests city: 'טירת הכרמל'. road=הרצל, city=טירת הכרמ |
| 65 | מלון ירמיהו 33, ירמיהו, ירושלים, יש | ירושלים | CONFIRMED_OK | Reverse geocode suggests city: 'ירושלים'. road=ירמיהו, city=ירושלים, s |
| 66 | אדרים חקלאות ובניה בע"מ, גבעתי, ישר | מועצה אזורית באר טוב | CONFIRMED_OK | Reverse geocode suggests city: 'מועצה אזורית באר טוביה'. road=גדוד שקד |
| 588 | Gat Center DC | קרית גת | CONFIRMED_OK | Reverse geocode suggests city: 'קרית גת'. road=שדרות אבני החושן, city= |
| 602 | Usha Public 01 | מועצה אזורית זבולון | CONFIRMED_OK | Reverse geocode suggests city: 'מועצה אזורית זבולון'. road=, city=מועצ |
| 603 | Usha Public 02 | מועצה אזורית זבולון | CONFIRMED_OK | Reverse geocode suggests city: 'מועצה אזורית זבולון'. road=, city=מועצ |
| 604 | Usha Public 03 | מועצה אזורית זבולון | CONFIRMED_OK | Reverse geocode suggests city: 'מועצה אזורית זבולון'. road=כביש ראשי ע |
| 606 | Beit Alfa Public 02 | מועצה אזורית גלבוע | CONFIRMED_OK | Reverse geocode suggests city: 'מועצה אזורית גלבוע'. road=, city=מועצה |
| 607 | Beit Alfa Public 04 | מועצה אזורית גלבוע | CONFIRMED_OK | Reverse geocode suggests city: 'מועצה אזורית גלבוע'. road=, city=מועצה |
| 608 | Beit Alfa Public 05 | מועצה אזורית גלבוע | CONFIRMED_OK | Reverse geocode suggests city: 'מועצה אזורית גלבוע'. road=6692, city=מ |
| 609 | Reshafim Public 01 | מועצה אזורית עמק המע | CONFIRMED_OK | Reverse geocode suggests city: 'מועצה אזורית עמק המעיינות'. road=, cit |
| 610 | Reshafim Public 02 | מועצה אזורית עמק המע | CONFIRMED_OK | Reverse geocode suggests city: 'מועצה אזורית עמק המעיינות'. road=, cit |
| 611 | Reshafim Public 03 | מועצה אזורית עמק המע | CONFIRMED_OK | Reverse geocode suggests city: 'מועצה אזורית עמק המעיינות'. road=, cit |
| 612 | Yahel Public 01 | מועצה אזורית חבל איל | CONFIRMED_OK | Reverse geocode suggests city: 'מועצה אזורית חבל אילות'. road=1129, ci |
| 614 | Yahel Public 02 | מועצה אזורית חבל איל | CONFIRMED_OK | Reverse geocode suggests city: 'מועצה אזורית חבל אילות'. road=1129, ci |
| 615 | Beit Berl Public 01 | מועצה אזורית דרום הש | CONFIRMED_OK | Reverse geocode suggests city: 'מועצה אזורית דרום השרון'. road=5503, c |
| 617 | Meirav Public 02 | מועצה אזורית עמק המע | CONFIRMED_OK | Reverse geocode suggests city: 'מועצה אזורית עמק המעיינות'. road=, cit |
| 618 | Meirav Public 01 | מועצה אזורית עמק המע | CONFIRMED_OK | Reverse geocode suggests city: 'מועצה אזורית עמק המעיינות'. road=, cit |
| 619 | Meirav Public 03 | מועצה אזורית עמק המע | CONFIRMED_OK | Reverse geocode suggests city: 'מועצה אזורית עמק המעיינות'. road=, cit |
| 2024 | פארן | מועצה אזורית הערבה ה | CONFIRMED_OK | Reverse geocode suggests city: 'מועצה אזורית הערבה התיכונה'. road=Vard |
| 2025 | בקתה בשומרה | מועצה אזורית מעלה יו | CONFIRMED_OK | Reverse geocode suggests city: 'מועצה אזורית מעלה יוסף'. road=, city=מ |
| 2034 | הרוח הגלילית - גורן | מועצה אזורית מעלה יו | CONFIRMED_OK | Reverse geocode suggests city: 'מועצה אזורית מעלה יוסף'. road=, city=מ |
| 2040 | חדנס מזכירות | מועצה אזורית גולן | CONFIRMED_OK | Reverse geocode suggests city: 'מועצה אזורית גולן'. road=כנרת, city=מו |
| 2043 | הרוח הגלילית | מועצה אזורית מעלה יו | CONFIRMED_OK | Reverse geocode suggests city: 'מועצה אזורית מעלה יוסף'. road=, city=מ |
| 2045 | חדנס בריכה | מועצה אזורית גולן | CONFIRMED_OK | Reverse geocode suggests city: 'מועצה אזורית גולן'. road=פרח הלילך, ci |
| 2047 | אירוח פארן | מועצה אזורית הערבה ה | CONFIRMED_OK | Reverse geocode suggests city: 'מועצה אזורית הערבה התיכונה'. road=, ci |
| 2048 | צרפתי אשדוד | אשדוד | CONFIRMED_OK | Reverse geocode suggests city: 'אשדוד'. road=הבנאים, city=אשדוד, subur |
| 2050 | פארן בקתות קלם | מועצה אזורית הערבה ה | CONFIRMED_OK | Reverse geocode suggests city: 'מועצה אזורית הערבה התיכונה'. road=Vard |
| 2053 | שופינג עד הלום - מתחם מקס סטוק | מועצה אזורית באר טוב | CONFIRMED_OK | Reverse geocode suggests city: 'מועצה אזורית באר טוביה'. road=4, city= |
| 2054 | אלעזר | מועצה אזורית גוש עצי | CONFIRMED_OK | Reverse geocode suggests city: 'מועצה אזורית גוש עציון'. road=חשמונאים |
| 2084 | באר שבע, ישראל | באר שבע | CONFIRMED_OK | Reverse geocode suggests city: 'באר שבע'. road=המשחררים, city=באר שבע, |
| 2532 | עמי סנטר -פתח תקווה | פתח תקווה | CONFIRMED_OK | Reverse geocode suggests city: 'פתח תקווה'. road=רפאל איתן, city=פתח ת |
| 2533 | מרכז מסחרי אלמוג-באר יעקב | באר יעקב | CONFIRMED_OK | Reverse geocode suggests city: 'באר יעקב'. road=אפרים קישון, city=באר  |
| 2536 | דיזינגוף סנטר | תל־אביב–יפו | CONFIRMED_OK | Reverse geocode suggests city: 'תל־אביב–יפו'. road=דיזנגוף, city=תל־אב |
| 2539 | כפר חסידים | מועצה אזורית זבולון | CONFIRMED_OK | Reverse geocode suggests city: 'מועצה אזורית זבולון'. road=מעלה הגבעה, |
| 2540 | אור עקיבא-נוף ים סנטר | אור עקיבא | CONFIRMED_OK | Reverse geocode suggests city: 'אור עקיבא'. road=שדרות שידלובסקי, city |
| 2543 | חצבה- חאן | מועצה אזורית הערבה ה | CONFIRMED_OK | Reverse geocode suggests city: 'מועצה אזורית הערבה התיכונה'. road=, ci |
| 2547 | מרכז מינקין-מודיעין | מודיעין-מכבים-רעות | CONFIRMED_OK | Reverse geocode suggests city: 'מודיעין-מכבים-רעות'. road=נחל זוהר, ci |
| 2553 | עפולה אדיר הום -DC | עפולה | CONFIRMED_OK | Reverse geocode suggests city: 'עפולה'. road=60, city=עפולה, suburb=,  |
| 2554 | אולם אירועים- אמרה | נס ציונה | CONFIRMED_OK | Reverse geocode suggests city: 'נס ציונה'. road=הנבחרת, city=נס ציונה, |
| 2561 | מתחם ספיר קצרין -DC | קצרין | CONFIRMED_OK | Reverse geocode suggests city: 'קצרין'. road=בדולח, city=קצרין, suburb |
| 2563 | בדיקות עמדות ציבוריות | מועצה אזורית חוף אשק | CONFIRMED_OK | Reverse geocode suggests city: 'מועצה אזורית חוף אשקלון'. road=34, cit |
| 2564 | עמי סנטר אור יהודה MINI DC60KW | אור יהודה | CONFIRMED_OK | Reverse geocode suggests city: 'אור יהודה'. road=יצחק רבין, city=אור י |
| 2572 | קיבוץ כיסופים | מועצה אזורית אשכול | CONFIRMED_OK | Reverse geocode suggests city: 'מועצה אזורית אשכול'. road=, city=מועצה |
| 2573 | כיסופים-עמדה מס' 1 | מועצה אזורית אשכול | CONFIRMED_OK | Reverse geocode suggests city: 'מועצה אזורית אשכול'. road=, city=מועצה |
| 2574 | עמדה מס' 2 - כיסופים | מועצה אזורית אשכול | CONFIRMED_OK | Reverse geocode suggests city: 'מועצה אזורית אשכול'. road=, city=מועצה |
| 2575 | כיסופים-עמדה מס' 3 | מועצה אזורית אשכול | CONFIRMED_OK | Reverse geocode suggests city: 'מועצה אזורית אשכול'. road=, city=מועצה |
| 2578 | אוניברסיטת בן גוריון עמדה ימנית | באר שבע | CONFIRMED_OK | Reverse geocode suggests city: 'באר שבע'. road=שדרות דוד בן גוריון, ci |
| 2579 | אוניברסיטת בן גוריון עמדה שמאלית | באר שבע | CONFIRMED_OK | Reverse geocode suggests city: 'באר שבע'. road=שדרות דוד בן גוריון, ci |
| 3033 | הרודס ים המלח - פתאל | מועצה אזורית תמר | CONFIRMED_OK | Reverse geocode suggests city: 'מועצה אזורית תמר'. road=דרך ים המלח, c |
| 3036 | הרודס ים המלח - פתאל | מועצה אזורית תמר | CONFIRMED_OK | Reverse geocode suggests city: 'מועצה אזורית תמר'. road=דרך ים המלח, c |
| 3210 | WIX Complex \| Glilot Junction | תל־אביב–יפו | CONFIRMED_OK | Reverse geocode suggests city: 'תל־אביב–יפו'. road=, city=תל־אביב–יפו, |
| 3215 | Kibbutz Ginegar - Secretariat Parki | מועצה אזורית עמק יזר | CONFIRMED_OK | Reverse geocode suggests city: 'מועצה אזורית עמק יזרעאל'. road=73, cit |
| 3216 | Private \| Amdocs Israel ltd \| Nazar | נצרת | CONFIRMED_OK | Reverse geocode suggests city: 'נצרת'. road=, city=נצרת, suburb=ארמון  |
| 3225 | דור אלון- פארק חדרה כביש 4 | חדרה | CONFIRMED_OK | Reverse geocode suggests city: 'חדרה'. road=65, city=חדרה, suburb=, co |
| 3230 | DC רמות, רמות | מועצה אזורית גולן | CONFIRMED_OK | Reverse geocode suggests city: 'מועצה אזורית גולן'. road=פני גולן, cit |
| 3231 | יער טמרה | טמרה | CONFIRMED_OK | Reverse geocode suggests city: 'טמרה'. road=, city=טמרה, suburb=, coun |
| 3234 | מועצה אזורית יואב צומת אולטרה DC | מועצה אזורית לכיש | CONFIRMED_OK | Reverse geocode suggests city: 'מועצה אזורית לכיש'. road=, city=מועצה  |
| 3236 | רמת הנגב עמדה מהירה | מועצה אזורית רמת נגב | CONFIRMED_OK | Reverse geocode suggests city: 'מועצה אזורית רמת נגב'. road=222, city= |
| 3237 | נווה אטיב- חניה מרכזית | מועצה אזורית גולן | CONFIRMED_OK | Reverse geocode suggests city: 'מועצה אזורית גולן'. road=, city=מועצה  |
| 3242 | חמי עין גדי | מועצה אזורית תמר | CONFIRMED_OK | Reverse geocode suggests city: 'מועצה אזורית תמר'. road=דרך ים המלח, c |
| 3245 | דור כימיכלים חיפה | חיפה | CONFIRMED_OK | Reverse geocode suggests city: 'חיפה'. road=, city=חיפה, suburb=, coun |
| 3252 | דרך יצחק בן צבי ראשון לציון | ראשון לציון | CONFIRMED_OK | Reverse geocode suggests city: 'ראשון לציון'. road=יצחק בן צבי, city=ר |
| 3253 | פז מפגש ארבל | מגדל | CONFIRMED_OK | Reverse geocode suggests city: 'מגדל'. road=807, city=מגדל, suburb=, c |
| 3254 | פז - מצפה טורען | מועצה אזורית גליל תח | CONFIRMED_OK | Reverse geocode suggests city: 'מועצה אזורית גליל תחתון'. road=65, cit |
| 3257 | פז - בחן בת חפר כביש 5714 |  | UNVERIFIED | No city in reverse geocode. road=5714, city=, suburb=, country=ישראל |
| 3258 | פז - עוקף נצרת | נצרת | CONFIRMED_OK | Reverse geocode suggests city: 'נצרת'. road=, city=נצרת, suburb=ארמון  |
| 3263 | תלפיות | ירושלים | CONFIRMED_OK | Reverse geocode suggests city: 'ירושלים'. road=פייר קניג, city=ירושלים |
| 3264 | פז - אצטדיון כפר סבא | כפר סבא | CONFIRMED_OK | Reverse geocode suggests city: 'כפר סבא'. road=התע"ש, city=כפר סבא, su |
| 3265 | טופז רמת השרון | רמת השרון | CONFIRMED_OK | Reverse geocode suggests city: 'רמת השרון'. road=משה סנה, city=רמת השר |
| 3271 | פז - קואופ רמלה | רמלה | CONFIRMED_OK | Reverse geocode suggests city: 'רמלה'. road=שדרות ירושלים, city=רמלה,  |
| 3274 | ברורים כביש 40 | מועצה אזורית נחל שור | CONFIRMED_OK | Reverse geocode suggests city: 'מועצה אזורית נחל שורק'. road=40, city= |
| 3285 | חניון פונדק יטבתה | מועצה אזורית חבל איל | CONFIRMED_OK | Reverse geocode suggests city: 'מועצה אזורית חבל אילות'. road=, city=מ |
| 3287 | פז - שיאונה הירקונים פתח תקווה | פתח תקווה | CONFIRMED_OK | Reverse geocode suggests city: 'פתח תקווה'. road=, city=פתח תקווה, sub |
| 3288 | פז - מסילת ציון | מועצה אזורית מטה יהו | CONFIRMED_OK | Reverse geocode suggests city: 'מועצה אזורית מטה יהודה'. road=38, city |

## Method & Confidence

### Methods used

1. **Reverse geocoding** (Nominatim /reverse): Applied to all stations to determine what's at the current coordinates.
2. **Forward geocoding** (Nominatim /search): Applied to stations with addresses to find expected coordinates and compare.
3. **Cross-reference**: Gov-verified status (g=1), source count, and dataset consistency used for duplicate resolution.
4. **Web search**: Not available in this environment — flagged where web verification would help.

### Confidence notes

- Reverse geocoding is highly reliable for water/void detection.
- Forward geocoding of Hebrew addresses has moderate accuracy — Nominatim may not resolve all Israeli street names.
- Stations marked UNVERIFIED could not be confirmed either way and need manual review.
- 4 rate-limit (429) errors encountered during verification.

## Recommended Fixes (NOT executed)

Sorted by confidence (highest first).

1. **Remove 23 foreign/test stations** (IDs: 1484, 1518, 1520, 1524, 1525, 1527, 1529, 1531, 1532, 1534, 1535, 1536, 1545, 1561, 1562, 1578, 1606, 1620, 1626, 3196, 3197, 3198, 3199) — confirmed outside Israel or test data. HIGH confidence.

2. **Fix coords for id=1752** 'אלרום' — move from (33.178548, 35.771916) to (32.069113, 34.840217). HIGH confidence.

3. **Fix coords for id=2173** 'Mechinat otzem' — move from (31.163300, 34.334600) to (31.842212, 35.242060). HIGH confidence.

4. **Fix coords for id=1939** 'Ar Bracha-kindergarten' — move from (32.194712, 35.267404) to (32.095925, 34.878732). HIGH confidence.

5. **Fix coords for id=1917** 'Ar Bracha-Kashti' — move from (32.191895, 35.264433) to (32.089479, 34.858705). HIGH confidence.

6. **Fix coords for id=1497** 'קיבוץ תל קציר' — move from (32.705753, 35.619317) to (32.488630, 35.101689). HIGH confidence.

7. **Fix coords for id=581** 'פז - עין חצבה - עמדה מהירה 2' — move from (30.798883, 35.244076) to (31.248332, 35.197941). HIGH confidence.

8. **Fix coords for id=582** 'עין חצבה - עמדה מהירה 1' — move from (30.798883, 35.244076) to (31.248332, 35.197941). HIGH confidence.

9. **Fix coords for id=2939** 'אולם מופעים אפיקים' — move from (32.682312, 35.580032) to (32.093311, 34.969990). HIGH confidence.

10. **Fix coords for id=2587** 'קיבוץ אפיקים' — move from (32.679845, 35.578389) to (32.093311, 34.969990). HIGH confidence.

11. **Fix coords for id=2662** 'קיבוץ אפיקים - חניה פרבר' — move from (32.680564, 35.577730) to (32.093311, 34.969990). HIGH confidence.

12. **Fix coords for id=2938** 'חניה שכונת כוח אפיקים' — move from (32.680832, 35.574417) to (32.093311, 34.969990). HIGH confidence.

13. **Fix coords for id=3063** 'אשדוד DC - ברק בן אבינועם 6' — move from (31.046051, 34.851612) to (32.333539, 34.868207). HIGH confidence.

14. **Fix coords for id=1864** 'בית השותפויות' — move from (33.056934, 35.104928) to (32.427106, 34.927261). HIGH confidence.

15. **Fix coords for id=1487** 'המרכז של קרסו אבן יהודה' — move from (32.269877, 34.888621) to (32.574525, 34.954112). HIGH confidence.

16. **Fix coords for id=641** 'קריית צאנז נתניה עמדת AC כפולה' — move from (32.820125, 34.999321) to (32.344519, 34.855661). HIGH confidence.

17. **Fix coords for id=2758** 'חניה-בית מוסדות' — move from (32.590879, 35.075777) to (32.146625, 34.883788). HIGH confidence.

18. **Fix coords for id=2653** 'קיבוץ דליה - חניה שכונה כב' — move from (32.588037, 35.070318) to (32.146625, 34.883788). HIGH confidence.

19. **Fix coords for id=1479** 'כפר מנחם' — move from (31.729733, 34.838861) to (31.788339, 35.213930). HIGH confidence.

20. **Fix coords for id=1509** 'חדשות 12 (לעובדים ואורחים בלבד)' — move from (31.808323, 35.080879) to (31.667790, 34.578546). HIGH confidence.

21. **Fix coords for id=626** 'הרואה בקפה - DC 40' — move from (32.393116, 34.915413) to (32.818807, 35.001096). HIGH confidence.

22. **Fix coords for id=1115** 'Leonardo Club Hotel - Fattal Hotels ltd | Dead Sea' — move from (31.164185, 35.367479) to (31.201383, 35.363884). HIGH confidence.

23. **Fix coords for id=2312** 'Kochav Yokneam business center' — move from (32.662569, 35.105113) to (33.018562, 35.097379). HIGH confidence.

24. **Fix coords for id=1109** 'Hevel Eilot | Eilot' — move from (29.894524, 35.065298) to (32.062951, 34.769329). HIGH confidence.

25. **Fix coords for id=2716** 'מועצה בני שמעון חניה' — move from (31.442056, 34.761263) to (31.330693, 34.776955). HIGH confidence.

26. **Fix coords for id=1854** 'מדרשת רמת הגולן' — move from (32.850071, 35.797567) to (32.988882, 35.681834). HIGH confidence.

27. **Fix coords for id=1132** 'Timna Lake | Eilot' — move from (29.760262, 34.969255) to (32.788192, 35.638211). HIGH confidence.

28. **Fix coords for id=1889** 'כניסה משרדי רכש' — move from (32.997070, 35.440621) to (32.937578, 35.454301). HIGH confidence.

29. **Fix coords for id=1888** 'חניית רכש' — move from (32.997285, 35.440831) to (32.937578, 35.454301). HIGH confidence.

30. **Fix coords for id=1633** 'חניון מועצה רמת הנגב' — move from (31.003910, 34.771460) to (33.221143, 35.630069). HIGH confidence.

31. **Fix coords for id=889** 'Nof Hasadot | Kibbutz Negba - Yoav Regional Council' — move from (31.658169, 34.684525) to (31.763304, 35.211982). HIGH confidence.

32. **Fix coords for id=2993** 'שיח מדבר (מרחבעם)' — move from (30.809577, 34.741866) to (30.888619, 34.828885). HIGH confidence.

33. **Fix coords for id=1553** '1309 - E (פרטי)' — move from (32.158066, 34.973009) to (32.157882, 34.881840). HIGH confidence.

34. **Fix coords for id=3283** 'גראנד קניון- חיפה' — move from (32.999574, 34.967197) to (32.789015, 35.011632). HIGH confidence.

35. **Fix coords for id=3284** 'גראנד קניון ב"ש- חניון צפוני' — move from (31.358888, 34.780752) to (31.250298, 34.771804). HIGH confidence.

36. **Fix city for id=3027** 'מחסן מלאי' — change from 'בית רימון' to reverse-geocoded city. MEDIUM confidence.

37. **Fix city for id=464** 'דור אלון צומת הגומא' — change from 'הגומא' to reverse-geocoded city. MEDIUM confidence.

38. **Fix city for id=1490** 'קניון צים סנטר מעלות' — change from 'מעלות' to reverse-geocoded city. MEDIUM confidence.

39. **Fix city for id=229** 'כפר הנופש רמות , כנרת' — change from 'רמות' to reverse-geocoded city. MEDIUM confidence.

40. **Fix city for id=551** 'דור אלון-חצור הגלילית' — change from 'חצור' to reverse-geocoded city. MEDIUM confidence.

41. **Fix city for id=2324** 'TEN Ashkelon - HaMetakhnen 10' — change from 'South District' to reverse-geocoded city. MEDIUM confidence.

42. **Fix city for id=2333** 'TEN Zavdiel' — change from 'South District' to reverse-geocoded city. MEDIUM confidence.

43. **Fix city for id=2671** 'מפעלי ים המלח סדום חניה' — change from 'סדום' to reverse-geocoded city. MEDIUM confidence.

44. **Fix city for id=3174** 'חניית הנהלה מתחם שורק למורשים בלבד' — change from 'ראשון לציון' to reverse-geocoded city. MEDIUM confidence.

45. **Fix city for id=3012** 'סונול שפיה' — change from 'כביש 67' to reverse-geocoded city. MEDIUM confidence.

46. **Fix city for id=561** 'דור אלון-פארק אפק, ראש העין' — change from 'ראש עין' to reverse-geocoded city. MEDIUM confidence.

47. **Fix city for id=1311** 'Isrotel Kayma Hotel | dead sea' — change from 'Unknown' to reverse-geocoded city. MEDIUM confidence.

48. **Fix city for id=2722** 'חניה שכונה מערבית' — change from 'קיבוץ גבת' to reverse-geocoded city. MEDIUM confidence.

49. **Fix city for id=2746** 'חניון הכלבו' — change from 'קיבוץ גבת' to reverse-geocoded city. MEDIUM confidence.

50. **Fix city for id=2725** 'חניון כרם דרום' — change from 'קיבוץ גבת' to reverse-geocoded city. MEDIUM confidence.

51. **Fix city for id=2764** 'חניון אשטרומים' — change from 'קיבוץ גבת' to reverse-geocoded city. MEDIUM confidence.

52. **Fix city for id=743** 'The Israeli addiction Center' — change from 'Unknown' to reverse-geocoded city. MEDIUM confidence.

53. **Fix city for id=3272** 'מודיעין הראל' — change from 'המכונאי 2' to reverse-geocoded city. MEDIUM confidence.

54. **Fix city for id=3182** 'דלק שדי תרומות (בכורה)' — change from 'כביש 90' to reverse-geocoded city. MEDIUM confidence.

55. **Fix city for id=2271** 'Scala office' — change from 'Neve Yamin' to reverse-geocoded city. MEDIUM confidence.

56. **Fix city for id=105** 'צומת גוש ציון' — change from 'גוש עציון' to reverse-geocoded city. MEDIUM confidence.

57. **Fix city for id=721** 'Rami Levy_Gush Etzion Branch' — change from 'גוש עציון' to reverse-geocoded city. MEDIUM confidence.

58. **Fix city for id=1814** 'יקבי גוש עציון' — change from 'צומת' to reverse-geocoded city. MEDIUM confidence.

59. **Fix city for id=1351** 'Shufersal ltd | Rehovot HaHadasha | DC chargers' — change from 'Unknown' to reverse-geocoded city. MEDIUM confidence.

60. **Fix city for id=3502** 'דלק פונדק הרים' — change from 'נווה אילן' to reverse-geocoded city. MEDIUM confidence.

61. **Fix city for id=1471** 'פונדק כושי הק"מ 101' — change from 'כביש הערבה' to reverse-geocoded city. MEDIUM confidence.

62. **Fix city for id=1436** 'Mirage Parking Lot | Dimona Municipality' — change from 'מחוז הדרום' to reverse-geocoded city. MEDIUM confidence.

63. **Fix city for id=1437** 'The Post Office Parking Lot | Dimona Municipality' — change from 'מחוז הדרום' to reverse-geocoded city. MEDIUM confidence.

64. **Fix city for id=1435** 'The Hamtens parking lot | Dimona Municipality' — change from 'מחוז הדרום' to reverse-geocoded city. MEDIUM confidence.

65. **Fix city for id=1234** 'Megiddo Junction | Commercial Center Terminal 65' — change from 'North District' to reverse-geocoded city. MEDIUM confidence.

66. **Fix city for id=3104** 'דלק מסמיה' — change from 'מלאכי' to reverse-geocoded city. MEDIUM confidence.

67. **Fix city for id=837** 'Nevo Hotel - Isrotel ltd | Dead Sea' — change from 'Dead Sea' to reverse-geocoded city. MEDIUM confidence.

68. **Fix city for id=271** 'אואזיס ים המלח-לאורחי המלון' — change from 'ים המלח' to reverse-geocoded city. MEDIUM confidence.

69. **Fix city for id=854** 'Isrotel Noga Hotel | Dead Sea' — change from 'Dead Sea' to reverse-geocoded city. MEDIUM confidence.

70. **Fix city for id=301** 'מלון לוט-לאורחי המלון' — change from 'ים המלח' to reverse-geocoded city. MEDIUM confidence.

71. **Fix city for id=2328** 'Nir David - Movement World' — change from 'North District' to reverse-geocoded city. MEDIUM confidence.

72. **Fix city for id=3489** 'Narkisim Tzuva' — change from 'Tzova' to reverse-geocoded city. MEDIUM confidence.

73. **Fix city for id=212** 'מילוס-ים המלח -לאורחי המלון' — change from 'ים המלח' to reverse-geocoded city. MEDIUM confidence.

74. **Fix city for id=1162** 'Vert Hotel | Dead Sea' — change from 'Dead Sea' to reverse-geocoded city. MEDIUM confidence.

75. **Fix city for id=2329** 'Nir David - Laundry' — change from 'North District' to reverse-geocoded city. MEDIUM confidence.

76. **Fix city for id=251** 'הוד-ים מלח -לאורחי המלון' — change from 'ים המלח' to reverse-geocoded city. MEDIUM confidence.

77. **Fix city for id=1101** 'Eilot Council Square | Eilot' — change from 'Eilot' to reverse-geocoded city. MEDIUM confidence.

78. **Fix city for id=556** 'דור אלון -ג'ת' — change from 'דור אלון' to reverse-geocoded city. MEDIUM confidence.

79. **Fix city for id=2302** 'Givat Haim Ihud - Hot Spot' — change from 'Center District' to reverse-geocoded city. MEDIUM confidence.

80. **Fix city for id=2499** 'Alonim - Old Laundry' — change from 'North District' to reverse-geocoded city. MEDIUM confidence.

81. **Fix city for id=2500** 'Alonim - Ceramic Studio' — change from 'North District' to reverse-geocoded city. MEDIUM confidence.

82. **Fix city for id=3449** 'פז אשכול' — change from 'באר שבע' to reverse-geocoded city. MEDIUM confidence.

83. **Fix city for id=2501** 'Alonim - Tennis Court' — change from 'North District' to reverse-geocoded city. MEDIUM confidence.

84. **Fix city for id=635** 'החברה לפיתוח דרום הר חברון - חניה מוסך' — change from 'הר חברון' to reverse-geocoded city. MEDIUM confidence.

85. **Fix city for id=636** 'החברה לפיתוח דרום הר חברון - חניה ראשית' — change from 'הר חברון' to reverse-geocoded city. MEDIUM confidence.

86. **Fix city for id=668** 'Haemek hospital' — change from 'North District' to reverse-geocoded city. MEDIUM confidence.

87. **Fix city for id=3278** 'עמק שרה באר שבע' — change from 'צאלים' to reverse-geocoded city. MEDIUM confidence.

88. **Fix city for id=1971** 'חוף ביאנקיני בים המלח' — change from 'ים המלח' to reverse-geocoded city. MEDIUM confidence.

89. **Fix city for id=1137** 'Timna Lake - Mevoa | Eilot' — change from 'Eilot' to reverse-geocoded city. MEDIUM confidence.

90. **Fix city for id=2314** 'Piano Center - South' — change from 'Center District' to reverse-geocoded city. MEDIUM confidence.

91. **Fix city for id=3132** 'ישיבת הגולן - חיספין' — change from 'רמת הגולן' to reverse-geocoded city. MEDIUM confidence.

92. **Fix city for id=3496** 'Panora Seeds - Ilan Yaar' — change from 'אליעד' to reverse-geocoded city. MEDIUM confidence.

93. **Fix city for id=2301** 'Beit Mai Parking - Haifa' — change from 'Haifa District' to reverse-geocoded city. MEDIUM confidence.

94. **Fix city for id=3181** 'דלק מעבר מכמש' — change from 'כביש 60' to reverse-geocoded city. MEDIUM confidence.

95. **Fix city for id=3086** 'דלק גל הערבה' — change from 'גל הערבה' to reverse-geocoded city. MEDIUM confidence.

96. **Fix city for id=2330** 'TEN Haifa - Oil Coast' — change from 'Haifa District' to reverse-geocoded city. MEDIUM confidence.

97. **Fix city for id=3273** 'פז - שער הגיא ירושלים' — change from 'ירושלים' to reverse-geocoded city. MEDIUM confidence.

98. **Fix city for id=1952** 'Hacal Golan - Hispin Pool' — change from 'חספין' to reverse-geocoded city. MEDIUM confidence.

99. **Fix city for id=628** 'בית מלון Oaks' — change from 'רמת הגולן' to reverse-geocoded city. MEDIUM confidence.

100. **Fix city for id=558** 'מרכז קהילתי מיר"ב חוף הכרמל' — change from 'חוף הכרמל' to reverse-geocoded city. MEDIUM confidence.

101. **Fix city for id=2319** 'TEN Nesher - Tel Hanan shopping center' — change from 'Haifa District' to reverse-geocoded city. MEDIUM confidence.

102. **Fix city for id=499** 'דור אלון -פארק חדרה כביש 4' — change from 'דרום חדרה' to reverse-geocoded city. MEDIUM confidence.

103. **Fix city for id=3240** 'מלון סטאי - חוף צאלון' — change from 'כנרת' to reverse-geocoded city. MEDIUM confidence.

104. **Fix city for id=2303** 'Rishpon' — change from 'Center District' to reverse-geocoded city. MEDIUM confidence.

105. **Fix city for id=2683** 'סונול עירון' — change from 'צומת חנה' to reverse-geocoded city. MEDIUM confidence.

106. **Fix city for id=667** 'Kfar Kara _Local Council' — change from 'מחוז חיפה' to reverse-geocoded city. MEDIUM confidence.

107. **Fix city for id=671** 'Kibbutz Nachshon_Factory' — change from 'לוד' to reverse-geocoded city. MEDIUM confidence.

108. **Fix city for id=3467** 'פז נטופה' — change from 'מצפה נטופה' to reverse-geocoded city. MEDIUM confidence.

109. **Fix city for id=2586** 'כינר' — change from 'טבריה' to reverse-geocoded city. MEDIUM confidence.

110. **Fix city for id=1976** 'בית הברכה' — change from 'חברון' to reverse-geocoded city. MEDIUM confidence.

111. **Merge duplicate** id=3174 + id=3175 — keep manual review needed: No geocode result, cannot determine correct coords. MEDIUM confidence.

112. **Merge duplicate** id=626 + id=630 — keep manual review needed: No geocode result, cannot determine correct coords. MEDIUM confidence.

113. **Merge duplicate** id=623 + id=626 — keep manual review needed: No geocode result, cannot determine correct coords. MEDIUM confidence.

114. **Merge duplicate** id=219 + id=3240 — keep id=219: More sources (4 vs 2). MEDIUM confidence.

115. **Merge duplicate** id=3177 + id=3508 — keep manual review needed: No geocode result, cannot determine correct coords. MEDIUM confidence.

116. **Merge duplicate** id=3126 + id=3499 — keep id=3126: Gov-verified (g=1). MEDIUM confidence.

117. **Merge duplicate** id=3491 + id=3492 — keep manual review needed: Equal sources, no clear winner. MEDIUM confidence.

118. **Merge duplicate** id=406 + id=3025 — keep id=406: More sources (4 vs 3). MEDIUM confidence.

119. **Merge duplicate** id=358 + id=1589 — keep id=358: More sources (4 vs 2). MEDIUM confidence.

120. **Merge duplicate** id=358 + id=3084 — keep manual review needed: Equal sources, no clear winner. MEDIUM confidence.

121. **Merge duplicate** id=783 + id=3202 — keep id=783: Gov-verified (g=1). MEDIUM confidence.

122. **Merge duplicate** id=553 + id=2628 — keep id=2628: Gov-verified (g=1). MEDIUM confidence.

123. **Merge duplicate** id=2073 + id=2714 — keep id=2714: More sources (4 vs 3). MEDIUM confidence.

124. **Merge duplicate** id=482 + id=3201 — keep id=482: Gov-verified (g=1). MEDIUM confidence.

125. **Merge duplicate** id=2855 + id=3115 — keep id=3115: More sources (6 vs 4). MEDIUM confidence.

126. **Merge duplicate** id=2551 + id=3161 — keep id=2551: Gov-verified (g=1). MEDIUM confidence.

127. **Merge duplicate** id=135 + id=2780 — keep id=135: More sources (6 vs 4). MEDIUM confidence.

128. **Merge duplicate** id=2591 + id=2664 — keep manual review needed: Equal sources, no clear winner. MEDIUM confidence.

129. **Merge duplicate** id=2988 + id=3203 — keep id=2988: More sources (2 vs 1). MEDIUM confidence.

130. **Merge duplicate** id=2856 + id=2860 — keep manual review needed: Equal sources, no clear winner. MEDIUM confidence.

131. **Merge duplicate** id=263 + id=3145 — keep id=263: More sources (4 vs 2). MEDIUM confidence.

132. **Merge duplicate** id=1494 + id=3165 — keep id=1494: Gov-verified (g=1). MEDIUM confidence.

133. **Merge duplicate** id=202 + id=1494 — keep manual review needed: Equal sources, no clear winner. MEDIUM confidence.

134. **Merge duplicate** id=1772 + id=2965 — keep id=2965: More sources (4 vs 3). MEDIUM confidence.

135. **Merge duplicate** id=569 + id=2869 — keep id=2869: Gov-verified (g=1). MEDIUM confidence.

136. **Merge duplicate** id=2367 + id=2368 — keep id=2368: More sources (4 vs 3). MEDIUM confidence.

137. **Merge duplicate** id=2660 + id=2692 — keep id=2692: More sources (3 vs 2). MEDIUM confidence.

138. **Merge duplicate** id=1040 + id=1051 — keep id=1040: More sources (2 vs 1). MEDIUM confidence.

139. **Merge duplicate** id=1094 + id=1098 — keep manual review needed: Equal sources, no clear winner. MEDIUM confidence.

140. **Merge duplicate** id=2714 + id=3475 — keep id=2714: Gov-verified (g=1). MEDIUM confidence.

141. **Merge duplicate** id=185 + id=186 — keep id=185: More sources (4 vs 3). MEDIUM confidence.

142. **Merge duplicate** id=100 + id=152 — keep manual review needed: Equal sources, no clear winner. MEDIUM confidence.

143. **Merge duplicate** id=1 + id=675 — keep id=675: More sources (4 vs 3). MEDIUM confidence.

144. **Merge duplicate** id=15 + id=675 — keep id=675: More sources (4 vs 2). MEDIUM confidence.

145. **Merge duplicate** id=41 + id=675 — keep id=675: More sources (4 vs 2). MEDIUM confidence.

146. **Merge duplicate** id=49 + id=675 — keep id=675: More sources (4 vs 2). MEDIUM confidence.

147. **Merge duplicate** id=580 + id=675 — keep id=675: Gov-verified (g=1). MEDIUM confidence.

148. **Merge duplicate** id=2073 + id=3475 — keep id=2073: Gov-verified (g=1). MEDIUM confidence.

149. **Merge duplicate** id=2871 + id=2872 — keep manual review needed: Equal sources, no clear winner. MEDIUM confidence.

150. **Merge duplicate** id=2650 + id=2872 — keep manual review needed: Equal sources, no clear winner. MEDIUM confidence.

151. **Merge duplicate** id=251 + id=271 — keep id=251: More sources (4 vs 3). MEDIUM confidence.

152. **Merge duplicate** id=107 + id=146 — keep manual review needed: Equal sources, no clear winner. MEDIUM confidence.

153. **Merge duplicate** id=212 + id=271 — keep id=212: More sources (5 vs 3). MEDIUM confidence.

154. **Merge duplicate** id=138 + id=146 — keep manual review needed: Equal sources, no clear winner. MEDIUM confidence.

155. **Merge duplicate** id=2239 + id=2559 — keep id=2239: More sources (4 vs 2). MEDIUM confidence.

156. **Merge duplicate** id=137 + id=569 — keep id=137: Gov-verified (g=1). MEDIUM confidence.

157. **Merge duplicate** id=98 + id=2880 — keep id=98: More sources (5 vs 3). MEDIUM confidence.

158. **Merge duplicate** id=1220 + id=1221 — keep id=1221: More sources (2 vs 1). MEDIUM confidence.

159. **Merge duplicate** id=1856 + id=2963 — keep id=2963: Gov-verified (g=1). MEDIUM confidence.

160. **Merge duplicate** id=285 + id=1474 — keep id=285: More sources (4 vs 3). MEDIUM confidence.

161. **Merge duplicate** id=2293 + id=2442 — keep id=2442: More sources (3 vs 2). MEDIUM confidence.

162. **Merge duplicate** id=2779 + id=2874 — keep manual review needed: Equal sources, no clear winner. MEDIUM confidence.

163. **Merge duplicate** id=458 + id=2841 — keep id=458: More sources (4 vs 3). MEDIUM confidence.

164. **Merge duplicate** id=306 + id=1474 — keep id=306: More sources (4 vs 3). MEDIUM confidence.

165. **Merge duplicate** id=285 + id=290 — keep manual review needed: Equal sources, no clear winner. MEDIUM confidence.

166. **Merge duplicate** id=1856 + id=2961 — keep id=2961: Gov-verified (g=1). MEDIUM confidence.

167. **Merge duplicate** id=2280 + id=2293 — keep id=2280: More sources (3 vs 2). MEDIUM confidence.

168. **Merge duplicate** id=1591 + id=1592 — keep id=1591: More sources (2 vs 1). MEDIUM confidence.

169. **Merge duplicate** id=1560 + id=1591 — keep id=1560: Gov-verified (g=1). MEDIUM confidence.

170. **Merge duplicate** id=1589 + id=3084 — keep id=3084: More sources (4 vs 2). MEDIUM confidence.

171. **Merge duplicate** id=2280 + id=2442 — keep manual review needed: Equal sources, no clear winner. MEDIUM confidence.

172. **Merge duplicate** id=971 + id=1179 — keep manual review needed: Equal sources, no clear winner. MEDIUM confidence.

173. **Merge duplicate** id=971 + id=983 — keep manual review needed: Equal sources, no clear winner. MEDIUM confidence.

174. **Merge duplicate** id=150 + id=306 — keep manual review needed: Equal sources, no clear winner. MEDIUM confidence.

175. **Merge duplicate** id=3152 + id=3509 — keep id=3152: Gov-verified (g=1). MEDIUM confidence.
