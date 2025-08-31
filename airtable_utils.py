
import requests
import logging
from typing import Any, Dict, Optional
from config import CONFIG

# Setup logging for diagnostics
logging.basicConfig(
	level=logging.INFO,
	format='%(asctime)s %(levelname)s %(message)s'
)

def log_error(error: Exception) -> None:
	"""
	Utility to log errors consistently.
	"""
	logging.error(str(error))


class AirtableAPIError(Exception):
	"""
	Custom exception for Airtable API errors.
	Includes status code and response text.
	"""
	def __init__(self, message: str,
				 status_code: Optional[int] = None,
				 response_text: Optional[str] = None,
				 tb: Optional[str] = None) -> None:
		super().__init__(message)
		self.status_code = status_code
		self.response_text = response_text
		self.traceback = tb

	def __str__(self) -> str:
		info = f"AirtableAPIError: {self.args[0]}"
		if self.status_code is not None:
			info += f" | Status: {self.status_code}"
		if self.response_text:
			info += f" | Response: {self.response_text}"
		if self.traceback:
			info += f"\nTraceback:\n{self.traceback}"
		return info

	def details(self) -> dict:
		"""
		Return error details as a dictionary.
		"""
		return {
			"message": self.args[0],
			"status_code": self.status_code,
			"response_text": self.response_text,
			"traceback": self.traceback
		}


class AirtableClient:
	"""
	Airtable API wrapper for basic CRUD operations.
	"""
	BASE_URL = "https://api.airtable.com/v0"

	def __init__(self, base_id: str = None,
				 api_key: Optional[str] = None) -> None:
		self.base_id = base_id or CONFIG["AIRTABLE_BASE_ID"]
		self.api_key = api_key or CONFIG["AIRTABLE_API_KEY"]
		if not self.api_key:
			raise ValueError("Airtable API key not found.")
		self.headers = {
			"Authorization": f"Bearer {self.api_key}",
			"Content-Type": "application/json"
		}

	def _request(self, method: str, table_name: str,
				 record_id: Optional[str] = None,
				 fields: Optional[Dict[str, Any]] = None,
				 params: Optional[Dict[str, Any]] = None) -> Any:
		"""
		Internal method to send HTTP requests to Airtable API.
		Handles error reporting and logs errors.
		Supports GET params and POST/PATCH/DELETE data.
		"""
		import traceback
		url = self._url(table_name, record_id)
		data = {"fields": fields} if fields is not None and method != "GET" else None
		try:
			response = requests.request(
				method,
				url,
				headers=self.headers,
				json=data,
				params=params
			)
			response.raise_for_status()
			return response.json()
		except requests.exceptions.HTTPError as e:
			tb = traceback.format_exc()
			err = AirtableAPIError(
				f"Airtable API error: {e}",
				status_code=response.status_code,
				response_text=response.text,
				tb=tb
			)
			log_error(err)
			raise err
		except Exception as e:
			tb = traceback.format_exc()
			err = AirtableAPIError(
				f"Airtable request failed: {e}",
				tb=tb
			)
			log_error(err)
			raise err

	def _url(self, table_name: str,
			 record_id: Optional[str] = None) -> str:
		url = f"{self.BASE_URL}/{self.base_id}/{table_name}"
		if record_id:
			url += f"/{record_id}"
		return url

	def create_record(self, table_name: str,
					 fields: Dict[str, Any]) -> Any:
		"""
		Create a new record in an Airtable table.
		"""
		return self._request("POST", table_name, fields=fields)

	def update_record(self, table_name: str,
					 record_id: str,
					 fields: Dict[str, Any]) -> Any:
		"""
		Update an existing record in an Airtable table.
		"""
		return self._request("PATCH", table_name,
							 record_id=record_id, fields=fields)

	def delete_record(self, table_name: str,
					 record_id: str) -> Any:
		"""
		Delete a record from an Airtable table.
		"""
		return self._request("DELETE", table_name,
							 record_id=record_id)

	def fetch_records(self, table_name: str,
					  params: Optional[Dict[str, Any]] = None) -> Any:
		"""
		Fetch records from an Airtable table.
		Supports optional filtering via params.
		"""
		return self._request("GET", table_name, params=params)

	def upsert_record(self, table_name: str,
					  record_id: Optional[str],
					  fields: Dict[str, Any]) -> Any:
		"""
		Upsert (create or update) a record in Airtable.
		If record_id is provided, update; else, create.
		"""
		if record_id:
			return self.update_record(table_name, record_id, fields)
		else:
			return self.create_record(table_name, fields)