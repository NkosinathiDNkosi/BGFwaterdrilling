# Launch checklist

## Render settings

- Build command: `pip install -r requirements.txt`
- Start command: `gunicorn app:app`
- Python version: 3.11 or newer

## Required environment variable

Create `FLASK_SECRET_KEY` in the hosting dashboard and give it a long random value. Do not place the secret in GitHub.

## Admin access

The included database may still contain the original starter admin credentials. Change the admin password before sharing the `/admin/login` address or accepting real enquiries.

## Search launch

1. Connect `burgersfortwaterdrilling.co.za` to the deployed service.
2. Confirm that `/robots.txt` and `/sitemap.xml` open successfully.
3. Add the domain property in Google Search Console.
4. Submit `https://burgersfortwaterdrilling.co.za/sitemap.xml`.
5. Request indexing for the homepage.
6. Create or complete the Google Business Profile using the same name, phone and address shown on the website.

SEO improvements help search engines understand the website, but no developer can guarantee a specific ranking position or instant indexing.
