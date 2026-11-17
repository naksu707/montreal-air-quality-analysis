#!/usr/bin/env python3
"""Reconstruir el dataset diario del RSQA (Montréal) a partir de archivos horarios multi-anuales."""

from pathlib import Path
import re
import numpy as np
import pandas as pd

# Umbrales diarios OMS 2021 (µg/m³)
WHO_THRESHOLDS = {
    "NO2": 25.0,
    "PM2.5": 15.0,
    "O3": 100.0,
}

# Tokens que significan "sin dato"
BAD_TOKENS = {"N/M", "NM", "INVLD", "DOWN", "FAILPWR", "NODATA", "NA", "NAN", "-", ""}

# Alias normalizados -> nombre canónico
COLUMN_ALIASES = {
    "STATION": {"NUMERO_STATION", "NO_POSTE", "NOPOSTE", "STATION", "POSTE"},
    "NO2": {"NO2", "NO2_UGM3"},
    "PM25": {"PM2,5", "PM25", "PM25_UGM3", "PM2,5_UGM3"},
    "O3": {"O3", "O3_UGM3"},
    "DATE_HEURE": {"DATE_HEURE", "DATEHEURE", "DATETIME"},
    "DATE": {"DATE", "JOUR"},
    "HEURE": {"HEURE", "HOUR", "TIME"},
}


def norm_col(col: str) -> str:
    """Normaliza nombres de columna: sin BOM, mayúsculas, sin espacios, punto -> coma."""
    s = str(col).replace("\ufeff", "").strip().upper()
    s = re.sub(r"\s+", "", s)      # colapsa espacios múltiples y tabs
    s = s.replace(".", ",")        # PM2.5 -> PM2,5
    return s


def map_columns(raw_columns: list[str]) -> dict[str, str]:
    """Mapea nombres canónicos a los nombres originales presentes en el CSV."""
    col_map: dict[str, str] = {}
    for orig in raw_columns:
        normalized = norm_col(orig)
        for canonical, aliases in COLUMN_ALIASES.items():
            if normalized in aliases and canonical not in col_map:
                col_map[canonical] = orig
    return col_map


def to_num(series: pd.Series) -> pd.Series:
    """Convierte tokens no numéricos a NaN y maneja coma decimal."""
    txt = series.astype(str).str.strip()
    # Tokens de "sin dato" -> NaN
    txt = txt.where(~txt.str.upper().isin(BAD_TOKENS), np.nan)
    # Coma decimal -> punto (solo si hay coma y no hay punto)
    txt = txt.str.replace(",", ".", regex=False)
    return pd.to_numeric(txt, errors="coerce")


def parse_datetime(df: pd.DataFrame, col_map: dict[str, str]) -> pd.Series:
    """Parsea fechas con estrategia en cascada (DATE_HEURE -> DATE+HEURE -> genérico)."""
    if "DATE_HEURE" in col_map:
        raw = df[col_map["DATE_HEURE"]].astype(str).str.strip()
    elif "DATE" in col_map and "HEURE" in col_map:
        raw = (
            df[col_map["DATE"]].astype(str).str.strip()
            + " "
            + df[col_map["HEURE"]].astype(str).str.strip()
        )
    elif "DATE" in col_map:
        raw = df[col_map["DATE"]].astype(str).str.strip()
    else:
        candidates = [c for c in df.columns if "DATE" in norm_col(c) or "JOUR" in norm_col(c)]
        if not candidates:
            return pd.Series(pd.NaT, index=df.index, dtype="datetime64[ns]")
        raw = df[candidates[0]].astype(str).str.strip()

    # Hora 24:00 -> 00:00 (preserva la fecha de la fila; el día se agrupa por DATE)
    raw = raw.str.replace(r"\b24:00(?::00)?\b", "00:00", regex=True)
    # Limpiar "nan" string que dejó astype(str) sobre NaN reales
    raw = raw.replace({"nan": np.nan, "None": np.nan, "": np.nan})

    # Separar ISO (YYYY-MM-DD) de DMY (DD-MM-YYYY) para no invertir mes/día
    is_iso = raw.str.match(r"^\s*\d{4}[-/]\d{1,2}[-/]\d{1,2}", na=False)
    dt = pd.Series(pd.NaT, index=df.index, dtype="datetime64[ns]")

    if is_iso.any():
        dt.loc[is_iso] = pd.to_datetime(
            raw.loc[is_iso], format="mixed", dayfirst=False, errors="coerce"
        )
    if (~is_iso).any():
        dt.loc[~is_iso] = pd.to_datetime(
            raw.loc[~is_iso], format="mixed", dayfirst=True, errors="coerce"
        )
    return dt


def find_input_files(base_dir: Path) -> list[Path]:
    """Busca los CSV anuales en la carpeta esperada relativa al script o al CWD."""
    relative_folder = Path("RSQA - Multi-Polluants (en continu)") / "dataset 2013 - 2025"
    search_roots = [
        base_dir / relative_folder,
        base_dir.parent / relative_folder,
        Path.cwd() / relative_folder,
        base_dir,
        base_dir.parent,
    ]
    for folder in search_roots:
        files = sorted(folder.glob("rsqa-multi-polluants*.csv"))
        if files:
            return files
    return []


def classify_day(df: pd.DataFrame) -> pd.DataFrame:
    """Calcula ratios frente a umbrales OMS 2021, IQA, contaminante dominante y TIPO_DIA."""
    ratios = pd.DataFrame(
        {
            "NO2": df["NO2"] / WHO_THRESHOLDS["NO2"],
            "PM25": df["PM2.5"] / WHO_THRESHOLDS["PM2.5"],
            "O3": df["O3"] / WHO_THRESHOLDS["O3"],
        },
        index=df.index,
    )

    # Solo filas con al menos un contaminante válido
    valid = ratios.notna().any(axis=1)
    df = df.loc[valid].copy()
    ratios = ratios.loc[valid]

    max_ratio = ratios.max(axis=1, skipna=True)
    df["IQA"] = (max_ratio * 100.0).round(2)
    df["DOMINANT"] = ratios.idxmax(axis=1, skipna=True)

    conditions = [
        df["IQA"] <= 100.0,
        (df["IQA"] > 100.0) & (df["IQA"] <= 200.0),
        df["IQA"] > 200.0,
    ]
    choices = ["Bon", "Acceptable", "Mauvais"]
    df["TIPO_DIA"] = np.select(conditions, choices, default=None)
    return df


def main() -> None:
    script_dir = Path(__file__).resolve().parent
    files = find_input_files(script_dir)

    if not files:
        raise FileNotFoundError(
            "No se encontraron archivos 'rsqa-multi-polluants*.csv'. "
            "Verifica la carpeta 'RSQA - Multi-Polluants (en continu)/dataset 2013 - 2025/'."
        )

    frames: list[pd.DataFrame] = []
    required_min = {"STATION", "NO2", "PM25", "O3"}

    print(f"Archivos detectados: {len(files)}\n")
    for csv_path in files:
        raw_df = pd.read_csv(
            csv_path,
            sep=",",
            decimal=".",
            dtype=str,
            encoding="utf-8-sig",
        )
        col_map = map_columns(list(raw_df.columns))
        missing = required_min - set(col_map.keys())
        has_date = ("DATE_HEURE" in col_map) or ("DATE" in col_map)

        if missing or not has_date:
            print(
                f"[AVISO] {csv_path.name}: faltan columnas requeridas {sorted(missing)} "
                f"(fecha_ok={has_date}). Columnas detectadas: {list(raw_df.columns)}"
            )
            continue

        dt = parse_datetime(raw_df, col_map)
        station = to_num(raw_df[col_map["STATION"]])
        no2 = to_num(raw_df[col_map["NO2"]])
        pm25 = to_num(raw_df[col_map["PM25"]])
        o3 = to_num(raw_df[col_map["O3"]])

        print(
            f"{csv_path.name}: filas={len(raw_df):,} | "
            f"fechas_validas={dt.notna().sum():,} | "
            f"NO2={no2.notna().sum():,} | "
            f"PM2.5={pm25.notna().sum():,} | "
            f"O3={o3.notna().sum():,}"
        )

        year_df = pd.DataFrame(
            {
                "NUMERO_STATION": station,
                "DATE": dt.dt.strftime("%Y-%m-%d"),
                "NO2": no2,
                "PM2.5": pm25,
                "O3": o3,
            }
        )
        frames.append(year_df)

    if not frames:
        raise RuntimeError("Ningún archivo pudo procesarse correctamente.")

    hourly = pd.concat(frames, ignore_index=True)
    hourly = hourly.dropna(subset=["NUMERO_STATION", "DATE"]).copy()
    hourly["NUMERO_STATION"] = hourly["NUMERO_STATION"].astype(int)

    hourly["has_valid_reading"] = hourly[["NO2", "PM2.5", "O3"]].notna().any(axis=1)

    # MEDIANA en lugar de media: los datos horarios tienen huecos de mantenimiento
    # y picos extremos transitorios (tráfico, inversión térmica) que sesgan el promedio.
    daily = (
        hourly.groupby(["NUMERO_STATION", "DATE"], as_index=False)
        .agg(
            NO2=("NO2", "median"),
            **{"PM2.5": ("PM2.5", "median")},
            O3=("O3", "median"),
            n_hours=("has_valid_reading", "sum"),
        )
    )

    daily = daily[daily["n_hours"] >= 18].copy()
    daily = classify_day(daily)
    daily = daily.dropna(subset=["TIPO_DIA"]).copy()

    daily = daily.rename(columns={"DATE": "DATE_HEURE"})
    daily["n_hours"] = daily["n_hours"].astype(int)
    output_cols = [
        "NUMERO_STATION",
        "DATE_HEURE",
        "NO2",
        "PM2.5",
        "O3",
        "TIPO_DIA",
        "IQA",
        "DOMINANT",
        "n_hours",
    ]
    daily = daily[output_cols].sort_values(["NUMERO_STATION", "DATE_HEURE"]).reset_index(drop=True)

    output_path = script_dir / "rsqa_daily_no2_o3_pm25_daytype.csv"
    daily.to_csv(output_path, index=False, float_format="%.4f")

    print("\n--- RESUMEN FINAL ---")
    print(f"Filas totales: {len(daily):,}")
    print(f"Estaciones únicas: {daily['NUMERO_STATION'].nunique()}")
    print(f"Días únicos: {daily['DATE_HEURE'].nunique()}")
    print(f"Rango de fechas: {daily['DATE_HEURE'].min()} a {daily['DATE_HEURE'].max()}")
    print("\nDistribución TIPO_DIA:")
    print(daily["TIPO_DIA"].value_counts().to_string())
    print("\nDistribución DOMINANT:")
    print(daily["DOMINANT"].value_counts().to_string())
    print(f"\nArchivo guardado en: {output_path}")


if __name__ == "__main__":
    main()