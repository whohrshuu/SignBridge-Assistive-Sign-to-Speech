# Deploy SignBridge — one Render web service + Supabase

The frontend and backend now run on the **same address**. No Cloudflare Pages project, manual frontend/config.js editing or cross-origin configuration is needed for this route.

## 1. Create/configure Supabase
1. Create/open your Supabase project.
2. Run `supabase/migrations/001_private_data.sql` in its SQL Editor once (if already applied, do not rerun the policy creation statements).
3. Enable Email sign-in in Authentication. Configure confirmation email delivery for your use.
4. Obtain the project URL and **publishable key** from the project Connect/API settings. Do not use a secret or service_role key.
5. Google sign-in is optional; if you use its button, enable the Google provider and configure the provider callback shown by Supabase.

## 2. Put the project in your GitHub repository
Upload the contents of `SignBridge-Production-MVP` to the repository root, including `frontend/vendor`, `gestures.js`, `api.py`, `requirements.txt`, `render.yaml` and `supabase/`. Do not upload local databases or credentials. For an existing repo, back up changes and commit this version normally; no force push is needed.

## 3. Deploy on Render
Create a **Web Service** connected to that repository, or use **New → Blueprint** with `render.yaml`.

| Setting | Value |
|---|---|
| Runtime | Python |
| Build command | `pip install -r requirements.txt` |
| Start command | `uvicorn api:app --host 0.0.0.0 --port $PORT` |
| Health check | `/api/health` |
| `SUPABASE_URL` | Your project URL |
| `SUPABASE_PUBLISHABLE_KEY` | Your publishable key |

Choose your plan in Render; check its current limits. The provided template selects its free plan. The former environment name `SUPABASE_ANON_KEY` remains supported for compatibility, but use the publishable-key setting for new configuration.

## 4. Finish authentication redirects
Once Render provides your `https://...onrender.com` address, set that as Supabase Authentication → URL Configuration → **Site URL**, and add the exact address (including the root slash variant if needed) to **Redirect URLs**. These settings control confirmation, password-reset and OAuth returns.

Open the Render address: it should show SignBridge's sign-in screen. There is no second frontend deployment. `/config.js` supplies only the public URL/key to the browser; private API requests require a verified user token.

## 5. Live verification
- Register/confirm/sign in; test sign-out and password recovery.
- Test all poses from README on your actual webcam, especially two open palms → I Need Assistance.
- Verify camera permissions over HTTPS and speech after clicking the app controls.
- Save samples/history in account A, then sign in as account B: A's entries must not appear. This live RLS check requires your real Supabase project; it has not been performed in this environment.
- Verify `/api/history` without a token returns 401.

Local authenticated preview (PowerShell, after installing requirements):
```powershell
$env:SUPABASE_URL="https://your-project.supabase.co"
$env:SUPABASE_PUBLISHABLE_KEY="your-publishable-key"
python -m uvicorn api:app --host 127.0.0.1 --port 8000
```
Add http://localhost:8000 to Supabase's redirects for local auth testing. Cloud database APIs need an internet connection.

This is a student project deployment configuration, not a certification of production security or universal gesture accuracy. Service monitoring, quotas/rate limiting and backups should be configured for broader public use.

Official references:
- https://render.com/docs/deploy-fastapi
- https://render.com/docs/configure-environment-variables
- https://supabase.com/docs/guides/auth/redirect-urls
- https://supabase.com/docs/guides/getting-started/api-keys
