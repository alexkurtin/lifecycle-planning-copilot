# Deploying the Lifecycle Planning Copilot

Goal: a single link your interviewer can click, with the AI features working and no setup on their end. We use **Streamlit Community Cloud** (free, built for Streamlit apps, deploys straight from GitHub). Budget about 10-15 minutes the first time.

The flow: push the repo to GitHub, deploy it on Streamlit Cloud, add your API key as a *secret* (never in the code), share the link.

---

## Step 0 — Your key is already protected

I added a `.gitignore` that excludes `.env` (where your real key lives) and any `.streamlit/secrets.toml`. I verified in a throwaway git repo that `.env` is ignored while the safe `.env.example` template is kept. So a committed key cannot happen as long as you do not remove those lines.

You will still confirm this yourself in Step 1 before the first push.

---

## Step 1 — Put the project on GitHub

From inside the project folder:

```bash
git init
git add .
git status          # <-- .env must NOT appear in this list. .env.example is fine.
git check-ignore .env   # should print ".env" (proves it is ignored)
```

**If `.env` shows up in `git status`, stop and do not commit.** It means the `.gitignore` is missing or edited. Otherwise continue:

```bash
git commit -m "Lifecycle Planning Copilot"
```

Create an empty repo at https://github.com/new (private is fine; Streamlit Cloud can deploy private repos), then:

```bash
git remote add origin https://github.com/<your-username>/lifecycle-planning-copilot.git
git branch -M main
git push -u origin main
```

---

## Step 2 — Make a dedicated API key with a spend cap (recommended)

So the hosted app cannot run up a surprise bill, and so you can shut it off cleanly after the interview:

1. Go to https://console.anthropic.com → **API Keys** → create a new key just for this demo (name it `lifecycle-demo`). Copy it once.
2. In **Billing / Limits**, set a low monthly spending limit (a few dollars is plenty: calls are cached, word-budgeted, and default to Sonnet).
3. After the interview, delete that one key. Nothing else you use is affected.

Cost in practice is tiny: one reviewer clicking a handful of "Draft" buttons is a few cents.

---

## Step 3 — Deploy on Streamlit Community Cloud

1. Go to https://share.streamlit.io and sign in with the **same GitHub account** that owns the repo. Authorize access if prompted.
2. Click **Create app** (top right) → **Deploy a public app from GitHub**.
3. Fill in:
   - **Repository:** `your-username/lifecycle-planning-copilot`
   - **Branch:** `main`
   - **Main file path:** `app.py`
   - **App URL:** pick a clean subdomain, e.g. `lifecycle-planning-copilot`.
4. Open **Advanced settings** before deploying and go to Step 4 (the secret). Then click **Deploy**.

Python 3.12 is the default and is correct for this app. First build takes a few minutes while it installs `requirements.txt`.

---

## Step 4 — Add your key as a secret (this is what makes the AI work)

In **Advanced settings → Secrets** (or later via your app's menu → **Settings → Secrets**), paste exactly this, with your real key:

```toml
ANTHROPIC_API_KEY = "sk-ant-...your-key..."
```

Two things that matter:
- Keep it at the **top, with no `[section]` header above it.** Streamlit exposes root-level secrets as environment variables, which is exactly how this app reads the key (`os.getenv("ANTHROPIC_API_KEY")`). Nest it under a section and the app will not see it.
- Use the **TOML format above** (key, space, `=`, space, value in quotes). Note this is different from the `.env` style (`ANTHROPIC_API_KEY=...`, no quotes). The format string is in `.streamlit/secrets.toml.example`.

Save. Streamlit reboots the app automatically.

---

## Step 5 — Test it, then share

1. Open your new URL. The seven pages should load with the dark-blue theme.
2. Go to **Executive Memo** (or any page) and click a **Draft** button. If a narrative appears with the green Verifier note, your key is wired correctly.
3. Send the link. That is the URL that goes in the email, in place of `[LIVE LINK]`.

---

## Good to know

- **The app sleeps after inactivity.** On the free tier, an unused app goes to sleep and takes ~30 seconds to wake on the next visit. Open it once an hour or so before you expect the interviewer to look, so it is warm.
- **Updates are automatic.** Any `git push` to `main` redeploys the app in a minute or two.
- **Taking it down:** your app's menu → **Settings → Delete app**. Then delete the `lifecycle-demo` API key in the Anthropic Console.
- **If the build fails:** it is almost always a missing package in `requirements.txt`. The current file already lists streamlit, pandas, numpy, plotly, python-dotenv, and anthropic, so it should build as-is.
- **If the AI says "no key found":** re-check Step 4 (root-level, TOML quotes, no section header), then reboot from the app menu.
