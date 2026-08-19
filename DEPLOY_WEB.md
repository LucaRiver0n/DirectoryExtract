# Publicar B2B Directory Intelligence en Streamlit Community Cloud

## 1. Subir a GitHub

En la raíz del repositorio deben verse, como mínimo:

```text
app.py
requirements.txt
src/
.streamlit/
```

No subas solamente los archivos internos de `src`: la carpeta `src` debe conservarse.

## 2. Crear / actualizar la aplicación

En Streamlit Community Cloud seleccioná:

- Repository: tu repositorio
- Branch: `main`
- Main file path: `app.py`

Si ya tenés la app publicada, alcanza con reemplazar los archivos del repositorio y hacer commit. Streamlit normalmente vuelve a desplegar con el último commit.

## 3. Personalizar la landing

Editá `src/settings.py` antes de publicar:

```python
BRAND_NAME = "Tu marca"
PRODUCT_NAME = "Directory Intelligence"
CONTACT_EMAIL = "ventas@tuempresa.com"
```

## 4. Probar un directorio nuevo

1. Entrá a la landing.
2. Tocá **Abrir plataforma**.
3. Pegá la URL exacta de la categoría o segmento.
4. Tocá **Analizar compatibilidad**.
5. Empezá con 10–25 empresas.
6. Revisá la cobertura.
7. Si está bien, elegí **Todas**.

Si el motor no detecta las fichas, abrí **Compatibilidad avanzada** y agregá el selector CSS del enlace/tarjeta de empresa. El selector de siguiente página es opcional.

## Nota técnica

No existe un scraper que pueda garantizar compatibilidad automática con literalmente cualquier web. Los sitios con login, CAPTCHA, protección anti-bot o contenido exclusivamente JavaScript pueden requerir una integración/adaptador específico. El motor universal está orientado a directorios públicos HTML y conserva el adaptador optimizado del directorio original.
