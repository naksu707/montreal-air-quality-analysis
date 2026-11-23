# Data Preparation — RSQA Daily Air-Quality Dataset (2013–2025)

This document explains **what was done** to turn thirteen yearly files of hourly measurements from
Montréal's air-quality monitoring network (RSQA) into one analysis-ready daily dataset, and **why** each
decision was made.

| Step | File | Output |
|---|---|---|
| 1. Consolidation (hourly → daily) | `01_build_daily_dataset.py` | `rsqa_daily_air_quality.csv`, `rsqa_build_report.csv`, `rsqa_station_report.csv` |
| 2. Review and cleaning | `02_data_review_cleaning.ipynb` | `rsqa_daily_clean.csv`, `rsqa_daily_quality_log.csv` |

```
RSQA - Multi-Polluants (en continu)/dataset 2013 - 2025/
    rsqa-multi-polluants2013.csv ... rsqa-multi-polluants2025.csv     hourly, 13 files, 1.25 M rows
lista-estaciones.csv                                                  official station list
                │
                ▼  01_build_daily_dataset.py
rsqa_daily_air_quality.csv  (+ build and station reports)             daily, 8 stations, 32,567 station-days
                │
                ▼  02_data_review_cleaning.ipynb
rsqa_daily_clean.csv  (+ rsqa_daily_quality_log.csv)                  analysis-ready
```

The first notebook (`airquality_tools4cities.ipynb`) was an initial exploration of every RSQA file
available. Its findings shaped the decisions below, and it has been replaced by this pipeline.

---

## 1. Source data

**RSQA – Multi-Polluants (en continu)**, Ville de Montréal, published on Données Québec under CC-BY 4.0.
Each yearly file holds hourly average concentrations per station.

**RSQA – Liste des stations**, Ville de Montréal: number, name, status (`ouvert`, `fermé`,
`fermé-historical`, `temp`) and coordinates of every station.

Facts from the official data dictionary that drive the processing:

| Item | Value |
|---|---|
| Units | **NO2 and O3 in ppb**; PM2.5 in µg/m³ |
| Time zone | Eastern Standard Time (HNE) all year — no daylight-saving change |
| Timestamp (from 2013) | Marks the **end** of the hour (`02:00` = measurements from 01:01 to 02:00) |
| Day | 01:00 → 24:00 |
| Non-measurement codes | `alarm`, `down`, `InVld`, `<Samp`, `calib`, `span`, `zero`, `purge`, `RS232`, `FailPwr`, `No Data`, `N/M`, `N/A`, empty cells |

Because the clock never switches to daylight time, every day has exactly 24 hourly slots.

---

## 2. Why consolidate the 13 files into one

The yearly files are not consistent with each other. Their structure, verified file by file:

| Years | Station column | Date and time | PM2.5 column | Last hour of the day written as |
|---|---|---|---|---|
| 2013 | `NUMERO_STATION` | `DATE_HEURE`, `dd-mm-yyyy hh:mm` | `PM2.5` | `24:00` |
| 2014 | `NUMERO_STATION` | `Date` (`yyyy-mm-dd`) + `heure` (`h:mm`), two columns | `PM2.5` | `0:00`, same date |
| 2015–2019 | `NO_POSTE` | `DATE_ HEURE` (space inside the name), `yyyy-mm-dd hh:mm` | `PM2,5` | `00:00`, same date |
| 2020–2021 | `NO_POSTE` | `DATE_HEURE`, `yyyy-mm-dd hh:mm` (2021 adds a `site` column) | `PM2,5` | `00:00`, same date |
| 2022–2023 | `NO_POSTE` | `DATE_HEURE`, `dd-mm-yyyy hh:mm` | `PM2,5` | `24:00` |
| 2024–2025 | `NO_POSTE` | `DATE_HEURE`, `dd-mm-yyyy hh:mm` | `PM2.5` | `24:00` |

Analysing the files one by one would repeat the same fixes thirteen times. A single script gives one
reproducible path from the raw files to one dataset. It handles:

* **Column names.** Names are normalised (upper case, no spaces, no quotes, no BOM, `.` → `,`) and matched
  against a list of aliases, never by position.
* **Separators.** Files are read with explicit `sep=","` and `decimal="."`; a decimal comma is converted
  only inside values that look like `123,45`, never with a global replacement.
* **Non-measurement codes.** Every non-numeric code becomes `NaN`, so the number of valid hours can be
  counted. Over the 13 files there are about 189,000 such codes for NO2, 94,000 for PM2.5 and 212,000 for
  O3 (counted per year in `rsqa_build_report.csv`).
* **Two date formats.** ISO (`yyyy-mm-dd`) and day-first (`dd-mm-yyyy`) dates are parsed separately with
  explicit formats, so day and month can never be swapped.
* **Two ways of writing midnight.** Both notations mean "the hour that closes the day". The script detects
  which one each file uses (in the ISO files the `00:00` row comes right after the `23:00` row of the same
  date) and converts both to the real instant, the next day at 00:00. The day of each hour is then
  `timestamp − 1 hour`. Every file then runs exactly from 1 January 01:00 to 1 January 00:00 of the next
  year.
* **Filler rows.** 2013, 2014 and 2022 contain rows for **29 February**, which does not exist in those
  years (288, 264 and 264 rows). All of them are empty (`N/M`) and are dropped. 2014 and 2023 also end with
  empty rows.
* **Duplicates.** 2023 and 2024 contain one exact copy of an hour for station 3 (31 December, 01:00). The
  copy is removed.

---

## 3. Why a daily resolution

1. **The atmospheric variables are daily.** Precipitation, maximum and minimum temperature, humidity,
   solar radiation, wind and pressure come from CHIRPS/CHIRTS and NASA POWER at a daily time step. Both
   datasets must share the same resolution to be joined by station and date.
2. **The task classifies days.** The project classifies each day as good or bad, so the unit of analysis
   is the station-day.
3. **Health guidelines are daily.** The WHO short-term guidelines are defined over 24 hours (NO2, PM2.5)
   or as a daily maximum (O3).
4. **Less noise.** Hourly data contain short peaks and maintenance gaps; a daily value is more stable.

---

## 4. Why only the open stations

The hourly files contain **15 stations**, but the official list marks only **9 as open** (`ouvert`), which
are the 9 stations on the project map. The dataset keeps only the open stations; **8 of them have data**
(see the end of this section for station 33).

| Station | Name | Status | Data 2013–2025 | In the dataset |
|---|---|---|---|---|
| 3 | Saint-Jean-Baptiste | ouvert | 2013–2025 | ✓ |
| 6 | Anjou | ouvert | 2020–2025 | ✓ |
| 17 | Caserne 17 | ouvert | 2014–2025 | ✓ |
| 31 | Saint-Dominique | ouvert | 2016–2025 | ✓ |
| 33 | Autoroute 13 | ouvert | **none yet** | — (no data) |
| 55 | Rivière-des-Prairies | ouvert | 2013–2025 | ✓ |
| 80 | Saint-Joseph | ouvert | 2013–2025 | ✓ |
| 99 | Sainte-Anne-de-Bellevue | ouvert | 2013–2025 | ✓ |
| 103 | York/Roberval | ouvert | 2016–2025 | ✓ |
| 28 | Échangeur Décarie | fermé-historical | 2013–2025 | ✗ |
| 50 | Hochelaga-Maisonneuve | fermé-historical | 2013–2025 (PM2.5 only) | ✗ |
| 66 | Aéroport de Montréal | fermé | 2013–2025 | ✗ |
| 7 | Chénier | fermé | 2013–2018 | ✗ |
| 13 | Drummond | fermé | 2013–2015 (PM2.5 only) | ✗ |
| 29 | Parc Pilon | fermé | 2013 (95 days) | ✗ |
| 61 | Maisonneuve | fermé | 2013–2015 | ✗ |

**Why**

1. **Consistency with the project output.** Predictions and the heatmap are displayed in CityLayers on the
   **current** network. A model built on stations that no longer exist would describe places where nothing
   is measured today.
2. **Comparable series.** Closed stations change the composition of the network over time, so a trend
   could reflect *which* stations were measuring rather than a real change in air quality.
3. **Complete pollutant set.** All eight open stations with data measure NO2, PM2.5 and O3. Several closed
   stations measured only one or two pollutants.
4. **Temporary stations are excluded** (`temp`: Station Nomade, Longue-Pointe). They are moved between
   sites, so their series do not describe a fixed location.

**Trade-off.** The filter removes 18,217 of 50,784 station-days (36%), including three stations that
measured until the end of 2025 (28, 50 and 66; the list was revised in May 2026, after the study period).
The decision favours a dataset that represents the current network. The filter is a single parameter in
the script (`STATION_STATUS_KEEP`), so the dataset can be regenerated with every station if needed, and
`rsqa_station_report.csv` lists each station with the reason it was included or excluded.

### Why the dataset has 8 stations and the map has 9

Station **33 (Autoroute 13)** is open and appears on the project map, but it is **not in the dataset**
because it has no measurements in the study period:

* The 13 hourly files (2013–2025) contain **0 rows** for station number 33, and the 2021 file, the only one
  with a station-name column, has no row named "Autoroute 13".
* Without hourly measurements there are no daily values or day types to compute for it.

It is most likely a recent station: it is 2.1 km from station 66 (Aéroport de Montréal), which measured
until 31 December 2025 and is now listed as closed. The station list does not state that one replaced the
other, so **station 66 is not used as a substitute**: it is a different site, and merging the two would
create an artificial series for the Autoroute 13 sector.

Station 33 can be added by re-running `01_build_daily_dataset.py` once its data are published. Meanwhile,
the Autoroute 13 sector has no observations in the dataset, and the heatmap should show it as "no data"
rather than interpolate it as if it were measured.

---

## 5. Why only three pollutants (NO2, PM2.5, O3)

| Criterion | NO2 | PM2.5 | O3 |
|---|---|---|---|
| Measured continuously 2013–2025 | ✓ | ✓ | ✓ |
| Measured at every open station | ✓ | ✓ | ✓ |
| WHO 2021 short-term guideline | ✓ | ✓ | ✓ |
| Part of the Québec air-quality index (IQA) | ✓ | ✓ | ✓ |

They are the urban pollutants most closely linked to health effects (traffic, combustion, photochemical
smog) and the only ones with near-complete coverage over the whole period.

**Excluded**

* **PM10.** Even after recovering the values written with a decimal comma in 2014 and the lower-case
  column `pm10` in 2021, about **90% of the hourly series is missing**. The column does not exist in
  2015–2017 and 2022–2023, and it is 100% `N/M` in 2024–2025. Data only exist for 2013–2014 and 2018–2021,
  at one to four stations at a time, most of which are now closed.

  | Year | Valid hours | Stations | Days with ≥ 18 h |
  |---|---|---|---|
  | 2013 | 10,256 | 29, 50 | 426 |
  | 2014 | 17,276 | 17, 50 | 718 |
  | 2015–2017 | 0 (no column) | — | 0 |
  | 2018 | 34,116 | 17, 28, 50, 103 | 1,421 |
  | 2019 | 33,706 | 17, 28, 50, 103 | 1,392 |
  | 2020 | 25,510 | 28, 50, 103 | 1,053 |
  | 2021 | 8,202 | 50 | 336 |
  | 2022–2023 | 0 (no column) | — | 0 |
  | 2024–2025 | 0 (100% `N/M`) | — | 0 |

* **CO, SO2, H2S, BTEX, PST.** Fewer stations and shorter series.
* **Black carbon (BC) and ultrafine particles (PUF).** Only available from 2017 and 2021.
* **The RSQA air-quality index dataset (IQA).** It is computed from these same measurements, so using it
  as an input or as the target would cause **data leakage**. It may be used later only as an external
  reference.

---

## 6. From hourly to daily values (`01_build_daily_dataset.py`)

### 6.1 Units

NO2 and O3 are converted from ppb to µg/m³ so that all three pollutants share the unit of the WHO
guidelines. Conversion at 25 °C and 1 atm (molar volume 24.45 L/mol):

| Pollutant | Molar mass | µg/m³ per ppb |
|---|---|---|
| NO2 | 46.01 g/mol | 1.882 |
| O3 | 48.00 g/mol | 1.963 |

> **Why this matters.** The first version of the pipeline compared NO2 and O3 in ppb with thresholds in
> µg/m³. Their ratios were about half their real value, which classified 92% of the days as "Bon" and made
> PM2.5 look like the dominant pollutant. With correct units, O3 and NO2 decide most days.

### 6.2 Hourly validity

* Negative concentrations are invalid (none were found in NO2, PM2.5 or O3).
* **O3 above 150 ppb in one hour is invalid.** Across 2013–2025 the highest hourly O3 is 88 ppb, except
  for 30 hours at station 99 in 2014 (9–10 February and 29–30 July) with values between 220 and 263 ppb,
  some of them at night, when O3 cannot be produced. They match unflagged calibration or instrument
  faults and are removed.

### 6.3 Completeness: 18 valid hours per pollutant

A pollutant's daily value is kept only if that pollutant has **at least 18 valid hours (75% of the day)**.
The rule is applied to each pollutant separately, so a day can have a valid NO2 value and no O3 value. It
is the same 75% criterion the RSQA uses to validate one hour from minute data. In practice about 95–97%
of the kept values use all 24 hours.

A station-day is kept when at least one of the three pollutants is valid.

### 6.4 Daily statistic: the one each guideline is defined on

| Pollutant | Daily metric used to classify | Why |
|---|---|---|
| NO2 | `NO2_MEAN` — 24-hour mean | WHO guideline is a 24-hour mean |
| PM2.5 | `PM25_MEAN` — 24-hour mean | WHO guideline is a 24-hour mean |
| O3 | `O3_MDA8` — daily maximum of the 8-hour running mean | WHO guideline is a maximum 8-hour mean |

`O3_MDA8` follows the usual convention (EU Air Quality Directive 2008/50/EC): each 8-hour window is
assigned to the day it ends, a window needs at least 6 valid hours, and the day needs at least 18 valid
windows plus the 18-hour rule above.

**Why not the median.** The first version used the daily median because it resists short peaks. The
guidelines are defined on the mean, though, and the median of right-skewed pollution data is lower than
the mean. The review notebook (section 2.7) shows that classifying with medians would label **1,971 of the
6,347 days that exceed a guideline (about 31%) as "Bon"**. The medians are kept as extra, robust features
(`NO2_MEDIAN`, `PM25_MEDIAN`, `O3_MEDIAN`, plus `O3_MEAN`).

---

## 7. Day-type classification

### 7.1 Reference values: WHO 2021

| Pollutant | WHO 2021 guideline | Averaging time |
|---|---|---|
| NO2 | 25 µg/m³ | 24 hours |
| PM2.5 | 15 µg/m³ | 24 hours |
| O3 | 100 µg/m³ | Daily maximum 8-hour mean |

**Why WHO 2021 and not the Québec IQA reference values.** The Québec IQA references (O3 160 µg/m³ in one
hour, NO2 400 µg/m³ in one hour, PM2.5 35 µg/m³ over 3 moving hours) are designed for **real-time hourly
alerts**. They do not match a daily value, and almost no day would exceed them. The WHO guidelines are
defined on daily time steps and are based on health evidence, which fits a model that classifies days.

### 7.2 Index and classes

* `WHO_INDEX` = 100 × the highest of the three ratios *daily value / guideline* (100 = exactly at the
  guideline). It is not the official Québec IQA, which uses a different scale.
* `DOMINANT` = pollutant with the highest ratio.
* `TIPO_DIA`:

| Class | Rule | Meaning |
|---|---|---|
| Bon | `WHO_INDEX` ≤ 100 | Every available pollutant at or below its guideline |
| Acceptable | 100 < `WHO_INDEX` ≤ 200 | At least one pollutant above, up to twice its guideline |
| Mauvais | `WHO_INDEX` > 200 | At least one pollutant more than twice its guideline |

* `EXCEEDS_WHO` = `TIPO_DIA != "Bon"`, a binary target for the model.
* `N_POLLUTANTS` = how many pollutants were available to classify the day (1–3).

The three classes are a project definition, not an official scale.

---

## 8. Review and cleaning (`02_data_review_cleaning.ipynb`)

The guiding rule is **flag first, delete only with a physical justification**. Every action is written to
`rsqa_daily_quality_log.csv`.

### 8.1 Verification of the build (all passed)

* 22 expected columns, 32,567 rows, 8 stations, 2013-01-01 to 2025-12-31.
* No invalid dates, no duplicated station-day, and every row has the station name and coordinates.
* The 18-hour rule (and the 18-window rule for O3) holds in every row; no day has more than 24 hours.
* `WHO_INDEX`, `DOMINANT`, `TIPO_DIA`, `EXCEEDS_WHO` and `N_POLLUTANTS` recomputed from the pollutant
  columns match the file in every row.
* No negative values.
* Monthly profiles follow known behaviour (O3 highest in April–July, NO2 highest in December–February),
  which confirms that dates and units are consistent.

### 8.2 Cleaning actions

| Issue | Station-days | Action | Reason |
|---|---|---|---|
| NO2 exactly 0 for all 24 hours (stations 55 and 99) | 6 | NO2 set to `NaN`; day type recomputed (no change) | Urban NO2 never stays at exactly zero for a whole day; the sensor was stuck at its lower limit. PM2.5 and O3 at the same station were normal. |
| Isolated PM2.5 spike (stations 31, 80, 103) | 7 | Kept, `FLAG_PM25_LOCAL_SPIKE = True` | PM2.5 has local sources (traffic, wood burning, fires, fireworks), so a peak at one station is possible, but it cannot be confirmed from daily data. |

**Isolated spikes** were detected with a spatial-consistency rule: a daily value above the pollutant's
99th percentile **and** more than 3 times the network median for the same day (at least 3 reporting
stations). No NO2 or O3 value meets it. The IQR rule was **not** used to delete data: pollution data are
right-skewed, so IQR would mark thousands of real high-pollution days as outliers, and those are the days
the model must learn.

**Network-wide extremes are real events and are kept**, for example 25 June 2023 (network median PM2.5
≈ 126 µg/m³), when wildfire smoke covered Montréal.

### 8.3 Final distribution

| Class | Station-days | Share |
|---|---|---|
| Bon | 26,220 | 80.5% |
| Acceptable | 5,936 | 18.2% |
| Mauvais | 411 | 1.3% |

| Dominant pollutant | Station-days | of which Mauvais |
|---|---|---|
| O3 | 18,440 | 0 |
| NO2 | 10,730 | 219 |
| PM2.5 | 3,397 | 192 |

* The share of "Bon" days moves from about 76–80% in 2013–2018 to about 80–84% from 2019 onwards.
* "Mauvais" days are most frequent in 2025 and 2023, the years with network-wide PM2.5 episodes.
* O3 decides the most days but never reaches "Mauvais"; NO2 and PM2.5 share the "Mauvais" days almost
  equally.

### 8.4 Coverage notes (no rows removed)

* Four stations cover 2013–2025 (3, 55, 80, 99); station 17 starts in 2014, 31 and 103 in 2016, and
  6 (Anjou) in 2020.
  Comparisons across years should take this into account.
* Missing pollutant values come from sensor downtime and are **not imputed**.

---

## 9. Data dictionary — `rsqa_daily_clean.csv`

All concentrations in µg/m³.

| # | Column | Description |
|---|---|---|
| 1 | `NUMERO_STATION` | RSQA station number |
| 2 | `STATION_NAME` | Station name (official list) |
| 3 | `LATITUDE` | Station latitude (WGS84) |
| 4 | `LONGITUDE` | Station longitude (WGS84) |
| 5 | `ELEVATION_M` | Station elevation (m) |
| 6 | `DATE` | Day (`YYYY-MM-DD`), 01:00 → 24:00 Eastern Standard Time |
| 7 | `YEAR` | Calendar year |
| 8 | `MONTH` | Calendar month |
| 9 | `NO2_MEAN` | NO2 24-hour mean — **classification metric** |
| 10 | `PM25_MEAN` | PM2.5 24-hour mean — **classification metric** |
| 11 | `O3_MDA8` | O3 daily maximum 8-hour mean — **classification metric** |
| 12 | `NO2_MEDIAN` | NO2 daily median |
| 13 | `PM25_MEDIAN` | PM2.5 daily median |
| 14 | `O3_MEAN` | O3 24-hour mean |
| 15 | `O3_MEDIAN` | O3 daily median |
| 16 | `NO2_N_HOURS` | Valid NO2 hours that day (0–24) |
| 17 | `PM25_N_HOURS` | Valid PM2.5 hours that day (0–24) |
| 18 | `O3_N_HOURS` | Valid O3 hours that day (0–24) |
| 19 | `O3_N_8H_WINDOWS` | Valid 8-hour O3 windows ending that day (0–24) |
| 20 | `N_POLLUTANTS` | Pollutants available to classify the day (1–3) |
| 21 | `WHO_INDEX` | 100 × highest *value / WHO guideline* ratio (100 = at the guideline) |
| 22 | `DOMINANT` | Pollutant that sets the index (`NO2`, `PM2.5`, `O3`) |
| 23 | `TIPO_DIA` | `Bon`, `Acceptable` or `Mauvais` |
| 24 | `EXCEEDS_WHO` | `True` if at least one pollutant exceeds its guideline |
| 25 | `FLAG_PM25_LOCAL_SPIKE` | `True` for an isolated PM2.5 peak kept for review |

An empty value in columns 9–15 is not an error: the sensor had fewer than 18 valid hours that day.

---

## 10. Notes for the modelling stage

* **Target:** `TIPO_DIA` (3 classes) or `EXCEEDS_WHO` (binary).
* **Leakage:** `WHO_INDEX`, `DOMINANT`, `TIPO_DIA` and `EXCEEDS_WHO` are computed from the pollutant
  columns. If the model predicts the day type from atmospheric variables, the pollutant columns of the
  **same day** must not be inputs.
* **Subset:** all rows for models that accept missing values; `N_POLLUTANTS == 3` when the full vector is
  needed. Excluding `FLAG_PM25_LOCAL_SPIKE` rows is a useful sensitivity test.
* **Imbalance:** "Mauvais" is 1.3% of the data. Use F1-macro or PR-AUC rather than accuracy, and class
  weights or threshold tuning.
* **Validation:** split by time (earlier years to train, later years to test), not at random, because
  consecutive days are strongly correlated.
* **Joining weather data:** by `DATE` and by `LATITUDE` / `LONGITUDE`. The RSQA day is in Eastern
  Standard Time all year; check the day definition of each weather source before joining.

---

## References

* Ville de Montréal. *RSQA – Multi-Polluants (en continu)* [dataset]. Données Québec, CC-BY 4.0.
  https://www.donneesquebec.ca/recherche/dataset/vmtl-rsqa-polluants-gazeux
* Ville de Montréal. *RSQA – Liste des stations* [dataset]. Données Québec.
  https://www.donneesquebec.ca/recherche/dataset/vmtl-rsqa-liste-des-stations
* Ville de Montréal. *RSQA – Indice de la qualité de l'air* [dataset]. Données Québec.
  https://www.donneesquebec.ca/recherche/dataset/vmtl-rsqa-indice-qualite-air
* World Health Organization (2021). *WHO global air quality guidelines: particulate matter (PM2.5 and
  PM10), ozone, nitrogen dioxide, sulfur dioxide and carbon monoxide.* Geneva: WHO.
  https://www.ncbi.nlm.nih.gov/books/NBK574591/
* Directive 2008/50/EC of the European Parliament and of the Council on ambient air quality and cleaner
  air for Europe (8-hour running-mean convention for O3).
