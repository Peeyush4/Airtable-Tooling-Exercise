import requests
import traceback
import time
from datetime import datetime
from geopy.geocoders import Nominatim
from config import CONFIG
from airtable_utils import AirtableClient, AirtableAPIError
from llm_utils import LLMClient

airtable = AirtableClient()
llm = LLMClient()
EXCHANGE_RATE_API_URL = (
    f"https://v6.exchangerate-api.com/v6/"
    f"{CONFIG['EXCHANGE_RATE_API_KEY']}/latest/USD"
)
conversion_rate_request = requests.get(EXCHANGE_RATE_API_URL)
conversion_rate_request.raise_for_status()
CONVERSION_RATES = conversion_rate_request.json().get("conversion_rates", {})
ALLOWED_LOCATIONS = CONFIG["ALLOWED_LOCATIONS"]
MIN_AVAILABILITY_HRS = CONFIG["MIN_AVAILABILITY_HRS"]
MAX_RATE_USD = CONFIG["MAX_RATE_USD"]
MIN_YEARS_EXPERIENCE = CONFIG["MIN_YEARS_EXPERIENCE"]


def create_shortlisted_lead(applicant_id, reason):
    """
    Update the Score Reason for an existing Shortlisted Lead record.
    Finds the record by applicant_id and updates the Score Reason field.
    """
    records = airtable.fetch_records(
        CONFIG["SHORTLISTED_LEADS_TABLE"],
        params={"filterByFormula": f"{{Applicants}} = {applicant_id}"}
    ).get("records", [])
    if records:
        record_id = records[0]["id"]
        airtable.update_record(
            CONFIG["SHORTLISTED_LEADS_TABLE"],
            record_id,
            {"Score Reason": reason}
        )


def check_experience(applicant_id):
    """
    Checks if the applicant meets experience criteria.
    Uses LLM to check if companies are tier-1 and calculates total years.
    Returns (bool, reason string).
    """
    experiences = airtable.fetch_records(
        CONFIG["WORK_EXPERIENCE_TABLE"],
        params={"filterByFormula": f"{{Applicants}} = '{applicant_id}'"}
    ).get("records", [])
    total_days = 0
    worked_at_tier_1 = False
    temp_tier_1 = False
    prompt = (
        "You are an expert in technology companies. Your task is to "
        "determine if the given company is widely considered a top-tier "
        "or 'FAANG-level' technology company in terms of prestige, "
        "engineering talent, and compensation. "
        "Answer only 'Yes' or 'No'. Do not make mistakes. "
        "Example: If the company is 'Google', answer 'Yes'. "
        "If the company is 'Infosys', answer 'No'. "
        "Company: '{company_name}'"
    )
    for experience_data in experiences:
        exp = experience_data.get("fields", {})
        # Use LLM to check if company is tier-1
        prompt_result = llm.generate_content(
            prompt.format(company_name=exp.get("Company", "").lower()),
            max_tokens=512
        )
        print("Company check:", prompt_result, exp.get("Company", "").lower())
        if prompt_result == "Yes":
            temp_tier_1 = True

        try:
            start_date_str = exp.get("Start")
            end_date_str = exp.get("End")
            if (not start_date_str) or (not end_date_str):
                continue
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
            if end_date_str.lower() == "present":
                end_date = datetime.now()
            else:
                end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
            worked_at_tier_1 = temp_tier_1 and (
                (end_date - start_date).days > 0
            )
            total_days += (end_date - start_date).days
        except (ValueError, TypeError):
            print(
                f"Warning: Could not parse dates for experience: "
                f"{exp.get('company')}"
            )
            continue
    total_years = total_days / 365.25
    # Return True if experience or tier-1 criteria met
    if ((total_years >= MIN_YEARS_EXPERIENCE) or worked_at_tier_1) \
            and total_years > 0:
        return True, (
            f"Experience: {total_years:.1f} years, Tier-1: "
            f"{'Yes' if worked_at_tier_1 else 'No'}"
        )
    return False, (
        f"Experience: {total_years:.1f} years (below min), Tier-1: No"
    )


def check_compensation(applicant_id):
    """
    Checks if the applicant meets compensation criteria.
    Converts rate to USD and checks minimums.
    Returns (bool, reason string).
    """
    salary_records = airtable.fetch_records(
        CONFIG["SALARY_PREFERENCES_TABLE"],
        params={"filterByFormula": f"{{Applicants}} = '{applicant_id}'"}
    ).get("records", [])
    salary = salary_records[0].get("fields", {}) if salary_records else {}
    if not salary:
        return False, "No salary information available."
    rate = salary.get("Preferred Rate", 0)
    currency = salary.get("Currency", "USD").upper()
    availability = salary.get("Availability (hrs/wk)", 0)
    # Convert rate to USD
    print("Preferred Rate (USD):", rate / CONVERSION_RATES.get(currency, 1))
    rate_ok = (
        rate is not None and
        rate / CONVERSION_RATES.get(currency, 1) <= MAX_RATE_USD
    )
    availability_ok = (
        availability is not None and
        availability >= MIN_AVAILABILITY_HRS
    )
    if rate_ok and availability_ok:
        return True, f"Compensation: ${rate}/hr, {availability} hrs/wk"
    reason = (
        f"Compensation: Rate ${rate} (>{MAX_RATE_USD}) "
        if not rate_ok else ""
    )
    reason += (
        f"Availability {availability}hrs (<{MIN_AVAILABILITY_HRS})"
        if not availability_ok else ""
    )
    return False, reason.strip()


def check_location(applicant_id):
    """
    Checks if the applicant's location is in the allowed list.
    Uses geopy and LLM for fuzzy matching.
    Returns (bool, reason string).
    """
    personal_records = airtable.fetch_records(
        CONFIG["PERSONAL_DETAILS_TABLE"],
        params={"filterByFormula": f"{{Applicants}} = '{applicant_id}'"}
    ).get("records", [])
    personal = personal_records[0].get("fields", {}) if personal_records else {}
    location = personal.get("Location", "").lower()
    print("Checking location:", location)
    try:
        # Use geopy to get country from location
        country = Nominatim(user_agent="geoapi").geocode(
            location
        ).address.split(",")[-1].strip()
        if country in ALLOWED_LOCATIONS:
            return True, (
                f"Location: {personal.get('location')} (Allowed)"
            )
    except AttributeError:
        print(
            f"Could not determine country for location: {location} "
            "using Nominatim"
        )
        # Use LLM for fuzzy location matching
        prompt = (
            "You are a location expert. Your task is to determine if a "
            "given place name refers to any location in the allowed "
            "locations list, even if there are spelling mistakes or minor "
            "variations. Use your knowledge to infer the intended location. "
            "If the location matches (directly or by correcting a spelling "
            "mistake), answer 'Yes'. Otherwise, answer 'No'. "
            f"Allowed locations: {ALLOWED_LOCATIONS}. "
            f"Place name: '{location}'. "
            "Respond only with 'Yes' or 'No'."
        )
        prompt_result = llm.generate_content(
            prompt.format(
                location=location,
                allowed_locations=ALLOWED_LOCATIONS
            ),
            max_tokens=512
        )
        print("Location Check:", prompt_result, location)
        if prompt_result == "Yes":
            return True, (
                f"Location: {personal.get('Location')} (Allowed)"
            )
    except Exception as e:
        print(f"Error checking location: {e}")
    return False, (
        f"Location: {personal.get('Location')} (Not in allowed list)"
    )


def main():
    """Main function to run the shortlisting script."""
    print("Starting lead shortlisting process...")
    try:
        applicants_to_review = airtable.fetch_records(
            CONFIG["APPLICANTS_TABLE"],
            params={
                "filterByFormula": (
                    "OR({Shortlist Status} = '', "
                    "{Shortlist Status} = 'Pending')"
                )
            }
        ).get("records", [])
        if not applicants_to_review:
            print("No new applicants to review.")
            return

        for record in applicants_to_review:
            applicant_id = record["fields"]["Applicant ID"]
            exp_ok, exp_reason = check_experience(applicant_id)
            comp_ok, comp_reason = check_compensation(applicant_id)
            loc_ok, loc_reason = check_location(applicant_id)
            all_criteria_met = exp_ok and comp_ok and loc_ok
            # Generate final reason string
            status = "Shortlisted" if all_criteria_met else "Not Shortlisted"
            final_reason = (
                f"Candidate {status} for the following reasons:\n"
                f"- {exp_reason}\n- {comp_reason}\n- {loc_reason}"
            )
            print(f"Updated status for Applicant {record['id']} to '{status}'")
            airtable.update_record(
                CONFIG["APPLICANTS_TABLE"], 
                record["id"], 
                {"Shortlist Status": status}
            )
            if status == "Shortlisted":
                time.sleep(5)  # Has to sleep for Airtable automation
                create_shortlisted_lead(applicant_id, final_reason)
        print("\nShortlisting process completed successfully.")

    except requests.exceptions.HTTPError as e:
        print(f"An API error occurred: {e}")
        print(f"Response body: {e.response.text}")
        traceback.print_exc()
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    main()
