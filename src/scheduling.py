import json  # JSON serialisation for schedule files
import re  # Regex — used to sanitise filenames (remove special chars)
import uuid  # Generate unique event IDs for .ics files
from datetime import datetime, timedelta  # Date arithmetic for slot handling
from pathlib import Path  # Cross-platform path handling

from icalendar import Calendar, Event  # Build .ics calendar invite files

from app.app_paths import data_path

# ─────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────

# Folder containing ranking_scores_*.json files produced by ranking_engine.py
RANKING_FOLDER    = data_path("output/ranking")

# Folder where schedule files and .ics invites are saved
OUTPUT_FOLDER     = data_path("output/scheduling")

# How many top-ranked candidates to invite for interviews.
# Lower this if you want a smaller shortlist.
TOP_N_CANDIDATES  = 10

# Number of slot options offered to each candidate.
# More options = higher confirmation rate but more calendar juggling for HR.
SLOTS_TO_OFFER    = 3

# Duration of each interview event in the .ics file and display text.
INTERVIEW_MINUTES = 60

# ─────────────────────────────────────────────
# STEP 1: LOAD TOP N CANDIDATES FROM RANKING
# ─────────────────────────────────────────────

def load_top_candidates(ranking_folder: Path, top_n: int) -> list:
    """
    Read the most recent ranking JSON file and return the top N candidates.

    The file is identified by globbing for 'ranking_scores*.json' and sorting
    reverse-alphabetically so the newest timestamp comes first.

    Returns [] if no ranking file exists or the ranking is empty.
    """
    ranking_files = sorted(ranking_folder.glob("ranking_scores*.json"), reverse=True)

    if not ranking_files:
        print(f"[ERROR] No ranking file found in '{ranking_folder}'.")
        print("  Run ranking_engine.py first.")
        return []

    latest_file = ranking_files[0]  # most recent ranking run
    print(f"> Loading ranking from: {latest_file.name}")

    with open(latest_file, encoding="utf-8") as f:
        data = json.load(f)

    all_candidates = data.get("ranked_candidates", [])

    # Guard: ranking file exists but contains no candidates (shouldn't happen, but safe)
    if not all_candidates:
        print("[ERROR] Ranking file is empty. Run ranking_engine.py first.")
        return []

    # Slice to top N only — candidates are already sorted by score in the file
    top_candidates = all_candidates[:top_n]

    print(f"> Total ranked candidates : {len(all_candidates)}")
    print(f"> Selecting top           : {len(top_candidates)}")

    return top_candidates

# ─────────────────────────────────────────────
# STEP 2: GET HR AVAILABILITY (GUI-ready)
# ─────────────────────────────────────────────

def get_hr_availability_terminal() -> list:
    """
    Collect HR available slots via terminal.
    GUI VERSION: Replace this function with a calendar picker widget.
    Returns list of datetime objects.
    """
    print("\n" + "=" * 50)
    print("  ENTER HR / HIRING MANAGER AVAILABILITY")
    print("=" * 50)
    print("> Enter available time slots one by one.")
    print("> Format: YYYY-MM-DD HH:MM  (e.g. 2026-03-01 10:00)")
    print("> Type 'DONE' when finished.\n")

    slots: list = []
    while True:
        raw = input(f"  Slot {len(slots)+1}: ").strip()

        if raw.upper() == "DONE":
            if len(slots) < SLOTS_TO_OFFER:
                print(f"  [WARNING] Please enter at least {SLOTS_TO_OFFER} slots.")
                continue
            break

        try:
            slot_dt = datetime.strptime(raw, "%Y-%m-%d %H:%M")
            if slot_dt < datetime.now():
                print("  [WARNING] Slot is in the past. Enter a future date.")
                continue
            slots.append(slot_dt)
            print(f"  Added: {slot_dt.strftime('%A, %B %d %Y at %I:%M %p')}")
        except ValueError:
            print("  [ERROR] Invalid format. Use: YYYY-MM-DD HH:MM")

    return slots

# ─────────────────────────────────────────────
# STEP 3: ASSIGN SLOTS TO CANDIDATES (core logic)
# ─────────────────────────────────────────────

def assign_slots_to_candidates(candidates: list, hr_slots: list, slots_per_candidate: int) -> list:
    """
    Assign multiple interview slot options to each candidate.

    Uses a rotation strategy so consecutive candidates receive different primary
    slot options rather than all being offered the same first slot.
    Example with 3 candidates and slots [A, B, C]:
      Candidate 1: [A, B, C]
      Candidate 2: [B, C, A]
      Candidate 3: [C, A, B]

    The slots are then sorted chronologically so the earliest option is always
    presented first.

    Returns:
      List of dicts — one per candidate, with 'offered_slots', 'selected_slot'
      (starts as None), and 'status' (starts as PENDING).
    """
    scheduled = []

    for i, candidate in enumerate(candidates):
        name   = candidate.get("candidate_name") or "Unknown"
        source = candidate.get("_source_file", "")
        score  = candidate.get("total_score", 0)

        # Build this candidate's slot list using a rotation offset
        offered_slots = []
        seen          = set()  # track seen slots to avoid duplicates

        for j in range(len(hr_slots)):
            slot_idx = (i + j) % len(hr_slots)  # wrap around the list
            slot     = hr_slots[slot_idx]
            slot_str = slot.strftime("%Y-%m-%d %H:%M")
            if slot_str not in seen:
                seen.add(slot_str)
                offered_slots.append(slot)
            if len(offered_slots) == slots_per_candidate:  # stop when we have enough
                break

        # Warn if HR didn't provide enough unique slots
        if len(offered_slots) < slots_per_candidate:
            print(f"  [WARNING] Only {len(offered_slots)} unique slot(s) available for {name} — consider adding more HR slots.")

        # Present slots in chronological order to the candidate
        offered_slots.sort()

        scheduled.append({
            "rank":           i + 1,                  # 1-based rank from leaderboard
            "candidate_name": name,
            "source_file":    source,
            "score":          score,
            "offered_slots":  [s.strftime("%Y-%m-%d %H:%M") for s in offered_slots],
            "selected_slot":  None,        # filled in when candidate confirms
            "status":         "PENDING"    # PENDING | CONFIRMED | SKIPPED
        })

    return scheduled

# ─────────────────────────────────────────────
# STEP 4: CANDIDATE SLOT SELECTION (GUI-ready)
# ─────────────────────────────────────────────

def collect_candidate_selections_terminal(scheduled: list) -> list:
    """
    Simulate candidate picking a slot via terminal.
    GUI VERSION: Replace with candidate-facing web form or email link.
    """
    print("\n" + "=" * 50)
    print("  CANDIDATE SLOT SELECTION (SIMULATION)")
    print("=" * 50)
    print("> In production: candidates receive an email with slot options.")
    print("> For now: manually select slot for each candidate.\n")

    for entry in scheduled:
        name   = entry["candidate_name"]
        source = entry["source_file"]
        slots  = entry["offered_slots"]

        print(f"\n  Candidate : {name} ({source})  [Score: {entry['score']}/100]")
        print("  Offered slots:")
        for idx, slot in enumerate(slots, start=1):
            dt = datetime.strptime(slot, "%Y-%m-%d %H:%M")
            print(f"    {idx}. {dt.strftime('%A, %B %d %Y at %I:%M %p')}")

        while True:
            choice = input(f"  Select slot (1-{len(slots)}) or 'SKIP' to skip: ").strip()

            if choice.upper() == "SKIP":
                entry["status"] = "SKIPPED"
                break

            try:
                choice_idx = int(choice) - 1
                if 0 <= choice_idx < len(slots):
                    entry["selected_slot"] = slots[choice_idx]
                    entry["status"]        = "CONFIRMED"
                    print(f"  Confirmed: {slots[choice_idx]}")
                    break
                else:
                    print(f"  [ERROR] Enter a number between 1 and {len(slots)}.")
            except ValueError:
                print("  [ERROR] Invalid input.")

    return scheduled

# ─────────────────────────────────────────────
# STEP 5: GENERATE .ICS CALENDAR INVITES
# ─────────────────────────────────────────────

def generate_ics(entry: dict, output_path: Path, hr_name: str, job_title: str, stamp: str, hr_email: str = ""):
    """
    Create a .ics calendar invite file for one confirmed interview.

    .ics is the standard iCalendar format supported by:
      - Google Calendar (import or email attachment)
      - Microsoft Outlook (double-click to add)
      - Apple Calendar (double-click to add)

    A unique UUID is generated for each event so importing the same file
    twice does not create duplicate calendar entries.

    Returns the Path of the created .ics file, or None if the entry was
    not CONFIRMED or had no selected slot.
    """
    # Only generate invites for candidates who confirmed a slot
    if entry["status"] != "CONFIRMED" or not entry["selected_slot"]:
        return None

    candidate_name = entry["candidate_name"]
    slot_dt        = datetime.strptime(entry["selected_slot"], "%Y-%m-%d %H:%M")
    end_dt         = slot_dt + timedelta(minutes=INTERVIEW_MINUTES)

    cal   = Calendar()
    event = Event()

    event.add("summary",     f"Interview — {candidate_name} for {job_title}")
    event.add("dtstart",     slot_dt)
    event.add("dtend",       end_dt)
    event.add("description", (
        f"Interview Details\n"
        f"Candidate  : {candidate_name}\n"
        f"File       : {entry['source_file']}\n"
        f"Rank       : #{entry['rank']}\n"
        f"Score      : {entry['score']}/100\n"
        f"Job Title  : {job_title}\n"
        f"Duration   : {INTERVIEW_MINUTES} minutes\n"
        f"Interviewer: {hr_name}"
    ))
    event.add("organizer", f"MAILTO:{hr_email}" if hr_email else "MAILTO:hr@company.com")
    event.add("uid",       str(uuid.uuid4()))
    event.add("status",    "CONFIRMED")

    cal.add_component(event)

    # Sanitise candidate name for use in the filename (remove special chars)
    # Timestamp is added to prevent overwriting if the schedule is re-run
    safe_name = re.sub(r'[^a-zA-Z0-9_]', '_', candidate_name)
    ics_path  = output_path / f"interview_{entry['rank']}_{safe_name}_{stamp}.ics"

    # Write binary iCal data — .ics files use \r\n line endings (RFC 5545)
    with open(ics_path, "wb") as f:
        f.write(cal.to_ical())

    return ics_path

# ─────────────────────────────────────────────
# STEP 6: SAVE SCHEDULE SUMMARY
# ─────────────────────────────────────────────

def save_schedule_summary(scheduled: list, output_path: Path, job_title: str, metadata: dict | None = None):
    """Save schedule as JSON and human-readable TXT."""

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Save JSON (machine readable / GUI ready)
    json_file = output_path / f"schedule_{timestamp}.json"
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump({
            "job_title":    job_title,
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total":        len(scheduled),
            "confirmed":    sum(1 for s in scheduled if s["status"] == "CONFIRMED"),
            "pending":      sum(1 for s in scheduled if s["status"] == "PENDING"),
            "skipped":      sum(1 for s in scheduled if s["status"] == "SKIPPED"),
            "metadata":     metadata or {},
            "schedule":     scheduled
        }, f, indent=4, ensure_ascii=False)

    # Save TXT (HR readable)
    txt_file = output_path / f"schedule_{timestamp}.txt"
    with open(txt_file, "w", encoding="utf-8") as f:
        f.write("=" * 60 + "\n")
        f.write("       INTERVIEW SCHEDULE\n")
        f.write("=" * 60 + "\n")
        f.write(f"Job Title  : {job_title}\n")
        f.write(f"Generated  : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Total      : {len(scheduled)}\n")
        f.write(f"Confirmed  : {sum(1 for s in scheduled if s['status'] == 'CONFIRMED')}\n")
        f.write(f"Pending    : {sum(1 for s in scheduled if s['status'] == 'PENDING')}\n")
        f.write(f"Skipped    : {sum(1 for s in scheduled if s['status'] == 'SKIPPED')}\n")
        if metadata:
            f.write(f"Slot Count : {metadata.get('slot_count', 'N/A')}\n")
            f.write(f"Top N      : {metadata.get('top_n', 'N/A')}\n")
        f.write("=" * 60 + "\n\n")

        for entry in scheduled:
            f.write(f"RANK #{entry['rank']}  —  {entry['candidate_name']} ({entry['source_file']})\n")
            f.write(f"{'─' * 40}\n")
            f.write(f"  Score   : {entry['score']}/100\n")
            f.write(f"  Status  : {entry['status']}\n")

            if entry["selected_slot"]:
                dt = datetime.strptime(entry["selected_slot"], "%Y-%m-%d %H:%M")
                f.write(f"  Slot    : {dt.strftime('%A, %B %d %Y at %I:%M %p')}\n")
                safe_name = re.sub(r'[^a-zA-Z0-9_]', '_', entry['candidate_name'])
                f.write(f"  .ics    : interview_{entry['rank']}_{safe_name}_{timestamp}.ics\n")
            else:
                f.write("  Slot    : Not selected\n")

            f.write("\n  Offered slots:\n")
            for slot in entry["offered_slots"]:
                dt = datetime.strptime(slot, "%Y-%m-%d %H:%M")
                f.write(f"    - {dt.strftime('%A, %B %d %Y at %I:%M %p')}\n")

            f.write("\n" + "=" * 60 + "\n\n")

    print(f"> Schedule JSON saved : {json_file}")
    print(f"> Schedule TXT saved  : {txt_file}")

# ─────────────────────────────────────────────
# MAIN PIPELINE
# ─────────────────────────────────────────────

def run_scheduling():
    ranking_path = Path(RANKING_FOLDER)
    output_path  = Path(OUTPUT_FOLDER)
    output_path.mkdir(parents=True, exist_ok=True)

    # Shared timestamp for this session — keeps all files consistent
    session_stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    print("=" * 50)
    print("   INTERVIEW SCHEDULING MODULE")
    print("=" * 50)

    # ── Step 1: Load top candidates ──
    top_candidates = load_top_candidates(ranking_path, TOP_N_CANDIDATES)
    if not top_candidates:
        return

    # ── Step 2: Get job title and HR name ──
    job_title = input("\n> Enter Job Title for this interview round: ").strip() or "Open Position"
    hr_name   = input("> Enter Hiring Manager Name               : ").strip() or "Hiring Manager"

    # ── Step 3: Get HR availability ──
    hr_slots = get_hr_availability_terminal()
    if not hr_slots:
        print("[ERROR] No slots entered. Exiting.")
        return

    # ── Step 4: Assign slots to candidates ──
    print(f"\n> Assigning slots to top {len(top_candidates)} candidates...")
    scheduled = assign_slots_to_candidates(top_candidates, hr_slots, SLOTS_TO_OFFER)

    # ── Step 5: Collect candidate selections ──
    scheduled = collect_candidate_selections_terminal(scheduled)

    # ── Step 6: Generate .ics files ──
    print("\n> Generating calendar invites (.ics)...")
    ics_count = 0
    for entry in scheduled:
        ics_path = generate_ics(entry, output_path, hr_name, job_title, session_stamp)
        if ics_path:
            print(f"  Created: {ics_path.name}")
            ics_count += 1

    # ── Step 7: Save summary ──
    print("\n> Saving schedule summary...")
    save_schedule_summary(scheduled, output_path, job_title)

    # ── Step 8: Print final summary ──
    confirmed = [s for s in scheduled if s["status"] == "CONFIRMED"]
    skipped   = [s for s in scheduled if s["status"] == "SKIPPED"]

    print(f"\n{'=' * 50}")
    print("  SCHEDULING COMPLETE")
    print(f"{'=' * 50}")
    print(f"  Confirmed interviews : {len(confirmed)}")
    print(f"  Skipped              : {len(skipped)}")
    print(f"  Calendar invites     : {ics_count} .ics files generated")
    print(f"  Output folder        : {OUTPUT_FOLDER}")
    print(f"{'=' * 50}")
    print("\n> TIP: .ics files can be opened with Google Calendar,")
    print("       Outlook, or Apple Calendar directly.")


if __name__ == "__main__":
    run_scheduling()
