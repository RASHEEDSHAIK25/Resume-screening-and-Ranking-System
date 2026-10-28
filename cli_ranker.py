"""
Command-Line Interface (CLI) for Resume Screening & Ranking
Allows quick candidate ranking directly from terminal.
"""

import os
import sys
import argparse
import glob
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
from src.parser import extract_text_from_file
from src.ranker import ResumeRanker
from src.sample_data import SAMPLE_JDS, create_sample_files


def run_cli():
    parser = argparse.ArgumentParser(description="NLP-based Resume Screening & Ranking System")
    parser.add_argument("--jd", type=str, help="Path to Job Description text or PDF file", default=None)
    parser.add_argument("--resumes", type=str, help="Directory containing candidate resumes (PDF, DOCX, TXT)", default=None)
    parser.add_argument("--sample", action="store_true", help="Run benchmark against Cirameti sample data")

    args = parser.parse_args()

    # Ensure sample data exists
    create_sample_files()

    if args.sample or (not args.jd and not args.resumes):
        print("\n" + "="*70)
        print("  RUNNING RESUME SCREENING BENCHMARK: CIRAMETI SENIOR ML ENGINEER")
        print("="*70)
        jd_text = SAMPLE_JDS["Cirameti - Senior Machine Learning Engineer"]
        resume_folder = os.path.join("data", "sample_resumes")
    else:
        if not os.path.exists(args.jd):
            print(f"Error: JD file not found at {args.jd}")
            return
        jd_text = extract_text_from_file(args.jd)
        resume_folder = args.resumes or os.path.join("data", "sample_resumes")

    # Read all candidate files in directory
    files = glob.glob(os.path.join(resume_folder, "*.*"))
    supported = [f for f in files if os.path.splitext(f)[1].lower() in [".pdf", ".docx", ".doc", ".txt"]]

    if not supported:
        print(f"No supported resume files found in {resume_folder}")
        return

    resumes_payload = []
    for fpath in supported:
        text = extract_text_from_file(fpath)
        resumes_payload.append({
            "filename": os.path.basename(fpath),
            "text": text
        })

    ranker = ResumeRanker()
    ranked_candidates = ranker.rank_candidates(jd_text, resumes_payload)

    # Pretty print summary table
    table_rows = []
    for c in ranked_candidates:
        table_rows.append({
            "Rank": f"#{c['rank']}",
            "Candidate Name": c["candidate_name"],
            "Score": f"{c['match_score']}%",
            "Tier": c["match_tier"],
            "TF-IDF": f"{c['tfidf_similarity']}%",
            "Skill Coverage": f"{c['skill_coverage_pct']}%",
            "Matched Count": len(c["matched_skills"]),
            "Missing Count": len(c["missing_skills"]),
        })

    df = pd.DataFrame(table_rows)
    print("\n" + df.to_string(index=False))
    print("\n" + "="*70)
    print("Top Candidate Detailed Breakdown:")
    top = ranked_candidates[0]
    print(f"[*] TOP MATCH: {top['candidate_name']} ({top['filename']}) - {top['match_score']}% ({top['match_tier']})")
    print(f"   Email: {top['email']} | Phone: {top['phone']}")
    print(f"   Matched Skills ({len(top['matched_skills'])}): {', '.join(top['matched_skills'])}")
    print(f"   Missing Required Skills ({len(top['missing_skills'])}): {', '.join(top['missing_skills']) if top['missing_skills'] else 'None (100% matched!)'}")
    print("="*70 + "\n")


if __name__ == "__main__":
    run_cli()
