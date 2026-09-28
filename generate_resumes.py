import os
from fpdf import FPDF

resumes_dir = os.path.expandvars(r'%LOCALAPPDATA%\AI Recruitment System\data\resumes')
os.makedirs(resumes_dir, exist_ok=True)

candidates = [
    {
        'name': 'Alice Smith',
        'file': 'alice_smith_resume.pdf',
        'content': '''Alice Smith
Email: alice@example.com | Phone: 555-0101
Location: San Francisco, CA

PROFESSIONAL SUMMARY
Highly skilled Senior Software Engineer with 8 years of experience in full-stack web development. Passionate about building scalable cloud architectures and leading agile teams to deliver high-quality software.

EXPERIENCE
Senior Software Engineer | TechCorp Inc. | 2019 - Present
- Architected and deployed microservices using Python, FastAPI, and Docker.
- Reduced API latency by 40% through aggressive caching and database query optimization.
- Mentored 5 junior developers and led the transition to CI/CD pipelines using GitHub Actions.

Software Developer | StartUp LLC | 2015 - 2019
- Developed responsive front-end interfaces using React and Redux.
- Built RESTful APIs using Node.js and Express.

EDUCATION
B.S. in Computer Science | University of California, Berkeley | 2011 - 2015

SKILLS
Languages: Python, JavaScript, TypeScript, SQL
Frameworks: React, Node.js, FastAPI, Flask, Django
Tools: Docker, Kubernetes, AWS, Git
'''
    },
    {
        'name': 'Bob Jones',
        'file': 'bob_jones_resume.pdf',
        'content': '''Bob Jones
Email: bob.jones@email.com | Phone: 555-0202
Location: Austin, TX

OBJECTIVE
Motivated Data Scientist looking to leverage machine learning and statistical analysis to drive business growth. 

EXPERIENCE
Data Analyst | DataWorks | 2021 - Present
- Analyzed large datasets using Python (Pandas, NumPy) to identify customer behavior trends.
- Built interactive Tableau dashboards for executive reporting.
- Developed predictive models for customer churn with 85% accuracy using Scikit-Learn.

Marketing Intern | SalesGen | 2020 - 2021
- Assisted in A/B testing of email campaigns.
- Managed social media analytics reporting.

EDUCATION
M.S. Data Science | University of Texas at Austin | 2021
B.A. Business Administration | Texas A&M | 2019

SKILLS
Python, SQL, R, Machine Learning, Data Visualization (Tableau, PowerBI), Excel
'''
    },
    {
        'name': 'Charlie Brown',
        'file': 'charlie_brown_resume.pdf',
        'content': '''Charlie Brown
Email: charlie.b@example.com | Phone: 555-0303
Location: Seattle, WA

SUMMARY
Results-driven Product Manager with 5 years of experience leading cross-functional teams to launch consumer-facing mobile applications.

EXPERIENCE
Product Manager | MobileFirst | 2020 - Present
- Led the development and launch of 3 flagship mobile apps on iOS and Android.
- Conducted user research and translated feedback into actionable product requirements.
- Coordinated with engineering, design, and marketing teams to ensure on-time delivery.

Business Analyst | Enterprise Solutions | 2017 - 2020
- Gathered and documented technical requirements for ERP implementations.
- Streamlined internal reporting processes, saving 15 hours per week.

EDUCATION
B.S. Information Systems | University of Washington | 2017

SKILLS
Agile/Scrum, Jira, Wireframing, User Story Mapping, Stakeholder Management
'''
    }
]

for cand in candidates:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font('Arial', size=11)
    
    # encode to latin-1 to avoid fpdf character issues
    text = cand['content'].encode('latin-1', 'replace').decode('latin-1')
    
    pdf.multi_cell(0, 5, txt=text)
    
    out_path = os.path.join(resumes_dir, cand['file'])
    pdf.output(out_path)
    print(f'Generated {out_path}')

