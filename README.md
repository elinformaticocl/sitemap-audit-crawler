# Sitemap Audit Crawler

![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)
![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)
![Desktop App](https://img.shields.io/badge/App-Desktop-lightgrey.svg)
![Status](https://img.shields.io/badge/Status-Active-brightgreen.svg)

**Sitemap Audit Crawler** is a desktop SEO auditing tool designed to detect sitemap files, collect URLs recursively, crawl pages concurrently, extract essential SEO fields, save and restore progress, and export structured audit results to Excel.

It was created as a practical local alternative for sitemap-based technical SEO audits, especially useful when access to paid crawling tools is limited, unavailable, or unnecessary for a specific review.

> Spanish version available here: [README.es.md](README.es.md)

---

## Overview

Sitemap Audit Crawler helps SEO specialists, developers, content teams, and technical auditors inspect large sets of URLs directly from sitemap files.

The application provides a graphical interface built with PyQt5 and allows users to:

- Detect sitemaps from a domain.
- Read sitemap URLs declared in `robots.txt`.
- Check common sitemap paths automatically.
- Parse nested sitemap indexes recursively.
- Crawl URLs with configurable concurrency.
- Extract relevant SEO fields from HTML pages.
- Save and restore progress.
- Resume pending or failed URL checks.
- Export results to Excel.

---

## Why this tool exists

Commercial SEO crawlers such as Screaming Frog or Sitebulb are powerful and widely used. However, there are situations where a lighter, local, and controllable tool is enough.

Sitemap Audit Crawler was created to solve that need: quickly audit URLs already exposed through sitemap files, without depending entirely on external or paid tools.

This project is not intended to replace full enterprise SEO platforms. Instead, it provides a focused workflow for sitemap-based URL inspection, technical checks, and structured exports.

---

## Main Features

### Sitemap detection

The tool can detect sitemap files from:

- Direct sitemap URLs.
- `robots.txt` declarations.
- Common sitemap paths such as:
  - `/sitemap.xml`
  - `/sitemap_index.xml`
  - `/wp-sitemap.xml`
  - `/sitemap-es.xml`
  - `/en/sitemap.xml`

### Recursive sitemap parsing

The crawler supports sitemap indexes and nested sitemap files, allowing it to collect URLs from large websites with multiple sitemap sources.

### Concurrent crawling

URLs can be processed using multiple concurrent requests. The number of workers is configurable from the application interface.

This allows the user to balance speed and server load depending on the website being audited.

### SEO field extraction

The application can extract selected SEO fields, including:

- HTTP status.
- Final URL after redirects.
- Content type.
- H1.
- H1 count.
- Title tag.
- Meta description.
- Canonical URL.
- Meta robots.
- JSON-LD structured data.

### User-Agent selection

The tool includes predefined User-Agent profiles and allows custom User-Agent values to be added and persisted locally.

This is useful when testing how a website responds to browsers, search engine bots, or custom HTTP agents.

### Progress management

Sitemap Audit Crawler can save and restore progress using JSON files.

This is useful for large audits where processing may take time or needs to be resumed later.

### Excel export

Audit results can be exported to `.xlsx` format for further analysis, filtering, reporting, or sharing.

---

