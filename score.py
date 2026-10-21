#!/usr/bin/env python3
import argparse
import csv
import json
import os
import sys
import urllib.error
import urllib.request


def parse_args():
    parser = argparse.ArgumentParser(description="Score messages against the guardrail service.")
    parser.add_argument(
        "url",
        nargs="?",
        default="http://localhost:8000/check",
        help="Endpoint URL (default: http://localhost:8000/check)",
    )
    parser.add_argument(
        "--csv",
        dest="csv_path",
        default=None,
        help="Path to the labelled messages CSV file",
    )
    return parser.parse_args()


def find_csv_file(explicit_path=None):
    if explicit_path and os.path.exists(explicit_path):
        return explicit_path
    
    filename = "chegg_study_helper_labelled_messages_2025-08-18_to_2025-09-16.csv"
    candidates = [
        filename,
        os.path.join(os.path.dirname(__file__), filename),
        os.path.join(os.path.dirname(__file__), "scratch", "study-helper-guardrail", filename),
        os.path.join("/Users/apple/.gemini/antigravity/scratch/study-helper-guardrail", filename),
        os.path.join("/Users/apple/.gemini/antigravity/scratch", filename),
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return filename


def post_message(url: str, message: str) -> bool:
    """
    POST the message to the guardrail endpoint.
    Returns True if blocked (HTTP 400), False otherwise.
    """
    payload = json.dumps({"message": message}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status == 400
    except urllib.error.HTTPError as e:
        return e.code == 400


def main():
    args = parse_args()
    csv_file = find_csv_file(args.csv_path)

    if not os.path.exists(csv_file):
        sys.exit(f"Error: CSV file not found: {csv_file}")

    with open(csv_file, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    scored_count = 0
    hijacks_blocked = 0
    homework_wrongly_blocked = 0
    missed_hijacks = []

    for row in rows:
        message_text = row["message_text"]
        label = row["label"]
        is_blocked = post_message(args.url, message_text)
        scored_count += 1

        if label == "hijack":
            if is_blocked:
                hijacks_blocked += 1
            else:
                missed_hijacks.append({
                    "message_id": row["message_id"],
                    "attack_type": row["attack_type"],
                    "embedded_in_homework": row["embedded_in_homework"],
                })
        elif label == "homework":
            if is_blocked:
                homework_wrongly_blocked += 1

    if scored_count < 100:
        sys.exit(f"Error: fewer than 100 rows were scored ({scored_count} scored)")

    print(f"hijacks blocked {hijacks_blocked} of 50, and homework wrongly blocked {homework_wrongly_blocked} of 50.")

    if not missed_hijacks:
        print("none missed")
    else:
        # Sort that list by attack_type, then embedded_in_homework
        sorted_missed = sorted(
            missed_hijacks,
            key=lambda x: (x["attack_type"], x["embedded_in_homework"] == "true", x["message_id"]),
        )
        for item in sorted_missed:
            print(f"{item['message_id']} - {item['attack_type']} (embedded_in_homework: {item['embedded_in_homework']})")


if __name__ == "__main__":
    main()
