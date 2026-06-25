---
name: infographic
description: Create polished HTML/CSS infographics for timelines, comparisons, SWOT, funnels, pyramids, roadmaps, data cards, organization charts, and structured information posters.
trigger: user asks for an infographic, poster-style visualization, structured information display, timeline poster, comparison visual, SWOT, funnel, pyramid, roadmap, or data-card layout
do-not-trigger: user asks for a technical Mermaid diagram, interactive widget, generated image, photo, code implementation, or spreadsheet analysis
user-invocable: true
disable-auto-invoke: false
argument-hint: <infographic content and desired format>
blocked-tools:
  - execute_office_shell
tags:
  - infographic
  - poster
  - visualization
  - abu-migrated
---

# Infographic

Generate a polished static HTML/CSS infographic in a fenced `html` code block.

## Rules

- Output one complete HTML fragment, not a full document.
- Use `<style>` followed by semantic HTML.
- Do not use JavaScript, external CDNs, canvas, or image generation.
- Keep the design light, restrained, and readable.

## Good Fit

- Timelines.
- Roadmaps.
- SWOT or 2x2 comparisons.
- Funnel or pyramid explanations.
- Metric cards and annotated summaries.
- Organization or responsibility maps.

## Style

- Use one main accent color plus neutral grays.
- Prefer whitespace and alignment over decoration.
- Use concise labels and short supporting text.
