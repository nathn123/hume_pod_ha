# Hume Body Pod for Home Assistant

[![Validate](https://github.com/danfulton72/hume_pod_ha/actions/workflows/validate.yml/badge.svg)](https://github.com/danfulton72/hume_pod_ha/actions/workflows/validate.yml)
[![Tests](https://github.com/danfulton72/hume_pod_ha/actions/workflows/tests.yml/badge.svg)](https://github.com/danfulton72/hume_pod_ha/actions/workflows/tests.yml)

A local, cloud-free Home Assistant integration for the **Hume Health Body Pod** smart scale. It talks to the scale over Bluetooth (any HA Bluetooth adapter or ESPHome Bluetooth proxy), so weigh-ins need no Hume account or phone. Several people can share one scale: each weigh-in is matched to the right person automatically by weight and body fat.

Protocol and body-composition maths are based on [Blue2Scale](https://github.com/JozefJarosciak/Blue2Scale.com) by Jozef Jarosciak, ported from JavaScript to Python.

## How it works

1. The Body Pod sleeps until you tap or step on it, then advertises over BLE for ~30 seconds.
2. Home Assistant sees the advertisement, connects, and starts a measurement.
3. The scale streams weight packets until the weight locks. **Stay on, barefoot, and hold the retractable hand bar with your arms out** until the scale finishes: it then measures segmental impedance (arms, trunk, legs) on two frequency bands, called the *low band* and *high band* below (the exact frequencies are unverified - see [Impedance input](#impedance-input)). Without the hand bar only weight is recorded. The Status sensor and the dashboard card show *Analysing body composition* during this stage; step off once it finishes.
4. The integration works out who it was (see below), computes 39 body-composition metrics with that person's profile, and updates their sensors.

Weigh-ins with socks on (or stepping off early) still record **weight** and **BMI**; body-composition sensors keep their previous values.

## Installation

**HACS:** HACS → ⋮ → Custom repositories → add `https://github.com/danfulton72/hume_pod_ha` as type *Integration* → install **Hume Body Pod** → restart Home Assistant.

**Manual:** copy `custom_components/hume_pod` into your `config/custom_components/` folder and restart.

Requires Home Assistant 2025.6 or newer with Bluetooth working, and the scale in range of an adapter or [ESPHome Bluetooth proxy](https://esphome.io/components/bluetooth_proxy.html) that supports active connections (`bluetooth_proxy: active: true`). A passive-only proxy can see the scale but can't talk to it. The integration's own icon shows in HA 2026.3 and later.

## Setup

Tap the scale to wake it. HA should show a *Discovered: Body Pod* card; otherwise go to **Settings → Devices & services → Add integration → Hume Body Pod**. Setup asks for the first person's details.

To add more people, open the integration and choose **Add person**. To change someone's height, date of birth and so on, use the ⋮ menu next to their name → **Reconfigure**. Age is recalculated from date of birth at every weigh-in.

Giving each person an **approximate weight** when you add them lets the very first weigh-ins be matched straight away.

## Who stepped on? Automatic matching

For every weigh-in the integration compares the reading with each person's previous weigh-in:

- **Weight**: a person is only considered if the reading is within the *weight tolerance* (default 3 kg) of their last weight.
- **Body fat**: when the reading includes impedance, body fat is calculated with *each candidate's own profile* and compared with their last body fat, scaled by the *body fat tolerance* (default 4 percentage points). This separates people of similar weight.
- The closest person wins. If two people are too close to call, or nobody is within tolerance (a guest, or a big change after a holiday), the reading is kept as an **unassigned weigh-in** instead of polluting anyone's history.
- An **approximate weight** entered at setup is treated as a rough guess: it gets three times the weight tolerance until that person's first real weigh-in.
- If only one person is set up and they haven't weighed in yet, the weigh-in goes to them whatever their approximate weight. Likewise, if someone has no history or estimate and nobody else matches, it goes to them.

Adjust both tolerances under the integration's **Configure** button.

### Unassigned weigh-ins

The scale device has an **Unassigned weigh-in** sensor showing the weight, with attributes explaining why it wasn't matched. Resolve it with:

- `hume_pod.assign_weigh_in`: pick the person's device; the weigh-in is recorded for them, with body composition calculated from their profile.
- `hume_pod.discard_weigh_in`: pick the scale device to throw it away.

An actionable phone notification is a convenient way to do this:

```yaml
automation:
  - alias: Body Pod - who was that?
    triggers:
      - trigger: state
        entity_id: sensor.body_pod_unassigned_weigh_in
        not_to: [unknown, unavailable]
    actions:
      - action: notify.mobile_app_phone
        data:
          message: "Unassigned weigh-in: {{ trigger.to_state.state }} kg"
          data:
            actions:
              - action: HUME_ASSIGN_DAN
                title: Dan
              - action: HUME_ASSIGN_SAM
                title: Sam
              - action: HUME_DISCARD
                title: Discard

  - alias: Body Pod - handle answer
    triggers:
      - trigger: event
        event_type: mobile_app_notification_action
        event_data: { action: HUME_ASSIGN_DAN }
        id: dan
      - trigger: event
        event_type: mobile_app_notification_action
        event_data: { action: HUME_ASSIGN_SAM }
        id: sam
      - trigger: event
        event_type: mobile_app_notification_action
        event_data: { action: HUME_DISCARD }
        id: discard
    actions:
      - choose:
          - conditions: "{{ trigger.id == 'discard' }}"
            sequence:
              - action: hume_pod.discard_weigh_in
                data:
                  scale: "{{ device_id('sensor.body_pod_status') }}"
        default:
          - action: hume_pod.assign_weigh_in
            data:
              person: "{{ device_id('sensor.' ~ trigger.id ~ '_weight') }}"
```

## Dashboard

The integration ships a **Hume Body Pod card**, modelled on the [Blue2Scale](https://github.com/JozefJarosciak/Blue2Scale.com) web app. It loads automatically: there's no dashboard resource to add.

| Overview | Body map | Trends |
| --- | --- | --- |
| ![Overview](docs/card-overview.png) | ![Body map](docs/card-body-map.png) | ![Trends](docs/card-trends.png) |

<sub>Screenshots rendered with sample data.</sub>

- **Overview:** weight, body fat, muscle and water with 30-day change and sparklines; a body-composition donut; key metrics (BMI, visceral fat, BMR, metabolic age, bone mineral); fat, lean and hydration breakdowns.
- **Body map:** male or female silhouette coloured by segment, switchable between muscle, fat % and fat mass, using Blue2Scale's ratings.
- **Trends:** charts for weight, body fat, muscle and lean mass, lean vs fat, body water, BMI and metabolic age, plus any metric you pick, over 1W/1M/3M/6M/1Y/ALL, from Home Assistant's long-term statistics. Hover or tap for values.
- Person switcher, a live "Measuring…" banner while someone is on the scale, and buttons to assign or discard an unassigned weigh-in.
- Follows your HA theme (light/dark) and unit system (kg/lb). Tap a value for its history.

**Ready-made dashboard:** create a new dashboard (Settings → Dashboards → Add dashboard → New dashboard from scratch), open it, choose Edit → ⋮ → Raw configuration editor, and paste [`dashboards/body_pod.yaml`](dashboards/body_pod.yaml). It has Overview, Body map and Trends pages plus scale status tiles.

**Single card:** add a card and pick *Hume Body Pod* from the list, or:

```yaml
type: custom:hume-pod-card
person: <person device>   # optional: omit to switch between everyone
view: overview            # overview | body | trends
show_tabs: true
```

The card shows every metric, even sensors that are disabled by default. Only *trend charts* need the sensor enabled, because they come from recorded statistics.

## Entities

**Scale device (`Body Pod`)**: status, unassigned weigh-in, last weigh-in, battery, signal strength, and live weight (disabled by default). The device page also shows the scale's model, firmware and hardware version once it has connected.

**One device per person**, linked to the scale:

- Enabled by default: weight, BMI, body fat %, fat mass, visceral fat, lean mass, skeletal muscle mass, body water %, bone mineral, BMR, metabolic age and last measured.
- Disabled by default: subcutaneous fat, android/gynoid fat and ratio, body cell mass, total/extra/intracellular water, mineral, skeletal and organ mass, segmental muscle and fat for each arm, leg and trunk, and the 10 raw impedance readings (diagnostic).

Each person's latest results are stored and survive restarts. Metric sensors use `state_class: measurement` for long-term statistics, and weights follow your HA unit system.

### Event

Every weigh-in fires `hume_pod_measurement`, including the matched `person` (or `null` if unassigned), `match_reason` (`matched`, `only_new_person`, `no_match`, `ambiguous`, `manual`), `match_distances`, all metric values and raw impedances.

## Impedance input

The hand bar measures each body segment on two frequency bands. The body-composition equations were calibrated around 50 kHz, which is much closer to the scale's **high band** than its **low band**, but earlier releases fed the low band into them (Blue2Scale's behaviour, kept for compatibility).

Under **Configure -> Impedance input band** you can pick which band feeds the equations:

- **Low band** (the default) keeps the historical values, so nothing changes on upgrade.
- **High band** uses the other series. On one Body Pod 2, a 93.6 kg, 183 cm male came out at roughly 30.6% body fat from the low band and 24.6% from the high band, against 25.5% in the Hume app: the high band is far closer to the manufacturer's figure. The size of the difference varies by body shape; the direction (high band gives lower body fat) is what the small validation set showed.

Only the *input* changes: no coefficient or formula differs between the bands, so every metric moves consistently. If a weigh-in arrives without high-band frames, the integration falls back to the low band and logs a warning.

The exact band frequencies are unverified. Hume Health's published specs for the Body Pod state 20-100 kHz, which is why the old "50 kHz"/"250 kHz" entity names were replaced with neutral **low band**/**high band** labels. Entity IDs, unique IDs and recorder history are unchanged. For context, see [openScale PR #1537](https://github.com/oliexdev/openScale/pull/1537) and [Blue2Scale issue #1](https://github.com/JozefJarosciak/Blue2Scale.com/issues/1).

Switching the option changes computed values from that moment on (the recorder keeps the history, so the switch appears as a step in the charts). Don't flip it mid-trend casually: pick a band and stay with it.

## Webhook

Each person's profile has an optional **Webhook URL** (⋮ menu next to their name → **Reconfigure**). While it is empty — the default — nothing is sent anywhere. When set, every weigh-in matched to that person is POSTed there as JSON, so weigh-ins can flow straight into another service or script. An optional **Webhook token** is sent with it as an `Authorization: Bearer` header.

Delivery is fire-and-forget: a single attempt with a 10 second timeout, no retries. Failures (timeouts, connection errors, non-2xx replies) are logged as warnings and never affect the weigh-in itself. Unassigned weigh-ins — where nobody matched — are never posted; assigning one afterwards with the *Assign weigh-in* service posts it then.

The payload is identical to the local `hume_pod_measurement` event, so anything you can do with a Home Assistant automation trigger you can do with the webhook. A full body-composition weigh-in looks like this:

```json
{
  "scale_entry_id": "01HX8Z4P9Q2R3S4T5U6V7W8X9Y",
  "person_id": "01JY0A1B2C3D4E5F6G7H8J9K0L",
  "person": "Dan",
  "match_reason": "matched",
  "match_distances": { "Dan": 0.14, "Sam": 2.87 },
  "composition": true,
  "measured_at": "2026-11-11T07:12:34+00:00",
  "weight": 93.05,
  "bmi": 31.1,
  "body_fat": 34.7,
  "fat_mass": 32.3,
  "subcutaneous_fat_mass": 28.1,
  "subcutaneous_fat": 30.2,
  "visceral_fat": 14,
  "android_fat": 12.9,
  "gynoid_fat": 12.4,
  "android_gynoid_ratio": 104.0,
  "lean_mass": 56.6,
  "lean_mass_percentage": 60.8,
  "skeletal_muscle_mass": 38.4,
  "body_cell_mass": 40.0,
  "body_water": 47.7,
  "total_body_water": 44.4,
  "extracellular_water": 16.4,
  "intracellular_water": 28.0,
  "bone_mineral": 3.3,
  "mineral_mass": 0.9,
  "skeletal_mass": 10.1,
  "organ_mass": 8.1,
  "bmr": 1658,
  "metabolic_age": 62,
  "right_arm_muscle": 2.3,
  "right_arm_fat": 32.5,
  "right_arm_fat_mass": 1.9,
  "left_arm_muscle": 2.3,
  "left_arm_fat": 32.5,
  "left_arm_fat_mass": 1.9,
  "trunk_muscle": 19.9,
  "trunk_fat": 33.9,
  "trunk_fat_mass": 16.6,
  "right_leg_muscle": 7.0,
  "right_leg_fat": 27.3,
  "right_leg_fat_mass": 4.4,
  "left_leg_muscle": 7.0,
  "left_leg_fat": 27.3,
  "left_leg_fat_mass": 4.4,
  "impedance_low_right_arm": 331.9,
  "impedance_low_left_arm": 322.9,
  "impedance_low_trunk": 27.0,
  "impedance_low_right_leg": 230.7,
  "impedance_low_left_leg": 232.1,
  "impedance_high_right_arm": 295.1,
  "impedance_high_left_arm": 289.0,
  "impedance_high_trunk": 20.9,
  "impedance_high_right_leg": 199.7,
  "impedance_high_left_leg": 203.7
}
```

| Field | Meaning |
| --- | --- |
| `scale_entry_id`, `person_id` | Home Assistant's internal IDs for the scale and the person's subentry |
| `person` | The person's name; always present, since unassigned weigh-ins are never posted |
| `match_reason` | How the weigh-in was attributed: `matched`, `only_new_person` or `manual` (assigned by you) |
| `match_distances` | How far each candidate was from the reading, in tolerance units (lower is closer) |
| `composition` | `true` when impedance was measured. When `false` (socks on, or stepped off early) the payload carries only the matching/metadata fields plus `weight`, `bmi` and the person's other last-known figures |
| `measured_at` | ISO 8601, UTC |
| `weight`, `bmi`, … | The composition metrics, exactly the keys of the person's sensors (all 39 after a full weigh-in) |
| `impedance_low_*`, `impedance_high_*` | The five segment impedances per band, in ohms, after a full weigh-in |

## Raw data capture

The scale's protocol is only partly documented: in particular, the payload of the four DF ("extended") frames is not decoded. If you want to help decode it, or simply keep every frame for your own analysis, turn on **Configure -> Log raw packets**. It is off by default, adds a few hundred bytes per weigh-in, and changes nothing else about how the integration works; capture does not depend on the log level.

Files are appended under your Home Assistant config directory, one directory per scale, so they ride along with your HA backups:

- `hume_pod_raw/<entry_id>/packets.csv` - one row per Bluetooth notification: weight frames, impedance frames, DF frames, advertisement manufacturer data, and any frame type the integration does not know yet, stored whole as hex. Duplicates and checksum failures are kept too; nothing is filtered or summarised.
- `hume_pod_raw/<entry_id>/sessions.csv` - one row per weigh-in with the raw hex of each frame type and who it matched. Weigh-ins rejected by person-matching are recorded too, with an empty `matched_person`: those are often the most valuable captures (e.g. deliberately loaded calibration weigh-ins).

| Column | Meaning |
| --- | --- |
| `ts_iso` | UTC timestamp, ISO 8601 |
| `mac` | The scale's Bluetooth address |
| `session_id` | Groups the frames of one weigh-in |
| `frame_type` | `cf` weight, `be` impedance, `df` extended, `adv` advertisement; otherwise the frame's first byte in hex |
| `index` | Impedance band (0 = low, 1 = high), DF index pair, or blank |
| `length`, `checksum_ok` | Frame length; checksum is the XOR rule seen on CF frames - a `false` on another frame type may just mean a different layout, and the frame is stored regardless |
| `frame_hex`, `decoded_json` | The full frame, and decoded values where known (weight for `cf`, the five segment impedances for `be`, the index pair for `df`); blank for unknown frames |
| `matched_person`, `match_distance` | Who the weigh-in was attributed to, and the match distance; both blank when nobody matched |
| `weight_kg`, `cf_hex`, `be_low_hex`, `be_high_hex`, `df_00_hex`, `df_10_hex`, `df_01_hex`, `df_11_hex` | The weigh-in's weight and the raw frame of each type; blank when that frame never arrived |

DF payloads are stored raw because their meaning is not decoded yet. Nothing rotates: data accumulates until you delete the directory. Turning the option off stops writing and leaves existing files alone.

Three months later, pulling everything into a dataframe:

```python
import pandas as pd

base = "/config/hume_pod_raw/<entry_id>"
packets = pd.read_csv(f"{base}/packets.csv", parse_dates=["ts_iso"])
sessions = pd.read_csv(f"{base}/sessions.csv", parse_dates=["ts_iso"])

# One row per weigh-in with both impedance bands:
with_bands = sessions.dropna(subset=["be_low_hex", "be_high_hex"])
```

## Limitations

- **Estimates, not clinical values.** The scale reports only weight and impedance; everything else comes from published BIA regression equations that Blue2Scale's author calibrated against the Hume app.
- **Discovery.** Scales are recognised by the name `Body Pod*`/`Hume*`, or, for units like the Body Pod 2 that advertise no name, by the `FFF0` service plus manufacturer data that starts with the scale's own Bluetooth address. If yours still isn't found, open an issue with a screenshot of its entry in **Settings → Bluetooth → Advertisement monitor**.
- The scale itself is always sent the first person's profile to start a measurement. This only affects the scale's own display; HA calculates results with the matched person's profile.
- After a weigh-in the integration ignores the scale for 45 seconds so it doesn't reconnect while the scale is still awake.

## Troubleshooting

The scale's device page shows a **Status** sensor (with `last_error`, `last_attempt` and `via` attributes) and a **Signal strength** sensor. Problems are also written to the log as warnings.

| What you see | What it means |
| --- | --- |
| `couldn't connect (RSSI -9x dBm via …)` | The proxy heard the scale but couldn't hold a connection. Below about -85 dBm this is common: move the proxy closer or add one near the scale. ESPHome proxies need `bluetooth_proxy: active: true`. |
| `connected, but the scale sent no data` | The connection worked but no readings arrived. Step on within a few seconds of waking the scale. If it keeps happening, please open an issue with a debug log. |
| `unexpected Bluetooth layout, missing …` | Your scale uses a different protocol from the one this integration knows. Please open an issue and include the message: it lists what the scale offers. |
| `no weight over 5 kg` | The scale connected and talked, but nobody was on it before it went quiet. |

For a debug log, use **Enable debug logging** on the integration page, tap the scale, weigh in, then **Disable debug logging** to download the log. It records each step: connection, the scale's services, every packet and the advertisement payload. Or add to `configuration.yaml`:

```yaml
logger:
  logs:
    custom_components.hume_pod: debug
```

Diagnostics (from the integration's ⋮ menu) include the same connection details, with names, birthdates and the Bluetooth address redacted.

## Development

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements_test.txt ruff
ruff check . && ruff format --check .
pytest
```

CI runs hassfest, HACS validation, ruff and the test suite on every push.

## Licence

The protocol details and BIA equations are derived from Blue2Scale, which is published under the **Blue2Scale Source-Available License 1.0** (see [BLUE2SCALE_LICENSE](BLUE2SCALE_LICENSE) and [NOTICE](NOTICE)). That licence allows forks and modifications for **non-production (personal, non-commercial) use** only. This project is for personal home use on that basis; ask the Blue2Scale author before using it commercially or submitting it to the default HACS store.
