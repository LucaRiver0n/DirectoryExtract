# B2B Data Extractor · Web Premium

Versión web del extractor de empresas, diseñada como un workspace profesional de inteligencia de datos.

## Ejecutar localmente

```bash
python -m pip install -r requirements.txt
streamlit run app.py
```

## Experiencia

- Barra lateral persistente con selector **Todas / Cantidad**.
- Modo **Claro / Oscuro** desde la propia interfaz.
- Extracción **Directorio** o **Enriquecida**.
- Segmento y país inferidos desde la URL.
- Progreso en tiempo real.
- Métricas de cobertura.
- Buscador y vista previa del dataset.
- Auditoría opcional de fuentes.
- Descarga directa a Excel.

## Publicación

El proyecto está listo para Streamlit Community Cloud o cualquier hosting compatible con Python/Docker. Ver `DEPLOY_WEB.md`.
