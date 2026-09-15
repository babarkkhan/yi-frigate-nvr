#!/bin/sh
# Install only on the validated cam1 firmware, mode 700, owned by root.
# Replace 192.0.2.10 with the NVR source address observed in SSH_CONNECTION.
case "$SSH_CONNECTION" in
"192.0.2.10 "*) ;;
*) exit 126 ;;
esac
case "$SSH_ORIGINAL_COMMAND" in
check)
    [ -p /tmp/audio_in_fifo ] || exit 1
    echo speaker-ready
    ;;
speaker)
    [ -p /tmp/audio_in_fifo ] || exit 1
    mkdir /tmp/frigate-speaker.lock 2>/dev/null || exit 75
    trap 'rmdir /tmp/frigate-speaker.lock 2>/dev/null' EXIT
    trap 'exit 1' HUP INT TERM
    cat > /tmp/audio_in_fifo
    ;;
*) exit 126 ;;
esac
