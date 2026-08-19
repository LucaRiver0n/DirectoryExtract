# Actualizar tu repositorio actual de v3 a v4

Como ya tenés la primera versión publicada, no hace falta crear otro repositorio.

## Reemplazá estos archivos

Subí/reemplazá en la raíz:

- `app.py`
- `README.md`
- `DEPLOY_WEB.md`

Subí/reemplazá la carpeta completa `src/`. La estructura debe quedar:

```text
src/
├── __init__.py
├── directorio.py
├── engine.py
├── enrichment.py
├── exporter.py
├── generic_directory.py
├── http_client.py
├── models.py
└── settings.py
```

También podés reemplazar `tests/` para conservar las pruebas nuevas.

No borres `.streamlit/config.toml` ni `requirements.txt`; esta versión sigue siendo compatible con ellos.

## En GitHub Web

1. Entrá al repositorio.
2. Para archivos existentes, abrilos y elegí editar/reemplazar o eliminá la versión anterior antes de subir la nueva.
3. Usá **Add file → Upload files** para subir las carpetas completas `src` y `tests`.
4. Confirmá que `app.py` sigue en la raíz.
5. Hacé **Commit changes**.
6. Streamlit Cloud debería redeployar automáticamente.

## Prueba recomendada

Primero usá Directorio de Carga para confirmar que el comportamiento anterior sigue funcionando. Luego probá otro directorio con **Cantidad = 10** y usá **Analizar compatibilidad** antes de ejecutar.
