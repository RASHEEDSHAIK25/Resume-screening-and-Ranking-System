"""
Flask Web Application & REST API for NLP Resume Screening & Ranking System.
Provides endpoints for parsing resumes, extracting skill taxonomies,
and ranking candidates against job descriptions using TF-IDF & skill overlap.
"""

import os
import sys
import glob
from typing import List, Dict, Any

from flask import Flask, render_template, request, jsonify, send_file
import pandas as pd

# Ensure root directory is on sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from src.parser import extract_text_from_file
from src.skill_extractor import extract_skills_from_text
from src.ranker import ResumeRanker
from src.sample_data import SAMPLE_JDS, create_sample_files

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB max upload
app.config["UPLOAD_FOLDER"] = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

# Ensure sample files exist
create_sample_files()

ranker = ResumeRanker(tfidf_weight=0.50, skill_weight=0.50)


@app.route("/")
def index():
    """Renders the primary interactive dashboard."""
    return render_template("index.html")


@app.route("/api/sample-data", methods=["GET"])
def get_sample_data():
    """Returns sample Job Descriptions and sample candidate metadata."""
    sample_resumes_dir = os.path.join("data", "sample_resumes")
    resume_files = []
    if os.path.exists(sample_resumes_dir):
        resume_files = [os.path.basename(f) for f in glob.glob(os.path.join(sample_resumes_dir, "*.txt"))]

    return jsonify({
        "status": "success",
        "job_descriptions": SAMPLE_JDS,
        "sample_resumes": sorted(resume_files)
    })


@app.route("/api/rank", methods=["POST"])
def rank_resumes_api():
    """
    Main ranking endpoint.
    Accepts:
    - job_description (text)
    - resumes (multiple uploaded files) OR use_sample_resumes (boolean)
    """
    try:
        jd_text = request.form.get("job_description", "").strip()
        use_sample = request.form.get("use_sample_resumes", "false").lower() == "true"
        
        if not jd_text:
            # Fallback to default Cirameti JD if empty
            jd_text = SAMPLE_JDS["Cirameti - Senior Machine Learning Engineer"]

        uploaded_files = request.files.getlist("resumes")
        resumes_payload: List[Dict[str, Any]] = []

        # 1. Process uploaded files if any
        for f in uploaded_files:
            if f and f.filename:
                filename = f.filename
                ext = os.path.splitext(filename)[1].lower()
                if ext in [".pdf", ".docx", ".doc", ".txt"]:
                    # Read into memory
                    text = extract_text_from_file(f.stream, filename=filename)
                    if text.strip():
                        resumes_payload.append({
                            "filename": filename,
                            "text": text
                        })

        # 2. Or load sample resumes if requested or if no files uploaded
        if use_sample or len(resumes_payload) == 0:
            sample_dir = os.path.join("data", "sample_resumes")
            for fpath in glob.glob(os.path.join(sample_dir, "*.txt")):
                with open(fpath, "r", encoding="utf-8", errors="ignore") as file:
                    text = file.read()
                resumes_payload.append({
                    "filename": os.path.basename(fpath),
                    "text": text
                })

        if not resumes_payload:
            return jsonify({
                "status": "error",
                "message": "No valid resumes provided. Upload at least one PDF, DOCX, or TXT file."
            }), 400

        # Run ranking engine
        ranked_candidates = ranker.rank_candidates(jd_text, resumes_payload)
        jd_skills = extract_skills_from_text(jd_text)

        return jsonify({
            "status": "success",
            "total_candidates": len(ranked_candidates),
            "jd_required_skills": jd_skills,
            "candidates": ranked_candidates
        })

    except Exception as e:
        app.logger.error(f"Error in /api/rank: {e}", exc_info=True)
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@app.route("/api/export-csv", methods=["POST"])
def export_csv():
    """Generates and downloads a CSV of the ranked candidates."""
    try:
        data = request.get_json()
        candidates = data.get("candidates", [])
        if not candidates:
            return jsonify({"status": "error", "message": "No candidates to export"}), 400

        rows = []
        for c in candidates:
            rows.append({
                "Rank": c.get("rank"),
                "Candidate Name": c.get("candidate_name"),
                "Match Score (%)": c.get("match_score"),
                "Match Tier": c.get("match_tier"),
                "TF-IDF Similarity (%)": c.get("tfidf_similarity"),
                "Skill Coverage (%)": c.get("skill_coverage_pct"),
                "Email": c.get("email"),
                "Phone": c.get("phone"),
                "Matched Skills": ", ".join(c.get("matched_skills", [])),
                "Missing Skills": ", ".join(c.get("missing_skills", [])),
                "Filename": c.get("filename"),
            })

        df = pd.DataFrame(rows)
        csv_path = os.path.join(app.config["UPLOAD_FOLDER"], "ranked_candidates.csv")
        df.to_csv(csv_path, index=False)

        return send_file(csv_path, as_attachment=True, download_name="ranked_candidates.csv")

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


if __name__ == "__main__":
    print("\n" + "="*65)
    print("  RESUME SCREENING & RANKING SYSTEM - FLASK SERVER")
    print("  URL: http://127.0.0.1:5000")
    print("="*65 + "\n")
    app.run(host="127.0.0.1", port=5000, debug=True)
