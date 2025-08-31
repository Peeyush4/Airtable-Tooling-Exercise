import os
import requests
import json
import traceback
from dotenv import load_dotenv

load_dotenv()

AIRTABLE_API_KEY = os.getenv("AIRTABLE_API_KEY")
AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID")

APPLICANTS_TABLE = "Applicants"
PERSONAL_DETAILS_TABLE = "Personal Details"
WORK_EXPERIENCE_TABLE = "Work Experience"
SALARY_PREFERENCES_TABLE = "Salary Preferences"

AIRTABLE_API_URL = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}"
HEADERS = {
    "Authorization": f"Bearer {AIRTABLE_API_KEY}",
    "Content-Type": "application/json",
}


def get_all_records(table_name, filterByFormula=None, fields=None):
    """Fetches all records from a given Airtable table/filterByFormula."""
    records = []
    params = {}
    if filterByFormula:
        params["filterByFormula"] = filterByFormula
    if fields:
        params["fields[]"] = fields
    while True:
        response = requests.get(
            f"{AIRTABLE_API_URL}/{table_name}",
            headers=HEADERS,
            params=params
        )
        response.raise_for_status()
        data = response.json()
        records.extend(data.get("records", []))
        offset = data.get("offset")
        if not offset:
            break
        params["offset"] = offset
    return records


def find_existing_record(records, applicant_id):
    for record in records:
        fields = record.get("fields", {})
        if fields.get("Applicants", [None])[0] == applicant_id:
            return record
    return None


def delete_work_experience_for_applicant(work_experiences, applicant_id):
    # Get all work experience records
    for record in work_experiences:
        fields = record.get("fields", {})
        if fields.get("Applicants", [None])[0] == applicant_id:
            record_id = record["id"]
            response = requests.delete(
                f"{AIRTABLE_API_URL}/{WORK_EXPERIENCE_TABLE}/{record_id}",
                headers=HEADERS
            )
            response.raise_for_status()


def upsert_single_record(table_name, present_records, applicant_record):
    payload = {"fields": applicant_record}
    existing = find_existing_record(present_records, applicant_record["Applicants"][0])
    if existing:
        record_id = existing["id"]
        requests.patch(
            f"{AIRTABLE_API_URL}/{table_name}/{record_id}",
            headers=HEADERS,
            json=payload
        )
    else:
        print("Creating new record in", table_name, "with data:", payload)
        response = requests.post(
            f"{AIRTABLE_API_URL}/{table_name}",
            headers=HEADERS,
            json=payload
        )
        response.raise_for_status()


def upsert_work_experience(applicant_id, present_work_exp_records, applicant_records):
    delete_work_experience_for_applicant(present_work_exp_records, applicant_id)
    for exp in applicant_records:
        payload = {"fields": exp}
        response = requests.post(
            f"{AIRTABLE_API_URL}/{WORK_EXPERIENCE_TABLE}",
            headers=HEADERS,
            json=payload
        )
        response.raise_for_status()


def main():
    print("Starting JSON decompression process...")
    try:
        filterByFormula=(
                "OR({Shortlist Status} = '', "
                "{Shortlist Status} = 'Pending')"
            )
        applicants_with_json = get_all_records(
            APPLICANTS_TABLE, 
            filterByFormula=filterByFormula,
            fields=["Compressed JSON"]
        )
        personal_details = get_all_records(
            PERSONAL_DETAILS_TABLE
        )
        salary_preferences = get_all_records(
            SALARY_PREFERENCES_TABLE
        )
        work_experiences = get_all_records(
            WORK_EXPERIENCE_TABLE
        )
        for applicant_record in applicants_with_json:
            # Get all relevant data for the applicant
            print("Processing applicant:", applicant_record)
            applicant_id = applicant_record["id"]
            compressed_json = applicant_record["fields"].get("Compressed JSON")
            if not compressed_json:
                continue
            compressed_json = compressed_json.replace('\xa0', ' ')
            data = json.loads(compressed_json)

            # Create dictionary for personal details
            applicant_personal_detail = {
                "Full Name": data["personal"].get("name"),
                "Email": data["personal"].get("email", ""),
                "Location": data["personal"].get("location", ""),
                "Applicants": [applicant_id]
            }
            upsert_single_record(
                PERSONAL_DETAILS_TABLE,
                personal_details,
                applicant_personal_detail
            )

            # Create dictionary for salary preferences
            applicant_salary_preference = {
                "Applicants": [applicant_id],
                "Preferred Rate": data["salary"].get("rate", None),
                "Currency": data["salary"].get("currency", None),
                "Minimum Rate": data["salary"].get("min_rate", None),
                "Availability (hrs/wk)": data["salary"].get("availability", None)
            }
            upsert_single_record(
                SALARY_PREFERENCES_TABLE,
                salary_preferences,
                applicant_salary_preference
            )

            # Create work experience records
            applicant_work_experience = []
            for exp in data.get("experience", []):
                record = {}
                record["Applicants"] = [applicant_id]
                record["Company"] = exp.get("company", None)
                record["Title"] = exp.get("title", None)
                record["Start"] = exp.get("start", None)
                record["End"] = exp.get("end", None)
                record["Technologies"] = exp.get("technologies", [])
                applicant_work_experience.append(record)
            upsert_work_experience(
                applicant_id, 
                work_experiences, 
                applicant_work_experience
            )
        print("\nDecompression process completed successfully.")
    except requests.exceptions.HTTPError as e:
        print(f"An API error occurred: {e}")
        print(f"Response body: {e.response.text}")
        traceback.print_exc()
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    main()
