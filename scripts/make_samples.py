"""Generate the demo workbooks in client/public/samples/ — shaped like real DepEd
teacher files: e-class record (Written Works / Performance Tasks / Quarterly Exam),
a masterlist with LRN, monthly attendance summaries, and a consolidated grade sheet.

Two fictional schools, four files each, two sections per file (~40 rows/sheet).
Every sheet's first column is "Student" so sheets and files merge cleanly in the app.
Run: .venv/bin/python scripts/make_samples.py
"""
import random
from pathlib import Path

import pandas as pd

OUT = Path(__file__).parent.parent / "client" / "public" / "samples"
rng = random.Random(42)

FIRST_M = ["Juan Miguel", "Maria Clara", "Jose Rafael", "Ana Sofia", "Miguel", "Katrina",
           "Jerome", "Bea", "Carlo", "Danica", "Enrico", "Faith", "Gabriel", "Hazel",
           "Ivan", "Jasmine", "Kenneth", "Liza", "Mark Anthony", "Nicole", "Oscar",
           "Patricia", "Ramon", "Samantha", "Anthony", "Bianca", "Christian", "Divine",
           "Edgar", "Francesca", "Gerardo", "Honey", "Ian", "Jocelyn", "Kevin"]
LAST = ["DELA CRUZ", "SANTOS", "REYES", "GARCIA", "MENDOZA", "TORRES", "FLORES", "RIVERA",
        "GONZALES", "RAMOS", "AQUINO", "NAVARRO", "SALAZAR", "MERCADO", "AGUILAR", "DIAZ",
        "CASTILLO", "SANTIAGO", "VILLANUEVA", "DOMINGO", "MARQUEZ", "SORIANO", "DELGADO",
        "PASCUAL", "BAUTISTA", "CORPUS", "MANALO", "PADILLA", "ROSALES", "SERRANO"]
BARANGAY = ["Brgy. Poblacion", "Brgy. San Roque", "Brgy. Sto. Niño", "Brgy. Mabini",
            "Brgy. Del Pilar", "Brgy. Bagumbayan", "Brgy. San Jose", "Brgy. Malinis"]

USED = set()  # names are unique across all sections/files so Student-keyed merges never collide
def roster(n):
    names = set()
    while len(names) < n:
        nm = f"{rng.choice(LAST)}, {rng.choice(FIRST_M)}"
        if nm not in USED:
            names.add(nm)
    USED.update(names)
    return sorted(names)

def sex_map(students):
    """Assign Sex once per roster so a student reads the same in every file."""
    return {s: ("M" if rng.random() < 0.52 else "F") for s in students}

def clamp(v, lo, hi):
    return max(lo, min(hi, int(round(v))))

def col_scores(n, mean, spread, lo, hi):
    return [clamp(rng.gauss(mean, spread), lo, hi) for _ in range(n)]


def masterlist(students, sex):
    """School Form 1-style learner info sheet."""
    return pd.DataFrame({
        "Student": students,
        "Learner Reference Number": [rng.randint(100000000000, 199999999999) for _ in students],
        "Sex": [sex[s] for s in students],
        "Age": [rng.randint(16, 20) for _ in students],
        "Birthdate": [f"{rng.choice(['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'])} {rng.randint(1,28)}, {rng.randint(2004,2008)}" for _ in students],
        "Address": [rng.choice(BARANGAY) for _ in students],
        "Guardian": [f"{rng.choice(FIRST_M).split()[0]} {s.split(',')[0].title()}" for s in students],
        "Contact No.": [f"09{rng.randint(100000000, 999999999)}" for _ in students],
    })


def grades_sheet(students, sex, subjects):
    """Consolidated report-card sheet: subject final ratings + general average + remarks."""
    df = pd.DataFrame({"Student": students, "Sex": [sex[s] for s in students]})
    for subj, (mean, spread) in subjects.items():
        df[subj] = col_scores(len(students), mean, spread, 60, 99)
    subj_cols = list(subjects)
    df["General Average"] = df[subj_cols].mean(axis=1).round(1)
    df["Remarks"] = df["General Average"].map(lambda a: "PASSED" if a >= 75 else "FAILED")
    return df


def eclass_sheet(students, sex):
    """E-class record: Written Works /20, Performance Tasks /50, Quarterly Exam /100."""
    df = pd.DataFrame({"Student": students, "Sex": [sex[s] for s in students]})
    for i in range(1, 7):
        df[f"Written Work {i} (20)"] = col_scores(len(students), 15, 4, 3, 20)
    for i in range(1, 7):
        df[f"Performance Task {i} (50)"] = col_scores(len(students), 38, 9, 10, 50)
    df["Quarterly Exam (100)"] = col_scores(len(students), 74, 13, 30, 100)
    ww = df[[f"Written Work {i} (20)" for i in range(1, 7)]].sum(axis=1) / 120 * 100
    pt = df[[f"Performance Task {i} (50)" for i in range(1, 7)]].sum(axis=1) / 300 * 100
    qe = df["Quarterly Exam (100)"]
    df["Quarterly Grade"] = (ww * .30 + pt * .50 + qe * .20).round(1)  # DepEd 30/50/20 weights
    return df


# SY 2025-26 school calendar: weekdays Aug 4 – Jan 30, minus PH holidays and the
# Dec 20 – Jan 4 sem break. One sheet per month like School Form 2 — dates across
# the top, one mark per student per day.
HOLIDAYS = {"2025-08-21", "2025-08-25", "2025-10-31", "2025-12-08"}
SEM_BREAK = (pd.Timestamp("2025-12-20"), pd.Timestamp("2026-01-04"))

def month_days():
    days = [d for d in pd.bdate_range("2025-08-04", "2026-01-30")
            if d.strftime("%Y-%m-%d") not in HOLIDAYS and not SEM_BREAK[0] <= d <= SEM_BREAK[1]]
    months = {}
    for d in days:
        months.setdefault(d.strftime("%B"), []).append(d)
    return months

def attendance_book(sections):
    """Calendar-view register: Student | Section | <date columns> | totals, one sheet
    per month, plus a Semester Summary. Absences cluster per student (chronic
    absentees) via a per-student propensity, like real classes."""
    by_month = month_days()
    all_days = [d for ds in by_month.values() for d in ds]
    rows = [(n, s) for s, st in sections.items() for n in st]
    marks = {}
    for n, _ in rows:
        p_abs, p_late = rng.betavariate(0.7, 10), rng.betavariate(0.5, 12)
        marks[n] = ["Excused" if r < p_abs and rng.random() < 0.12 else
                    "Absent" if r < p_abs else
                    "Late" if r < p_abs + p_late else "Present"
                    for r in (rng.random() for _ in all_days)]
    sheets, i = {}, 0
    for month, ds in by_month.items():
        labels = [f"{d.strftime('%b')} {d.day}" for d in ds]  # "Aug 4"
        df = pd.DataFrame({"Student": [n for n, _ in rows], "Section": [s for _, s in rows]})
        for j, lab in enumerate(labels):
            df[lab] = [marks[n][i + j] for n, _ in rows]
        block = df[labels]
        df["Days Absent"] = (block == "Absent").sum(axis=1)
        df["Days Late"] = (block == "Late").sum(axis=1)
        sheets[month] = df
        i += len(ds)
    summ = pd.DataFrame({
        "Student": [n for n, _ in rows],
        "Section": [s for _, s in rows],
        "School Days": len(all_days),
        "Days Present": [marks[n].count("Present") for n, _ in rows],
        "Days Late": [marks[n].count("Late") for n, _ in rows],
        "Days Absent": [marks[n].count("Absent") for n, _ in rows],
        "Days Excused": [marks[n].count("Excused") for n, _ in rows],
    })
    summ["Attendance %"] = (summ["Days Present"] / summ["School Days"] * 100).round(1)
    sheets["Semester Summary"] = summ
    return sheets


def tests_sheet(students, sex):
    """Quiz battery + exams with real max scores baked into column names."""
    df = pd.DataFrame({"Student": students, "Sex": [sex[s] for s in students]})
    for i in range(1, 7):
        df[f"Quiz {i} (50)"] = col_scores(len(students), 38, 9, 12, 50)
    df["Long Exam 1 (100)"] = col_scores(len(students), 71, 14, 25, 100)
    df["Long Exam 2 (100)"] = col_scores(len(students), 74, 13, 28, 100)
    df["Midterm (100)"] = col_scores(len(students), 75, 12, 35, 100)
    df["Final (100)"] = col_scores(len(students), 77, 11, 40, 100)
    return df


TEST_INFO = pd.DataFrame({
    "Test": [*(f"Quiz {i}" for i in range(1, 7)), "Long Exam 1", "Long Exam 2", "Midterm", "Final"],
    "Max Score": [50] * 6 + [100] * 4,
    "Weight %": [5] * 6 + [15, 15, 20, 20],
})

# ---------------------------------------------------------------- rosters
BU = {"BSIT 1-A": roster(39), "BSIT 1-B": roster(42)}   # Bicol University
DW = {"BSA 2-A": roster(40), "BSA 2-B": roster(38)}      # Divine Word College

BU_SUBJ = {"Programming 1": (82, 9), "Calculus": (73, 12), "Physics": (75, 11),
           "English": (82, 8), "Filipino": (84, 7), "NSTP": (88, 5), "PE": (90, 4)}
DW_SUBJ = {"Financial Accounting": (74, 13), "Business Math": (72, 12), "Marketing": (80, 9),
           "Economics": (75, 10), "English": (82, 8), "Theology": (86, 6)}

def build(sections, subjects):
    sex = {s: sex_map(st) for s, st in sections.items()}
    return {
        "grades": {s: grades_sheet(st, sex[s], subjects) for s, st in sections.items()},
        "attendance": attendance_book(sections),
        "tests": {s: tests_sheet(st, sex[s]) for s, st in sections.items()},
        "eclass": {s: eclass_sheet(st, sex[s]) for s, st in sections.items()},
        "masterlist": {s: masterlist(st, sex[s]) for s, st in sections.items()},
    }

def save(name, sheets):
    with pd.ExcelWriter(OUT / name, engine="openpyxl") as w:
        for s, df in sheets.items():
            df.to_excel(w, sheet_name=s, index=False)
    print(f"{name}: {list(sheets)} ({sum(len(d) for d in sheets.values())} rows)")

OUT.mkdir(parents=True, exist_ok=True)
for slug, data in [("bicol_university", build(BU, BU_SUBJ)),
                   ("divine_word_college", build(DW, DW_SUBJ))]:
    grades = {**data["grades"], "Masterlist": pd.concat(data["masterlist"].values(), ignore_index=True)}
    save(f"{slug}_grades.xlsx", grades)
    save(f"{slug}_attendance.xlsx", data["attendance"])
    save(f"{slug}_tests.xlsx", {**data["tests"], "Test Info": TEST_INFO})
    # a 4th file: the e-class record (raw WW/PT/QE components)
    save(f"{slug}_eclass_record.xlsx", data["eclass"])
