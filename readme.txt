AI-powered Natural Language Data Analytics Platform
Project Start date -25-09-26
By gurpreet singh
Complete flow 
Kaggle CSV
    ↓
Data Cleaning
    ↓
MySQL Database
    ↓
Backend (FastAPI)
    ↓
AI / LLM
    ↓
User Question
    ↓
Natural Language → SQL
    ↓
MySQL Query
    ↓
Pandas Analysis
    ↓
Matplotlib / Plotly Chart
    ↓
AI Explanation
    ↓
Recommendations
    ↓
Warnings / Risks
    ↓
Website


Architecture:

                 YOUR WEBSITE
                     ↓
            "Ask your data..."
                     ↓
                FastAPI
                     ↓
              Local LLM
             (Ollama model)
                     ↓
        ┌────────────┴────────────┐
        ↓                         ↓
   Generate SQL            Generate analysis
        ↓                         ↓
      MySQL               Python/Pandas
        ↓                         ↓
    Query result         Matplotlib/Plotly
        └────────────┬────────────┘
                     ↓
                AI explains
                     ↓
        Insights + Recommendations
        + Warnings + Graph + Table

In this project we are using 3 ai layer 
1. Query AI
Natural Language
      ↓
SQL / analysis plan
2. Visualization AI
"show trend"
"make pie chart"
"compare branches"
      ↓
chart specification
For example:
{
  "chart": "line",
  "x": "year",
  "y": "placement_rate"
}
3. Insight AI
Actual results
      ↓
Insights
      ↓
Recommendations
      ↓
Warnings
Phase 1: Kaggle CSV → MySQL
Phase 2: Python → MySQL se data read
Phase 3: 20–30 manual analytics queries
Phase 4: FastAPI backend
Phase 5: React UI
Phase 6: Ollama integration
Phase 7: Natural language → structured analytics plan
Phase 8: SQL execution + Pandas
Phase 9: Matplotlib/Plotly auto charts
Phase 10: AI insights/recommendations/warnings
Phase 11: Google login + project history


Start project now 
User Login
    ↓
Upload / Select Dataset
    ↓
Ask question in natural language
    ↓
Gemini understands question
    ↓
Analytics Plan
    ↓
SQL → MySQL
    ↓
Pandas / NumPy
    ↓
Matplotlib / Plotly
    ↓
Actual result
    ↓
Gemini explains result
    ↓
Insights + Recommendations + Warnings
    ↓
Interactive Dashboard

Full roadmap 

PHASE 0 — Project Planning
Goal
Project ko properly define karna.
Decide:
•	First dataset: College Placement
•	Database: MySQL
•	Backend: FastAPI + Python
•	Frontend: React + Tailwind
•	AI: Gemini API
•	Analytics: Pandas + NumPy
•	Charts: Matplotlib + Plotly
•	Authentication: Google Login
•	Deployment: free-tier hosting where practical
Deliverable
Ek document:
Project Name
Problem Statement
Features
Tech Stack
Architecture
Database Design
User Flow
________________________________________






PHASE 1 — Dataset Selection & Understanding
Kaggle se ek good-quality placement dataset choose kar.
Dataset check karo
Rows
Columns
Data types
Missing values
Duplicates
Categorical columns
Numerical columns
Example:
student_id
gender
branch
cgpa
internship
aptitude_score
skills
placement_status
package
company
Deliverable
Ek cleaned CSV:
placement_cleaned.csv
Aur ek data dictionary:
Column	Meaning	Type
student_id	Student identifier	INT
cgpa	CGPA	FLOAT
branch	Student branch	VARCHAR
internship	Internship status	BOOLEAN
package	Placement package	FLOAT
Phase complete when
Tu manually bata sake:
“Mere dataset me har column ka kya meaning hai.”
________________________________________












PHASE 2 — Database Design
Ab CSV ko directly dump nahi karna.
Pehle database design.
Example:
placement_analytics
│
├── students
├── companies
├── placements
├── internships
└── skills
Relationship:
Students
   │
   ├──── Internships
   │
   └──── Placements
              │
              └──── Companies
Deliverables
1.	ER Diagram
2.	SQL schema
3.	Primary Keys
4.	Foreign Keys
5.	Unique constraints
6.	NOT NULL
7.	Appropriate indexes
Example:
CREATE DATABASE placement_analytics;
Then:
CREATE TABLE Students (…);
CREATE TABLE Companies (…);
CREATE TABLE Placements (…);
________________________________________




PHASE 3 — Load CSV into MySQL
Ab actual data database me jayega.
Flow:
CSV
 ↓
Python/Pandas
 ↓
Validation
 ↓
MySQL
Check:
SELECT COUNT(*) FROM Students;
SELECT * FROM Students LIMIT 10;
Deliverable
Complete MySQL database populated with dataset.
________________________________________










PHASE 4 — Manual SQL Analytics
⚠️ Ye phase bahut important hai.
AI se pehle manually analytics kar.
At least 25–40 useful SQL questions.
Example:
1. Total students?
2. Placement rate?
3. Average package?
4. Branch-wise placement?
5. Internship vs placement?
6. CGPA vs placement?
7. Company-wise hiring?
8. Highest package?
9. Average package by branch?
10. Students with CGPA > 8?
Then advanced:
JOIN
GROUP BY
HAVING
CASE
CTE
Subqueries
Window functions
Deliverable
Folder:
/sql
   01_basic.sql
   02_grouping.sql
   03_joins.sql
   04_advanced.sql
Why?
Later Gemini will generate queries similar to these.
________________________________________






PHASE 5 — Python Analytics Engine
Now MySQL → Python.
Use:
Pandas
NumPy
Matplotlib
Python should be able to do:
Load SQL data
↓
Clean data
↓
Filter
↓
Group
↓
Aggregate
↓
Calculate metrics
↓
Generate charts
Example:
df.groupby("branch")
and:
placement_rate = placed / total * 100
Deliverable
Create:
analytics_engine/
    loader.py
    cleaning.py
    metrics.py
    charts.py
________________________________________







PHASE 6 — Chart Engine
Don’t let AI directly write arbitrary Matplotlib code initially.
Create controlled chart functions:
create_bar_chart()
create_line_chart()
create_pie_chart()
create_histogram()
create_scatter_plot()
create_box_plot()
Example internally:
create_bar_chart(    dataframe=df,    x=”branch”,    y=”placement_rate”)
Deliverable
Your backend can generate charts based on parameters.
________________________________________











PHASE 7 — FastAPI Backend
Now frontend and analytics ko connect karenge.
Backend structure:
backend/
│
├── main.py
├── database/
├── models/
├── services/
├── analytics/
├── charts/
├── auth/
└── api/
Endpoints:
POST /login
POST /upload
GET  /dataset
POST /query
GET  /history
Later AI endpoints:
POST /ai/analyze
POST /ai/chat
Phase goal
React → FastAPI → MySQL works.
________________________________________
PHASE 8 — React Frontend
Ab beautiful website.
Pages
/login
/dashboard
/dataset
/ask
/history
/profile
Main screen:
┌─────────────────────────────────────────┐
│           Ask Your Data                 │
│                                         │
│ "What is placement rate by internship?" │
│                             [Analyze]   │
└─────────────────────────────────────────┘
Result page
Answer
↓
KPI cards
↓
Graph
↓
Table
↓
Insights
↓
Recommendations
↓
Warnings
Phase goal
Frontend backend se actual data fetch kare.
________________________________________





PHASE 9 — Google Authentication
Ab login add kar.
Flow:
User
 ↓
Continue with Google
 ↓
Google OAuth
 ↓
Backend verifies user
 ↓
Create/find account
 ↓
Dashboard
Database:
Users
Fields:
user_id
google_id
email
name
created_at
Important
Google login ka use:
identity ke liye
Gemini access ke liye nahi.
________________________________________
PHASE 10 — Gemini Integration
🔥 Ab AI add karenge.
Gemini ka role initially:
Natural Language
      ↓
Structured Analytics Plan
Example:
User:
Internship wale students ka placement rate compare karo.
Gemini returns something like:
{
  "intent": "comparison",
  "group_by": "internship",
  "metric": "placement_rate",
  "chart": "bar"
}
Not arbitrary code.
Phase goal
Gemini correctly understands 10–20 predefined questions.
________________________________________




PHASE 11 — Natural Language → SQL
Ab AI ko database schema provide karenge.
Gemini:
Question
↓
Schema
↓
SQL
Example:
"Show average package by branch"
↓
SELECT branch, AVG(package)
FROM placements
GROUP BY branch;
Add SQL validator
Allow:
SELECT
WITH
Block:
DROP
DELETE
UPDATE
INSERT
ALTER
TRUNCATE
Phase goal
AI-generated queries safely execute hon.
________________________________________











PHASE 12 — AI → Analytics Plan → Python
Ab user बोले:
"Branch-wise placement rate ka graph bana do."
Gemini returns:
{
  "group_by": "branch",
  "metric": "placement_rate",
  "chart_type": "bar"
}
Backend:
Plan
 ↓
SQL
 ↓
MySQL
 ↓
Pandas
 ↓
Chart Engine
Phase goal
User ke natural language instructions se automatic chart generate ho.
________________________________________


PHASE 13 — AI Insights
Now actual result Gemini ko do.
Example:
{
  "cse": 82.4,
  "ece": 71.2,
  "me": 64.8
}
Gemini explains:
Key Insight:
CSE has the highest observed placement rate.
Important:
AI ko raw database se answer nahi banana.
Usko calculated result dena hai.
Database/Pandas = numbers
Gemini = explanation
________________________________________








PHASE 14 — Recommendations Engine
Ab recommendation system.
Example result:
Internship:
Yes = 86%
No = 50%
AI:
Recommendation:
Increase internship participation.
Lekin recommendations ko data-backed rakho.
Backend structured findings de:
{
  "metric": "placement_rate",
  "difference": 36,
  "sample_size": 1200
}
Then Gemini converts that into understandable recommendations.
________________________________________








PHASE 15 — Warning / Risk Engine
Ye feature project ko interesting banayega.
Examples:
Small sample
Only 12 students are present in this group.
Interpret results cautiously.
Missing data
28% of package values are missing.
Package analysis may be unreliable.
Correlation warning
This relationship does not establish causation.
Outlier warning
A small number of extreme package values may affect the average.
Some warnings should come from code/rules, not only AI.
________________________________________






PHASE 16 — Conversation / Chat History
Ab system conversational banega.
User:
Placement rate by internship?
AI:
86% vs 50%.
User:
What about CGPA?
AI knows conversation context.
User:
Only for CSE.
AI understands:
Previous question
+
New filter
Database:
chat_sessions
chat_messages
query_history
________________________________________






PHASE 17 — Show the Reasoning/Work
UI me:
[Show SQL]
[Show Analysis]
[Show Dataset]
Example:
Generated SQL
SELECT ...
Analysis
Grouped by: Internship
Metric: Placement Rate
Chart: Bar
This makes the platform transparent.
Don't expose private chain-of-thought; expose the generated SQL, parameters, calculations, and concise rationale instead.
________________________________________







PHASE 18 — Dataset Upload System
Ab user apna CSV upload kar sake.
Flow:
Upload CSV
 ↓
Validate
 ↓
Preview
 ↓
Detect columns
 ↓
Clean
 ↓
Create tables
 ↓
Import MySQL
 ↓
Ask questions
Example:
Rows: 12,430
Columns: 14
Missing: 312
Duplicates: 41
This turns your project from:
"Placement analyzer"
into:
"General AI Data Analytics Platform."
________________________________________












PHASE 19 — Multiple Dataset Support
After placement dataset works:
Placement
Sales
E-commerce
HR
Student Performance
Finance
User chooses:
My Project
   ↓
Placement Dataset
or:
My Project
   ↓
Sales Dataset
________________________________________








PHASE 20 — Security
Before public deployment, do this.
Backend
•	API authentication
•	Rate limiting
•	SQL validation
•	Input validation
•	File-size limits
•	CSV validation
•	Query timeout
•	Error handling
AI
Never allow:
arbitrary Python execution
arbitrary SQL writes
shell commands
User data
Each user's dataset must be isolated.
User A
 ↓
Dataset A

User B
 ↓
Dataset B
No cross-user access.
________________________________________
PHASE 21 — Testing
Create test cases.
SQL
50 questions
→ expected result
AI
50 natural language questions
→ expected analytics plan
Charts
bar
line
pie
histogram
scatter
Edge cases
missing values
empty dataset
wrong column
invalid question
large dataset
duplicate rows
________________________________________



PHASE 22 — Deployment
Once everything works locally:
React
 ↓
Frontend hosting

FastAPI
 ↓
Backend hosting

MySQL
 ↓
Cloud database

Gemini
 ↓
API
For the zero-cost version, use available free tiers and impose sensible user/rate limits.
________________________________________






PHASE 23 — Final Polish
Add:
Dark mode
Loading animations
Error messages
Query history
Export CSV
Download graph
Download report
Maybe:
Export Analysis as PDF
Later.
________________________________________
The exact order you should follow
Don't jump around.
PHASE 0   Planning
   ↓
PHASE 1   Kaggle Dataset
   ↓
PHASE 2   MySQL Design
   ↓
PHASE 3   Import Data
   ↓
PHASE 4   SQL Analytics
   ↓
PHASE 5   Python Analytics
   ↓
PHASE 6   Chart Engine
   ↓
PHASE 7   FastAPI
   ↓
PHASE 8   React
   ↓
PHASE 9   Google Login
   ↓
PHASE 10  Gemini
   ↓
PHASE 11  NL → SQL
   ↓
PHASE 12  NL → Charts
   ↓
PHASE 13  AI Insights
   ↓
PHASE 14  Recommendations
   ↓
PHASE 15  Warnings
   ↓
PHASE 16  Chat History
   ↓
PHASE 17  Transparency
   ↓
PHASE 18  CSV Upload
   ↓
PHASE 19  Multi-Dataset
   ↓
PHASE 20  Security
   ↓
PHASE 21  Testing
   ↓
PHASE 22  Deployment
   ↓
PHASE 23  Final Polish
   ↓
PHASE 24  Advanced Search & Dataset Catalog
MVP vs Final Project
Don't build all 23 phases immediately.
MVP — first target
Get only this working:
Kaggle CSV
   ↓
MySQL
   ↓
FastAPI
   ↓
React
   ↓
Question
   ↓
Gemini
   ↓
SQL
   ↓
MySQL
   ↓
Pandas
   ↓
Graph
   ↓
Answer
Once this works, you already have a working AI analytics product.
Then add:
Recommendations
Warnings
Login
History
CSV Upload
Multi-dataset
Deployment
One golden rule for this project
Never make the AI the actual analytics engine.
Use:
MySQL       → data retrieval
Python      → calculations
Matplotlib  → visualization
Gemini      → understanding + planning + explanation
FastAPI     → orchestration
React       → user experience
That's the clean architecture.
What we should do first
Phase 1: Dataset Selection.
Pick a good Kaggle dataset first. For the first version, College Placement Analytics is a strong choice because it gives us enough dimensions—CGPA, internship, branch, placement, package, skills, company—to test almost every feature we want later.
Once the dataset is selected, the next concrete sequence is:
Kaggle CSV
→ understand columns
→ clean data
→ design MySQL tables
→ import data
→ verify relationships
That becomes our first milestone: a clean, trustworthy MySQL database ready for analytics.

________________________________________
PHASE 24 — Advanced Search, Dataset Discovery & Unified Data Catalog
Goal: Build a unified discovery and search system for AskMyData.
- Global search for datasets, conversations, saved queries, reports, and workspaces.
- Dataset Catalog and Dataset Discovery pages.
- Advanced filters, sorting, and suggestions.
- Favorites, bookmarks, tags, and search history.
- Granular permission-aware search and UI.
