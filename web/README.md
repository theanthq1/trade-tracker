# Trade Desk web dashboard

This is a separate React/Vite frontend for the existing desktop trade tracker. It reads `public.trades`; it does not modify the Python collector or database schema.

## Local development

```bash
cd web
cp .env.example .env.local
# Edit .env.local with the Supabase project URL and publishable/anon key.
npm install
npm run dev
```

The Supabase Auth redirect URL must include the local URL (usually `http://localhost:5173`) and the GitHub Pages URL. Use an email/password account created in Supabase Auth.

## Security requirement

The current `trades` table has no `user_id`, so RLS cannot distinguish one signed-in user from another. Do not deploy a policy that exposes the table to `anon`. For a personal single-user deployment, an authenticated-only SELECT policy limits access to signed-in users, but it is not a multi-user ownership model. The secure multi-user model is to add `user_id`, populate it for each trade, update the Python collector to write it, and add `user_id = auth.uid()` policies. That migration is intentionally not included.

Before using the frontend, inspect `pg_policies` for `public.trades` in Supabase SQL Editor and ensure the policy matches your intended ownership model.

## GitHub Pages

Set repository Actions variables `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY`, then use the workflow at `../.github/workflows/deploy-dashboard.yml`. The app uses `/trading-dashboard/` as its default base path.
