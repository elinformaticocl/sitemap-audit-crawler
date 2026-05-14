## `README.es.md`

```md
# Sitemap Audit Crawler

![Licencia: MIT](https://img.shields.io/badge/Licencia-MIT-green.svg)
![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)
![Aplicación](https://img.shields.io/badge/App-Escritorio-lightgrey.svg)
![Estado](https://img.shields.io/badge/Estado-Activo-brightgreen.svg)

**Sitemap Audit Crawler** es una herramienta de escritorio para auditorías SEO técnicas. Permite detectar archivos sitemap, recolectar URLs de forma recursiva, procesar páginas en paralelo, extraer campos SEO relevantes, guardar/restaurar avances y exportar los resultados a Excel.

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
  - `/wp-sitemap.xml`
  - `/sitemap-es.xml`
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
- Etiqueta title.
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

