<div align="center">

# Montréal Air Quality Analysis
### Daily air quality, weather and pollution-day prediction for Montréal (2013–2025)

<p>
<img src="https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white" /> <img src="https://img.shields.io/badge/pandas-150458?style=for-the-badge&logo=pandas&logoColor=white" /> <img src="https://img.shields.io/badge/Jupyter-F37626?style=for-the-badge&logo=jupyter&logoColor=white" /> <img src="https://img.shields.io/badge/scikit--learn-F7931E?style=for-the-badge&logo=scikitlearn&logoColor=white" />
</p>

**In collaboration with Concordia University (Montréal) · Next-Generation Cities Institute (NGCI)**

</div>

> [!NOTE]
> **Status: in progress 🚧** · Air-quality data ✅ built and cleaned · Atmospheric data ✅ 2013–2020 received · Prediction model ⏳ next · CityLayers heatmap ⏳ planned

---

## 💡 About

How often does Montréal breathe clean air, which pollutant is responsible when it does not, and can the weather tell us in advance?

This project builds a **clean daily air-quality dataset** from the city's monitoring network (RSQA), joins it with **atmospheric variables**, and trains a model that classifies each day as **good, acceptable or bad**. The predictions and a **heatmap** will be displayed in **[CityLayers](https://ngci.encs.concordia.ca/citylayers/login)**, the urban data platform of NGCI at Concordia.

---

## 🔄 Workflow

| # | Stage | Output | Status |
|---|---|---|---|
| 1 | **Build** the daily dataset from 13 yearly hourly files | `rsqa_daily_air_quality.csv` | ✅ Done |
| 2 | **Review and clean** the daily data | `rsqa_daily_clean.csv` + quality log | ✅ Done |
| 3 | **Join** air quality with atmospheric variables | Model-ready dataset | ⏳ Next |
| 4 | **Model**: classify days as Bon / Acceptable / Mauvais | Trained model + evaluation | ⏳ Planned |
| 5 | **Visualize**: predictions and heatmap in CityLayers | Map layers | ⏳ Planned |

---

## 📊 Data

### Air quality: RSQA (Réseau de surveillance de la qualité de l'air)

| Dataset | Content | Source |
|---|---|---|
| **RSQA – Multi-Polluants (en continu)**, 2013–2025 | Hourly NO₂, O₃ and PM2.5, about 1.25 M rows | [donnees.montreal.ca](https://donnees.montreal.ca/fr/dataset/rsqa-polluants-gazeux) |
| **RSQA – Liste des stations** | Location, status and monitoring region of each station | [donnees.montreal.ca](https://donnees.montreal.ca/fr/dataset/rsqa-liste-des-stations) |

*Licence: CC-BY 4.0, Ville de Montréal.*

### Atmospheric variables (2013–2020)

| Variables | Source |
|---|---|
| Maximum and minimum temperature | **CHIRTS** (Climate Hazards Center, UC Santa Barbara) |
| Precipitation | **CHIRPS** (Climate Hazards Center, UC Santa Barbara) |
| Solar radiation, UV, relative humidity, surface pressure, wind | **NASA POWER** (NASA Langley Research Center) |

### Deliberately excluded

- **RSQA – Indice de la qualité de l'air (historique):** it is computed from the same measurements, so using it as an input or target would cause **data leakage**. It may be used later only as an external check.
- **PM10, CO, SO₂, H₂S, BTEX, black carbon and ultrafine particles:** too many gaps or too short a series across the open stations (PM10 is about 90% missing).

---

## 📍 Monitoring network

The analysis uses **8 of the 9 open stations** on the official list. Closed and historical stations were removed, and temporary stations were excluded because they move between sites.

| ID | Station | Coverage |
|---|---|---|
| 3 | Saint-Jean-Baptiste | 2013–2025 |
| 6 | Anjou | 2020–2025 |
| 17 | Caserne 17 | 2014–2025 |
| 31 | Saint-Dominique | 2016–2025 |
| 55 | Rivière-des-Prairies | 2013–2025 |
| 80 | Saint-Joseph | 2013–2025 |
| 99 | Sainte-Anne-de-Bellevue | 2013–2025 |
| 103 | York/Roberval | 2016–2025 |

> **Station 33 (Autoroute 13)** is open on the official list but has **no data** in any of the 13 files. It is not replaced by a nearby station; the map shows its sector as *no data* instead of interpolating values.

![Air quality monitoring stations in Montréal](img/initial_map_mtl.jpg)

*Monitoring stations across the Montréal agglomeration by status: closed (fermé), historically closed (fermé-historique), open (ouvert) and temperature-only (temp).*

![Air pollution monitoring regions in Montréal](img/mapa_regiones_monitoreo_mtl.jpg)

*Air pollution monitoring regions of the agglomeration (2026), with the representative station of each region.*

---

## 🧹 Data preparation

Full details, decisions and column dictionary: **[`data_preparation.md`](RSQA%20-%20Multi-Polluants%20(en%20continu)/data_preparation.md)**.

**From hourly to daily**
- NO₂ and O₃ converted from ppb to µg/m³ (25 °C, 1 atm).
- A pollutant's daily value requires **at least 18 valid hours**.
- **NO₂ and PM2.5:** 24-hour mean. **O₃:** daily maximum 8-hour mean (`O3_MDA8`), as defined by the WHO.
- Non-measurement codes, decimal commas, mixed date formats, duplicate hours and empty filler rows were standardized or removed.

**Cleaning**
- 6 station-days with NO₂ stuck at exactly 0 for 24 hours were set to missing.
- 7 isolated local PM2.5 spikes were **kept and flagged**, not deleted.
- Real network-wide episodes, such as the **June 2023 wildfire smoke**, were kept. The IQR rule was not used to delete values because it would remove real high-pollution days.
- Missing values come from sensor downtime and are **not imputed**.

**Result:** 32,567 station-days, 8 stations, no duplicates and 25 columns.

---

## 🏷️ Day classification

Each station-day is classified against the **WHO 2021 Air Quality Guidelines**:

| Pollutant | Daily metric | WHO 2021 guideline |
|---|---|---|
| NO₂ | 24-hour mean | 25 µg/m³ |
| PM2.5 | 24-hour mean | 15 µg/m³ |
| O₃ | Daily maximum 8-hour mean | 100 µg/m³ |

`WHO_INDEX` = 100 × the highest ratio between a pollutant's daily value and its guideline. It is a project index, not the official Québec IQA.

| Class | Rule | Station-days | Share |
|---|---|---|---|
| **Bon** | index ≤ 100 | 26,220 | 80.5% |
| **Acceptable** | 100 < index ≤ 200 | 5,936 | 18.2% |
| **Mauvais** | index > 200 | 411 | 1.3% |

**What the data shows**
- **O₃** is the dominant pollutant on most days but never drives a *Mauvais* day; *Mauvais* days come from **NO₂** (219) and **PM2.5** (192).
- The share of *Bon* days rose from about 76–80% (2013–2018) to about 80–84% (from 2019).
- *Mauvais* days peak in **2023 and 2025**, years with network-wide PM2.5 episodes.

**Regulatory context:** Québec's **IQA** (MELCCFP) uses per-pollutant sub-indices with categories *Bon*, *Acceptable* and *Mauvais*, and Canada's **AQHI** combines the three pollutants (Québec uses Info-Smog instead). The project follows the stricter WHO 2021 guidelines and keeps the IQA category names.

---

## 🌦️ Atmospheric data

Daily files for each station (`at_data_<station>.csv`, 2,922 days from 2013 to 2020) with:

`TMAX`, `TMIN`, `PREC`, solar radiation (`ALLSKY_SFC_SW_DWN`), UV (`ALLSKY_SFC_UVA`, `ALLSKY_SFC_UVB`, `ALLSKY_SFC_UV_INDEX`), relative humidity (`RH2M`), surface pressure (`PS`), wind speed range (`WS2M_RANGE`, `WS10M_RANGE`) and wind direction (`WD2M`, `WD10M`).

**Known limitations**
- **Coarse resolution:** all stations fall in one NASA POWER grid cell, so those variables are identical for every station. Only temperature and precipitation differ.
- **Not measured on site:** CHIRPS/CHIRTS are gridded estimates, not station measurements.
- **Wind is a range** (daily max − min), not mean wind speed.
- **Shorter period:** atmospheric data ends in 2020, while air quality runs to 2025.

**In progress:** two additional sources are being requested through NGCI: a database generated from a calibrated model, and **Hydro-Québec** measured data (2021–2025). Both will be assessed before being integrated.

---

## 🧠 Modelling plan

- **Target:** `TIPO_DIA` (Bon / Acceptable / Mauvais) or `EXCEEDS_WHO`.
- **Inputs:** atmospheric variables, calendar features and previous days' pollution. **Same-day pollutant values are not used as inputs**, since the target is computed from them.
- **Validation:** time-based split (train on earlier years, test on later ones), not a random split.
- **Metrics:** F1-macro and PR-AUC instead of accuracy, because *Mauvais* days are only 1.3% of the data.

---

## 📁 Repository structure

```text
montreal-air-quality-analysis/
├── RSQA - Multi-Polluants (en continu)/
│   ├── dataset 2013 - 2025/              # 13 yearly hourly files (raw)
│   ├── 01_build_daily_dataset.py         # Step 1: hourly → daily
│   ├── 02_data_review_cleaning.ipynb     # Step 2: review and cleaning
│   ├── data_preparation.md               # Decisions and column dictionary
│   ├── rsqa_daily_air_quality.csv        # Daily dataset (before cleaning)
│   ├── rsqa_daily_clean.csv              # Clean daily dataset ← use this one
│   ├── rsqa_daily_quality_log.csv        # Cleaning log
│   └── rsqa_station_report.csv           # Coverage per station
├── RSQA - liste des stations/            # Station list and agglomeration limits (GeoJSON)
├── Atmospheric data (CHIRPS-CHIRTS, NASA POWER)/
│   ├── dataset 2013 - 2020/              # One file per station
│   └── README.md                         # Variables and limitations
├── docs/                                 # Reference papers and reports
├── img/                                  # Maps used in this README
└── maps/                                 # Maps in PDF
```

---

## ▶️ Reproduce

```bash
cd "RSQA - Multi-Polluants (en continu)"
python 01_build_daily_dataset.py
```

Then open `02_data_review_cleaning.ipynb` and run all cells. Requires Python 3 with pandas, NumPy and Jupyter.

---

## 📚 References

The methodological framework draws on the documents in [`docs/`](docs/), including:

- **WHO (2021).** *WHO global air quality guidelines.* Basis for the day classification.
- **Direction régionale de santé publique de Montréal (2023).** Air quality in Montréal report.
- **Rowland et al. (2024).** Atmospheric variables and their relationship with air pollutants: temperature, wind, rainfall, temporal patterns and thermal inversions.
- Spanish-language studies and monitoring protocols on atmospheric variables and pollutant behaviour.

---

## 🗺️ Roadmap

- [x] Station selection and monitoring network maps
- [x] Daily air-quality dataset 2013–2025
- [x] Data review, cleaning and day classification
- [x] Atmospheric data 2013–2020
- [ ] Atmospheric data 2021–2025 (NGCI / Hydro-Québec)
- [ ] Join air quality and atmospheric data
- [ ] Prediction model and evaluation
- [ ] Heatmap and predictions in CityLayers
- [ ] Comparison with Cali, Colombia

---

## 🤝 Acknowledgements

Developed in collaboration with **Concordia University** and the **Next-Generation Cities Institute (NGCI)**, Montréal.

**Data:** Ville de Montréal, RSQA (CC-BY 4.0) · Climate Hazards Center, UC Santa Barbara (CHIRPS/CHIRTS) · NASA Langley Research Center (POWER).

<div align="center">

Made by **[Maria Jose Ospina](https://github.com/naksu707)** and **[Edwin Alejandro Chávez](https://www.linkedin.com/in/edwin-alejandro-ch%C3%A1vez-esquivel-2b9718323/)**

</div>
