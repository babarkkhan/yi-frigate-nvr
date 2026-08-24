# BFUS decision table

BFUS is a supported serial prefix — it appears in supported rows of **both**
yi-hack-MStar and yi-hack-Allwinner-v2. The serial prefix alone does NOT pick
the project. The **stock firmware version** does.

## The rule

The first digit of the stock firmware version identifies the hardware platform:

| Firmware starts with | Platform | Project |
|---|---|---|
| `4.x` | MStar | yi-hack-MStar |
| `9.x`, `11.x`, `12.0`, `12.1` | Allwinner | yi-hack-Allwinner-v2 |
| `12.2` or higher | Allwinner, **too new** | none — see below |

## Every BFUS row

| Firmware | Model | Project | Code |
|---|---|---|---|
| `4.5.0*` | Yi 1080p Home | MStar | y203c |
| `4.6.0*` | Yi 1080p Dome | MStar | h201c |
| `9.0.19*` or `12.1.19*` | Yi 1080p Home | Allwinner-v2 | y21ga |
| `9.0.22*` | Yi Dome U | Allwinner-v2 | h52ga |
| `9.0.05*` / `12.1.05*` (beta) | Yi 1080p Dome | Allwinner-v2 | r30gb |

## The risk: firmware that is too new

Confirmed case — a BFUS / y21ga on stock firmware `12.2.0.5_202411131404`
applied the hack via SD card and the HTTP/RTSP/Telnet services simply did not
start. Reported as issue #1125 on yi-hack-Allwinner-v2; **open and unresolved**.

Neither project documents a stock-firmware downgrade path. The wiki's
"Manual firmware upgrade" page covers upgrading the *hack*, not reverting
stock firmware. So a camera that has auto-updated past `12.1.x` currently has
**no documented route** to being flashed.

## Consequence for sequencing

1. Read the firmware version off every camera in the Yi app **first**, before
   anything else. This is the field that decides everything.
2. Once read, stop the cameras from updating further — block their internet
   access at the router. An auto-update between today and flashing day can
   silently move a camera from supported to unsupported.
3. Order of preference if versions differ across cameras: flash the one whose
   version matches a row most exactly, and do it first, as the test case.

## Sources
- https://github.com/roleoroleo/yi-hack-Allwinner-v2 (supported table)
- https://github.com/roleoroleo/yi-hack-MStar (supported table)
- https://github.com/roleoroleo/yi-hack-Allwinner-v2/issues/1125 (12.2.0.5 failure)
