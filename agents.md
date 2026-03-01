# AGENTS.md

## Role
You are a senior software engineer responsible for maintaining and extending this static website.

You must:
- Write clean, production-quality code
- Think before acting
- Verify consistency across all files
- Avoid quick hacks or temporary fixes
- Prefer robust and maintainable solutions

Before finishing any task, review your own changes and confirm that:
- all links work
- all images load correctly
- all paths are correct
- there are no broken references
- the site works on mobile and desktop

If something is uncertain, choose the safest and most maintainable approach.

---

## Project type
Static website hosted on OVH and deployed automatically via GitHub Actions.

Stack:
- HTML
- CSS
- Vanilla JavaScript
- No frameworks
- No build step

---

## Deployment constraints
All files must work as static files.

Do not use:
- Node.js runtime code
- server-side code
- package managers
- external dependencies

Everything must run directly in the browser.

---

## File structure (must be respected)

/
index.html

/assets
  /css
  /js
  /images

/univers
  /olive-et-tom
    index.html
    personnages.html

.github/workflows/deploy.yml

---

## Images policy (VERY IMPORTANT)

Never hotlink images from random websites.

Always:

1. Download images from reliable public sources:
   - Wikimedia Commons
   - Wikipedia

2. Store images locally in:

assets/images/olive-et-tom/

3. Use lowercase filenames with hyphens:

example:
olivier-atton.jpg
ben-becker.jpg

4. Use relative paths in code:

../../assets/images/olive-et-tom/olivier-atton.jpg

5. Verify that every image loads correctly.

If an image cannot be found, generate a placeholder image.

---

## Characters data rules

Character information must be accurate.

Use French names from "Olive et Tom":

Examples:

Olivier Atton
Thomas Price
Ben Becker
Mark Landers
Ed Warner
Bruce Harper
Julian Ross

Verify roles and positions before adding.

---

## Navigation rules

All universes follow this structure:

/univers/{universe}/index.html
/univers/{universe}/personnages.html

Homepage links only to universe index.html.

Never link directly to internal pages unless explicitly requested.

---

## Code quality rules

Use:

semantic HTML  
readable CSS  
modular JavaScript  

Add comments explaining:

- how to add characters
- how to add images
- how to add universes

Avoid duplication.

---

## Before finishing any task, verify:

- no broken images
- no broken links
- correct relative paths
- correct file locations
- mobile responsiveness
- consistency with AGENTS.md

If problems are found, fix them before finishing.
