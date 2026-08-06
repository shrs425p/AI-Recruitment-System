import argparse
import datetime as dt
import os
import random

from fpdf import FPDF
from fpdf.enums import XPos, YPos

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MONTHS = [
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
]

FIRST_NAMES = [
    "Aiden",
    "Amelia",
    "Aria",
    "Ava",
    "Benjamin",
    "Blake",
    "Cameron",
    "Charlotte",
    "Chloe",
    "Daniel",
    "Eli",
    "Ella",
    "Ethan",
    "Gabriel",
    "Grace",
    "Hannah",
    "Henry",
    "Isabella",
    "Jackson",
    "James",
    "Jasmine",
    "Jordan",
    "Joseph",
    "Julian",
    "Kara",
    "Layla",
    "Liam",
    "Lila",
    "Lucas",
    "Maya",
    "Mia",
    "Mila",
    "Nathan",
    "Noah",
    "Nora",
    "Olivia",
    "Owen",
    "Parker",
    "Quinn",
    "Riley",
    "Ryan",
    "Samantha",
    "Sara",
    "Sophia",
    "Tessa",
    "Thomas",
    "Victoria",
    "William",
    "Zoe",
]

LAST_NAMES = [
    "Adams",
    "Allen",
    "Baker",
    "Barnes",
    "Bell",
    "Brooks",
    "Brown",
    "Campbell",
    "Carter",
    "Clark",
    "Collins",
    "Cooper",
    "Cox",
    "Davis",
    "Edwards",
    "Evans",
    "Fisher",
    "Flores",
    "Foster",
    "Garcia",
    "Gomez",
    "Gonzalez",
    "Gray",
    "Green",
    "Harris",
    "Henderson",
    "Hughes",
    "Jackson",
    "Kelly",
    "King",
    "Lee",
    "Lewis",
    "Lopez",
    "Martin",
    "Martinez",
    "Mitchell",
    "Moore",
    "Morgan",
    "Nelson",
    "Parker",
    "Perez",
    "Phillips",
    "Price",
    "Ramirez",
    "Reed",
    "Rivera",
    "Roberts",
    "Robinson",
    "Rogers",
    "Scott",
    "Stewart",
    "Taylor",
    "Thomas",
    "Thompson",
    "Turner",
    "Walker",
    "White",
    "Wilson",
    "Wood",
    "Young",
]

CITIES = [
    ("Austin", "TX"),
    ("Boston", "MA"),
    ("Charlotte", "NC"),
    ("Chicago", "IL"),
    ("Columbus", "OH"),
    ("Dallas", "TX"),
    ("Denver", "CO"),
    ("Detroit", "MI"),
    ("Irvine", "CA"),
    ("Kansas City", "MO"),
    ("Las Vegas", "NV"),
    ("Madison", "WI"),
    ("Minneapolis", "MN"),
    ("Nashville", "TN"),
    ("Newark", "NJ"),
    ("Orlando", "FL"),
    ("Phoenix", "AZ"),
    ("Portland", "OR"),
    ("Raleigh", "NC"),
    ("Sacramento", "CA"),
    ("Salt Lake City", "UT"),
    ("San Diego", "CA"),
    ("San Jose", "CA"),
    ("St. Louis", "MO"),
    ("Tampa", "FL"),
]

COMPANY_PREFIXES = [
    "Northwind",
    "Blue Ridge",
    "Silver Pine",
    "Summit Ridge",
    "Harbor Point",
    "Maple Street",
    "Riverstone",
    "Cedar Grove",
    "Red Oak",
    "Lakeshore",
    "Evergreen",
    "Ironwood",
    "Clearwater",
    "Prairie",
    "Skyline",
    "Sierra",
    "Granite",
    "Beacon",
    "Horizon",
    "Juniper",
    "Keystone",
    "Pioneer",
    "Seabright",
    "Westbrook",
    "Willow",
]

COMPANY_SUFFIXES = [
    "Labs",
    "Solutions",
    "Group",
    "Partners",
    "Systems",
    "Analytics",
    "Holdings",
    "Logistics",
    "Manufacturing",
    "Retail",
    "Digital",
    "Health",
    "Energy",
    "Capital",
    "Ventures",
    "Media",
    "Consulting",
    "Networks",
    "Services",
]

UNIVERSITIES = [
    "North Valley University",
    "Cedar Ridge College",
    "Rivergate Institute of Technology",
    "Lakeside University",
    "Summit State University",
    "Pinecrest College",
    "Westbrook University",
    "Silver Pine Institute",
    "Redwood State College",
    "Oakview University",
    "Clearwater University",
    "Granite Bay College",
    "Horizon Tech Institute",
    "Prairie State University",
    "Evergreen College",
]

ROLE_TEMPLATES = {
    "software": {
        "label": "Software Engineer",
        "titles": {
            "junior": ["Software Engineer I", "Junior Software Engineer", "Backend Engineer I"],
            "mid": ["Software Engineer", "Backend Engineer", "Full Stack Engineer"],
            "senior": ["Senior Software Engineer", "Staff Software Engineer", "Lead Backend Engineer"],
        },
        "skills": [
            "Python",
            "JavaScript",
            "SQL",
            "REST APIs",
            "Docker",
            "AWS",
            "CI/CD",
            "Git",
            "PostgreSQL",
            "Unit Testing",
        ],
        "certs": ["AWS Certified Developer", "Azure Developer Associate", "CKA"],
        "majors": ["Computer Science", "Software Engineering", "Information Systems"],
        "tools": ["GitHub Actions", "Jenkins", "Docker", "Kubernetes", "Terraform"],
        "tech": ["Python", "Go", "TypeScript", "Flask", "FastAPI"],
        "domains": ["payments", "onboarding", "analytics", "billing", "identity"],
        "kpi": ["availability", "throughput", "error rate", "latency", "quality"],
        "bullets": [
            "Built {domain} services in {tech}, improving {kpi} by {metric_pct}%.",
            "Reduced {domain} latency by {metric_pct}% through {tech2} and profiling.",
            "Implemented CI/CD in {tool}, cutting release time by {metric_pct2}%.",
            "Collaborated with {stakeholder} to deliver {platform} features for {users} users.",
            "Designed {artifact} and API contracts, lowering defects by {metric_pct}%.",
        ],
        "projects": [
            "Event-Driven Billing Service",
            "SRE Readiness Initiative",
            "Internal Developer Portal",
            "Customer Identity Migration",
        ],
    },
    "data": {
        "label": "Data Analyst",
        "titles": {
            "junior": ["Data Analyst", "Junior Data Analyst", "Reporting Analyst"],
            "mid": ["Data Analyst", "Analytics Engineer", "Business Intelligence Analyst"],
            "senior": ["Senior Data Analyst", "Lead Analytics Engineer", "Data Insights Lead"],
        },
        "skills": [
            "SQL",
            "Python",
            "Tableau",
            "Power BI",
            "Data Modeling",
            "ETL",
            "Statistics",
            "A/B Testing",
            "Data Quality",
            "Stakeholder Management",
        ],
        "certs": ["Tableau Desktop Specialist", "Google Data Analytics", "Microsoft Power BI"],
        "majors": ["Data Analytics", "Statistics", "Information Systems", "Economics"],
        "tools": ["Tableau", "Power BI", "Looker", "Airflow", "dbt"],
        "tech": ["SQL", "Python", "Snowflake", "BigQuery", "Databricks"],
        "domains": ["revenue", "growth", "customer success", "supply chain", "product"],
        "kpi": ["retention", "conversion", "forecast accuracy", "cycle time", "NPS"],
        "bullets": [
            "Developed ETL pipelines in {tech}, reducing refresh time by {metric_pct}%.",
            "Built {artifact} in {tool} to track {kpi} across {region}.",
            "Modeled {domain} data in {tech2}, improving data quality by {metric_pct2}%.",
            "Partnered with {stakeholder} to define {kpi} and success metrics.",
            "Automated {process}, saving {metric_weeks} weeks per quarter.",
        ],
        "projects": [
            "Customer Health Dashboard",
            "Forecast Accuracy Program",
            "Data Quality Scorecard",
            "Revenue Attribution Model",
        ],
    },
    "product": {
        "label": "Product Manager",
        "titles": {
            "junior": ["Associate Product Manager", "Product Analyst", "Product Coordinator"],
            "mid": ["Product Manager", "Product Owner", "Technical Product Manager"],
            "senior": ["Senior Product Manager", "Group Product Manager", "Product Lead"],
        },
        "skills": [
            "Roadmapping",
            "User Research",
            "OKRs",
            "Agile",
            "Go-To-Market",
            "Analytics",
            "Stakeholder Alignment",
            "PRDs",
            "Experimentation",
            "Competitive Analysis",
        ],
        "certs": ["Pragmatic Product Management", "Certified Scrum Product Owner"],
        "majors": ["Business", "Information Systems", "Marketing", "Industrial Engineering"],
        "tools": ["Jira", "Aha!", "Productboard", "Confluence", "Asana"],
        "tech": ["APIs", "mobile", "web", "platform", "integrations"],
        "domains": ["self-serve onboarding", "billing", "workflow automation", "reporting"],
        "kpi": ["activation", "retention", "conversion", "ARR", "NPS"],
        "bullets": [
            "Owned roadmap for {platform} product, increasing {kpi} by {metric_pct}%.",
            "Led discovery with {stakeholder}, translating insights into {artifact}.",
            "Shipped {domain} enhancements for {customer} customers, boosting {kpi} by {metric_pct2}%.",
            "Defined OKRs and tracked outcomes in {tool}.",
            "Coordinated launch with {campaign}, delivering in {timeframe}.",
        ],
        "projects": [
            "Pricing and Packaging Refresh",
            "Self-Serve Onboarding",
            "Enterprise Reporting Suite",
            "Workflow Automation",
        ],
    },
    "design": {
        "label": "UX Designer",
        "titles": {
            "junior": ["UX Designer", "Junior Product Designer", "UI Designer"],
            "mid": ["Product Designer", "UX Designer", "Interaction Designer"],
            "senior": ["Senior Product Designer", "Lead UX Designer", "Design Lead"],
        },
        "skills": [
            "Figma",
            "User Research",
            "Wireframing",
            "Prototyping",
            "Design Systems",
            "Accessibility",
            "Information Architecture",
            "Usability Testing",
            "Visual Design",
            "Design Ops",
        ],
        "certs": ["NNg UX Certification", "Google UX Design"],
        "majors": ["Design", "Human-Computer Interaction", "Graphic Design"],
        "tools": ["Figma", "Sketch", "InVision", "Miro", "Adobe XD"],
        "tech": ["design systems", "prototypes", "components", "design tokens"],
        "domains": ["checkout", "account setup", "analytics", "search"],
        "kpi": ["task success", "conversion", "engagement", "CSAT"],
        "bullets": [
            "Led UX research with {metric_num} users to refine {domain} flows.",
            "Designed {platform} experiences in {tool}, improving {kpi} by {metric_pct}%.",
            "Created {artifact} and component specs for engineers.",
            "Partnered with {stakeholder} to align {artifact} with brand.",
            "Ran A/B tests, increasing {kpi} by {metric_pct2}%.",
        ],
        "projects": [
            "Design System Rollout",
            "Checkout Experience Redesign",
            "Mobile Navigation Refresh",
            "Customer Insights Hub",
        ],
    },
    "hr": {
        "label": "HR Specialist",
        "titles": {
            "junior": ["HR Coordinator", "Recruiting Coordinator", "People Operations Associate"],
            "mid": ["HR Specialist", "People Operations Specialist", "Talent Acquisition Partner"],
            "senior": ["Senior HR Specialist", "People Operations Lead", "Talent Acquisition Lead"],
        },
        "skills": [
            "Recruiting",
            "Employee Relations",
            "Onboarding",
            "Performance Reviews",
            "HRIS",
            "Compliance",
            "Compensation",
            "Training",
            "Policy Development",
            "Workforce Planning",
        ],
        "certs": ["SHRM-CP", "PHR"],
        "majors": ["Human Resources", "Business", "Psychology"],
        "tools": ["Greenhouse", "Workday", "BambooHR", "Lever"],
        "tech": ["HRIS", "surveys", "automation", "analytics"],
        "domains": ["onboarding", "performance", "benefits", "engagement"],
        "kpi": ["time-to-fill", "retention", "engagement", "offer acceptance"],
        "bullets": [
            "Streamlined {process}, reducing time-to-fill by {metric_pct}%.",
            "Owned onboarding for {volume} hires, improving {kpi} scores.",
            "Built {artifact} in {tool} for compliance tracking.",
            "Partnered with {stakeholder} to roll out {domain} programs.",
            "Improved retention by {metric_pct2}% via {campaign}.",
        ],
        "projects": [
            "Onboarding Standardization",
            "Engagement Survey Program",
            "Interview Training Curriculum",
            "Performance Review Refresh",
        ],
    },
    "sales": {
        "label": "Account Executive",
        "titles": {
            "junior": ["Sales Development Representative", "Account Executive", "Sales Associate"],
            "mid": ["Account Executive", "Senior Account Executive", "Strategic Account Executive"],
            "senior": ["Sales Manager", "Enterprise Account Executive", "Regional Sales Lead"],
        },
        "skills": [
            "Pipeline Management",
            "Negotiation",
            "CRM",
            "Prospecting",
            "Account Planning",
            "Forecasting",
            "Territory Strategy",
            "Contracting",
            "Stakeholder Alignment",
            "Presentation",
        ],
        "certs": ["Salesforce Administrator", "Miller Heiman Sales"],
        "majors": ["Business", "Marketing", "Communications"],
        "tools": ["Salesforce", "HubSpot", "Outreach", "Gong"],
        "tech": ["sales automation", "CRM", "enablement"],
        "domains": ["renewals", "expansion", "pipeline growth"],
        "kpi": ["quota attainment", "win rate", "pipeline coverage"],
        "bullets": [
            "Closed {volume} {customer} deals totaling {revenue} in ARR.",
            "Exceeded quota by {metric_pct}% through {process} improvements.",
            "Built pipeline reports in {tool} to track {kpi}.",
            "Led {campaign} outreach, increasing meetings by {metric_pct2}%.",
            "Collaborated with {stakeholder} to refine {artifact}.",
        ],
        "projects": [
            "Territory Realignment",
            "Pipeline Forecasting Model",
            "Enterprise Account Plans",
            "Renewal Playbook",
        ],
    },
    "marketing": {
        "label": "Marketing Manager",
        "titles": {
            "junior": ["Marketing Coordinator", "Digital Marketing Specialist", "Content Specialist"],
            "mid": ["Marketing Manager", "Growth Marketing Manager", "Demand Generation Manager"],
            "senior": ["Senior Marketing Manager", "Marketing Director", "Growth Lead"],
        },
        "skills": [
            "Campaign Management",
            "SEO",
            "Content Strategy",
            "Email Marketing",
            "Paid Media",
            "Analytics",
            "Brand Messaging",
            "Lifecycle Marketing",
            "A/B Testing",
            "Partner Marketing",
        ],
        "certs": ["Google Analytics", "HubSpot Inbound"],
        "majors": ["Marketing", "Communications", "Business"],
        "tools": ["Google Analytics", "HubSpot", "Marketo", "SEMrush"],
        "tech": ["automation", "segmentation", "attribution"],
        "domains": ["product launches", "content", "events"],
        "kpi": ["pipeline", "MQLs", "CTR", "CAC"],
        "bullets": [
            "Grew {kpi} by {metric_pct}% via {campaign} and SEO.",
            "Managed {budget} budget across {region} campaigns.",
            "Built {artifact} in {tool} to monitor funnel performance.",
            "Launched {domain} messaging for {customer} audience.",
            "Improved CTR by {metric_pct2}% through creative testing.",
        ],
        "projects": [
            "Product Launch Campaign",
            "Lifecycle Email Refresh",
            "SEO Content Hub",
            "Partner Marketing Program",
        ],
    },
    "finance": {
        "label": "Financial Analyst",
        "titles": {
            "junior": ["Financial Analyst", "Junior Financial Analyst", "FP&A Analyst"],
            "mid": ["Financial Analyst", "Senior Financial Analyst", "Finance Manager"],
            "senior": ["Senior Finance Manager", "FP&A Lead", "Director of Finance"],
        },
        "skills": [
            "Financial Modeling",
            "Budgeting",
            "Forecasting",
            "Variance Analysis",
            "Excel",
            "Business Partnering",
            "KPI Reporting",
            "Cost Optimization",
            "Scenario Planning",
            "Presentation",
        ],
        "certs": ["CFA Level I", "CPA"],
        "majors": ["Finance", "Accounting", "Economics"],
        "tools": ["Excel", "Adaptive Insights", "Anaplan", "Power BI"],
        "tech": ["automation", "financial models", "reporting"],
        "domains": ["operating expense", "revenue", "cash flow"],
        "kpi": ["forecast accuracy", "margin", "cost savings"],
        "bullets": [
            "Built {artifact} for {domain} forecasting, reducing variance to {metric_pct}%.",
            "Managed {budget} operating budget and monthly close.",
            "Automated {process} in {tool}, saving {metric_weeks} weeks per year.",
            "Partnered with {stakeholder} on {domain} investment cases.",
            "Improved margin by {metric_pct2}% through cost optimization.",
        ],
        "projects": [
            "Annual Planning Model",
            "Cost Optimization Review",
            "Revenue Forecasting Toolkit",
            "Investor Metrics Pack",
        ],
    },
}

SUMMARY_TEMPLATES = {
    "junior": [
        "Early-career {label} with {years} years of experience and a focus on quality execution.",
        "Motivated {label} with hands-on experience delivering projects in fast-paced teams.",
        "Detail-oriented {label} with {years} years of experience and a strong foundation in core tools.",
    ],
    "mid": [
        "Experienced {label} with {years}+ years driving measurable outcomes across cross-functional teams.",
        "Results-driven {label} with {years}+ years of experience improving {kpi} and operational performance.",
        "Proven {label} with {years}+ years leading initiatives from discovery to delivery.",
    ],
    "senior": [
        "Senior {label} with {years}+ years leading strategy, execution, and stakeholder alignment.",
        "Strategic {label} with {years}+ years building scalable programs and coaching teams.",
        "Seasoned {label} with {years}+ years delivering high-impact outcomes across the organization.",
    ],
}

PROJECT_BULLETS = [
    "Defined scope and milestones with {stakeholder} to deliver in {timeframe}.",
    "Built {artifact} using {tool}, improving {kpi} by {metric_pct}%.",
    "Automated {process} with {tech}, saving {metric_weeks} weeks annually.",
    "Created documentation and training materials for {stakeholder}.",
]


def parse_args():
    parser = argparse.ArgumentParser(description="Generate synthetic resume PDFs.")
    parser.add_argument("--count", type=int, default=100)
    parser.add_argument("--output", default=os.path.join("data", "resumes"))
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def month_year(date_value):
    return f"{MONTHS[date_value.month - 1]} {date_value.year}"


def add_months(date_value, months):
    month_index = date_value.month - 1 + months
    year = date_value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(date_value.day, 28)
    return dt.date(year, month, day)


def random_company():
    return f"{random.choice(COMPANY_PREFIXES)} {random.choice(COMPANY_SUFFIXES)}"


def unique_name(used):
    for _ in range(5000):
        name = f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"
        if name not in used:
            used.add(name)
            return name
    raise RuntimeError("Could not generate unique name")


def build_context(role_data):
    def pick(key, fallback):
        return random.choice(role_data.get(key, fallback))

    return {
        "metric_pct": str(random.choice([8, 10, 12, 15, 18, 22, 25, 30])),
        "metric_pct2": str(random.choice([6, 9, 11, 14, 16, 20, 24, 28])),
        "metric_num": str(random.choice([12, 15, 18, 20, 24, 30, 40, 55])),
        "metric_days": str(random.choice([2, 3, 4, 5, 7])),
        "metric_weeks": str(random.choice([2, 3, 4, 6, 8])),
        "kpi": pick("kpi", ["quality", "throughput", "retention", "conversion"]),
        "tool": pick("tools", ["Excel", "Google Sheets"]),
        "tool2": pick("tools", ["Jira", "Asana"]),
        "tech": pick("tech", ["automation", "Python"]),
        "tech2": pick("tech", ["automation", "Python"]),
        "domain": pick("domains", ["operations", "customer experience", "growth"]),
        "artifact": pick("artifacts", ["dashboards", "playbooks", "process docs", "roadmaps"]),
        "stakeholder": pick("stakeholders", ["cross-functional teams", "leadership", "clients"]),
        "process": pick("processes", ["forecasting", "planning", "quality review"]),
        "platform": pick("platforms", ["web", "mobile", "internal tools"]),
        "campaign": pick("campaigns", ["product launch", "nurture program", "paid search"]),
        "region": pick("regions", ["North America", "EMEA", "APAC"]),
        "budget": random.choice(["$1.2M", "$2.5M", "$3.8M", "$5.0M"]),
        "revenue": random.choice(["$450K", "$900K", "$1.4M", "$2.2M"]),
        "users": random.choice(["15k", "30k", "50k", "120k"]),
        "volume": random.choice(["120+", "250+", "400+", "750+"]),
        "timeframe": random.choice(["2 weeks", "4 weeks", "6 weeks", "1 quarter"]),
        "customer": random.choice(["enterprise", "mid-market", "SMB"]),
    }


def pick_seniority_mix(count):
    counts = {
        "junior": int(count * 0.4),
        "mid": int(count * 0.4),
    }
    counts["senior"] = count - counts["junior"] - counts["mid"]
    mix = ["junior"] * counts["junior"] + ["mid"] * counts["mid"] + ["senior"] * counts["senior"]
    random.shuffle(mix)
    return mix


def build_experience(seniority):
    if seniority == "junior":
        return 2
    if seniority == "mid":
        return 3
    return 4


def experience_years(seniority):
    if seniority == "junior":
        return random.choice([1, 2, 3])
    if seniority == "mid":
        return random.choice([4, 5, 6, 7, 8])
    return random.choice([9, 10, 11, 12, 13, 14, 15])


def date_ranges(num_roles, seniority):
    end_date = dt.date(2026, 5, 1)
    ranges = []
    gap_months = [1, 2, 3]
    if seniority == "senior":
        durations = (24, 48)
    elif seniority == "mid":
        durations = (18, 36)
    else:
        durations = (14, 28)

    for idx in range(num_roles):
        months = random.randint(*durations)
        start_date = add_months(end_date, -months)
        if idx == 0 and random.random() < 0.7:
            end_label = "Present"
        else:
            end_label = month_year(end_date)
        ranges.append((month_year(start_date), end_label))
        end_date = add_months(start_date, -random.choice(gap_months))
    return ranges


def format_contact(name, index, city_state):
    first, last = name.split(" ")
    email = f"{first.lower()}.{last.lower()}{index:02d}@example.com"
    phone = f"(555) 010-{1000 + index:04d}"
    city, state = city_state
    return f"{city}, {state} | {phone} | {email}"


def add_section(pdf, title):
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 6, title, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "", 10)


def add_bullets(pdf, bullets, indent=4):
    for item in bullets:
        pdf.set_x(pdf.l_margin + indent)
        pdf.multi_cell(0, 5, f"- {item}")
    pdf.set_x(pdf.l_margin)
    pdf.ln(1)


def render_resume(index, role_key, seniority, output_dir, used_names):
    role_data = ROLE_TEMPLATES[role_key]
    name = unique_name(used_names)
    city_state = random.choice(CITIES)
    ctx = build_context(role_data)
    years = experience_years(seniority)

    summary_template = random.choice(SUMMARY_TEMPLATES[seniority])
    summary = summary_template.format(label=role_data["label"], years=years, kpi=ctx["kpi"])
    summary += " " + random.choice(
        [
            f"Skilled in {random.choice(role_data['skills'])} and {random.choice(role_data['skills'])}.",
            f"Known for improving {ctx['kpi']} and delivering on tight timelines.",
            f"Comfortable partnering with {ctx['stakeholder']} to drive outcomes.",
        ]
    )

    title = random.choice(role_data["titles"][seniority])
    skills = sorted(set(random.sample(role_data["skills"], k=8)))

    pdf = FPDF("P", "mm", "Letter")
    pdf.set_auto_page_break(auto=True, margin=12)
    pdf.set_margins(15, 15, 15)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 8, name, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 6, title, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 5, format_contact(name, index, city_state), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(2)

    add_section(pdf, "SUMMARY")
    pdf.multi_cell(0, 5, summary)
    pdf.ln(1)

    add_section(pdf, "SKILLS")
    pdf.multi_cell(0, 5, ", ".join(skills))
    pdf.ln(1)

    add_section(pdf, "EXPERIENCE")
    exp_count = build_experience(seniority)
    date_labels = date_ranges(exp_count, seniority)

    for idx in range(exp_count):
        job_title = random.choice(role_data["titles"][seniority if idx == 0 else "mid"]) if seniority != "junior" else random.choice(role_data["titles"]["junior"])
        company = random_company()
        location = f"{random.choice(CITIES)[0]}, {random.choice(CITIES)[1]}"
        start_label, end_label = date_labels[idx]

        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(0, 5, f"{job_title} | {company} | {location}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(0, 5, f"{start_label} - {end_label}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        bullets = [random.choice(role_data["bullets"]).format_map(ctx) for _ in range(random.randint(3, 5))]
        add_bullets(pdf, bullets)

    add_section(pdf, "PROJECTS")
    for _ in range(2):
        project = random.choice(role_data["projects"])
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(0, 5, project, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_font("Helvetica", "", 10)
        project_bullets = [random.choice(PROJECT_BULLETS).format_map(ctx) for _ in range(2)]
        add_bullets(pdf, project_bullets)

    add_section(pdf, "EDUCATION")
    degree = "B.S." if seniority != "senior" else random.choice(["B.S.", "M.S.", "MBA"])
    major = random.choice(role_data["majors"])
    grad_year = random.choice([2024, 2023, 2022, 2021, 2020])
    if seniority == "mid":
        grad_year = random.choice([2018, 2017, 2016, 2015, 2014])
    if seniority == "senior":
        grad_year = random.choice([2012, 2011, 2010, 2009, 2008])

    university = random.choice(UNIVERSITIES)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 5, f"{degree} in {major}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 5, f"{university} | {grad_year}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(1)

    add_section(pdf, "CERTIFICATIONS")
    certs = random.sample(role_data["certs"], k=min(2, len(role_data["certs"])))
    if not certs:
        certs = ["Professional Development Coursework"]
    add_bullets(pdf, certs, indent=2)

    filename = f"resume_{index:03d}.pdf"
    output_path = os.path.join(output_dir, filename)
    pdf.output(output_path)


def main():
    args = parse_args()
    random.seed(args.seed)

    output_dir = args.output
    if not os.path.isabs(output_dir):
        output_dir = os.path.join(ROOT_DIR, output_dir)

    os.makedirs(output_dir, exist_ok=True)

    roles = list(ROLE_TEMPLATES.keys())
    used_names = set()
    seniority_mix = pick_seniority_mix(args.count)

    for idx in range(1, args.count + 1):
        role_key = roles[(idx - 1) % len(roles)]
        seniority = seniority_mix[idx - 1]
        render_resume(idx, role_key, seniority, output_dir, used_names)

    print(f"Generated {args.count} resumes in {output_dir}")


if __name__ == "__main__":
    main()
