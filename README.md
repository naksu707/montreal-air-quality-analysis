# Montréal Air Quality Analysis

A data science project developed in collaboration with **Concordia University
(Montréal)**, exploring air quality in the city using open RSQA data combined
with atmospheric variables. Results — predictions and a heatmap — are
visualized in the **CityLayers** platform (NGCI, Concordia).

## Overview

The project processes, cleans and organizes air quality monitoring data,
analyzes atmospheric pollutants, identifies temporal patterns and trends, and
builds a prediction model. The outputs are a pollutant prediction model and an
interactive heatmap displayed in CityLayers alongside those predictions.

## Workflow

1. **Data cleaning and treatment** — classify, clean and validate the raw data
   before any analysis.
2. **Prediction model** — train a model on the cleaned data.
3. **Heatmap** — spatial visualization of air quality, shown in CityLayers
   together with the predictions.

## Data

**Air quality (RSQA)**
- **RSQA – Multi-Polluants (en continu)** (2013–2025)
- **Station list** (`liste-des-stations_do_rev_2026-05-22.csv`)

**Atmospheric variables**
- **CHIRPS / CHIRTS** (Climate Hazards Center, UC Santa Barbara)
  https://swat.tamu.edu/data/chirps-chirts/
- **NASA POWER** (NASA Langley Research Center)
  https://power.larc.nasa.gov/data-access-viewer/

**Deliberately excluded:** the *RSQA – Indice de la qualité de l'air
(historique)* dataset. It is a derived, aggregated product rather than raw
measurement data; using it as a label or feature would introduce data leakage
and hide the underlying pollutant values the model is meant to learn from. It
may still be used later as an external validation reference.

## Focus

The current task is to classify days as "good" or "bad" based on NO2, O3 and
PM2.5 concentrations, grounded in scientific literature and official Québec
(IQA) and Canadian (AQHI) air quality standards.

## Visualization

Predictions and the heatmap are integrated into CityLayers:
https://ngci.encs.concordia.ca/citylayers/login

## Status

Work in progress — data cleaning and validation first, then modeling and
visualization.