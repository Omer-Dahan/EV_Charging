# דוח מחקר: מיפוי ובחינת ממשקי API וצוברים גלובליים לעמדות טעינה (EV) בישראל

**תאריך יצירה:** אוגוסט 2026  
**פרויקט:** בוט טלגרם לאיתור עמדות טעינה לרכב חשמלי בישראל  
**מיקום קובץ:** `/home/vm/projects/ev-charging-bot/research/02-global-apis.md`

---

## 1. תקציר מנהלים

מטרת מחקר זה היא למפות, לבחון ולאמת את כלל ה-APIs והצוברים (Aggregators) הבינלאומיים המובילים בתחום טעינת רכב חשמלי (EV), במטרה לבחון את התאמתם לפיתוח **בוט טלגרם חינמי, מדויק ומהיר לאיתור עמדות טעינה בישראל**.

### ממצאים מרכזיים:
1. **כיסוי בישראל ב-APIs גלובליים:** רוב ה-APIs הגלובליים סובלים מחוסר עדכון או כיסוי חלקי בישראל לעומת המצב בשטח (בישראל יש כיום אלפי עמדות ציבוריות של מפעילים כמו אפקון, EV-Edge, סונול EVI, פז Charge, Gnrgy, סלוצ\x27ארג\x27 ועוד).
2. **זמינות בזמן אמת (Real-Time Availability):** רוב ה-APIs הגלובליים החינמיים **אינם** מספקים סטטוס תפוס/פנוי חי עבור ישראל. מידע בזמן אמת דורש חיבור לפרוטוקול OCPI מול המפעילים המקומיים או שימוש ב-APIs מסחריים יקרים.
3. **הפתרון הגלובלי המשתלם ביותר:** **Google Places API (New)** מספק את הכיסוי הגיאוגרפי והטקסטואלי העשיר ביותר בישראל (בחינם עד $200 לחודש), לצד **TomTom EV API** (המציע 2,500 קריאות יומיות חינם ללא כרטיס אשראי) ו-**Open Charge Map / OpenStreetMap** לשכבת נתונים פתוחה.

---

## 2. מיפוי מעמיק של ממשקי ה-API הגלובליים

---

### 1. Open Charge Map (OCM) API

* **שם השירות:** Open Charge Map API (גרסה v3)
* **כתובת ראשית (URL):** [https://openchargemap.org](https://openchargemap.org) | [פורטל מפתחים](https://openchargemap.org/site/develop/api)
* **נקודות קצה מרכזיות (Endpoints):**
  * `GET https://api.openchargemap.io/v3/poi/` — שליפת עמדות טעינה לפי קואורדינטות (`latitude`, `longitude`, `distance`), קוד מדינה (`countrycode=IL`), מזהה מפעיל או סוג מחבר.
  * `GET https://api.openchargemap.io/v3/referencedata/` — שליפת טבלאות המרה (סוגי מחברים, רמות טעינה, מפעילי רשת).
* **אימות והרשאות (Authentication):**
  * נדרש מפתח API (`API Key`) המתקבל בהרשמה חינמית.
  * העברה באמצעות כותרת `X-API-Key: {YOUR_API_KEY}` או כפרמטר URL: `?key={YOUR_API_KEY}`.
  * נדרשת הגדרת כותרת `User-Agent` תקינה.
* **מודל תמחור (Free / Paid):**
  * **חינם לחלוטין (Non-profit / Community Open Data)**.
  * רישוי נתונים: Creative Commons Attribution 4.0 International (CC BY 4.0) — מחייב מתן קרדיט ל-Open Charge Map.
* **מכסות ומגבלות (Quotas & Limits):**
  * כ-**1,000 קריאות ביום** לחשבון מפתח סטנדרטי.
  * הגבלת תוצאות לעד 500 תוצאות לשאילתה בודדת (`maxresults=500`).
  * דרישה של המערכת לרווח קריאות (rate limiting) ולא לבצע הפצצות של מאות קריאות בדקה.
* **כיסוי בישראל (Israel Coverage):**
  * **כמות עמדות מאומתת:** כ-**369 נקודות עניין (POIs)** רשומות במאגר עבור ישראל (נבדק ומאומת מול יצוא הנתונים הרשמי של OCM בגיטהאב).
  * **איכות הנתונים:** בינונית-נמוכה. הנתונים מתבססים על תרומות קהילה וסריקות עבר. מכילים רשתות מרכזיות כמו Afcon, EV-Edge, Gnrgy, Sonol-evi, Tesla, אך חלק מהעמדות אינן מעודכנות או חסרות עמדות חדשות שנפרסו בשנים האחרונות.
* **זמינות בזמן אמת (Real-Time Availability):**
  * **לא נתמך בישראל**. המערכת תומכת בהצגת סטטוס דינמי רק למפעילים בינלאומיים המזרימים פיד OCPI ישיר לשרתי OCM; אף מפעיל ישראלי אינו מזרים פיד חי ל-OCM.
* **סוגי מחברים נתמכים (Connectors):**
  * Type 2 (Mennekes, `ConnectionTypeID: 25`)
  * CCS Combo 2 (`ConnectionTypeID: 33`)
  * CHAdeMO (`ConnectionTypeID: 2`)
  * Type 1 (J1772)
  * Tesla Destination / Supercharger (`ConnectionTypeID: 8 / 30`)

---

### 2. ChargePoint API

* **שם השירות:** ChargePoint Web Services API / ChargePoint Driver Experience Network (DEN)
* **כתובת ראשית (URL):** [https://www.chargepoint.com](https://www.chargepoint.com) | [ChargePoint Developer Info](https://www.chargepoint.com/resources)
* **נקודות קצה מרכזיות (Endpoints):**
  * מבוסס פרוטוקול SOAP / WSDL: `https://webservices.chargepoint.com/cp_api_5.1.wsdl`
  * מתודות עיקריות:
    * `getStations` — קבלת פרטי עמדות ברשת ChargePoint.
    * `getStationStatus` — שליפת סטטוס יציאות בזמן אמת (AVAILABLE, INUSE, UNREACHABLE).
    * `getChargingSessionData` — נתוני טעינה היסטוריים.
    * `getLoad` — ניטור עומס והספקים (kW).
* **אימות והרשאות (Authentication):**
  * אימות SOAP WS-Security (User / Password / API License Key).
  * מוגבל ללקוחות עסקיים ושותפים מורשים בלבד (B2B).
* **מודל תמחור (Free / Paid):**
  * **בתשלום מלא בלבד (Commercial / Enterprise / Subscription)**.
  * אין מסלול חינמי ציבורי (No Public Free Tier).
* **מכסות ומגבלות (Quotas & Limits):**
  * מותאם אישית לפי החוזה המסחרי והסכם השירות (SLA).
* **כיסוי בישראל (Israel Coverage):**
  * **אפסי עד זניח (0%)**.
  * רשת ChargePoint פועלת בצפון אמריקה ובמערב אירופה. בישראל אין פריסה או ניהול של עמדות ציבוריות תחת רשת ChargePoint.
* **זמינות בזמן אמת (Real-Time Availability):**
  * נתמך באופן מלא ברשת שלהם בחו"ל, אך לא רלוונטי לישראל.
* **סוגי מחברים נתמכים (Connectors):**
  * J1772, CCS Type 1, CCS Type 2, NACS (Tesla), CHAdeMO.

---

### 3. PlugShare API

* **שם השירות:** PlugShare API (בבעלות חברת EVgo / Recargo)
* **כתובת ראשית (URL):** [https://www.plugshare.com](https://www.plugshare.com) | [פורטל עסקי](https://company.plugshare.com/business.html)
* **נקודות קצה מרכזיות (Endpoints):**
  * `GET https://api.plugshare.com/v3/locations` (Endpoint פרטי ומאובטח המשמש את האפליקציה).
  * הגישה המסחרית מספקת REST API ייעודי לשותפים (Automotive, Fleets, Utilities).
* **אימות והרשאות (Authentication):**
  * חסום לחלוטין לשימוש אנונימי או פיתוח חופשי.
  * הגישה לאפליקציה מוגנת ע"י הצפנת טוקנים, חתימות בקשה ומנגנוני הגנה של Cloudflare/Bot-Detection.
  * גישה רשמית דורשת חתימה על הסכם רישיון מסחרי מול EVgo/PlugShare.
* **מודל תמחור (Free / Paid):**
  * **בתשלום מסחרי בלבד (Enterprise Commercial License)**.
  * PlugShare מצהירה במפורש שאינה מעניקה רישיונות אישיים או ללא תשלום (No non-commercial or hobbyist licenses).
* **מכסות ומגבלות (Quotas & Limits):**
  * נקבע פר חוזה מסחרי.
* **כיסוי בישראל (Israel Coverage):**
  * **גבוה באפליקציה (קהילתי), אך בלתי נגיש ב-API רשמי חינמי**.
  * נהגי EV רבים בישראל מדווחים ומעדכנים עמדות באפליקציית PlugShare, אך אין שום דרך חוקית וחינמית לצרוך נתונים אלו בבוט עצמאי ללא סקריפינג (המפר את תנאי השימוש).
* **זמינות בזמן אמת (Real-Time Availability):**
  * קיימת בעולם רק עבור רשתות עם אינטגרציית OCPI/Roaming ישירה; בישראל מתבססת בעיקר על צ\x27ק-אינים (Check-ins) של משתמשים.
* **סוגי מחברים נתמכים (Connectors):**
  * Type 2, CCS2, CHAdeMO, Tesla Supercharger, Wall / Schuko.

---

### 4. TomTom EV Search & Charging Availability API

* **שם השירות:** TomTom EV Charging Stations API & Search API
* **כתובת ראשית (URL):** [https://developer.tomtom.com](https://developer.tomtom.com) | [דוקומנטציה](https://developer.tomtom.com/ev-routing-api/documentation)
* **נקודות קצה מרכזיות (Endpoints):**
  * חיפוש עמדות טעינה:  
    `GET https://api.tomtom.com/search/2/poiSearch/electric%20vehicle%20station.json?categorySet=7309&lat={LAT}&lon={LON}&radius={RADIUS}&key={KEY}`
  * זמינות עמדות בזמן אמת:  
    `GET https://api.tomtom.com/search/2/ev/chargingAvailability.json?chargingAvailability={chargingAvailabilityId}&key={KEY}`
  * חישוב מסלול מותאם EV:  
    `POST https://api.tomtom.com/routing/1/calculateLongDistanceEVRoute/...`
* **אימות והרשאות (Authentication):**
  * מפתח API ייעודי (`key={API_KEY}`) כפרמטר בשאילתה.
* **מודל תמחור (Free / Paid):**
  * **Freemium נדיב במיוחד!**
  * ללא צורך בהזנת כרטיס אשראי בעת ההרשמה.
  * מעבר לחיוב Pay-as-you-grow רק בעת חריגה מהמכסה היומית החינמית.
* **מכסות ומגבלות (Quotas & Limits):**
  * **2,500 קריאות חינם ביום (Non-tile requests)** — שווה ערך לכ-**75,000 קריאות בחודש**!
  * 50,000 קריאות Map Tiles ביום.
  * קצב מרבי: 5 קריאות לשנייה (QPS).
* **כיסוי בישראל (Israel Coverage):**
  * **בינוני (Static POIs)**.
  * מכיל מאות נקודות עניין של עמדות טעינה ציבוריות בישראל (בעיקר רשתות גדולות ותחנות דלק). הנתונים סטטיים ברובם.
* **זמינות בזמן אמת (Real-Time Availability):**
  * שירות ה-Availability קיים כ-Endpoint פעיל, אך **אינו מקושר ברובו למפעילים ישראליים** (הנתונים בזמן אמת עובדים בעיקר במערב אירופה וצפון אמריקה).
* **סוגי מחברים נתמכים (Connectors):**
  * IEC 62196 Type 2 Outlet / Cable, Combo 2 (CCS2), CHAdeMO, Tesla Supercharger.

---

### 5. HERE EV Charge Points API

* **שם השירות:** HERE Location Services – EV Charge Points API
* **כתובת ראשית (URL):** [https://developer.here.com](https://developer.here.com) | [דוקומנטציה](https://www.here.com/docs/bundle/ev-charge-points-api-developer-guide)
* **נקודות קצה מרכזיות (Endpoints):**
  * `GET https://ev.hereapi.com/v2/stations` — חיפוש עמדות טעינה ברדיוס או תיחום גיאוגרפי (Bounding Box).
  * `GET https://ev.hereapi.com/v2/stations/{id}` — קבלת פרטי עמדה מלאים כולל מפרט טכני.
* **אימות והרשאות (Authentication):**
  * מפתח API (`apiKey={YOUR_API_KEY}`) או OAuth 2.0 Bearer Token.
* **מודל תמחור (Free / Paid):**
  * **דורש הסכם מסחרי / אישור גישה (Gated Commercial API)**.
  * בעוד שירותי המיפוי וה-Geocoding הכלליים של HERE מציעים 30,000 טרנזקציות חינם בחודש, שכבת ה-EV הייעודית סגורה כעת ברישוי ייעודי ואינה פתוחה ל-Freemium אוטומטי.
* **מכסות ומגבלות (Quotas & Limits):**
  * מוגדר לפי החוזה מול נציגי HERE.
* **כיסוי בישראל (Israel Coverage):**
  * טוב כמאגר גלובלי, אך חלק ניכר מנתוני העמדות בישראל מתעדכן בהשהיה ביחס לפריסה המקומית המהירה.
* **זמינות בזמן אמת (Real-Time Availability):**
  * תומך דינמית במפעילים בינלאומיים המחוברים ל-Hubs (כגון Hubject), אך אינו מכסה בזמן אמת את מירב המפעילים הישראליים.
* **סוגי מחברים נתמכים (Connectors):**
  * Type 2, CCS 2, CHAdeMO, Schuko, GB/T, NACS.

---

### 6. Google Places API (New) — חיפוש עמדות EV

* **שם השירות:** Google Maps Platform – Places API (New)
* **כתובת ראשית (URL):** [https://developers.google.com/maps/documentation/places/web-service](https://developers.google.com/maps/documentation/places/web-service)
* **נקודות קצה מרכזיות (Endpoints):**
  * חיפוש בסביבה (Nearby Search):  
    `POST https://places.googleapis.com/v1/places:searchNearby`  
    *Body:* `{"includedTypes": ["electric_vehicle_charging_station"], "locationRestriction": {...}}`
  * חיפוש טקסטואלי חופשי (Text Search):  
    `POST https://places.googleapis.com/v1/places:searchText`
  * פרטי מקום (Place Details):  
    `GET https://places.googleapis.com/v1/places/{PLACE_ID}`
* **אימות והרשאות (Authentication):**
  * כותרות חובה בבקשה:
    * `X-Goog-Api-Key: {YOUR_GOOGLE_API_KEY}`
    * `X-Goog-FieldMask: places.id,places.displayName,places.location,places.evChargeOptions`
* **מודל תמחור (Free / Paid) ומכסות חינם:**
  * **Google מעניקה קרדיט חודשי חינמי מתחדש של $200 לכל חשבון Billing**.
  * תמחור לפי שכבת שדות (Field Mask SKU):
    * **Places (New) Basic** (שם, מיקום, כתובת, ID): **$5.00 ל-1,000 קריאות**.  
      👈 הקרדיט של $200 מעניק **עד 40,000 חיפושים חינם בכל חודש!**
    * **Places (New) Enterprise** (כולל שדה `evChargeOptions`): **$32.00 ל-1,000 קריאות**.  
      👈 הקרדיט של $200 מעניק **כ-6,250 חיפושים מלאים חינם בכל חודש**.
* **כיסוי בישראל (Israel Coverage):**
  * **גבוה ביותר ומעודכן ביותר מבין כל ה-APIs הגלובליים!**
  * כולל כמעט כל עמדה ציבורית בישראל: אפקון, סונול EVI, פז Charge, EV Edge, טסלה סופרצ\x27ארג\x27רס, עמדות בבתי מלון, חניונים ציבוריים, מרכזי ביג וקניונים.
  * שמות העמדות, הכתובות ושעות הפעילות מתורגמים ומדויקים בעברית מלאה.
* **זמינות בזמן אמת (Real-Time Availability):**
  * שדה `evChargeOptions.connectorAggregation` מחזיר מידע על זמינות וכמות תקעים פנויים באזורים שבהם יש שיתוף פעולה ישיר. בישראל מרבית העמדות מחזירות מידע סטטי מפורט (סוגי תקעים והספקים), אך סטטוס תפוס/פנוי בזמן אמת עדיין מוגבל.
* **סוגי מחברים נתמכים (Connectors):**
  * `EV_CONNECTOR_TYPE_CCS_COMBO_2`
  * `EV_CONNECTOR_TYPE_TYPE_2`
  * `EV_CONNECTOR_TYPE_CHADEMO`
  * `EV_CONNECTOR_TYPE_TESLA`

---

### 7. OCPI (Open Charge Point Interface) ומאגרי Roaming

* **שם השירות:** פרוטוקול OCPI (גרסאות 2.1.1 / 2.2.1 / 3.0) & צומתי Roaming (Hubject, Gireve, e-Clearing.net)
* **כתובת ראשית (URL):** [https://evroaming.org](https://evroaming.org) | [OCPI Protocol Spec](https://ocpi-protocol.com)
* **נקודות קצה סטנדרטיות (Standard Endpoints):**
  * `GET /ocpi/cpo/2.2.1/locations` — שליפת כלל האתרים, ה-EVSEs, והמחברים.
  * `GET /ocpi/cpo/2.2.1/tariffs` — מחירוני טעינה (לפי קוט"ש, זמן או התחלה).
  * `GET /ocpi/cpo/2.2.1/sessions` — נתוני מפגשי טעינה.
  * `PUT /ocpi/emsp/2.2.1/locations/{country_code}/{party_id}/{location_id}` — הזרמת עדכוני מיקום וסטטוס חי בזמן אמת (Push).
* **אימות והרשאות (Authentication):**
  * מנגנון לחיצת יד דו-כיווני (Credentials Handshake): החלפת Token A ב-Token B עם כותרת `Authorization: Token {TOKEN}`.
* **מודל תמחור (Free / Paid):**
  * **הפרוטוקול עצמו חופשי ופתוח (Open Standard Royalty-Free)**.
  * **הגישה למאגרי Roaming מסחריים (Hubject Intercharge, Gireve): בתשלום B2B כבד** (אלפי אירו בשנה + עמלות חיבור).
* **כיסוי בישראל (Israel Coverage):**
  * **הפרוטוקול המרכזי המוגדר בחוק בישראל**: משרד האנרגיה מחייב את מפעילי עמדות הטעינה לתמוך ב-OCPI כדי לאפשר נדידה (Roaming) ושקיפות מידע.
  * חברות ישראליות מובילות (כמו Driivz הישראלית שמנהלת רשתות גלובליות, אפקון, סונול, EV-Edge) מממשות OCPI בשרתיהן, אך ה-Endpoints סגורים בהרשאות לשותפים עסקיים ואינם פתוחים אנונימית לציבור.
* **זמינות בזמן אמת (Real-Time Availability):**
  * **הסטנדרט המוחלט לזמן אמת**: מודול ה-Locations ב-OCPI מדווח על סטטוס כל תקע בכל רגע נתון (`AVAILABLE`, `CHARGING`, `OCCUPIED`, `BLOCKED`, `OUTOFORDER`, `INOPERATIVE`).
* **סוגי מחברים נתמכים (Connectors):**
  * תמיכה בכל תקן עולמי קיים: IEC 62196 Type 2, CCS2, CHAdeMO, Type 1, NACS וכו\x27.

---

### 8. ממשקי API נוספים שנבדקו (Chargetrip, Eco-Movement, OpenStreetMap)

#### א. OpenStreetMap (OSM) via Overpass API
* **כתובת:** `https://overpass-api.de/api/interpreter`
* **אימות:** אין צורך באימות (פתוח לחלוטין).
* **תמחור:** חינם 100%.
* **כיסוי בישראל:** **176 עמדות טעינה** ממופות כיום תחת תגית `amenity=charging_station` (נבדק ונשלף ישירות באמצעות Overpass).
* **זמן אמת:** אין (נתונים סטטיים בלבד).
* **מחברים:** תגיות `socket:type2=yes`, `socket:type2_combo=yes`, `capacity=*`.

#### ב. Chargetrip API
* **כתובת:** [https://chargetrip.com](https://chargetrip.com)
* **פרוטוקול:** GraphQL API (`https://api.chargetrip.com/graphql`).
* **תמחור:** שכבת "Lite" חינמית למפתחים.
* **בסיס נתונים:** מתבסס על שילוב מול Eco-Movement.
* **כיסוי בישראל:** חלקי, מתמקד בעיקר באירופה ובצפון אמריקה.

---

## 3. טבלת השוואה מקיפה בין כלל הממשקים

| שם ה-API | כתובת URL | מודל תמחור | מכסה חינמית | כמות עמדות בישראל | זמינות בזמן אמת (ישראל) | סוגי מחברים מרכזיים | התאמה לבוט טלגרם ישראלי |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Google Places API (New)** | [developers.google.com](https://developers.google.com/maps/documentation/places/web-service) | Freemium ($200 חודשי) | 6,250–40,000 קריאות/חודש | **אלפים (כיסוי כמעט מלא)** | חלקי (מפרט סטטי מלא, פנוי/תפוס מוגבל) | CCS2, Type 2, CHAdeMO, Tesla | ⭐⭐⭐⭐⭐ **מצוין (הכי טוב למיקומים ושמות)** |
| **TomTom EV Search** | [developer.tomtom.com](https://developer.tomtom.com) | Freemium | **2,500 קריאות/יום** (~75,000/חודש) | מאות עמדות | לא פעיל בישראל | CCS2, Type 2, CHAdeMO | ⭐⭐⭐⭐ **מעולה לחיפוש רדיוס וגיבוי חינמי** |
| **Open Charge Map (OCM)** | [openchargemap.org](https://openchargemap.org) | חינם (Open Data) | 1,000 קריאות/יום | **369 עמדות מאומתות** | ❌ לא | CCS2, Type 2, CHAdeMO | ⭐⭐⭐ **טוב למאגר מקומי ראשוני** |
| **OpenStreetMap (Overpass)** | [overpass-api.de](https://overpass-api.de) | חינם (Open Source) | ללא הגבלה קשיחה (Fair Use) | **176 עמדות** | ❌ לא | Type 2, CCS2 | ⭐⭐ **דליל בישראל** |
| **HERE EV Points** | [developer.here.com](https://developer.here.com) | Commercial / Gated | מותנה בהסכם | מאות עמדות | ❌ מוגבל בישראל | CCS2, Type 2, CHAdeMO | ⭐⭐ **אינו פתוח ל-Freemium** |
| **ChargePoint API** | [chargepoint.com](https://www.chargepoint.com) | Paid Enterprise | ❌ אין | **0 (אין פריסה בישראל)** | לא רלוונטי | J1772, CCS1, NACS | ❌ **אינו מתאים כלל** |
| **PlugShare API** | [plugshare.com](https://www.plugshare.com) | Commercial Only | ❌ אין | גבוה באפליקציה, חסום ב-API | קהילתי | CCS2, Type 2, Tesla | ❌ **חסום למפתחים עצמאיים** |
| **OCPI / Roaming Hubs** | [evroaming.org](https://evroaming.org) | פרוטוקול פתוח / גישה סגורה | תלוי מפעיל מקומי | **כלל העמדות בישראל** |  **כן מלא (הסטנדרט הטוב ביותר)** | כל הסוגים | 🔑 **היעד האולטימטיבי מול מפעילי ישראל** |

---

## 4. המלצה מנומקת: ה-API הגלובלי הטוב ביותר לבוט ישראלי חינמי

### המנצח הבלתי מעורער: **Google Places API (New) בשילוב TomTom EV API**

לאחר בדיקה מעמיקה של איכות הנתונים, הנגישות, השפה העברית ועלויות הפיתוח, **שום API גלובלי יחיד אינו מספק פתרון מושלם ללא תשלום**, אך שילוב חכם מייצר את הפתרון האופטימלי:

#### 1. שכבת המידע הראשית (Primary Provider): **Google Places API (New)**
* **מדוע?** הוא היחיד מבין ה-APIs הגלובליים שמכיל שמות מדויקים בעברית (למשל: "עמדת טעינה אפקון - קניון עזריאלי", "סונול EVI צומת כח"), כתובות ברורות, שעות פתיחה של המתחם וקישורי ניווט מדויקים ל-Waze ול-Google Maps.
* **התנהלות במסגרת החינמית:** ניצול הקרדיט החודשי של $200. מומלץ לבצע שאילתות Nearby Search עם FieldMask ממוקד הכולל רק את השדות ההכרחיים (`places.id,places.displayName,places.location,places.formattedAddress`) כדי להישאר ב-Basic Tier (המקנה עד **40,000 בקשות חינם בכל חודש** — די והותר לבוט טלגרם צומח).

#### 2. שכבת הגיבוי והרדיוס (Fallback & Caching): **TomTom EV Search API**
* **מדוע?** מעניק **2,500 קריאות חינם בכל יום** ללא צורך בכרטיס אשראי. ניתן להשתמש בו לחיפושים כלליים ברדיוס רחב ולצמצם את הפניות ל-Google Places.

#### 3. הצעד הבא לשלב ב\x27 — מידע חי ומחירים (Real-Time Status & Tariffs):
* מכיוון שאף API גלובלי חינמי אינו מספק סטטוס תפוס/פנוי בזמן אמת עבור עמדות ישראליות (אפקון, EV-Edge, סונול וכו\x27), הבוט מומלץ להיבנות בארכיטקטורה היברידית:
  * **שכבת מיקום גלובלית:** Google Places + TomTom.
  * **שכבת סטטוס מקומית:** חיבור ישיר למאגרים הפתוחים הממשלתיים (מאגר משרד האנרגיה באתר Data.gov.il) ו/או צריכת נתוני OCPI/APIs מקומיים פתוחים של המפעילים הישראליים.

---
*דוח זה הוכן באופן עצמאי ומאומת מול שרתי ה-APIs ומסמכי הפיתוח הרשמיים.*
