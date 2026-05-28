# RUNBOOK — TLS / HTTPS Cutover (IIS)

Audience: IT engineer configuring IIS on the production VM hosting the
Wealth Planning v2 backend and frontend services.

## 1. Goal

Enable HTTPS for `team-dashboard.lighthouse-canton.com`, terminating TLS at
IIS in front of the FastAPI backend (127.0.0.1:8000) and the Next.js
frontend (127.0.0.1:3000). Success looks like:

- `https://team-dashboard.lighthouse-canton.com/` serves the login page.
- `https://team-dashboard.lighthouse-canton.com/health` returns HTTP 200.
- Browser DevTools shows the session cookie with `Secure`, `HttpOnly`,
  `SameSite=Lax` flags and the `__Secure-` name prefix.
- HTTP requests on `:80` are 301-redirected to HTTPS.
- An external TLS scan (SSL Labs or equivalent) reports no major findings
  and confirms TLS 1.2+ only.

The application code is already TLS-ready as of Phase 2 (PR
`feat/p0-phase-2-foundations`). Enforcement is gated by two environment
variables that are unset in Phase 2 and flipped on at Phase 3 cutover:

- `ENFORCE_HTTPS=true` — backend rejects non-HTTPS requests with HTTP 400.
- `NEXTAUTH_USE_SECURE_COOKIES=true` — Next.js issues `__Secure-` cookies
  with the `Secure` flag set.

## 2. Prerequisites

- Corporate-CA TLS certificate for `team-dashboard.lighthouse-canton.com`
  installed into the **Local Computer → Personal** certificate store on
  the VM. Confirm the cert chain is complete (no missing intermediates)
  via `certlm.msc`.
- IIS 10+ with the **URL Rewrite** module installed
  (`https://www.iis.net/downloads/microsoft/url-rewrite`).
- Backend FastAPI service running on `127.0.0.1:8000` (Windows service or
  scheduled task).
- Next.js service running on `127.0.0.1:3000`.
- Existing IIS bindings:
  - `http://team-dashboard.lighthouse-canton.com:8081` → reverse-proxies
    to the Next.js / backend. Leave this active until Phase 3 cutover.
- Firewall: confirm inbound TCP/443 is allowed on the VM's network
  security group / Windows firewall.

## 3. Configure IIS HTTPS listener

1. Open **IIS Manager** → select the site that fronts the dashboard.
2. Right-click the site → **Edit Bindings...** → **Add**.
3. Set:
   - Type: `https`
   - IP address: `All Unassigned` (or the VM's internal IP)
   - Port: `443`
   - Host name: `team-dashboard.lighthouse-canton.com`
   - Require Server Name Indication: checked
   - SSL certificate: select the corporate-CA cert imported above.
4. Click OK. Do **not** remove the existing port-8081 HTTP binding yet —
   we keep both listeners alive through Phase 2 so the current users
   are unaffected.
5. Confirm the reverse-proxy / URL Rewrite rules forwarding to
   `127.0.0.1:8000` (backend) and `127.0.0.1:3000` (frontend) apply to
   the new HTTPS binding. If they're site-level, no change needed.

## 4. Configure HTTP → HTTPS redirect

Add a URL Rewrite rule at the site level. In `web.config`:

```xml
<rewrite>
  <rules>
    <rule name="Redirect HTTP to HTTPS" stopProcessing="true">
      <match url="(.*)" />
      <conditions>
        <add input="{HTTPS}" pattern="off" ignoreCase="true" />
        <add input="{SERVER_PORT}" pattern="^80$" />
      </conditions>
      <action type="Redirect" url="https://{HTTP_HOST}/{R:1}"
              redirectType="Permanent" />
    </rule>
  </rules>
</rewrite>
```

The `SERVER_PORT == 80` condition deliberately leaves the existing
port-8081 HTTP binding alone during Phase 2. At Phase 3 cutover, remove
the port-8081 binding entirely (see step 6).

## 5. Health check (Phase 2 smoke test)

From an internal host on the corporate network:

```bash
curl -kI https://team-dashboard.lighthouse-canton.com/health
# expect: HTTP/1.1 200 OK

curl -I http://team-dashboard.lighthouse-canton.com/
# expect: HTTP/1.1 301 Moved Permanently
#         Location: https://team-dashboard.lighthouse-canton.com/

curl -I http://team-dashboard.lighthouse-canton.com:8081/health
# expect (Phase 2): HTTP/1.1 200 OK   (port-8081 still alive)
```

Drop the `-k` flag once the cert chain is verified.

## 6. Phase 3 cutover — flipping enforcement

When the team is ready to switch to HTTPS-only:

1. Update the backend service environment (e.g. `nssm edit
   WealthPlanningBackend` or the equivalent Task Scheduler action):
   - Add `ENFORCE_HTTPS=true`.
   - Confirm `X-Forwarded-Proto` is being passed through by the IIS
     reverse-proxy. URL Rewrite's ARR proxy adds it automatically; if
     the binding uses a custom rule, add a
     `<set name="HTTP_X_FORWARDED_PROTO" value="https" />` server
     variable.
2. Update the frontend service environment:
   - Add `NEXTAUTH_USE_SECURE_COOKIES=true`.
   - Confirm `NEXTAUTH_URL=https://team-dashboard.lighthouse-canton.com`.
3. Remove the port-8081 HTTP binding from the IIS site.
4. Restart both services:
   ```
   nssm restart WealthPlanningBackend
   nssm restart WealthPlanningFrontend
   ```
5. Re-run the smoke checks in section 5. Port 8081 should now refuse
   the connection; ports 80 and 443 behave as before.
6. Existing users will be signed out once (the cookie name changes from
   `next-auth.session-token` to `__Secure-next-auth.session-token`).
   This is expected.

## 7. Rollback

If the cutover causes user-visible breakage:

1. Re-add the port-8081 HTTP binding in IIS Manager.
2. Remove `ENFORCE_HTTPS` and `NEXTAUTH_USE_SECURE_COOKIES` from both
   service environments (or set them to anything other than `true`).
3. Restart both services.
4. Users on the new HTTPS cookie will be signed out once more when the
   cookie name flips back; that's the trade-off for a fast rollback.

The HTTPS listener and redirect rule stay in place — rolling back only
the enforcement leaves the safer-by-default infrastructure intact.

## 8. Verifying secure cookies in the browser

After Phase 3:

1. Open Chrome DevTools → **Application** → **Cookies** →
   `https://team-dashboard.lighthouse-canton.com`.
2. Confirm a cookie named `__Secure-next-auth.session-token` exists.
3. Confirm its flags:
   - `HttpOnly`: checked
   - `Secure`: checked
   - `SameSite`: `Lax`
   - `Path`: `/`
4. The non-`__Secure-` variant should not appear. If it does, the
   frontend service didn't pick up `NEXTAUTH_USE_SECURE_COOKIES=true`
   — re-check the env var and restart.

## 9. External TLS scan

Run an external scan once the deployment is reachable from the
internet-facing path (or from an equivalent internal scanner if the host
is intranet-only):

- SSL Labs: `https://www.ssllabs.com/ssltest/analyze.html?d=team-dashboard.lighthouse-canton.com`
- Or `testssl.sh` from a Linux host with internal network access.

Acceptance criteria:

- TLS 1.2 and 1.3 only — TLS 1.0 / 1.1 / SSLv3 disabled.
- Cipher suites: no RC4, no 3DES, no NULL, no EXPORT.
- Certificate chain validates without warnings.
- HSTS header optional in Phase 3, recommended in Phase 4 once the
  team is confident the redirect path is stable.

Document the scan output in the change-management ticket alongside the
cutover record.
