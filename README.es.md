# Sitemap Audit Crawler

![Licencia: MIT](https://img.shields.io/badge/Licencia-MIT-green.svg)
![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)
![Aplicación](https://img.shields.io/badge/App-Escritorio-lightgrey.svg)
![Estado](https://img.shields.io/badge/Estado-Activo-brightgreen.svg)

**Sitemap Audit Crawler** es una herramienta de escritorio para auditorías SEO técnicas. Permite detectar archivos sitemap, recolectar URLs de forma recursiva, procesar páginas en paralelo, extraer campos SEO relevantes, guardar y restaurar avances, y exportar los resultados a Excel.

Fue creada como una alternativa local y práctica para realizar auditorías basadas en sitemaps, especialmente cuando no se dispone de herramientas comerciales, cuando una licencia no está disponible o cuando se necesita una solución simple, controlable y enfocada.

> English version available here: [README.md](README.md)

---

## Descripción general

Sitemap Audit Crawler ayuda a especialistas SEO, desarrolladores, equipos de contenido y perfiles técnicos a revisar grandes conjuntos de URLs obtenidas desde archivos sitemap.

La aplicación cuenta con una interfaz gráfica desarrollada en PyQt5 y permite:

- Detectar sitemaps desde un dominio.
- Leer sitemaps declarados en `robots.txt`.
- Revisar rutas comunes de sitemap automáticamente.
- Procesar índices de sitemap anidados.
- Revisar URLs usando concurrencia configurable.
- Extraer campos SEO relevantes desde páginas HTML.
- Guardar y restaurar avances.
- Reprocesar URLs pendientes o fallidas.
- Exportar resultados a Excel.

---

## Por qué existe esta herramienta

Herramientas comerciales como Screaming Frog o Sitebulb son muy potentes y ampliamente utilizadas. Sin embargo, hay situaciones donde una herramienta más liviana, local y controlable es suficiente.

Sitemap Audit Crawler nace para cubrir esa necesidad: auditar rápidamente URLs expuestas en sitemaps sin depender completamente de soluciones externas o de pago.

Este proyecto no busca reemplazar plataformas SEO empresariales. Su objetivo es ofrecer un flujo de trabajo enfocado para inspección de URLs desde sitemaps, revisiones técnicas y exportación estructurada de resultados.

---

## Funciones principales

### Detección de sitemaps

La herramienta puede detectar sitemaps desde:

- Una URL directa de sitemap.
- Declaraciones dentro de `robots.txt`.
- Rutas comunes como:
  - `/sitemap.xml`
  - `/sitemap_index.xml`
  - `/sitemap-index.xml`
  - `/wp-sitemap.xml`
  - `/sitemap-es.xml`
  - `/es/sitemap.xml`
  - `/en/sitemap.xml`

### Procesamiento recursivo

La aplicación soporta índices de sitemap y archivos sitemap anidados, permitiendo recolectar URLs desde sitios grandes con múltiples fuentes.

### Crawling concurrente

Las URLs pueden ser procesadas usando múltiples solicitudes concurrentes. La cantidad de solicitudes simultáneas es configurable desde la interfaz.

Esto permite equilibrar velocidad y carga sobre el servidor auditado.

### Extracción de campos SEO

La herramienta puede extraer campos como:

- Estado HTTP.
- URL final después de redirecciones.
- Tipo de contenido.
- H1.
- Cantidad de H1.
- Etiqueta `title`.
- Meta description.
- Canonical.
- Meta robots.
- Datos estructurados JSON-LD.

### Selección de User-Agent

La aplicación incluye perfiles User-Agent predefinidos y permite agregar User-Agent personalizados.

Esto es útil para probar cómo responde un sitio frente a navegadores, bots de búsqueda o agentes HTTP personalizados.

### Gestión de progreso

Sitemap Audit Crawler permite guardar y restaurar avances mediante archivos JSON.

Esto es especialmente útil para auditorías grandes que pueden tomar tiempo o que necesitan retomarse más tarde.

### Exportación a Excel

Los resultados pueden exportarse a formato `.xlsx` para análisis, filtros, reportes o documentación.

---

## Capturas de pantalla

Las capturas pueden agregarse dentro de la carpeta `screenshots/`.

Ejemplo:

```md
![Interfaz principal](screenshots/main-interface.png)
```

Capturas recomendadas:

- Interfaz principal.
- Resultado de detección de sitemaps.
- Tabla de URLs con campos SEO.
- Ejemplo de exportación a Excel.

---

## Instalación

### Requisitos

- Python 3.10 o superior.
- Un entorno de escritorio compatible con aplicaciones PyQt5.

### Clonar el repositorio

```bash
git clone https://github.com/elinformaticocl/sitemap-audit-crawler.git
cd sitemap-audit-crawler
```

### Crear entorno virtual

```bash
python -m venv .venv
```

### Activar entorno virtual

En Windows:

```bash
.venv\Scripts\activate
```

En Linux o macOS:

```bash
source .venv/bin/activate
```

### Instalar dependencias

```bash
pip install -r requirements.txt
```

---

## Uso

Ejecuta la aplicación con:

```bash
python sitemap_audit_crawler.py
```

Flujo básico:

1. Ingresa un dominio o una URL directa de sitemap.
2. Haz clic en **Detect Sitemaps**.
3. Revisa los sitemaps detectados.
4. Selecciona URLs específicas o procesa todas.
5. Configura timeout, delay, concurrencia y User-Agent.
6. Elige los campos SEO que deseas extraer.
7. Ejecuta el procesamiento.
8. Guarda el progreso si es necesario.
9. Exporta el resultado a Excel.

---

## Archivos generados

La aplicación puede generar archivos locales como:

```text
sitemap_audit_user_agents.json
sitemap_audit_progress_*.json
sitemap_audit_export.xlsx
```

Estos archivos se usan para guardar User-Agent personalizados, avances de auditoría y exportaciones.

---

## Estructura recomendada del repositorio

```text
sitemap-audit-crawler/
├── sitemap_audit_crawler.py
├── README.md
├── README.es.md
├── LICENSE
├── requirements.txt
├── screenshots/
└── .gitignore
```

---

## Próximas mejoras posibles

Ideas para futuras versiones:

- Agregar más campos SEO.
- Detectar enlaces rotos.
- Analizar cadenas de redirección.
- Comparar sitemaps entre auditorías.
- Validar reglas de `robots.txt`.
- Agregar exportación CSV.
- Generar versiones ejecutables.
- Crear reportes históricos de crawls.

---

## Autor

**Daniel Alday**

Sitio web: [https://www.elinformatico.cl](https://www.elinformatico.cl)  
GitHub: [https://github.com/elinformaticocl](https://github.com/elinformaticocl)

---

## Licencia

Este proyecto se publica bajo la Licencia MIT.

Puedes usarlo, modificarlo y distribuirlo, siempre que se conserve el aviso de copyright original y la licencia.

Consulta el archivo [LICENSE](LICENSE) para más detalles.

---

## Aviso de uso responsable

Esta herramienta realiza solicitudes HTTP a sitios web. Úsala de forma responsable.

Antes de auditar un sitio, asegúrate de tener autorización o de que el uso cumpla con las políticas del sitio. Configura cuidadosamente la concurrencia y el delay para evitar una carga innecesaria sobre el servidor.