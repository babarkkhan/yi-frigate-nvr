# Camera naming - authoritative map

Renamed 2026-08-22: cam5 and cam6 swapped labels. The physical devices did not
move; only the names changed.

| # | Room | Frigate key | Hostname | IP | Serial | Platform |
|---|---|---|---|---|---|---|
| 1 | men's room | cam1_mensroom | yi-cam1-mensroom | 192.168.3.5 | BFUSY21xxxxxxxxxxxx | MStar y203c |
| 2 | living room | cam2_living | yi-cam2-living | 192.168.3.22 | BFUSY21xxxxxxxxxxxx | MStar y203c |
| 3 | kitchen | cam3_kitchen | yi-cam3-kitchen | 192.168.3.3 | BFUSY31xxxxxxxxxxxx | Allwinner y20ga |
| 4 | hallway | cam4_hallway | yi-cam4-hallway | 192.168.3.4 | BFUSY21xxxxxxxxxxxx | MStar y203c |
| 5 | **laundry** | cam5_laundry | yi-cam5-laundry | 192.168.3.149 | BFUSY21xxxxxxxxxxxx | MStar y203c |
| 6 | **extra** | cam6_extra | yi-cam6-extra | 192.168.3.6 | BFUSY31xxxxxxxxxxxx | Allwinner y20ga |

Serials confirm identity through the rename - cam5 is still the y203c at .149,
cam6 is still the y20ga at .6.

## Note on old recordings

Frigate stores recordings under the camera key. Footage recorded before the
rename lives in `cam5_extra/` and `cam6_laundry/` and will not appear in the UI
under the new names. With 2-day retention it ages out on its own; no action
needed unless something from before the rename matters.
