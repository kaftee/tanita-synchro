# How it works

```
tanita_synchro/
├── mytanita.py  MyTanita client: sign-in, CSV export, parsing; credentials
├── garmin.py    Garmin side: session, listing weigh-ins, FIT upload
├── notify.py    Failure mail over SMTP (--notify, --test-notify)
└── cli.py       Command-line entry point, the sync loop and retries
```

## MyTanita

The mytanita.eu portal is a server-rendered website.

1. `GET /en/user/login` — the login form carries a hidden `token` field.
2. `POST /en/user/processlogin` with `mail`, `password`, `token` and `login`.
   A failed sign-in returns the login form again.
3. `GET /en/user/export-csv` — the "Export list as CSV" link on the
   Measurements page: every measurement in the account, one row each.

Dates in the export are local times without an offset. Missing values are `-`.
The export can contain the same measurement twice; rows with the same time are
kept once.

## Garmin

Measurements are uploaded the way Garmin's own Index scale data arrives: a small
FIT file with a `weight_scale` message, posted to the Garmin Connect upload
service. Garmin lists them with source `INDEX_SCALE`.

The FIT file is built with the encoder from the `garminconnect` library, with
one change: values are **rounded** to the FIT scale instead of truncated
(`54.3 * 100` is `5429.999…` in floating point and would be stored as 54.29 kg).

### Field mapping

| MyTanita column | FIT `weight_scale` field | Garmin Connect |
|---|---|---|
| Weight (kg) | `weight` | Weight |
| BMI | `bmi` | BMI |
| Body Fat (%) | `percent_fat` | Body Fat |
| Body Water (%) | `percent_hydration` | Body Water |
| Muscle Mass (kg) | `muscle_mass` | Skeletal Muscle Mass |
| Bone Mass (kg) | `bone_mass` | Bone Mass |
| BMR (kcal) | `basal_met` | — |
| Metab Age | `metabolic_age` | Metabolic Age |
| Physique Rating | `physique_rating` | Physique Rating |
| Visc Fat | `visceral_fat_rating` | Visceral Fat |

Not sent: Muscle Quality, the per-segment values (arms, legs, trunk) and heart
rate, which have no `weight_scale` field.

Notes:

- Tanita's *Visc Fat* is a rating (1–59), not a mass, so it goes to
  `visceral_fat_rating`. Garmin keeps whole numbers only: 6.5 is stored as 6.
- Tanita's *Muscle Mass* is all muscle including the water in it; Garmin labels
  the field *Skeletal Muscle Mass*. The value is sent unchanged.

## Matching

Before uploading, the sync lists every Garmin weigh-in in the period of the
measurements (the weight range endpoint, which returns all weigh-ins of a day;
the body composition endpoint returns only the latest one per day). A
measurement is skipped when Garmin has any weigh-in within one minute of it, so
manual entries at other times are left alone and nothing is uploaded twice.
