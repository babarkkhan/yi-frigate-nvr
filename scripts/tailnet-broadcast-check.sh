#!/bin/bash
# Verify every part of the NVR is reachable over the tailnet, and time it.
# Run from the Windows side (git bash), NOT through wsl - a wsl command starts
# the distro and can mask an availability fault.
#
#   bash scripts/tailnet-broadcast-check.sh
BASE_TLS=https://home-nvr.<your-tailnet>.ts.net
BASE_RAW=http://home-nvr:5000
CAMS="cam1_mensroom cam2_living cam3_kitchen cam4_hallway cam5_laundry cam6_extra"
rc=0

hit() { # url label
  printf '  %-30s ' "$2"
  out=$(curl -s -o /dev/null -w '%{http_code} %{size_download} %{time_total}' --max-time 30 "$1" 2>/dev/null)
  set -- $out
  if [ "$1" = "200" ]; then printf 'HTTP 200  %8sB  %ss\n' "$2" "$3"
  else printf 'FAIL (%s)\n' "${1:-no response}"; rc=1; fi
}

echo "=== core ==="
hit "$BASE_RAW/api/version" "version"
hit "$BASE_RAW/api/stats"   "stats"
hit "$BASE_TLS/"            "web UI (via Serve)"
echo "=== live frame per camera ==="
for c in $CAMS; do hit "$BASE_RAW/api/$c/latest.jpg" "$c"; done
echo
[ $rc -eq 0 ] && echo "STATUS: all systems broadcasting over tailnet" \
              || echo "STATUS: one or more endpoints FAILED"
exit $rc
