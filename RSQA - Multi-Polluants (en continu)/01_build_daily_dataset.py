#!/usr/bin/env python3
"""
Construye el dataset diario de calidad del aire del RSQA (Montréal, 2013-2025)
a partir de los 13 archivos horarios "rsqa-multi-polluants<AÑO>.csv".

Entradas:
    rsqa-multi-polluants<AÑO>.csv  -> mediciones horarias (13 archivos)
    lista-estaciones.csv           -> lista oficial de estaciones del RSQA (estado y coordenadas)

Salida (una fila por estación y día):
    rsqa_daily_air_quality.csv   -> dataset diario
    rsqa_build_report.csv        -> diagnóstico por archivo (filas, fechas, tokens, etc.)
    rsqa_station_report.csv      -> estaciones incluidas y excluidas, con el motivo

Decisiones principales (ver docs/data_preparation.md):
  * Estaciones: solo las de estado "ouvert" en la lista oficial (red permanente actual).
    Se excluyen las cerradas y las temporales ("temp"), que cambian de ubicación.
  * Unidades: NO2 y O3 vienen en ppb en los archivos del RSQA; se convierten a µg/m³
    (25 °C, 1 atm) para compararlos con las guías OMS 2021. PM2.5 ya viene en µg/m³.
  * Hora: desde 2013 el RSQA marca el FINAL de la hora. El día va de 01:00 a 24:00.
    Los archivos escriben esa última hora como "24:00" (2013, 2022-2025) o como
    "00:00" con la fecha del mismo día (2014-2021). Ambas se convierten al instante real
    (día siguiente 00:00) y el día se asigna con (timestamp - 1 h).
  * Completitud: >= 18 horas válidas (75 %) POR CONTAMINANTE.
  * Estadístico diario según la definición de la guía OMS:
        NO2 y PM2.5 -> media de 24 h
        O3          -> máximo diario de la media móvil de 8 h (MDA8)
    Se guardan también la mediana y la media de 24 h de O3 como variables adicionales.
  * Clasificación: WHO_INDEX = 100 x max(valor / guía OMS); Bon <= 100 < Acceptable <= 200 < Mauvais.

Uso:
    python3 01_build_daily_dataset.py
    python3 01_build_daily_dataset.py --input-dir "ruta/a/los/csv" --stations-file "ruta/lista-estaciones.csv"
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Parámetros
# ---------------------------------------------------------------------------

# Guías OMS 2021 de corto plazo (µg/m³)
WHO_GUIDELINES = {
    "NO2": 25.0,    # media de 24 h
    "PM2.5": 15.0,  # media de 24 h
    "O3": 100.0,    # máximo diario de la media móvil de 8 h
}

# Conversión ppb -> µg/m³ a 25 °C y 1 atm: µg/m³ = ppb x masa molar / 24.45
MOLAR_VOLUME_L = 24.45
PPB_TO_UGM3 = {
    "NO2": 46.0055 / MOLAR_VOLUME_L,  # ~1.882
    "O3": 47.9982 / MOLAR_VOLUME_L,   # ~1.963
}

MIN_VALID_HOURS = 18        # 75 % de las 24 horas del día
MIN_HOURS_PER_8H_WINDOW = 6  # 75 % de una ventana de 8 h
MIN_VALID_8H_WINDOWS = 18    # 75 % de las 24 ventanas de 8 h del día

# Límite físico horario (en la unidad ORIGINAL, ppb). Valores por encima se consideran
# lecturas de calibración/falla no marcadas. Fundamento: en 2013-2025 el máximo horario
# de O3 fuera de la estación 99 en 2014 es 88 ppb; en esa estación hay 30 horas entre
# 220 y 263 ppb, incluso de madrugada, cuando el O3 no puede formarse.
MAX_PLAUSIBLE_HOURLY_PPB = {"O3": 150.0}

# Alias de columnas (tras normalizar: mayúsculas, sin espacios, sin comillas, "." -> ",")
COLUMN_ALIASES = {
    "STATION": {"NUMERO_STATION", "NO_POSTE", "NOPOSTE", "STATION", "POSTE"},
    "DATE_HEURE": {"DATE_HEURE", "DATEHEURE", "DATETIME"},
    "DATE": {"DATE", "JOUR"},
    "HEURE": {"HEURE", "HOUR", "TIME"},
    "NO2": {"NO2"},
    "PM2.5": {"PM2,5", "PM25"},
    "O3": {"O3"},
}

POLLUTANTS = ["NO2", "PM2.5", "O3"]
OUTPUT_NAME = "rsqa_daily_air_quality.csv"
REPORT_NAME = "rsqa_build_report.csv"
STATION_REPORT_NAME = "rsqa_station_report.csv"

# Estaciones: estados de la lista oficial que se conservan.
# "ouvert" = red permanente actual. Se excluyen "fermé", "fermé-historical" y "temp".
# Para incluir todas las estaciones con datos, use STATION_STATUS_KEEP = None.
STATION_STATUS_KEEP: set[str] | None = {"ouvert"}
STATION_FILE_PATTERNS = ["lista-estaciones*.csv", "liste-des-stations*.csv"]


# ---------------------------------------------------------------------------
# Lectura y normalización
# ---------------------------------------------------------------------------

def norm_col(col: str) -> str:
    """Normaliza un nombre de columna: sin BOM, sin comillas, sin espacios, mayúsculas, '.' -> ','."""
    s = str(col).replace("﻿", "").replace('"', "").strip().upper()
    s = re.sub(r"\s+", "", s)  # "DATE_ HEURE" -> "DATE_HEURE"
    return s.replace(".", ",")  # "PM2.5" -> "PM2,5"


def map_columns(columns: list[str]) -> dict[str, str]:
    """Devuelve {nombre canónico: nombre original} para las columnas reconocidas."""
    col_map: dict[str, str] = {}
    for orig in columns:
        n = norm_col(orig)
        for canonical, aliases in COLUMN_ALIASES.items():
            if n in aliases and canonical not in col_map:
                col_map[canonical] = orig
    return col_map


def to_num(series: pd.Series) -> tuple[pd.Series, dict[str, int]]:
    """
    Convierte texto a float. Cualquier código no numérico (N/M, InVld, Down, NoData,
    <Samp, Calib, Zero, Span, Purge, RS232, FailPwr, Warm Up, celdas vacías...) pasa a NaN.
    La coma decimal solo se reemplaza en valores con forma numérica "123,45".
    Devuelve también el conteo de códigos no numéricos para el reporte.
    """
    txt = series.astype("string").str.strip()
    txt = txt.where(~txt.str.fullmatch(r"-?\d+,\d+", na=False), txt.str.replace(",", ".", regex=False))
    num = pd.to_numeric(txt, errors="coerce")
    tokens = txt[num.isna() & txt.notna() & (txt != "")].value_counts().to_dict()
    return num.astype("float64"), {str(k): int(v) for k, v in tokens.items()}


def build_datetime_text(df: pd.DataFrame, col_map: dict[str, str]) -> pd.Series:
    """Une fecha y hora en un solo texto 'fecha HH:MM' según el esquema del archivo."""
    if "DATE_HEURE" in col_map:
        raw = df[col_map["DATE_HEURE"]].astype("string").str.strip()
    elif "DATE" in col_map and "HEURE" in col_map:
        hour = df[col_map["HEURE"]].astype("string").str.strip()
        hour = hour.where(~hour.str.fullmatch(r"\d{1,2}", na=False), hour + ":00")  # "5" -> "5:00"
        raw = df[col_map["DATE"]].astype("string").str.strip() + " " + hour
    else:
        raise KeyError("No se encontró columna de fecha/hora")
    # Normaliza la hora a dos dígitos: "1:00" -> "01:00"
    return raw.str.replace(r"\s(\d):(\d{2})$", r" 0\1:\2", regex=True)


def parse_end_of_hour(raw: pd.Series, station: pd.Series) -> tuple[pd.Series, str, dict[str, int]]:
    """
    Convierte el texto de fecha/hora al instante real de FIN de la hora medida.

    Formatos observados:
      * DD-MM-YYYY HH:MM (2013, 2022-2025) con "24:00" para la última hora del día.
      * YYYY-MM-DD HH:MM (2014-2021) con "00:00" y la MISMA fecha para la última hora del día
        (la fila 00:00 aparece después de la fila 23:00 de ese día).
    En ambos casos esa última hora corresponde al día siguiente a las 00:00.

    La convención "00:00 del mismo día" se detecta automáticamente mirando la fila anterior
    de la misma estación en el orden del archivo, en lugar de suponerla por año.
    """
    info: dict[str, int] = {}
    is_24 = raw.str.contains(r"\s24:00", na=False)
    txt = raw.str.replace(r"\s24:00", " 00:00", regex=True)

    is_iso = txt.str.match(r"^\d{4}-\d{2}-\d{2}", na=False)
    ts = pd.Series(pd.NaT, index=raw.index, dtype="datetime64[ns]")
    ts[is_iso] = pd.to_datetime(txt[is_iso], format="%Y-%m-%d %H:%M", errors="coerce")
    ts[~is_iso] = pd.to_datetime(txt[~is_iso], format="%d-%m-%Y %H:%M", errors="coerce")
    info["invalid_datetime"] = int((ts.isna() & raw.notna() & (raw != "")).sum())

    # Convención "24:00" -> día siguiente
    ts[is_24] = ts[is_24] + pd.Timedelta(days=1)
    info["rows_24h"] = int(is_24.sum())

    # Convención "00:00 del mismo día": la fila anterior (misma estación) es 23:00 del MISMO día
    midnight = (ts.dt.hour == 0) & (ts.dt.minute == 0) & ~is_24
    prev_ts = ts.groupby(station).shift(1)
    same_day_close = midnight & (prev_ts.dt.normalize() == ts.dt.normalize()) & (prev_ts.dt.hour == 23)
    next_day_open = midnight & ((ts - prev_ts) == pd.Timedelta(hours=1))
    info["midnight_same_date"] = int(same_day_close.sum())
    info["midnight_next_date"] = int(next_day_open.sum())

    if is_24.any():
        convention = "24:00"
    elif same_day_close.sum() > next_day_open.sum():
        convention = "00:00 same date"
        ts[midnight] = ts[midnight] + pd.Timedelta(days=1)
    else:
        convention = "00:00 next date"
    return ts, convention, info


def find_input_files(input_dir: Path | None, script_dir: Path) -> list[Path]:
    """Busca los CSV anuales en la carpeta indicada o en las rutas habituales del repo."""
    pattern = "rsqa-multi-polluants*.csv"
    if input_dir is not None:
        return sorted(input_dir.glob(pattern))
    relative = Path("RSQA - Multi-Polluants (en continu)") / "dataset 2013 - 2025"
    for folder in (script_dir / relative, script_dir.parent / relative,
                   Path.cwd() / relative, script_dir, Path.cwd()):
        files = sorted(folder.glob(pattern))
        if files:
            return files
    return []


def load_file(path: Path) -> tuple[pd.DataFrame | None, dict]:
    """Lee un archivo anual y devuelve datos horarios normalizados + su reporte."""
    raw = pd.read_csv(path, sep=",", decimal=".", dtype=str, encoding="utf-8-sig",
                      keep_default_na=False, na_values=[""])
    report: dict = {"file": path.name, "rows_read": len(raw)}
    col_map = map_columns(list(raw.columns))

    missing = {"STATION", *POLLUTANTS} - col_map.keys()
    has_date = "DATE_HEURE" in col_map or {"DATE", "HEURE"} <= col_map.keys()
    if missing or not has_date:
        print(f"[AVISO] {path.name}: faltan columnas {sorted(missing)} "
              f"(fecha_ok={has_date}). Columnas: {list(raw.columns)}")
        report["status"] = "skipped: missing columns"
        return None, report

    station = pd.to_numeric(raw[col_map["STATION"]], errors="coerce")
    ts, convention, dt_info = parse_end_of_hour(build_datetime_text(raw, col_map), station)
    report.update({"midnight_convention": convention, **dt_info})

    out = pd.DataFrame({"NUMERO_STATION": station, "TIMESTAMP": ts})
    for p in POLLUTANTS:
        values, tokens = to_num(raw[col_map[p]])
        report[f"{p}_valid_hours"] = int(values.notna().sum())
        report[f"{p}_non_numeric_codes"] = sum(tokens.values())
        report[f"{p}_negative"] = int((values < 0).sum())
        values = values.where(values >= 0)  # concentraciones negativas = inválidas

        limit = MAX_PLAUSIBLE_HOURLY_PPB.get(p)
        if limit is not None:
            implausible = values > limit
            report[f"{p}_implausible_hours"] = int(implausible.sum())
            values = values.where(~implausible)

        if p in PPB_TO_UGM3:
            values = values * PPB_TO_UGM3[p]
        out[p] = values

    before = len(out)
    out = out.dropna(subset=["NUMERO_STATION", "TIMESTAMP"])
    report["rows_without_station_or_datetime"] = before - len(out)
    out["NUMERO_STATION"] = out["NUMERO_STATION"].astype(int)
    report["first_timestamp"] = str(out["TIMESTAMP"].min())
    report["last_timestamp"] = str(out["TIMESTAMP"].max())
    report["status"] = "ok"
    return out, report


def find_station_file(stations_file: Path | None, script_dir: Path) -> Path:
    """Busca la lista oficial de estaciones del RSQA."""
    if stations_file is not None:
        return stations_file
    for folder in (script_dir, script_dir.parent, Path.cwd(), script_dir / "datasets", Path.cwd() / "datasets"):
        for pattern in STATION_FILE_PATTERNS:
            files = sorted(folder.glob(pattern))
            if files:
                return files[-1]
    raise FileNotFoundError(
        "No se encontró la lista de estaciones (lista-estaciones.csv / liste-des-stations*.csv). "
        "Indíquela con --stations-file."
    )


def load_stations(path: Path) -> pd.DataFrame:
    """Lee la lista oficial (separador ';') y devuelve número, nombre, estado y coordenadas."""
    st = pd.read_csv(path, sep=None, engine="python", dtype=str, encoding="utf-8-sig")
    st.columns = [c.strip().lower() for c in st.columns]
    out = pd.DataFrame({
        "NUMERO_STATION": pd.to_numeric(st["numero_station"], errors="coerce"),  # "26-1" -> NaN
        "STATION_NAME": st["nom"].str.strip(),
        "STATUT": st["statut"].str.strip(),
        "LATITUDE": pd.to_numeric(st["latitude"], errors="coerce"),
        "LONGITUDE": pd.to_numeric(st["longitude"], errors="coerce"),
        "ELEVATION_M": pd.to_numeric(st.get("élévation", st.get("elevation")), errors="coerce"),
    })
    # Las estaciones temporales tienen identificadores no numéricos o cambian de lugar
    return out.dropna(subset=["NUMERO_STATION"]).astype({"NUMERO_STATION": int})


def select_stations(hourly: pd.DataFrame, stations: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Aplica el filtro de estado y arma el reporte de estaciones incluidas/excluidas."""
    counts = hourly.groupby("NUMERO_STATION").agg(
        hourly_rows=("TIMESTAMP", "size"),
        first_timestamp=("TIMESTAMP", "min"),
        last_timestamp=("TIMESTAMP", "max"),
    )
    report = stations.set_index("NUMERO_STATION").join(counts, how="outer")
    report["STATUT"] = report["STATUT"].fillna("not in station list")
    report["has_data"] = report["hourly_rows"].notna()
    if STATION_STATUS_KEEP is None:
        report["included"] = report["has_data"]
    else:
        report["included"] = report["STATUT"].isin(STATION_STATUS_KEEP) & report["has_data"]
    report["reason"] = np.select(
        [report["included"],
         ~report["has_data"] & report["STATUT"].isin(STATION_STATUS_KEEP or set()),
         ~report["has_data"]],
        ["included", "status kept but no data in the hourly files", "no data in the hourly files"],
        default="excluded by status: " + report["STATUT"],
    )
    keep = report.index[report["included"]]
    return hourly[hourly["NUMERO_STATION"].isin(keep)].copy(), report.reset_index()


# ---------------------------------------------------------------------------
# Agregación diaria
# ---------------------------------------------------------------------------

def daily_basic_stats(hourly: pd.DataFrame) -> pd.DataFrame:
    """Media, mediana y horas válidas por contaminante; NaN si hay menos de 18 horas."""
    g = hourly.groupby(["NUMERO_STATION", "DATE"])
    parts = []
    for p in POLLUTANTS:
        key = p.replace(".", "")  # PM2.5 -> PM25 en nombres de columna
        stats = g[p].agg(["mean", "median", "count"])
        stats.columns = [f"{key}_MEAN", f"{key}_MEDIAN", f"{key}_N_HOURS"]
        enough = stats[f"{key}_N_HOURS"] >= MIN_VALID_HOURS
        stats.loc[~enough, [f"{key}_MEAN", f"{key}_MEDIAN"]] = np.nan
        parts.append(stats)
    return pd.concat(parts, axis=1)


def daily_o3_mda8(hourly: pd.DataFrame) -> pd.DataFrame:
    """
    Máximo diario de la media móvil de 8 h de O3 (MDA8).
    Cada ventana se asigna al día en que TERMINA; es válida con >= 6 horas,
    y el día es válido con >= 18 ventanas válidas.
    """
    results = []
    for station, s in hourly[["NUMERO_STATION", "TIMESTAMP", "O3"]].groupby("NUMERO_STATION"):
        series = s.set_index("TIMESTAMP")["O3"].sort_index().asfreq("h")  # rejilla horaria completa
        rolling = series.rolling(8, min_periods=MIN_HOURS_PER_8H_WINDOW).mean()
        day = (rolling.index - pd.Timedelta(hours=1)).normalize()
        daily = rolling.groupby(day).agg(["max", "count"])
        daily.columns = ["O3_MDA8", "O3_N_8H_WINDOWS"]
        daily.loc[daily["O3_N_8H_WINDOWS"] < MIN_VALID_8H_WINDOWS, "O3_MDA8"] = np.nan
        daily["NUMERO_STATION"] = station
        results.append(daily)
    out = pd.concat(results)
    out.index.name = "DATE"
    return out.reset_index().set_index(["NUMERO_STATION", "DATE"])


def classify(daily: pd.DataFrame) -> pd.DataFrame:
    """Índice OMS, contaminante dominante y tipo de día."""
    metric = {"NO2": "NO2_MEAN", "PM2.5": "PM25_MEAN", "O3": "O3_MDA8"}
    ratios = pd.DataFrame({p: daily[col] / WHO_GUIDELINES[p] for p, col in metric.items()})
    has_any = ratios.notna().any(axis=1)

    daily["N_POLLUTANTS"] = ratios.notna().sum(axis=1)
    max_ratio = ratios.max(axis=1, skipna=True)
    daily["WHO_INDEX"] = (max_ratio * 100).round(2)
    daily["DOMINANT"] = ratios[has_any].idxmax(axis=1)
    daily["TIPO_DIA"] = pd.Series(
        np.select([max_ratio <= 1, max_ratio <= 2, max_ratio > 2],
                  ["Bon", "Acceptable", "Mauvais"], default=""),
        index=daily.index).replace("", np.nan)
    daily["EXCEEDS_WHO"] = max_ratio > 1
    return daily[has_any]


# ---------------------------------------------------------------------------
# Programa principal
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input-dir", type=Path, default=None, help="Carpeta con los CSV anuales")
    parser.add_argument("--output-dir", type=Path, default=None, help="Carpeta de salida (por defecto, la del script)")
    parser.add_argument("--stations-file", type=Path, default=None, help="Lista oficial de estaciones del RSQA")
    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent
    output_dir = args.output_dir or script_dir
    files = find_input_files(args.input_dir, script_dir)
    if not files:
        raise FileNotFoundError("No se encontraron archivos 'rsqa-multi-polluants*.csv'.")

    print(f"Archivos detectados: {len(files)}\n")
    frames, reports = [], []
    for path in files:
        data, report = load_file(path)
        reports.append(report)
        if data is None:
            continue
        frames.append(data)
        print(f"{path.name}: filas={report['rows_read']:,} | medianoche='{report['midnight_convention']}' | "
              f"fechas inválidas={report['invalid_datetime']} | "
              f"NO2={report['NO2_valid_hours']:,} PM2.5={report['PM2.5_valid_hours']:,} "
              f"O3={report['O3_valid_hours']:,} | O3 implausible={report.get('O3_implausible_hours', 0)}")

    if not frames:
        raise RuntimeError("Ningún archivo pudo procesarse.")

    hourly = pd.concat(frames, ignore_index=True)

    # Estaciones: solo las de la red permanente actual (estado "ouvert")
    stations = load_stations(find_station_file(args.stations_file, script_dir))
    hourly, station_report = select_stations(hourly, stations)
    print("\nEstaciones incluidas:", sorted(station_report.loc[station_report["included"], "NUMERO_STATION"]))
    excluded = station_report[~station_report["included"] & station_report["has_data"]]
    print("Estaciones con datos excluidas:",
          ", ".join(f"{n} ({s})" for n, s in zip(excluded["NUMERO_STATION"], excluded["STATUT"])))
    no_data = station_report[station_report["STATUT"].isin(STATION_STATUS_KEEP or set()) & ~station_report["has_data"]]
    if len(no_data):
        print("[AVISO] Estaciones abiertas sin datos en 2013-2025:",
              ", ".join(f"{n} {name}" for n, name in zip(no_data["NUMERO_STATION"], no_data["STATION_NAME"])))

    # Filas repetidas (misma estación y hora): se conserva la primera
    dup = hourly.duplicated(["NUMERO_STATION", "TIMESTAMP"])
    print(f"\nHoras duplicadas eliminadas: {dup.sum()}")
    hourly = hourly[~dup].copy()

    # Día de la medición: la hora que termina a las 00:00 pertenece al día anterior
    hourly["DATE"] = (hourly["TIMESTAMP"] - pd.Timedelta(hours=1)).dt.normalize()

    daily = daily_basic_stats(hourly).join(daily_o3_mda8(hourly), how="left")
    # El MDA8 también exige >= 18 horas válidas de O3 en el propio día (misma regla que NO2 y PM2.5)
    daily.loc[daily["O3_N_HOURS"] < MIN_VALID_HOURS, "O3_MDA8"] = np.nan
    daily = classify(daily).reset_index()

    daily = daily.merge(stations, on="NUMERO_STATION", how="left")

    output_cols = [
        "NUMERO_STATION", "STATION_NAME", "LATITUDE", "LONGITUDE", "ELEVATION_M", "DATE",
        "NO2_MEAN", "PM25_MEAN", "O3_MDA8",                  # métricas de clasificación (µg/m³)
        "NO2_MEDIAN", "PM25_MEDIAN", "O3_MEAN", "O3_MEDIAN",  # variables adicionales (µg/m³)
        "NO2_N_HOURS", "PM25_N_HOURS", "O3_N_HOURS", "O3_N_8H_WINDOWS",
        "N_POLLUTANTS", "WHO_INDEX", "DOMINANT", "TIPO_DIA", "EXCEEDS_WHO",
    ]
    daily = daily[output_cols].sort_values(["NUMERO_STATION", "DATE"]).reset_index(drop=True)
    for c in ["NO2_N_HOURS", "PM25_N_HOURS", "O3_N_HOURS", "O3_N_8H_WINDOWS"]:
        daily[c] = daily[c].fillna(0).astype(int)

    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / OUTPUT_NAME
    daily.to_csv(out_path, index=False, float_format="%.4f", date_format="%Y-%m-%d")
    pd.DataFrame(reports).to_csv(output_dir / REPORT_NAME, index=False)
    station_report.to_csv(output_dir / STATION_REPORT_NAME, index=False)

    print("\n--- RESUMEN ---")
    print(f"Filas (estación-día): {len(daily):,}")
    print(f"Estaciones: {daily['NUMERO_STATION'].nunique()} | "
          f"Rango: {daily['DATE'].min():%Y-%m-%d} a {daily['DATE'].max():%Y-%m-%d}")
    print("\nTIPO_DIA:\n" + daily["TIPO_DIA"].value_counts().to_string())
    print("\nDOMINANT:\n" + daily["DOMINANT"].value_counts().to_string())
    print("\nN_POLLUTANTS:\n" + daily["N_POLLUTANTS"].value_counts().sort_index().to_string())
    print(f"\nGuardado: {out_path}\nReportes: {output_dir / REPORT_NAME}, {output_dir / STATION_REPORT_NAME}")


if __name__ == "__main__":
    main()
