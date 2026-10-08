from zoneinfo import ZoneInfo

import pytest

WARSAW = ZoneInfo("Europe/Warsaw")

# Synthetic export in the MyTanita CSV format (header shortened to the columns used + a few unused)
CSV = '''Date,"Weight (kg)",BMI,"Body Fat (%)","Visc Fat","Muscle Mass (kg)","Muscle Quality","Bone Mass (kg)","BMR (kcal)","Metab Age","Body Water (%)","Physique Rating","Muscle mass - right arm","Heart rate"
"2026-03-02 07:15:00",70.40,22.10,18.20,4.50,54.30,70.00,2.90,1650.00,31.00,57.80,5.00,-,-
"2026-01-10 06:50:30",71.00,22.30,-,5.00,54.60,70.00,2.90,1660.00,31.00,57.10,5.00,-,-
"2026-03-02 07:15:00",70.40,22.10,18.20,4.50,54.30,70.00,2.90,1650.00,31.00,57.80,5.00,-,-
"2026-03-05 21:05:10",70.10,22.00,17.90,4.50,54.25,71.00,2.90,1648.00,30.00,58.00,5.00,-,-
'''


@pytest.fixture
def csv_text():
    return CSV


class FakeGarmin:
    """Stands in for garminconnect.Garmin: stores uploads, serves weigh-ins."""

    garmin_connect_upload = "/upload-service/upload"

    def __init__(self, existing=None, fail=False):
        self.existing = existing or []
        self.uploads = []
        self.ranges = []
        self.fail = fail
        self.client = self

    def get_weigh_ins(self, start, end):
        self.ranges.append((start, end))
        days = {}
        for e in self.existing:
            if start <= e["calendarDate"] <= end:
                days.setdefault(e["calendarDate"], []).append(e)
        return {"dailyWeightSummaries": [
            {"summaryDate": d, "allWeightMetrics": es} for d, es in days.items()]}

    def post(self, domain, url, files=None, api=False):
        self.uploads.append(files["file"][1])
        failures = [{"messages": ["rejected"]}] if self.fail else []
        return {"detailedImportResult": {"failures": failures}}


@pytest.fixture
def fake_garmin():
    return FakeGarmin
