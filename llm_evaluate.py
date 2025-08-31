import re
from llm_utils import LLMClient
from airtable_utils import AirtableClient, AirtableAPIError
import logging
from config import CONFIG

# Airtable client
airtable = AirtableClient()

# LLM client
llm = LLMClient()

# --- LLM Prompt ---
PROMPT_TEMPLATE = (
    "You are a world-class recruiting analyst. "
    "I will provide you with a JSON object containing an applicant's "
    "profile.\nYour task is to analyze the profile and do four things "
    "EXACTLY as specified below.\n\nJSON Profile:\n{json_data}\n\n" 
    "Based on the profile, provide the following four items. Return ONLY "
    "the text for these four items and nothing else. Follow the format "
    "precisely.\n\n"
    "Summary: <A concise summary of the applicant's profile in 75 words or "
    "less.>\n"
    "Score: <An integer quality score from 1 to 10, where 10 is best.>\n"
    "Issues: <A comma-separated list of any missing, incomplete, or "
    "contradictory fields. If there are no issues, write 'None'.>\n"
    "Follow-Ups: <A bulleted list of up to three follow-up questions to ask "
    "the candidate to clarify gaps or learn more. If none, write 'None'.>\n"
)


def parse_llm_response(response_text):
    """
    Parses the raw text response from the LLM into a structured dict.
    """
    parsed_data = {}
    try:
        summaries = re.search(
            r"Summary: (.+?)\n", response_text.strip()
        )
        score = re.search(
            r"Score: (\d+)\n", response_text.strip()
        )
        issues = re.search(
            r"Issues: (.+?)\n", response_text.strip()
        )
        follow_ups = re.search(
            r"Follow-Ups:(.+?)$", response_text.strip(), re.DOTALL
        )
        if summaries:
            parsed_data["LLM Summary"] = summaries.group(1)
        if score:
            parsed_data["LLM Score"] = int(score.group(1))
        if follow_ups:
            parsed_data["LLM Follow-Ups"] = follow_ups.group(1).strip()
            if issues:
                parsed_data["LLM Follow-Ups"] += (
                    f"\n(Issues: {issues.group(1)})"
                )
    except (IndexError, ValueError, TypeError) as e:
        print(f"Error parsing LLM response: {e}")
        print(f"--- Raw Response ---\n{response_text}\n--------------------")
        return None
    return parsed_data


def fetch_applicants():
    """Fetch applicants needing LLM evaluation."""
    response = airtable.fetch_records(
        CONFIG["APPLICANTS_TABLE"],
        params={
            "filterByFormula": (
                "AND({Compressed JSON} != '', {LLM Summary} = '')"
            )
        }
    )
    applicants = response.get("records", [])
    print(f"Found {len(applicants)} new applicants to evaluate.")
    return applicants


def evaluate_applicant(json_str):
    """Generate LLM evaluation for an applicant's JSON profile."""
    prompt = llm.with_template(PROMPT_TEMPLATE, json_data=json_str)
    llm_response = llm.generate_content(prompt)
    if not llm_response:
        print("Failed to get a valid response from LLM.")
        return None
    return parse_llm_response(llm_response)



def main():
    """Main function to run the LLM evaluation script."""
    print("Starting LLM evaluation process...")
    try:
        applicants = fetch_applicants()
        if not applicants:
            print("No new applicants to process. Exiting.")
            return
        # For each record, write a LLM response
        for record in applicants:
            # Get all the relevant fields
            record_id = record["id"]
            json_str = record.get("fields", {}).get("Compressed JSON")
            if not json_str:
                print(f"Skipping record {record_id} due to missing JSON.")
                continue
            # Evaluate applicant using LLM and update record
            print(f"\nEvaluating applicant {record_id}...")
            parsed_data = evaluate_applicant(json_str)
            if parsed_data:
                airtable.update_record(CONFIG["APPLICANTS_TABLE"], record_id, parsed_data)
                print(f"Successfully updated record {record_id} with LLM evaluation.")
            else:
                print(
                    f"Failed to parse LLM response for {record_id}. "
                    "Skipping update."
                )
                airtable.update_record(
                    CONFIG["APPLICANTS_TABLE"],
                    record_id,
                    {"LLM Summary": "Error: Failed to parse LLM response."}
                )

        print("\nLLM evaluation process completed.")

    except AirtableAPIError as e:
        logging.error(str(e))
        print(f"Airtable API error occurred: {e}")
    except Exception as e:
        logging.error(str(e))
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    main()
