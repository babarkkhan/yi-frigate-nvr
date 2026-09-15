# Google-authenticated camera website

**Public templates are sanitized.** Replace `example.com` and the documentation
address `203.0.113.10` with your own domain and relay IP before deployment.
The private deployment repository holds the installed values. Do not overwrite
those values by copying a public template directly onto a running system.

Deployment: **2026-09-15, Riyadh time**. The gateway and tunnel are running.
**DNS and HTTPS are verified. Real Google-login/phone acceptance remains pending.**

## What the owner needs to do

1. In the authoritative DNS service for `example.com`, create:

   | Type | Name | Value | TTL |
   |---|---|---|---|
   | A | `cam` | `203.0.113.10` | 300 seconds, or provider default |

   Use a direct DNS record, without a CDN proxy. Do not add an AAAA record:
   this deployment was tested over IPv4. At deployment the camera hostname
   returned NXDOMAIN. DNS management credentials were not
   available to this task. There is no home-router port forwarding to configure.

2. Once DNS resolves, open **https://cam.example.com** and sign in with the
   Google account already allowed by the server's existing login. The Google
   OAuth callback remains on `auth.example.com`; no new OAuth client is needed.
   Additional accounts require an explicit allowlist change by the
   owner/developer and an application-authorization review as described below.

3. Turn off Tailscale on the phone and test on mobile data as well as home Wi-Fi:
   open a camera, unmute, switch Data saver / Full resolution, and play a recent
   recording. Compare a clap or visible clock with the live picture. Check both
   Android Chrome and iPhone Chrome. Backend tests cannot establish audible
   sound, browser playback behavior, or glass-to-glass delay on those devices.

Caddy automatically requests the HTTPS certificate when DNS points here. If it
is still backing off from earlier NXDOMAIN failures, the developer can run:

```sh
caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
caddy reload --config /etc/caddy/Caddyfile --adapter caddyfile --force
```

Check certificate issuance in `journalctl -u caddy`; never work around a browser
certificate warning. The new hostname's certificate was not issuable while DNS
was absent.

## Deployed route

```text
Phone browser (HTTPS; Google session)
  -> Hetzner Caddy :443
     -> existing OAuth2 Proxy :4180 (authentication subrequest)
     -> VPS loopback :18971
        -> outbound SSH connection from home
           -> WSL loopback :18971 -> Frigate :8971
```

The website is a viewer for all six cameras. Trusted LAN/tailnet administration
continues on port 5000. The public gateway never forwards to that unauthenticated
port, the cameras, or go2rtc's management port. Tailscale is not part of this
website's transport. Recording and GPU video processing stay at home; the VPS
relays browser traffic and does not continuously ingest or transcode all cameras.

The existing Data saver streams remain the default: 960 pixels wide, targeting
10 fps and 400 kbit/s video, with audio and transport overhead in addition.
Full resolution remains selectable. Media uses MSE over authenticated WebSockets
and recording playback over HTTPS. This does not provide public WebRTC/TURN or
two-way speech; those are separate work. Keep MSE/automatic playback selected.

The tested software is Caddy 2.6.2, OAuth2 Proxy 7.7.1 and Frigate 0.17.2.
Check the relay's available CPU, memory and provider traffic allowance before
deployment; bandwidth grows with viewer-hours and stream bitrate. Existing
applications and sites were preserved. No package upgrade was performed.

## Files and trust boundaries

### Guests on a shared Google login

Adding a camera guest to the shared OAuth email list can also admit them to
other applications using that login. Install application-specific authorization
before expanding that list. This deployment adds the private
`camera-only-users.caddy` guard to the existing portal, after `forward_auth` and
before its upstream, inside an explicit `route` block. Clear client-supplied
`X-Auth-Request-Email` before authentication. The example in `services/gateway/`
contains a placeholder; actual email addresses stay in the private deployment.

The added camera viewer is denied by that portal guard. Existing portal users
and the pre-existing allowed-email-domain policy are preserved. Additional
protected applications must define their own authorization policy before
reusing this shared login. Public applications are unaffected.

An isolated auth-stub test using the installed Caddy routes verified camera
viewer access (200), Frigate administration denial (403), guest portal denial
(403), retained existing portal access (200), and anonymous redirects (302).
The camera test used the real Frigate backend through the SSH relay. It did not
perform the guest's actual Google sign-in. The six-camera health check passed
after the OAuth service restart.

### Installed files

| Location | Purpose |
|---|---|
| Repo `services/gateway/cam.caddy` | Google gate, viewer headers, reverse proxy, private cache policy |
| VPS `/etc/caddy/Caddyfile` | Existing sites plus import of `/etc/caddy/cam.caddy` |
| VPS `/etc/caddy/cam-proxy-secret.caddy` | Private shared secret, root:caddy, mode 0640 |
| Repo `services/gateway/sshd-nvr-tunnel.conf` | Installed as VPS `/etc/ssh/sshd_config.d/60-home-nvr.conf` |
| VPS `/var/lib/nvr-tunnel/.ssh/authorized_keys` | Dedicated public key restricted to loopback port 18971 |
| WSL `/etc/home-nvr/tunnel_ed25519` | Dedicated private key, root only, mode 0600 |
| WSL `/etc/home-nvr/known_hosts` | VPS key obtained over the already trusted SSH connection |
| WSL `/etc/home-nvr/tunnel.env` | `NVR_RELAY_HOST=203.0.113.10` |
| WSL `/etc/systemd/system/home-nvr-tunnel.service` | Persistent outbound transport; enabled at boot |
| Private deployment `secrets/frigate.env` | Random `FRIGATE_PROXY_SECRET`, never committed |
| VPS `/usr/local/sbin/check-camera-gateway.py` | Read-only manual transport/recording check |

The two shared-secret copies must match. The VPS snippet is a single directive:
`header_up X-Proxy-Secret <private random value>`. Generate at least 32 random
bytes for a new installation; do not deploy the example placeholder. Frigate
expands `{FRIGATE_PROXY_SECRET}` from its container environment at startup.

Frigate's native login is disabled **only in conjunction with** the proxy secret,
viewer role mapping, and loopback publishing of 8971. TLS on that endpoint is
disabled because this hop is loopback plus encrypted SSH. Never publish 8971
with these settings or weaken the secret check. Port 5000 retains its existing
trusted-network behavior. Do not forward it from the internet.

Caddy discards client identity, role, proxy-secret and Authorization headers,
then obtains the user's email from the real OAuth service and supplies a fixed
`viewer` role. The existing OAuth service uses a parent-domain secure session
cookie and an explicit email allowlist. This route grants no admin role.
The dedicated SSH user cannot open shells, use local forwarding, or bind an
arbitrary remote port. SSH server `GatewayPorts no` keeps its listener private.

Google sessions are checked on each HTTP request and WebSocket establishment.
Caddy 2.6.2 does not support `stream_timeout`; an already-open stream is not
reauthenticated continuously. For urgent revocation, revoke the user's session
or allowlist access and **force-reload Caddy** to disconnect existing streams.
This may also disconnect streams on other existing sites. Test revocation with
the actual OAuth session policy when adding users. This is a shared VPS with
other applications, not strong isolation from compromise of those applications
or server root.

## Evidence from deployment

- Before and after the coordinated Frigate restart, all six recent recording
  samples decoded with H.264 video and AAC audio; no decoder errors were reported.
- VPS loopback 18971 returned 401 without a secret or with a wrong secret.
  Correct credentials returned a viewer profile; user administration returned
  403. The configuration response did not expose the shared secret.
- Production HTTPS requests sent through the existing valid `auth` TLS hostname
  with `Host: cam.example.com` redirected to Google login for the camera root,
  API and MSE route, including requests with forged identity/role headers.
  This tests the deployed host route, **not** the missing camera DNS/certificate.
- A temporary, loopback-only OAuth stub exercised a separate Caddy process using
  the deployed camera route. Without its synthetic cookie, forged identity was
  rejected; with it, the real backend still reported viewer and denied admin.
  Production OAuth was never bypassed or modified. Temporary listeners were
  removed after testing. A real Google sign-in remains pending.
- Through that route and the real SSH transport, six concurrent Data saver MSE
  samples decoded: MStar 960x544, Allwinner 960x540, H.264 + AAC. Cam5 Full
  resolution decoded at 1920x1088 with AAC. These were short samples, not a soak.
  Cold Data saver startup was 5.24–6.20 seconds; cam5 Full resolution startup
  was 2.04 seconds. Startup time is **not** ongoing viewing latency.
- Cam5 recording playback through the same proxy returned an HLS playlist and
  media, plus an MP4 clip. The clip decoded at 1920x1088 with AAC and no errors.
- Killing the tunnel's SSH process caused a measured disconnect followed by a
  protected responding endpoint after about 11.3 seconds. systemd recorded one
  automatic restart. Frigate's start timestamp did not change.
- Caddy, OAuth2 Proxy and the existing applications remained active. The existing
  portal still redirected to login. No broad regression test of other apps was
  performed.

## Operation and recovery

On the VPS, this check does not invoke WSL or repair the state it measures:

```sh
python3 /usr/local/sbin/check-camera-gateway.py
ss -lnt | grep 18971
systemctl is-active caddy oauth2-proxy
```

The JSON check fails for incorrect authorization, a non-viewer profile, missing
capture, or recordings older than 120 seconds. A five-second allowance for future
segment end timestamps avoids false alarms from small clock skew. It does not prove public DNS/TLS,
Google login, playable media, or deliver alerts. It is installed for manual use;
no scheduled monitor or external notification service was added. The broader
[unattended recovery/independent alerting gap](unattended-recovery-and-alerts.md)
remains open.

For deliberate repair/inspection inside WSL:

```sh
systemctl status home-nvr-tunnel
journalctl -u home-nvr-tunnel --since '15 minutes ago'
systemctl restart home-nvr-tunnel
```

Invoking WSL can start a stopped distro: do not use those commands as an
independent uptime measurement. The tunnel retries after 10 seconds; SSH
keepalives detect an unresponsive peer in roughly 45 seconds. Existing Windows
WSL keepalive/startup tasks are still necessary. Tunnel recovery cannot repair
camera failure, an offline Windows host, or a stopped Docker/Frigate stack.
Use the existing `scripts/restart-nvr.sh --apply` for a coordinated NVR restart.

Before changing SSH restrictions, run `sshd -t`, reload `ssh`, and verify a
separate administrator connection still works. Before changing Caddy, validate
the complete Caddyfile and reload it. It also contains other applications and
a private Authorization value; do not replace or publish it wholesale.

## Rollback

To remove the website, remove only `import /etc/caddy/cam.caddy` from the existing
Caddyfile, validate, then force-reload Caddy. Disable the WSL tunnel with
`systemctl disable --now home-nvr-tunnel`. Home recording is independent of it.

For a complete Frigate rollback, restore the pre-gateway `compose.yaml` and
`services/nvr/config/config.yml` from the private
`runtime/gateway-backup/<timestamp>/` backup and use the coordinated restart.
That backup also includes the pre-change environment file. Do not remove the
proxy secret while the gateway configuration still references it. The VPS
pre-change Caddyfile is `/etc/caddy/Caddyfile.before-home-nvr`; use it only if no
other site has changed since that backup. Remove the dedicated account/key and
SSH drop-in only after disabling the tunnel. Leave the existing Google login
and other sites intact.

## Reference implementation checks

- [Frigate 0.17.2 proxy configuration](https://github.com/blakeblackshear/frigate/blob/v0.17.2/frigate/config/proxy.py)
- [Frigate 0.17.2 authentication handling](https://github.com/blakeblackshear/frigate/blob/v0.17.2/frigate/api/auth.py)
- [Frigate 0.17.2 live player](https://github.com/blakeblackshear/frigate/blob/v0.17.2/web/src/components/player/LivePlayer.tsx)
- [Caddy forward_auth](https://caddyserver.com/docs/caddyfile/directives/forward_auth)
- [OpenSSH server restrictions](https://man.openbsd.org/sshd_config)

The installed source/configuration was checked as well as these references.
