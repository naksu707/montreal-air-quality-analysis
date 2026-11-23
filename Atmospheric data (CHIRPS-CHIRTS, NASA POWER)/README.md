# Atmospheric data per monitoring site (2013–2020)

Daily atmospheric variables for each of the 9 open RSQA stations shown on the project map. One file per
station, one row per day.

**Sources**

* **CHIRTS** (temperature) and **CHIRPS** (precipitation), North America.
* **NASA POWER**, native-resolution daily data (CERES SYN1deg and MERRA-2).

**Period:** 01/01/2013 to 31/12/2020 (2,922 days). CHIRPS/CHIRTS data for 2021–2025 are being updated
by the providers and have not been published yet, so this period is shorter than the air-quality data
(2013–2025).

## Files and stations

The file names use the station name. To join them with the air-quality data, use `NUMERO_STATION`:

| File | NUMERO_STATION | Station |
|---|---|---|
| `at_data_saint_jean.csv` | 3 | Saint-Jean-Baptiste |
| `at_data_anjou.csv` | 6 | Anjou |
| `at_data_caserne.csv` | 17 | Caserne 17 |
| `at_data_saint_dominique.csv` | 31 | Saint-Dominique |
| `at_data_autoroute13.csv` | 33 | Autoroute 13 (no air-quality data in 2013–2025) |
| `at_data_riviere.csv` | 55 | Rivière-des-Prairies |
| `at_data_saint_joseph.csv` | 80 | Saint-Joseph |
| `at_data_sainte_anne.csv` | 99 | Sainte-Anne-de-Bellevue |
| `at_data_sainte_york.csv` | 103 | York/Roberval |

## Variables

| Column | Description | Unit | Source |
|---|---|---|---|
| `date` | Day, format `dd/mm/yy` | — | — |
| `TMAX` | Maximum temperature | °C | CHIRTS |
| `TMIN` | Minimum temperature | °C | CHIRTS |
| `PREC` | Daily precipitation | mm | CHIRPS |
| `ALLSKY_SFC_SW_DWN` | All-sky surface shortwave downward irradiance | MJ/m²/day | NASA POWER (CERES SYN1deg) |
| `ALLSKY_SFC_UVA` | All-sky surface UVA irradiance | MJ/m²/day | NASA POWER (CERES SYN1deg) |
| `ALLSKY_SFC_UVB` | All-sky surface UVB irradiance | MJ/m²/day | NASA POWER (CERES SYN1deg) |
| `ALLSKY_SFC_UV_INDEX` | All-sky surface UV index | W m⁻² × 40 | NASA POWER (CERES SYN1deg) |
| `RH2M` | Relative humidity at 2 m | % | NASA POWER (MERRA-2) |
| `PS` | Surface pressure | kPa | NASA POWER (MERRA-2) |
| `WS2M_RANGE` | Wind speed range at 2 m (daily max − min) | m/s | NASA POWER (MERRA-2) |
| `WD2M` | Wind direction at 2 m | degrees | NASA POWER (MERRA-2) |
| `WS10M_RANGE` | Wind speed range at 10 m (daily max − min) | m/s | NASA POWER (MERRA-2) |
| `WD10M` | Wind direction at 10 m | degrees | NASA POWER (MERRA-2) |

## Notes for using the data

* **Spatial resolution.** CHIRTS/CHIRPS have a fine grid, so `TMAX`, `TMIN` and `PREC` differ between
  stations. The NASA POWER grid is coarse, and all nine stations fall in the same cell: the NASA POWER
  columns are **identical in every file**. Differences between stations therefore come only from
  temperature and precipitation.
* **Wind.** `WS2M_RANGE` and `WS10M_RANGE` are the daily range of wind speed (maximum − minimum), not
  the mean wind speed.
* **Overlap with the air-quality data.** The two datasets overlap from 2013 to 2020. For stations that
  start later in the air-quality data, the overlap is shorter: Saint-Dominique (31) and York/Roberval
  (103) from 2016, and Anjou (6) only 2020.
* **Quality checks done on receipt:** every file has 2,922 rows, valid dates, no duplicated days and no
  missing values.
