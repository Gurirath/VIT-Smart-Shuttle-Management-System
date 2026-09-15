# Architecture Notes — Proposed / Future Work

**Status: design proposal. None of the changes described here are implemented in the
current codebase.** This note documents how the present VIT Smart Shuttle prototype
would have to evolve to support three architectural directions requested for the next
iteration. It is written to sit alongside the methodology section of the paper/patent
submission and to make explicit which behaviour is *current* and which is *proposed*.

---

## Current architecture (baseline for the discussion below)

The deployed prototype is a single-tier, stream-oriented system:

- The on-vehicle unit (ESP32 sketch `VIT-Shuttle.ino`, mirrored by
  `vit_smart_shuttle_gui.py` for desktop simulation) publishes **every sensor event as
  it happens** to a public MQTT broker (`broker.hivemq.com`) on three topics:
  `vit/shuttle1/gps`, `vit/shuttle1/seat`, and `vit/shuttle1/billing`. GPS is emitted
  on a fixed cadence; seat-state and billing (`ENTRY` / `EXIT`) messages are emitted on
  transition. If Wi-Fi/MQTT is unavailable the unit falls back to GSM and continues
  publishing the same messages.
- A FastAPI backend (`backend/`) runs an MQTT client (`mqtt_client.py`) that consumes
  each message individually and writes it straight into **one SQLite database**
  (`vit_shuttle.db`) through SQLAlchemy. Every GPS message also appends a
  `VehicleLogEntry` row. The React dashboard polls the REST API roughly once per
  second for near-real-time display.
- Passenger identity is currently synthetic: the vehicle unit fabricates sequential
  IDs (`VIT21001`, `VIT21002`, …) on each face-scan button press, and the backend
  auto-registers any unknown ID it receives (`process_entry` in `mqtt_client.py`).

The three proposals below change, respectively, *when* data leaves the vehicle, *where*
it is stored, and *how* a passenger is identified.

---

## 1. Trip-wise data batching instead of continuous MQTT streaming

**Current behaviour.** The vehicle unit is a pure publisher: each GPS fix, seat change,
and billing event is transmitted the moment it is generated, and the backend commits it
row-by-row. Connectivity loss is handled only by switching transport (Wi-Fi → GSM); if
both are down, messages are lost because nothing on the vehicle retains them.

**Proposed change.** Treat a *trip* (shuttle departs a terminus → returns / completes
its loop) as the unit of transfer. During a trip the vehicle unit writes every reading
to a local append-only store (see §2) and transmits **nothing** except, optionally, a
low-rate "vehicle alive + coarse position" heartbeat for the live map. When the trip
ends (detected by the existing route-completion / long-idle condition already tracked
on the unit), the unit assembles one **trip batch**: trip metadata (shuttle ID, start/
end time, start/end GPS, route), the ordered GPS track, the seat-occupancy timeline,
and the list of `ENTRY`/`EXIT` billing records with their per-passenger distance and
fare. This batch is uploaded as a single message (or a single HTTP `POST /api/trips/
batch`) and acknowledged atomically.

**Implications for the current code.**
- The MQTT topic set collapses from a continuous per-event stream to one
  `vit/shuttleN/trip` publish per completed trip (plus the optional heartbeat topic).
  `mqtt_client.py` gains a `process_trip_batch()` that validates the batch, then
  performs the same inserts it does today (`Trip`, `Seat` history, `VehicleLogEntry`)
  inside **one transaction** per trip rather than one transaction per message.
- Delivery becomes reliable without a message broker guaranteeing it: the vehicle
  keeps the batch in local storage until it receives an application-level ACK, then
  marks it `synced`. A dropped connection during upload simply means the batch is
  retried on the next window; nothing is lost and nothing is double-counted because
  the batch carries a deterministic `trip_id`.
- Bandwidth and broker load drop by roughly the ratio of (events per trip) to (1),
  and GSM data cost becomes predictable — one upload per trip instead of a live stream.
- Trade-off: the live dashboard loses true second-by-second fidelity for in-progress
  trips. The heartbeat keeps the map usable; full detail for a trip appears once it
  completes. This is acceptable for an operations/billing tool and is the main design
  cost to acknowledge in the evaluation.

---

## 2. Two-tier storage: on-vehicle DB syncing to a central college server

**Current behaviour.** There is exactly one database. The backend's SQLite file is the
only persistent store; the vehicle unit holds no database at all, only transient
in-memory sensor state.

**Proposed change.** Introduce two tiers with a clear ownership boundary.

*Tier 1 — vehicle-local DB.* A small embedded database on the on-vehicle compute unit
(SQLite or an equivalent flash-friendly store; LittleFS-backed on a bare ESP32, or a
real SQLite file if the unit is upgraded to a Raspberry-Pi-class board). It holds only
**current and recent trips** — a rolling window of, say, the last N trips or last 7
days — plus a `sync_state` table. It is the system of record *while a trip is in
progress* and the buffer that makes §1's batching reliable. Schema is a subset of the
current models: `trip`, `gps_sample`, `seat_event`, `billing_event`, each tagged with
`trip_id` and a `synced` flag.

*Tier 2 — central college server DB.* A server-class database (PostgreSQL is the
natural upgrade from the prototype's SQLite) hosted on college infrastructure, holding
the **permanent, fleet-wide** record: every completed trip from every vehicle, the
student roster, fee accounts, request history, and aggregate reporting tables. The
FastAPI backend and the React dashboard talk only to this tier.

*Synchronisation.* One-directional for trip data: when a trip completes, its rows move
vehicle → server as the §1 batch. The server assigns nothing — the vehicle-authored
`trip_id` is globally unique (e.g. `SHUTTLE01-20260829-014`) so the upload is
idempotent and a retried batch is a no-op. After the server ACKs, the vehicle marks
those rows `synced` and is free to prune them once they age out of the local window.
Reference data that the vehicle needs (roster deltas, fee-account status, firmware/
config) syncs server → vehicle on connect, so an offline vehicle keeps working against
its last-known snapshot.

**Implications for the current code.**
- `mqtt_client.py` stops being the write path for live events and becomes the
  **ingestion endpoint** for trip batches landing on Tier 2.
- The current `vit_shuttle.db` is re-cast as the Tier 2 schema and migrated to
  Postgres; `database.py` already centralises the connection URL, so this is a
  configuration and migration change, not a rewrite of the routers.
- `process_entry`'s "auto-register any unknown ID" behaviour is removed: on Tier 2,
  an unknown register number is a hard error or a flagged exception, because identity
  now comes from the roster sync and (see §3) the biometric app, not from IDs the
  vehicle invents.
- New operational concerns to document: clock discipline on the vehicle (trip
  timestamps come from the unit, so it needs NTP-on-connect or GPS time), local-store
  wear/size limits, and a monitoring signal for "vehicle has unsynced trips older
  than X hours".

---

## 3. Interfacing with VIT's existing biometric / attendance app for face verification

**Current behaviour.** Face verification is simulated. The vehicle unit treats a short
button press as a verified boarding and a long press as an alighting, and it generates
a fresh sequential pseudo-ID for every boarding. The backend trusts whatever ID
arrives and creates a student record for it if none exists. No real recognition,
enrolment, or identity check occurs anywhere in the pipeline.

**Proposed change.** Delegate identity to VIT's existing biometric/attendance
platform, which already holds enrolled face templates and the authoritative
student/staff directory, and which the institution already operates for classroom
attendance. The shuttle system becomes a **consumer** of that platform's verification
result rather than an identity system in its own right.

**Proposed integration shape.**
- *Enrolment:* none on the shuttle side. The shuttle system never stores or transmits
  face images or templates. It only ever handles the register number that the
  biometric platform returns after a successful match, keeping biometric data inside
  the system already approved to hold it.
- *At boarding:* the on-vehicle camera captures a frame and calls the biometric
  platform's verification API — either directly (if the vehicle has connectivity) or
  via the campus edge when the shuttle is in range of a stop. The platform responds
  with `{matched: true, register_number, confidence}` or `{matched: false}`. Only on a
  match does the unit emit the `ENTRY` billing event, now carrying the **real**
  register number instead of a fabricated one. A non-match falls back to a manual
  path (ID-card tap / conductor override) so a failed recognition never blocks
  boarding.
- *Offline case:* if the platform is unreachable, the unit queues the captured frame
  reference plus timestamp and seat, and boards the passenger provisionally against a
  temporary token. The verification call is retried from the §1/§2 sync path when
  connectivity returns; the trip batch is then reconciled server-side so the fare
  attaches to the correct student. Provisional-then-reconciled boardings are flagged
  for audit.
- *Attendance reuse:* because the same verification event establishes that a given
  student physically boarded a shuttle at a known time and stop, it can optionally be
  forwarded to the attendance platform as a location/movement record, without the
  shuttle system itself becoming an attendance authority.

**Implications for the current code.**
- The `ENTRY`/`EXIT` billing contract gains a verified-identity field and a
  verification-status field (`verified`, `provisional`, `manual`). `process_entry`
  loses its auto-registration branch entirely — every boarding now resolves to a real
  roster entry, immediately or after reconciliation.
- A new backend service wraps the biometric platform's API (auth, ret/timeout policy,
  confidence threshold) and is the only component that talks to it; the routers and
  the dashboard stay unaware of biometrics and continue to work in terms of register
  numbers.
- Privacy posture to state explicitly in the paper: no biometric data at rest or in
  transit within the shuttle system; identity is a returned identifier; all
  face-template handling remains the responsibility of the existing, already-governed
  campus platform.

---

## Summary of the change surface

| Area | Current | Proposed |
|---|---|---|
| Data egress from vehicle | Per-event MQTT stream | One trip batch on completion (+ heartbeat) |
| Reliability on connectivity loss | Transport fallback only; data lost if fully offline | Local store + ACK'd batch upload, retried, idempotent |
| Storage | Single SQLite DB in the backend | Tier 1 rolling DB on vehicle → Tier 2 central server DB |
| `mqtt_client.py` role | Row-by-row live writer | Trip-batch ingestion + validation |
| Passenger identity | Vehicle-fabricated sequential IDs, backend auto-registers | Real register number from VIT biometric platform; no auto-register |
| Biometric data in this system | N/A (simulated) | None — identity consumed as an identifier only |

All items above are proposed for a subsequent development phase and are not reflected in
the current prototype, its database, or the accompanying screenshots.
