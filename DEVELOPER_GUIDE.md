# Burgersfort Water Drilling — editing guide

## Where to make common changes

| Change | File | Search for |
| --- | --- | --- |
| Page wording, phone, services, gallery, FAQ | `templates/index.html` | A labelled HTML section such as `<!-- SERVICES -->` |
| SEO, favicon and social preview | `templates/base.html` | `SEO`, `Browser and device icons`, or `Social sharing metadata` |
| Colours, spacing, fonts and mobile layout | `static/style.css` | The CSS contents block |
| Price calculator values | `static/script.js` | `EDIT HERE: PRICE CATALOGUE` |
| WhatsApp quote text or number | `static/script.js` | `EDIT HERE: WHATSAPP QUOTE` |
| Form and database behaviour | `app.py` | `Public website routes` |
| Admin behaviour | `app.py` | `Admin routes` |
| Standalone admin design | `admin/static/admin.css` | The section comments |

## Image naming

General photographs use simple sequential names such as `image1.jpg`,
`image2.jpg`, and `image10.png`. Functional assets keep descriptive names such
as `hero-drilling.webp`, `brand-logo.webp`, and `favicon-32x32.png` because the
name explains their role. When replacing an image, keep its current filename
and extension so existing template and stylesheet references continue working.

## How the CSS cascade works

CSS runs from the top of `static/style.css` to the bottom. When two rules have equal specificity, the later rule wins. This project follows this order:

1. Design variables and reset
2. Shared layout and buttons
3. Components in the same order as the HTML
4. Animations
5. Responsive desktop/tablet/mobile rules
6. Final launch refinements

The final launch section intentionally comes last. If an earlier edit has no visible effect, search for the same selector in that final section and edit the last matching rule.

## Safe workflow

1. Change one labelled section at a time.
2. Run `python app.py`.
3. Check desktop and mobile widths.
4. Submit a test enquiry and check `/admin`.
5. Commit only after those checks pass.

## Before production

Set `FLASK_SECRET_KEY` to a long random value in your hosting environment and change the starter admin password. Never commit real secrets, customer exports, or a production database to GitHub.
