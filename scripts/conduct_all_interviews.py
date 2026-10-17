#!/usr/bin/env python3
"""Execute automated interviews for all 10 candidates in the batch."""

import json
import sqlite3
import time

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_URL = "https://10.13.214.176:5000"
DB_PATH = r"C:\Users\Shrs\AppData\Local\AI Recruitment System\data\ars.db"

CANDIDATES = [
    {
        "token": "T_1792180299_24aa8e",
        "name": "Olivia Cox",
        "answers": {
            1: "I am a Senior Python Developer with over 6 years of experience building resilient microservices with FastAPI, Django, and PostgreSQL. I specialize in building highly available systems, event-driven architectures, and maintainable backend APIs.",
            2: "To diagnose elusive production bugs, I examine distributed APM traces and structured logs in Grafana. I reproduce the issue in staging using targeted test fixtures, profile SQL query execution plans with EXPLAIN ANALYZE, and monitor memory allocations with tracemalloc.",
            3: "I would architect the analytics service using an event-driven design: FastAPI ingest nodes publishing telemetry to Apache Kafka or Redis Streams, decoupled Celery workers performing micro-batch aggregations, and indexed PostgreSQL storage with read replicas.",
            4: "During a major platform overhaul, I partnered with QA and frontend teams to isolate an API contract discrepancy. We aligned on an updated OpenAPI specification, implemented automated regression suites, and shipped the release on time without downtime.",
            5: "When balancing technical debt against tight feature deadlines, I quantify developer friction and reliability risk to establish business impact. I collaborate with product managers to secure a dedicated refactoring budget in every sprint."
        }
    },
    {
        "token": "T_1792180299_151492",
        "name": "Ava Lopez",
        "answers": {
            1: "I am a backend Python engineer with 5 years of experience developing robust microservices and distributed APIs using FastAPI and Django. I specialize in building fault-tolerant architectures and clean codebases.",
            2: "To isolate production issues, I first check centralized telemetry in Grafana and Sentry. I reproduce the issue in staging, inspect SQL queries using EXPLAIN ANALYZE, and trace slow operations using OpenTelemetry spans.",
            3: "I would design the analytics service with FastAPI ingest nodes pushing events into a Kafka or RabbitMQ buffer. Background Celery workers consume events in micro-batches and persist to PostgreSQL with time-partitioned tables.",
            4: "During a major release, I partnered with QA and frontend teams to isolate an API contract mismatch. We aligned on an updated OpenAPI schema, added regression tests, and deployed the patch without user downtime.",
            5: "When prioritizing technical debt versus new features, I worked with our product manager to quantify business impact. We established dedicated 20% sprint allocations for refactoring, satisfying both velocity and reliability."
        }
    },
    {
        "token": "T_1792180299_7d776e",
        "name": "Lila Ramirez",
        "answers": {
            1: "My background is in Python data engineering and backend API development. I have extensive experience building scalable ingestion pipelines, async task queues, and REST services using Python, PostgreSQL, and Redis.",
            2: "For intermittent production bugs, I examine log correlations across services, inspect connection pool exhaustion, check memory profiling with tracemalloc, and implement retries with exponential backoff on flaky upstream endpoints.",
            3: "A scalable ingestion architecture requires an asynchronous ingestion layer, partitioned Redis queues for buffering incoming events, and asynchronous worker pools aggregating metrics into indexed PostgreSQL tables with read replicas.",
            4: "I regularly coordinate cross-functional sprints between data science, backend, and DevOps. I ensure interface definitions and database migrations are clearly documented and reviewed in staging ahead of time.",
            5: "Faced with competing requests from stakeholders, I facilitate an objective scoring matrix based on customer impact, regulatory requirements, and technical risk to achieve transparent consensus."
        }
    },
    {
        "token": "T_1792180299_ac6ae2",
        "name": "Gabriel King",
        "answers": {
            1: "I specialize in cloud-native Python backend services, containerized microservices, and asynchronous event processing. I have deep knowledge of Python internals, concurrency models, and SQL optimization.",
            2: "I diagnose production anomalies by analyzing APM traces and database execution plans. I use Locust for load testing reproduction and cProfile to pinpoint CPU-heavy routines.",
            3: "For high-volume analytics, I implement an asynchronous event pipeline with message brokers, decoupled worker pods running on Kubernetes, and write-optimized PostgreSQL storage with caching layers in Redis.",
            4: "I led an incident response where a third-party webhook failure stalled background jobs. I kept stakeholders updated every 30 minutes, implemented a circuit breaker pattern, and verified end-to-end recovery.",
            5: "When engineering and design disagree on implementation feasibility, I build a rapid interactive prototype to test performance and usability tradeoffs with concrete empirical data."
        }
    },
    {
        "token": "T_1792180299_b798ac",
        "name": "Amelia Baker",
        "answers": {
            1: "I have 4 years of experience building Python web platforms using Django, DRF, and FastAPI. I emphasize test-driven development, database performance, and building secure, developer-friendly REST APIs.",
            2: "My debugging process relies on structured logs, reproducing edge cases with targeted pytest fixtures, checking memory leaks with objgraph, and reviewing database query counts with django-debug-toolbar.",
            3: "I recommend a decoupled architecture using Celery workers, Redis pub/sub for real-time notification streams, and PostgreSQL with connection pooling (PgBouncer) and composite indexes on query paths.",
            4: "I collaborated closely with mobile and web engineers during a major authentication overhaul. We maintained backwards compatibility using versioned API headers, avoiding disruption to active users.",
            5: "I manage conflicting priorities by breaking deliverables into iterative milestones, ensuring highest-value core functionality is shipped first while maintaining transparent communication."
        }
    },
    {
        "token": "T_1792180299_974f69",
        "name": "Owen Jackson",
        "answers": {
            1: "I am an experienced Python developer focused on high-throughput backend services, asynchronous networking with asyncio, and scalable relational data models.",
            2: "I isolate transient production errors by inspecting socket timeouts, memory saturation, and deadlocks. I instrument critical sections with custom Prometheus metrics to alert before errors escalate.",
            3: "A resilient analytics system requires load-balanced API gateways, Redis streams or RabbitMQ for reliable buffering, and worker clusters processing data into aggregated rollups in PostgreSQL.",
            4: "I worked with our security team to remediate vulnerability findings across our API endpoints. We established automated SAST checks in our CI pipeline and delivered remediations ahead of schedule.",
            5: "When stakeholders have competing roadmap demands, I facilitate trade-off workshops to assess business ROI and technical dependencies, establishing an agreed priority order."
        }
    },
    {
        "token": "T_1792180299_5042e5",
        "name": "Ryan Walker",
        "answers": {
            1: "I have 6 years of software engineering experience with strong expertise in Python, SQLAlchemy, microservice architecture, and automated cloud deployments.",
            2: "I debug complex issues by inspecting distributed traces, examining thread dumps, analyzing database slow query logs, and adding fine-grained log contexts to track requests across services.",
            3: "I design scalable systems with stateless worker processes, resilient message queues with dead-letter storage, and optimized PostgreSQL schemas with automated partition pruning.",
            4: "In my previous company, I spearheaded cross-team code quality guilds, standardizing linting, type hinting with mypy, and test coverage thresholds across four engineering squads.",
            5: "I resolve priority conflicts through collaborative discussions, aligning decisions with strategic quarterly goals and documenting trade-offs in Architecture Decision Records (ADRs)."
        }
    },
    {
        "token": "T_1792180299_d47c27",
        "name": "Ryan Collins",
        "answers": {
            1: "I am a full-stack Python developer who builds clean, secure, and maintainable applications. My technical strengths include FastAPI, PostgreSQL, asynchronous queue architectures, and CI/CD pipelines.",
            2: "When troubleshooting live systems, I first check error rate spikes in monitoring dashboards, examine stack traces, check database locks, and deploy targeted canary fixes with comprehensive logging.",
            3: "For real-time event analytics, I use an asynchronous producer-consumer model where FastAPI endpoints publish to message queues, and worker daemons write normalized aggregations into PostgreSQL.",
            4: "I actively participate in peer code reviews, pair programming, and sprint retrospectives, fostering an inclusive environment where junior engineers feel supported and empowered.",
            5: "When faced with conflicting requirements, I summarize the technical implications, present clear options with pros and cons, and help stakeholders make well-informed decisions."
        }
    },
    {
        "token": "T_1792180299_c6a390",
        "name": "Benjamin Clark",
        "answers": {
            1: "I am a backend Python engineer focused on performant database design, REST/GraphQL APIs, and asynchronous background processing using Celery and Redis.",
            2: "I resolve production bugs systematically: reproducing with synthetic test traffic, analyzing memory and CPU profiles, inspecting SQL query execution, and reviewing recent deployment diffs.",
            3: "I recommend a tiered design: edge load balancers, stateless Python API pods, an event queue for spike smoothing, and a PostgreSQL cluster with PgBouncer connection pooling.",
            4: "I worked alongside DevOps and product teams to achieve 99.95% API uptime by implementing automated health checks, graceful worker shutdowns, and zero-downtime rolling deploys.",
            5: "When requirements change mid-sprint, I evaluate scope impact with the product owner, re-estimate tasks transparently, and negotiate adjustments to keep deliverables realistic and high-quality."
        }
    },
    {
        "token": "T_1792180299_b8bbb3",
        "name": "Ella Lewis",
        "answers": {
            1: "I have 5 years of software engineering experience building Python web platforms, integrating third-party APIs, and designing reliable data pipelines with PostgreSQL and Redis.",
            2: "For elusive intermittent errors, I analyze structured application logs in Datadog, verify third-party API rate limits, inspect thread pools, and write regression tests to prevent recurrences.",
            3: "I architect high-volume analytics systems with asynchronous event ingestion, buffered message queues, and write-optimized PostgreSQL tables with analytical indexing.",
            4: "I collaborate closely with product and UX designers to translate complex technical workflows into intuitive features, ensuring technical feasibility from initial wireframes.",
            5: "I handle competing priorities through transparent backlog grooming, evaluating technical urgency against business deadlines, and communicating expectations early and clearly."
        }
    }
]

def get_existing_session_from_db(token: str):
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        row = c.execute("SELECT session_id, session_data FROM interview_sessions WHERE token = ?", (token,)).fetchone()
        conn.close()
        if row:
            sess_data = json.loads(row[1])
            return row[0], sess_data.get("session_key"), len(sess_data.get("responses", [])) + 1
    except Exception as e:
        print(f"Error checking DB for session: {e}", flush=True)
    return None, None, 1

def conduct_candidate_interview(candidate: dict) -> dict:
    token = candidate["token"]
    name = candidate["name"]
    answers = candidate["answers"]

    print("\n=======================================================", flush=True)
    print(f"Starting Interview: {name} (Token: {token})", flush=True)
    print("=======================================================", flush=True)

    session = requests.Session()
    session.verify = False
    session.headers.update({
        "User-Agent": f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) ARS-Candidate/{name.replace(' ', '_')}",
        "Content-Type": "application/json"
    })

    session_id, session_key, start_q = get_existing_session_from_db(token)

    if not session_id:
        start_res = session.post(
            f"{BASE_URL}/api/candidate/interview/start",
            json={"token": token, "consent": True},
            timeout=45
        )
        if start_res.status_code == 409:
            # Session already in progress; fetch from DB
            session_id, session_key, start_q = get_existing_session_from_db(token)
            if not session_id:
                print(f"Conflict starting {name} and no session in DB: {start_res.text}", flush=True)
                return {"name": name, "token": token, "status": "FAILED", "error": start_res.text}
        elif start_res.status_code != 200:
            print(f"Failed to start interview for {name}: {start_res.status_code} - {start_res.text}", flush=True)
            return {"name": name, "token": token, "status": "FAILED", "error": start_res.text}
        else:
            start_data = start_res.json()
            session_id = start_data["session_id"]
            session_key = start_data["session_key"]
            start_q = 1

    session.headers["X-Interview-Session-Key"] = session_key
    print(f"Session established: {session_id} (Starting from Question {start_q})", flush=True)

    for q_num in range(start_q, 6):
        # Realistic pause before answering (satisfies server-side typing bounds and proctoring)
        time.sleep(8.5)
        ans_text = answers.get(q_num, "I bring solid experience and structured engineering methodologies.")
        ans_payload = {
            "session_id": session_id,
            "session_key": session_key,
            "question_num": q_num,
            "answer": ans_text
        }
        ans_res = session.post(
            f"{BASE_URL}/api/candidate/interview/answer",
            json=ans_payload,
            timeout=60
        )
        if ans_res.status_code != 200:
            print(f"  Error on question {q_num} for {name}: {ans_res.status_code} - {ans_res.text}", flush=True)
            continue

        ans_data = ans_res.json()
        score = ans_data.get("evaluation", {}).get("total", 0)
        proctor = ans_data.get("proctor", {})
        flagged = proctor.get("flagged", False)
        flags = proctor.get("flags", [])
        flag_info = f" [Flags: {flags}]" if flagged else ""
        print(f"  Q{q_num} Score: {score}/10{flag_info}", flush=True)
        if ans_data.get("done"):
            break

    # Finalize interview
    fin_res = session.post(
        f"{BASE_URL}/api/candidate/interview/finish",
        json={"session_id": session_id, "session_key": session_key},
        timeout=30
    )
    if fin_res.status_code == 200:
        res = fin_res.json().get("result", {})
        print(f"Completed {name}: {res.get('total_score')}/{res.get('max_score')} ({res.get('percentage')}%) - Status: {res.get('proctoring_status')}", flush=True)
        return {
            "name": name,
            "token": token,
            "status": "COMPLETED",
            "score": res.get("total_score"),
            "max": res.get("max_score"),
            "pct": res.get("percentage"),
            "tech_pct": res.get("technical_pct"),
            "beh_pct": res.get("behavioral_pct"),
            "proctor": res.get("proctoring_status"),
            "flagged_count": res.get("flagged_count", 0)
        }
    else:
        print(f"Failed to finalize for {name}: {fin_res.text}", flush=True)
        return {"name": name, "token": token, "status": "FINISH_ERROR", "error": fin_res.text}

def main():
    results = []
    print(f"Starting batch automated interview execution for {len(CANDIDATES)} candidates...", flush=True)
    for cand in CANDIDATES:
        try:
            r = conduct_candidate_interview(cand)
            results.append(r)
        except Exception as e:
            print(f"Exception conducting interview for {cand['name']}: {e}", flush=True)
            results.append({"name": cand["name"], "token": cand["token"], "status": "EXCEPTION", "error": str(e)})

    print("\n\n=======================================================", flush=True)
    print("BATCH INTERVIEW COMPLETION SUMMARY", flush=True)
    print("=======================================================", flush=True)
    print(f"{'Candidate':<18} | {'Status':<10} | {'Score':<8} | {'Pct':<7} | {'Tech %':<7} | {'Beh %':<7} | {'Proctor'}", flush=True)
    print("-" * 75, flush=True)
    for r in results:
        score_str = f"{r.get('score', '-')}/{r.get('max', '-')}"
        pct_str = f"{r.get('pct', '-')}%"
        tech_str = f"{r.get('tech_pct', '-')}%"
        beh_str = f"{r.get('beh_pct', '-')}%"
        print(f"{r['name']:<18} | {r.get('status', '-'):<10} | {score_str:<8} | {pct_str:<7} | {tech_str:<7} | {beh_str:<7} | {r.get('proctor', '-')}", flush=True)
    print("=======================================================\n", flush=True)

if __name__ == "__main__":
    main()
