# Printechs Support — Expo mobile app

React Native (Expo) client for the **Printechs Support** Frappe app. One app for customers and internal users; behavior follows the same **portal API** as the web SPA.

## Copy to your Windows folder

This project lives in the repo at `printechs_support/mobile/`. To use it under  
`D:\Development Project\Printechs Support\`:

1. Copy the entire `mobile` folder to that location, **or**
2. Clone the repo and open `printechs_support/mobile` in your editor.

Use **Node.js 20 LTS** (recommended by Expo SDK 54).

```bash
cd mobile
npm install
npx expo start
```

Scan the QR code with **Expo Go**, or press `a` for Android emulator.

## Configure the ERP site URL

Set your bench URL (HTTPS, no trailing slash):

- **Option A — environment file** (recommended): create `.env` in `mobile/`:

  ```env
  EXPO_PUBLIC_FRAPPE_URL=https://your-erp-site.com
  ```

  Restart Expo after changing `.env`.

- **Option B — `app.json`**: set `expo.extra.frappeUrl` to the same URL.

You can also type the URL on the **Sign in** screen each time; it is stored with the session.

## Sign in

1. **Email + password** — uses Frappe `/api/method/login` and session cookies. On some devices the OS does not expose `Set-Cookie` to the app; if sign-in fails, use API keys.

2. **API Key + API Secret** — in Desk: **User → Settings → API Access → Generate Keys**. Use the key and secret on the **API Key** tab of the login screen. This uses `Authorization: token …` and works reliably on mobile.

## Features (v1)

- Home dashboard (KPIs from `get_portal_dashboard_stats`)
- Tickets list → ticket detail → conversation (comments)
- Tasks list → task detail
- Agenda (tasks grouped by due date)
- New ticket (portal + internal customer selection)
- Offline banner (network awareness); data is online-first (extend with persisted cache later)

## Backend requirements

Same as the web portal: HTTPS, whitelisted `portal_api` methods, user roles (e.g. **Printechs Support Customer** or internal desk roles).

## Building for stores

Use [EAS Build](https://docs.expo.dev/build/introduction/) when you are ready for TestFlight / Play Console.
