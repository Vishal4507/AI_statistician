# Deploying the explorer

Currently deployed at <https://ai-statistician.netlify.app>
(Netlify project `ai-statistician`, site id `888411cf-9a46-44ea-a6c6-9ce5c3c24982`).
Redeploy after any new evaluation with `make site` then a fresh Netlify deploy.

The site is static: no build step, no backend, no environment variables.

## Fastest — drag and drop (about 30 seconds)

1. Go to <https://app.netlify.com/drop>
2. Drag `ai-statistician-site.zip` (or the `site/` folder itself) onto the page
3. Netlify returns a live URL immediately

No CLI, no token, and no account needed to get the first URL — sign in afterwards
if you want to keep it or attach a custom domain.

## From a Git remote

Push the repository, then in Netlify choose **Add new site → Import an existing
project**. `netlify.toml` already declares the settings:

    publish   = "site"
    command   = ""          # nothing to build

## From the CLI

    npm install -g netlify-cli
    netlify login           # opens a browser for your account
    netlify deploy --prod --dir=site

## Regenerating the data

The explorer reads precomputed JSON. After any new evaluation:

    make site               # rewrites site/data/*.json
    make artifact           # rebuilds the single-file explorer.html

## Why there is no Python here

SciPy, statsmodels, NumPy and pandas total ~321 MB installed, against a 250 MB
unzipped ceiling for Netlify Functions. Reimplementing the statistics in
JavaScript would defeat the point of the project, which is that validated
libraries perform every numerical operation. The site therefore serves what the
system already computed; `make demo` runs the live analysis path locally.
