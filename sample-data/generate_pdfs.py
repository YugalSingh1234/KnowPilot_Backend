"""Generate the sample PDFs for two FICTIONAL organizations into org1/ and org2/.

    pip install -r sample-data/requirements.txt
    python sample-data/generate_pdfs.py
"""
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

ROOT = Path(__file__).resolve().parent
FOOTER = "Illustrative policy for a fictional organization"

# Standard PDF fonts have no rupee sign, so register a TrueType font that does.
FONT_CANDIDATES = [  # (regular, bold)
    ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"),
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ("/Library/Fonts/Arial Unicode.ttf", "/Library/Fonts/Arial Unicode.ttf"),
]
for regular, bold in FONT_CANDIDATES:
    if Path(regular).exists() and Path(bold).exists():
        pdfmetrics.registerFont(TTFont("Body", regular))
        pdfmetrics.registerFont(TTFont("Body-Bold", bold))
        break
else:
    raise SystemExit("No TrueType font with the rupee sign found; add one to FONT_CANDIDATES.")

BODY = ParagraphStyle("body", fontName="Body", fontSize=11, leading=16, spaceAfter=8)
BULLET = ParagraphStyle("bullet", parent=BODY, leftIndent=18, bulletIndent=6, spaceAfter=3)
HEADING = ParagraphStyle("h", fontName="Body-Bold", fontSize=13.5, leading=18, spaceBefore=14, spaceAfter=6,
                         textColor=colors.HexColor("#1f3b57"))
TITLE = ParagraphStyle("t", fontName="Body-Bold", fontSize=19, leading=24, spaceAfter=4,
                       textColor=colors.HexColor("#1f3b57"))
SUB = ParagraphStyle("s", parent=BODY, textColor=colors.grey, spaceAfter=12)
BIG = ParagraphStyle("big", fontName="Body-Bold", fontSize=22, leading=30, alignment=TA_CENTER)


def inr(amount: int) -> str:
    """Indian digit grouping: 800000 -> ₹8,00,000."""
    s = str(amount)
    head, last3 = s[:-3], s[-3:]
    groups = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    if head:
        groups.insert(0, head)
    return "₹" + ",".join(groups + [last3] if len(s) > 3 else [s])


assert inr(800000) == "₹8,00,000" and inr(50000) == "₹50,000" and inr(12345678) == "₹1,23,45,678" and inr(500) == "₹500"


class Doc:
    """Collects numbered sections, then writes an A4 PDF with a header and footer on every page."""

    def __init__(self, org: str, title: str, intro: str):
        self.org, self.title, self.n = org, title, 0
        self.flow = [Paragraph(title, TITLE), Paragraph(f"{org} &nbsp;|&nbsp; {intro}", SUB)]

    def section(self, heading: str, *paras: str, bullets: list[str] = (), after: list[str] = ()):
        self.n += 1
        self.flow.append(Paragraph(f"{self.n}. {heading}", HEADING))
        self.flow += [Paragraph(p, BODY) for p in paras]
        self.flow += [Paragraph(b, BULLET, bulletText="•") for b in bullets]
        self.flow += [Paragraph(p, BODY) for p in after]

    def faq(self, qa: list[tuple[str, str]]):
        self.section("Frequently Asked Questions")
        for q, a in qa:
            self.flow += [Paragraph(f"<b>Q. {q}</b>", BODY), Paragraph(f"A. {a}", BODY)]

    def table(self, rows: list[list[str]], widths: list[float]):
        t = Table(rows, colWidths=[w * inch for w in widths], hAlign="LEFT", repeatRows=1)
        t.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), "Body"), ("FONTNAME", (0, 0), (-1, 0), "Body-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f3b57")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f1f4f8")]),
            ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        self.flow += [t, Spacer(1, 8)]

    def own_page(self, *paras: str, heading: str = ""):
        self.n += 1
        self.flow += [PageBreak(), Spacer(1, 2.2 * inch), Paragraph(f"{self.n}. {heading}", HEADING)]
        self.flow += [Paragraph(p, BIG if i == 0 else BODY) for i, p in enumerate(paras)]

    def save(self, path: Path):
        def chrome(canvas, doc):
            w, h = A4
            canvas.saveState()
            canvas.setFont("Body-Bold", 9)
            canvas.drawString(0.8 * inch, h - 0.55 * inch, self.org)
            canvas.setFont("Body", 9)
            canvas.drawRightString(w - 0.8 * inch, h - 0.55 * inch, self.title)
            canvas.setStrokeColor(colors.grey)
            canvas.line(0.8 * inch, h - 0.65 * inch, w - 0.8 * inch, h - 0.65 * inch)
            canvas.line(0.8 * inch, 0.7 * inch, w - 0.8 * inch, 0.7 * inch)
            canvas.setFont("Body", 8)
            canvas.drawString(0.8 * inch, 0.5 * inch, FOOTER)
            canvas.drawRightString(w - 0.8 * inch, 0.5 * inch, f"Page {doc.page}")
            canvas.restoreState()

        path.parent.mkdir(parents=True, exist_ok=True)
        SimpleDocTemplate(str(path), pagesize=A4, title=self.title, author=self.org,
                          leftMargin=0.8 * inch, rightMargin=0.8 * inch,
                          topMargin=0.95 * inch, bottomMargin=0.95 * inch).build(
            self.flow, onFirstPage=chrome, onLaterPages=chrome)
        print("wrote", path.relative_to(ROOT.parent))


# ---------------------------------------------------------------- Org 1: Navodaya Institute of Technology
NIT = "Navodaya Institute of Technology, Kanpur"


def nit_scholarship():
    d = Doc(NIT, "Scholarship Policy 2025-26", "Effective for academic year 2025-26")
    d.section(
        "Merit-cum-Means Scholarship",
        "The Merit-cum-Means Scholarship supports deserving B.Tech students. It is open to students in "
        "<b>Year 2, Year 3 or Year 4</b> of the B.Tech programme only. Year 1 students are not eligible.",
        "A student is eligible only if <b>all</b> of the following conditions are met:",
        bullets=[
            "CGPA of <b>7.5 or above</b> (CGPA &gt;= 7.5).",
            f"Annual family income of <b>{inr(800000)} or less</b> (income &lt;= {inr(800000)}).",
            "The student must <b>not already receive any other scholarship</b>, including a state "
            "post-matric scholarship or any scholarship through the National Scholarship Portal (NSP).",
            "Attendance of <b>75% or above</b> (attendance &gt;= 75%).",
        ],
        after=[f"Award: <b>{inr(50000)} per year</b>, paid in two equal instalments."],
    )
    d.section(
        "Sports Excellence Scholarship",
        "The Sports Excellence Scholarship rewards students who have represented at a high level. A student "
        "is eligible if:",
        bullets=[
            "The student has won a <b>medal at state level or above</b> in a recognised sport.",
            "CGPA is <b>6.5 or above</b> (CGPA &gt;= 6.5).",
        ],
        after=[
            "This scholarship <b>can be combined</b> with the Merit-cum-Means Scholarship. Holding it does not "
            "count as 'receiving another scholarship' for Merit-cum-Means eligibility.",
            f"Award: <b>{inr(25000)} per year</b>.",
        ],
    )
    d.section(
        "Girl Child Tuition Waiver",
        "The Girl Child Tuition Waiver is open to <b>female students</b> whose annual family income is "
        f"<b>{inr(500000)} or less</b> (income &lt;= {inr(500000)}).",
        "Benefit: a <b>50% waiver</b> of the annual tuition fee.",
    )
    d.section(
        "Category-wise Seat Quota",
        "Seats in each B.Tech batch are reserved according to the following shares.",
    )
    d.table([["Category", "Share of seats"], ["GENERAL", "40.5%"], ["EWS", "10%"], ["OBC-NCL", "27%"],
             ["SC", "15%"], ["ST", "7.5%"]], [2.2, 2.0])
    d.section(
        "Required Documents",
        "Applicants must upload the following documents with the application:",
        bullets=[
            "Latest semester grade card showing CGPA.",
            "Income certificate issued within the last 12 months by a competent authority.",
            "Category certificate (for GENERAL / EWS / OBC-NCL / SC / ST claims).",
            "Attendance certificate signed by the Head of Department.",
            "Self-declaration stating whether any other scholarship is received.",
            "Sports medal certificate (Sports Excellence Scholarship only).",
        ],
    )
    d.section(
        "Application Dates",
        "Applications open on <b>1 June 2025</b> and close on <b>31 July 2025</b>. Results are published on "
        "<b>15 August 2025</b>. Late applications are not accepted.",
    )
    d.section(
        "Renewal and Cancellation",
        "Scholarships are awarded for one academic year and must be renewed each year through a fresh "
        "application. A scholarship is cancelled immediately if:",
        bullets=[
            "The student's CGPA falls below the minimum for that scholarship at the end of the year.",
            "The student's attendance falls below 75% in any semester.",
            "The student is found to have given false information, in which case the amount already paid must "
            "be returned and the student cannot apply again.",
            "The student starts receiving another scholarship that is not allowed to be combined with it.",
        ],
        after=["Disbursement is made to the student's bank account in two instalments, in September and in "
               "February."],
    )
    d.section(
        "Selection and Grievances",
        "The Scholarship Committee, chaired by the Dean of Student Affairs, verifies all applications. If more "
        "eligible students apply than funds allow, awards go to the applicants with the <b>lowest family "
        "income</b>; ties are broken by higher CGPA. A student who disagrees with a decision may appeal in "
        "writing to the Dean within <b>7 days</b> of the result.",
    )
    d.section(
        "Definitions",
        "<b>Family income</b> means the total annual income of the student's parents or guardians from all "
        "sources in the previous financial year, as shown on the income certificate. <b>CGPA</b> means the "
        "cumulative grade point average on the 10-point scale shown on the latest grade card. <b>Attendance</b> "
        "means the overall attendance percentage in the preceding semester. <b>Other scholarship</b> means any "
        "scholarship paid by a government, trust or company, but not a fee concession given by the Institute "
        "itself.",
    )
    d.faq([
        ("My CGPA is 7.4. Can I get the Merit-cum-Means Scholarship?",
         "No. The minimum CGPA is 7.5. A CGPA of 7.4 does not qualify."),
        ("I get a state post-matric scholarship. Can I also get the Merit-cum-Means Scholarship?",
         "No. A student receiving any other scholarship, including state post-matric or NSP, is not eligible for "
         "Merit-cum-Means."),
        ("Can a Sports Excellence winner also get Merit-cum-Means?",
         f"Yes, if the student meets all Merit-cum-Means conditions. The two can be combined, for a total of "
         f"{inr(75000)} per year."),
        ("Can a first-year student apply for Merit-cum-Means?",
         "No. Only students in years 2, 3 and 4 can apply."),
        ("My family income is exactly Rs 8 lakh. Am I eligible?",
         f"Yes. The limit is {inr(800000)} or less, so exactly {inr(800000)} qualifies."),
    ])
    d.own_page("Percentage equivalent = CGPA x 9.5",
               "Use this formula wherever a percentage is required. For example, a CGPA of 8.0 is equivalent to "
               "76 percent.",
               heading="CGPA to Percentage Conversion")
    d.save(ROOT / "org1" / "NIT_Scholarship_Policy_2025-26.pdf")


def nit_fees():
    d = Doc(NIT, "Admission and Fee Rules", "Fee structure for academic year 2025-26")
    d.section(
        "Annual Fees",
        "The following fees are payable each year by every B.Tech student. Hostel and mess fees apply only to "
        "students who take hostel accommodation.",
    )
    d.table([["Fee", "Amount per year"], ["Tuition fee", inr(145000)], ["Hostel fee", inr(65000)],
             ["Mess fee", inr(35000)], ["Total with hostel and mess", inr(145000 + 65000 + 35000)]], [3.0, 2.2])
    d.section(
        "Instalments",
        "Fees may be paid in two instalments:",
        bullets=[
            "<b>Instalment 1:</b> 60% of the annual fee, due on or before <b>15 July</b>.",
            "<b>Instalment 2:</b> 40% of the annual fee, due on or before <b>15 December</b>.",
        ],
    )
    d.section(
        "Late Fee",
        f"A late fee of <b>{inr(500)} per week</b> (or part of a week) is charged after the due date. The late "
        f"fee is capped at <b>{inr(5000)}</b> per instalment. Students whose dues remain unpaid 30 days after "
        "the due date may be barred from classes.",
    )
    d.section(
        "Refund After Withdrawal",
        "A student who withdraws from the Institute receives a refund of the fees paid (excluding a "
        f"non-refundable {inr(5000)} processing charge) according to this schedule:",
    )
    d.table([["Date of written withdrawal request", "Refund"],
             ["Before the first day of classes", "100%"],
             ["Within 15 days after classes begin", "80%"],
             ["16 to 30 days after classes begin", "50%"],
             ["More than 30 days after classes begin", "0%"]], [3.8, 1.4])
    d.section(
        "Admission Documents",
        "At admission, students must submit:",
        bullets=["Class 12 mark sheet and passing certificate.", "Entrance examination scorecard.",
                 "Transfer certificate and migration certificate.", "Four passport-size photographs.",
                 "Aadhaar card copy."],
    )
    d.section(
        "Instalment Amounts",
        f"For a student with hostel and mess, the total annual fee is {inr(245000)}. Instalment 1 is "
        f"{inr(147000)} and Instalment 2 is {inr(98000)}. For a day scholar paying tuition only "
        f"({inr(145000)}), Instalment 1 is {inr(87000)} and Instalment 2 is {inr(58000)}.",
    )
    d.section(
        "Caution Deposit",
        f"A one-time, refundable caution deposit of <b>{inr(10000)}</b> is collected at admission. It is "
        "returned within 60 days of the student leaving the Institute, after deducting any dues or damages.",
    )
    d.section(
        "Payment Modes",
        "Fees can be paid by online bank transfer, UPI or demand draft payable to 'Navodaya Institute of "
        "Technology, Kanpur'. Cash is not accepted. A fee receipt is issued within 2 working days.",
    )
    d.section(
        "Hostel Rules",
        "Hostel rooms are allotted on a first-come basis after the first instalment is paid. Students must be "
        "inside the hostel by 10:00 pm. The hostel fee is not refunded if a student is asked to leave the "
        "hostel for breaking the rules. Mess fee is charged for the full year; there is no deduction for "
        "absence of less than 30 days.",
    )
    d.section(
        "Worked Refund Examples",
        f"Example 1: a day scholar withdraws 10 days after classes begin, having paid {inr(87000)}. The "
        f"refund is 80% of {inr(87000)} minus the {inr(5000)} processing charge. "
        f"Example 2: a student withdraws 40 days after classes begin. The refund is 0%.",
    )
    d.section(
        "Scope",
        "These rules apply to all B.Tech students admitted from academic year 2025-26. Fees are fixed for the "
        "year and may be revised by up to <b>5%</b> at the start of the next academic year. The Institute "
        "does not charge any capitation fee or donation.",
    )
    d.faq([
        ("When is the first instalment due?", "On or before 15 July. It is 60% of the annual fee."),
        ("What is the late fee if I pay 3 weeks late?",
         f"{inr(500)} per week, so {inr(1500)} for 3 weeks. The cap is {inr(5000)} per instalment."),
        ("Do day scholars pay hostel fee?", "No. Hostel and mess fees apply only to hostel students."),
        ("How much is the tuition fee for one year?", f"{inr(145000)} per year."),
        ("Can I get a refund if I leave after 2 months?", "No. After 30 days from the start of classes the "
         "refund is 0%, except for the caution deposit."),
    ])
    d.save(ROOT / "org1" / "NIT_Admission_and_Fee_Rules.pdf")


def nit_academics():
    d = Doc(NIT, "Academic Regulations", "Applicable to all B.Tech programmes")
    d.section(
        "Attendance",
        "A student must have <b>at least 75% attendance</b> in each course to be allowed to sit the "
        "end-semester examination.",
        "<b>Medical exemption:</b> a student with a valid medical certificate, approved by the Institute Medical "
        "Officer, may be allowed to sit the examination with attendance of <b>65% or above</b>. Attendance below "
        "65% is never condoned.",
    )
    d.section("Grading Scale", "Marks are converted to grade points on a 10-point scale:")
    d.table([["Marks", "Grade", "Grade points"], ["90 - 100", "O", "10"], ["80 - 89", "A+", "9"],
             ["70 - 79", "A", "8"], ["60 - 69", "B+", "7"], ["50 - 59", "B", "6"], ["45 - 49", "C", "5"],
             ["40 - 44", "P", "4"], ["Below 40", "F (fail)", "0"]], [1.8, 1.4, 1.4])
    d.section(
        "Supplementary Examinations",
        "A student who fails in <b>up to 3 courses</b> in a semester may appear in the supplementary "
        f"examination held in July. The fee is <b>{inr(500)} per course</b>. A student who fails in more than 3 "
        "courses must repeat the semester.",
    )
    d.section(
        "Re-evaluation",
        "A student who is not satisfied with a grade may apply for re-evaluation:",
        bullets=[
            "The application must be made within <b>10 days</b> of the result being declared.",
            f"The fee is <b>{inr(300)} per course</b>, refunded in full if the grade improves.",
            "The re-evaluated result is announced within <b>21 days</b> of the application.",
            "The re-evaluated grade is final.",
        ],
    )
    d.section(
        "Examination Structure",
        "Each course has <b>40 marks of internal assessment</b> (two class tests and assignments) and "
        "<b>60 marks of end-semester examination</b>. To pass a course, a student needs at least 40 marks out "
        "of 100 overall and at least 24 marks out of 60 in the end-semester examination.",
    )
    d.section(
        "CGPA Calculation",
        "SGPA is the credit-weighted average of grade points in a semester. CGPA is the credit-weighted "
        "average of grade points over all semesters completed. Courses with an F grade are counted with 0 grade "
        "points until they are cleared.",
    )
    d.section(
        "Promotion to the Next Year",
        "A student is promoted to the next year if the student has cleared at least <b>75% of the credits</b> "
        "offered in the year so far (about 36 of 48 credits per year). Students with fewer credits are "
        "detained and must repeat the year's failed courses.",
    )
    d.section(
        "Semester Break and Repeat",
        "A student may take a semester break once during the programme, for up to <b>1 year</b>, for medical "
        "or family reasons. The application must be made before the semester begins and approved by the Dean "
        "of Academics. The programme must be completed within <b>6 years</b> from admission.",
    )
    d.section(
        "Examination Malpractice",
        "Use of unfair means in an examination results in an F grade in that course for a first offence and "
        "an F grade in all courses of the semester for a second offence. A third offence leads to expulsion "
        "from the Institute.",
    )
    d.section(
        "Leave of Absence",
        "Students absent for more than 7 consecutive days must submit a leave application to the Head of "
        "Department. Approved leave does not change the attendance percentage; it only explains the absence.",
    )
    d.section(
        "Definitions",
        "<b>Credit</b> is the weight of a course; a typical 3-hour-per-week course carries 3 credits. "
        "<b>SGPA</b> is the grade point average of one semester. <b>Detention</b> means a student must repeat "
        "a year or a course. <b>Condonation</b> means the Institute allows a student to sit an examination "
        "despite low attendance, for example on medical grounds.",
    )
    d.faq([
        ("My attendance is 70%. Can I sit the examination?",
         "Only with a medical certificate approved by the Institute Medical Officer, which allows 65% or above. "
         "Without it, the minimum is 75% and you cannot sit."),
        ("My attendance is 60% and I have a medical certificate. Can I sit?",
         "No. Even with medical exemption the minimum is 65%."),
        ("I failed 4 courses. Can I take the supplementary examination?",
         "No. Supplementary examinations are only for up to 3 failed courses. With 4 or more you must repeat "
         "the semester."),
        ("How much does re-evaluation of two courses cost?",
         f"{inr(300)} per course, so {inr(600)} for two courses, refunded if the grade improves."),
        ("How long do I have to apply for re-evaluation?", "10 days from the date the result is declared."),
    ])
    d.save(ROOT / "org1" / "NIT_Academic_Regulations.pdf")


# ---------------------------------------------------------------- Org 2: Navyug Infotech Pvt. Ltd.
NAV = "Navyug Infotech Pvt. Ltd., Pune"


def navyug_leave():
    d = Doc(NAV, "Leave Policy", "Applicable to all permanent employees")
    d.section(
        "Earned Leave",
        "Each employee earns <b>18 days of earned leave per year</b>, accrued monthly at 1.5 days per month. "
        "Unused earned leave can be carried forward, up to a <b>maximum balance of 30 days</b>.",
    )
    d.section(
        "Casual and Sick Leave",
        "Each employee gets <b>8 days of casual leave</b> and <b>10 days of sick leave</b> per calendar year. "
        "Sick leave of more than 2 consecutive days needs a medical certificate.",
    )
    d.section(
        "Leave During Probation",
        "During the first <b>6 months</b> (probation), only <b>casual leave and sick leave</b> may be taken. "
        "Earned leave does not accrue during probation and cannot be used.",
    )
    d.section(
        "Marriage Leave",
        "An employee is entitled to <b>5 days of paid marriage leave, once</b> during employment. It can be "
        "taken only <b>after probation</b> is completed.",
    )
    d.section(
        "Maternity and Paternity Leave",
        "Maternity leave is <b>26 weeks</b> of paid leave. Paternity leave is <b>10 working days</b> of paid "
        "leave, to be taken within 3 months of the birth.",
    )
    d.section(
        "Blackout Period",
        "Employees in <b>client-facing roles</b> cannot take leave between <b>15 March and 31 March</b> "
        "(inclusive) because of financial year-end deliveries. Leave in this period is approved only for "
        "medical emergencies.",
    )
    d.section(
        "Leave Encashment",
        "Earned leave balance above 30 days at year end is not carried forward. It is encashed at "
        "(monthly basic salary / 30) per day. Casual and sick leave cannot be encashed or carried forward.",
    )
    d.section(
        "How to Apply for Leave",
        "Leave must be applied for in the HR portal and approved by the reporting manager.",
        bullets=[
            "Leave of 1 to 2 days: apply at least <b>1 working day</b> in advance.",
            "Leave of 3 or more days: apply at least <b>5 working days</b> in advance.",
            "Sick leave: inform the manager before 10:00 am on the first day and apply in the portal within "
            "2 working days of returning.",
        ],
        after=["Weekends and public holidays that fall within a period of leave are not counted as leave."],
    )
    d.section(
        "Public Holidays",
        "The company observes <b>12 public holidays</b> per year. The list is published in January. Offices in "
        "Pune, Bengaluru and Noida may follow different local holidays, but the total stays at 12.",
    )
    d.section(
        "Leave Without Pay",
        "When all paid leave is used up, a manager may approve leave without pay for up to <b>15 days</b> in a "
        "year. Longer unpaid leave needs approval from the HR Head. Leave without pay does not count towards "
        "gratuity service if it exceeds 30 days in a year.",
    )
    d.section(
        "Compensatory Off",
        "An employee who works on a weekend or public holiday at a manager's written request earns one "
        "compensatory day off, which must be used within <b>60 days</b>. Compensatory offs cannot be encashed.",
    )
    d.section(
        "Worked Example: Accrual After Probation",
        "An employee who joins on 1 January completes probation on 30 June. Earned leave starts accruing from "
        "1 July, at 1.5 days per month. By 31 December, the employee has accrued 9 days of earned leave "
        "(6 months x 1.5). The employee had 8 casual leave and 10 sick leave days available from the start "
        "of the year.",
    )
    d.section(
        "Scope and Definitions",
        "This policy applies to all permanent employees in Pune, Bengaluru and Noida. <b>Probation</b> is the "
        "first 6 months from the date of joining. <b>Client-facing role</b> means a role where the employee "
        "works directly with a client's team or at a client site. <b>Year</b> means the calendar year, 1 "
        "January to 31 December.",
    )
    d.faq([
        ("I joined 2 months ago. Can I take earned leave?",
         "No. During the first 6 months (probation) only casual leave and sick leave can be taken."),
        ("Can I take marriage leave during probation?",
         "No. Marriage leave of 5 days can be taken only once, and only after probation."),
        ("I am in a client-facing role. Can I take leave on 20 March?",
         "No. Leave is not approved between 15 and 31 March for client-facing roles, except medical emergencies."),
        ("I have 40 days of earned leave at year end. What happens?",
         "Only 30 days can be carried forward. The extra 10 days are encashed at (monthly basic / 30) per day."),
        ("How many leaves of each type do I get in a year?",
         "Earned leave 18, casual leave 8 and sick leave 10, a total of 36 days, after probation."),
    ])
    d.save(ROOT / "org2" / "Navyug_Leave_Policy.pdf")


def navyug_handbook():
    d = Doc(NAV, "Employee Handbook", "Welcome to Navyug Infotech")
    d.section(
        "About Navyug",
        "Navyug Infotech Pvt. Ltd. is an IT services company headquartered in Pune. We have offices in "
        "<b>Pune, Bengaluru and Noida</b>.",
    )
    d.section(
        "Probation",
        "Every new employee serves a probation period of <b>6 months</b> from the date of joining. At the end of "
        "probation, the manager confirms the employee in writing.",
    )
    d.section(
        "Notice Period",
        "The notice period is <b>60 days</b> for confirmed employees and <b>30 days</b> during probation. "
        "Either side may pay in lieu of notice.",
    )
    d.section(
        "Work From Home",
        "Employees may work from home <b>2 days per week</b> after completing probation. Employees on "
        "probation work from the office. Work-from-home days are agreed with the manager.",
    )
    d.section(
        "Working Hours",
        "Standard hours are 9:30 am to 6:30 pm, Monday to Friday. Core hours, when everyone is available, are "
        "11:00 am to 4:00 pm.",
    )
    d.section(
        "Grievances",
        "Employees can raise a grievance with HR by email. HR acknowledges it within <b>2 working days</b> and "
        "resolves it within <b>15 working days</b>.",
    )
    d.section(
        "Performance Reviews",
        "The review year runs from 1 April to 31 March. Employees are rated on a scale of 1 to 5 in "
        "April. A rating of 3 or above is needed to be considered for a salary increment. Ratings of 1 or 2 "
        "lead to a 90-day improvement plan.",
    )
    d.section(
        "Dress Code and Conduct",
        "Business casual is the standard dress. Employees must treat colleagues with respect. Discrimination, "
        "harassment and bullying are not tolerated. Complaints of sexual harassment go to the Internal "
        "Complaints Committee, which completes its inquiry within <b>90 days</b>.",
    )
    d.section(
        "Information Security",
        "Company laptops must have disk encryption. Passwords must be at least 12 characters long and "
        "changed every 90 days. Client data must never be copied to personal devices or personal email.",
    )
    d.section(
        "Expense Reimbursement",
        f"Business expenses are reimbursed on submission of bills within <b>30 days</b>. Hotel stays are "
        f"reimbursed up to {inr(5000)} per night in metro cities and {inr(3500)} per night elsewhere. Meals on "
        f"travel are reimbursed up to {inr(1000)} per day.",
    )
    d.section(
        "Referral Bonus",
        f"An employee who refers a candidate who joins receives a referral bonus of <b>{inr(25000)}</b>, "
        "paid after the new hire completes 6 months in the company.",
    )
    d.section(
        "Exit Process",
        "On resignation the employee serves the notice period, returns all company assets and completes a "
        "knowledge handover. Full and final settlement is paid within <b>45 days</b> of the last working day. "
        "The relieving and experience letters are issued within 7 days of settlement.",
    )
    d.section(
        "Joining Formalities",
        "On the first day, new employees submit identity proof, address proof, PAN card, bank details, "
        "educational certificates and relieving letters from previous employers. Background verification is "
        "completed within 30 days of joining. An employee whose verification fails may be separated without "
        "notice.",
    )
    d.section(
        "Attendance and Timekeeping",
        "Employees mark attendance in the HR portal every working day, including work-from-home days. Arriving "
        "after 11:00 am more than 3 times in a month is treated as half a day of casual leave for each "
        "further late arrival. Timesheets for client projects are submitted every Friday by 6:00 pm.",
    )
    d.faq([
        ("I am on probation. How many days notice must I give?", "30 days. Confirmed employees give 60 days."),
        ("Can I work from home in my third month?",
         "No. Work from home (2 days per week) starts only after probation, which is 6 months."),
        ("Where are the Navyug offices?", "Pune (head office), Bengaluru and Noida."),
        ("How soon is my final settlement paid after I leave?", "Within 45 days of the last working day."),
        ("What rating do I need for a salary increment?", "A rating of 3 or above on the 1 to 5 scale."),
    ])
    d.save(ROOT / "org2" / "Navyug_Employee_Handbook.pdf")


def navyug_benefits():
    d = Doc(NAV, "Benefits Policy", "Applicable to all confirmed employees")
    d.section(
        "Provident Fund",
        "The employee and the company each contribute <b>12% of basic salary</b> to the Provident Fund (PF).",
    )
    d.section(
        "Gratuity",
        "As company policy, gratuity is paid to employees who complete <b>5 years of continuous service</b>. It "
        "equals 15 days of last drawn basic salary for each completed year of service: "
        "(15 x last drawn monthly basic x years of service) / 26.",
    )
    d.section(
        "Health Insurance",
        f"Every confirmed employee is covered by a family floater health insurance policy of <b>{inr(500000)}</b> "
        f"(5 lakh), covering the employee, spouse and up to 2 children. A top-up of {inr(300000)} (3 lakh) "
        "is available at the employee's own cost.",
    )
    d.section(
        "Relocation Allowance",
        f"An employee who relocates to another Navyug office at the company's request receives a one-time "
        f"relocation allowance of <b>{inr(50000)}</b>, plus one-way economy travel for the employee and "
        "family.",
    )
    d.section(
        "Gratuity Example",
        f"An employee with a last drawn monthly basic salary of {inr(60000)} who leaves after 8 years of "
        f"continuous service receives (15 x {inr(60000)} x 8) / 26 = {inr(276923)}, rounded to the nearest "
        "rupee. An employee who leaves after 4 years and 11 months does not receive gratuity under this "
        "policy.",
    )
    d.section(
        "Insurance Details",
        "Health insurance starts on the date of confirmation. It covers hospitalisation, day-care procedures "
        "and pre- and post-hospitalisation costs for 30 and 60 days. Parents can be added at the employee's "
        "own cost. Maternity expenses are covered up to " + inr(75000) + " per delivery.",
    )
    d.section(
        "Term Life Insurance",
        "The company provides term life insurance of <b>3 times the annual fixed salary</b> for every confirmed "
        "employee, at no cost to the employee.",
    )
    d.section(
        "Meal Card and Internet Allowance",
        f"Employees receive a meal card of <b>{inr(2200)} per month</b>. Employees who work from home on "
        f"approved days receive an internet allowance of <b>{inr(1000)} per month</b>, paid against a bill.",
    )
    d.section(
        "Learning Budget",
        f"Every confirmed employee has a learning budget of <b>{inr(30000)} per financial year</b> for courses, "
        "books and certifications related to their work. Unused budget does not carry forward. Employees who "
        "leave within 12 months of a certification paid by the company must repay it in full.",
    )
    d.section(
        "Relocation Details",
        "In addition to the relocation allowance, the company provides temporary accommodation for up to "
        "<b>30 days</b> in the new city. The allowance is paid in the month of joining the new office.",
    )
    d.section(
        "Insurance Claims",
        "For planned hospitalisation, inform the insurance desk at least <b>3 days</b> in advance to get "
        "cashless approval. For emergencies, inform within <b>24 hours</b> of admission. Reimbursement claims "
        "must be filed within <b>30 days</b> of discharge with original bills, the discharge summary and "
        "prescriptions. Claims are settled within 30 days of complete documents.",
    )
    d.section(
        "National Pension System",
        "Employees may choose to have up to <b>10% of basic salary</b> contributed to the National Pension "
        "System (NPS) as part of their fixed pay. The choice can be changed once per financial year, in April.",
    )
    d.section("Eligibility Summary", "Which benefits start when:")
    d.table([["Benefit", "Starts from"], ["Provident Fund", "Date of joining"],
             ["Health insurance", "Date of confirmation (after 6 months)"],
             ["Term life insurance", "Date of confirmation"], ["Meal card", "Date of joining"],
             ["Learning budget", "Date of confirmation"], ["Gratuity", "After 5 years of continuous service"]],
            [2.4, 3.2])
    d.faq([
        ("I have worked 4 years and 6 months. Do I get gratuity?",
         "No. Under company policy gratuity needs 5 years of continuous service."),
        ("How much does the company contribute to PF?", "12% of basic salary, matched by 12% from the employee."),
        ("What is my health insurance cover?",
         f"{inr(500000)} (5 lakh) family floater for the employee, spouse and up to 2 children."),
        ("Is there a relocation allowance if I move from Pune to Bengaluru?",
         f"Yes. A one-time {inr(50000)} plus one-way economy travel, if the move is at the company's request."),
        ("Does the learning budget carry over to next year?", "No. Unused budget lapses at the financial year end."),
    ])
    d.save(ROOT / "org2" / "Navyug_Benefits_Policy.pdf")


if __name__ == "__main__":
    for build in (nit_scholarship, nit_fees, nit_academics, navyug_leave, navyug_handbook, navyug_benefits):
        build()
