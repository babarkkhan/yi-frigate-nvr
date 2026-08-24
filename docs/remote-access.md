# Remote access via Tailscale

Built and validated, but **inert until you add an auth key**. Nothing is
running yet.

## What it does

Adds a Tailscale sidecar that serves Frigate at:

    https://home-nvr.<your-tailnet>.ts.net

from any device on your tailnet - phone, laptop, anywhere. Real HTTPS via
Tailscale's certs, no browser warnings.

**Nothing is exposed to the public internet.** No port forwarding, and
Tailscale Funnel is deliberately left off (`"AllowFunnel": {}` in serve.json).
If you ever want a genuinely public URL you would have to opt in explicitly -
don't, for cameras.

## Turning it on, when you want it

1. Create a **reusable, non-ephemeral** auth key at
   https://login.tailscale.com/admin/settings/keys
2. `cp secrets/tailscale.env.example secrets/tailscale.env` and paste the key.
   That file is gitignored.
3. Start with the overlay:

       docker compose -f compose.yaml -f compose.tailscale.yaml up -d

4. Approve the device in the Tailscale admin console if your tailnet requires it.
5. Visit `https://home-nvr.<tailnet>.ts.net`.

To go back to local-only, just `docker compose up -d` without the overlay.

## Design choices

**Container, not Tailscale-on-Windows.** Running Tailscale on the Windows host
would work and is simpler to click through, but it puts the *whole machine* on
the tailnet and lives outside this repo. The sidecar exposes exactly one thing -
Frigate - and its configuration is version controlled.

**Userspace networking** (`TS_USERSPACE: "true"`). No `/dev/net/tun`, no
`NET_ADMIN` capability. This matters because the stack runs inside WSL2 where
TUN access is awkward. Slightly lower throughput, irrelevant for a web UI.

**Tailscale Serve, not just a tailnet IP.** Serve terminates TLS and proxies to
`http://frigate:5000` over the internal docker network, so the browser gets a
real certificate rather than a self-signed warning.

## Before you rely on it

- **This PC must not sleep.** It is the NVR now. Sleep means no recording and
  no remote access. Set the power plan to never sleep, and confirm WSL and
  Docker start on boot.
- **Frigate has its own login.** Auth is enabled (`.jwt_secret` exists in the
  config dir). On first start Frigate creates an `admin` user and prints a
  generated password in the logs. If you never captured it:

      docker exec -it frigate python3 -m frigate --reset-admin-password

- Tailscale ACLs can restrict which of your devices reach the NVR. Worth doing
  if the tailnet has devices you would not want on the camera feed.

## When this moves to the EQ14

The overlay ports unchanged. Drop `TS_USERSPACE` if you give the container
`/dev/net/tun` and `NET_ADMIN` on a normal Linux host - marginally faster, not
required.
