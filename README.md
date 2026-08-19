# B2B Directory Intelligence · Web v4

Plataforma web para convertir directorios empresariales públicos en bases B2B estructuradas y exportables a Excel.

## Qué cambió en v4

- Landing page comercial completa.
- Motor de extracción universal para directorios HTML públicos.
- Adaptador optimizado para Directorio de Carga.
- Detección automática de fichas empresariales y paginación.
- Parser genérico con soporte para JSON-LD / Schema.org, `mailto:`, `tel:`, etiquetas y enlaces externos.
- Selector CSS manual como fallback para directorios con una estructura poco convencional.
- Barra lateral con **Todas / Cantidad**.
- Modo **Claro / Oscuro**.
- Modo **Directorio / Enriquecida**.
- Analizador de compatibilidad antes de extraer.
- Métricas de cobertura, auditoría y descarga Excel.

## Ejecutar localmente

```bash
python -m pip install -r requirements.txt
streamlit run app.py
```

## Publicar

El proyecto está preparado para Streamlit Community Cloud. `app.py` debe quedar en la raíz del repositorio junto a `requirements.txt` y la carpeta `src/`.

## Personalización comercial

Editá `src/settings.py` para cambiar el nombre del producto y, si querés, agregar un correo comercial:

```python
BRAND_NAME = "B2B DATA"
PRODUCT_NAME = "Directory Intelligence"
TAGLINE = "Convertí directorios públicos en datos B2B accionables."
CONTACT_EMAIL = "ventas@tuempresa.com"
```

Si `CONTACT_EMAIL` queda vacío, la landing simplemente no muestra el botón de contacto.

## Compatibilidad

El motor universal está pensado para directorios públicos que exponen enlaces o fichas empresariales en HTML. Sitios con autenticación, CAPTCHA, bloqueos anti-bot o renderizado exclusivamente JavaScript pueden requerir un adaptador específico.

## Salida

El Excel mantiene siempre estas columnas principales:

- Nombre de empresa
- Correo
- Teléfono 1
- Teléfono 2
- Dirección
- Estado
- País
- Sitio web
- LinkedIn
- Segmento

Y opcionalmente columnas de control/trazabilidad.
