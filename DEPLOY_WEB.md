# Publicar B2B Data Extractor en la web

## Opción recomendada: Streamlit Community Cloud

1. Crear un repositorio en GitHub.
2. Subir el contenido de esta carpeta a la raíz del repositorio.
3. Entrar a Streamlit Community Cloud.
4. Elegir **Create app**.
5. Seleccionar el repositorio, rama y `app.py` como entrypoint.
6. Publicar.

`requirements.txt` contiene las dependencias necesarias y `.streamlit/config.toml` define los temas visuales.

## Hosting propio / contenedor

También puede desplegarse en un servidor Python ejecutando:

```bash
streamlit run app.py --server.address=0.0.0.0 --server.port=8501
```

Para uso corporativo se recomienda colocar la app detrás de HTTPS y autenticación (SSO, proxy o plataforma de hosting con acceso privado).

## Nota sobre scraping

En hosting cloud las solicitudes salen desde la IP del servidor. Si una fuente limita datacenters o automatizaciones, puede ser necesario usar infraestructura propia o ajustar la estrategia de extracción.
