import copy
import json
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from completeness_checker import (
    COMPLETE,
    NEEDS_REVIEW,
    check_listing,
    check_listings,
    format_report,
)

FIXTURES = pathlib.Path(__file__).resolve().parents[1] / "fixtures" / "synthetic_listings.json"


def complete_listing():
    return {
        "title": "Synthetic Community Arts Grant",
        "source_url": "https://example.org/grants/community-arts",
        "deadline": "2027-03-04",
        "deadline_status": "dated",
    }


class CompletenessCheckerTests(unittest.TestCase):
    def test_complete_listing(self):
        result = check_listing(complete_listing())
        self.assertEqual(result["status"], COMPLETE)
        self.assertEqual(result["fields_needing_attention"], [])
        self.assertEqual(result["parsed_deadline"], "2027-03-04")

    def test_missing_and_blank_fields(self):
        result = check_listing({"title": "  ", "source_url": "", "deadline": None})
        self.assertEqual(result["status"], NEEDS_REVIEW)
        self.assertIn("title", result["fields_needing_attention"])
        self.assertIn("source_url", result["fields_needing_attention"])
        self.assertIn("deadline", result["fields_needing_attention"])

    def test_missing_title_key_and_invalid_url(self):
        result = check_listing(
            {"source_url": "not a url", "deadline": "2027-03-04", "deadline_status": "dated"}
        )
        self.assertEqual(result["status"], NEEDS_REVIEW)
        self.assertIn("title", result["fields_needing_attention"])
        self.assertIn("source_url", result["fields_needing_attention"])
        self.assertNotIn("deadline", result["fields_needing_attention"])

    def test_malformed_url_does_not_stop_batch(self):
        # Regression: a malformed source_url (an invalid IPv6
        # literal) placed before a valid listing must be flagged
        # NEEDS_REVIEW naming source_url -- it must not raise and
        # stop the batch -- and the valid listing still completes.
        malformed = complete_listing()
        malformed["title"] = "Synthetic Malformed URL Listing"
        malformed["source_url"] = "http://[::1"
        results = check_listings([malformed, complete_listing()])
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["status"], NEEDS_REVIEW)
        self.assertIn("source_url", results[0]["fields_needing_attention"])
        self.assertEqual(results[1]["status"], COMPLETE)

    def test_url_without_hostname(self):
        # A URL with a netloc but no hostname is not a valid
        # source URL and must never return COMPLETE.
        listing = complete_listing()
        listing["source_url"] = "http://:8080/path"
        result = check_listing(listing)
        self.assertEqual(result["status"], NEEDS_REVIEW)
        self.assertIn("source_url", result["fields_needing_attention"])

    def test_invalid_deadline(self):
        listing = complete_listing()
        listing["deadline"] = "2027-13-40"
        result = check_listing(listing)
        self.assertEqual(result["status"], NEEDS_REVIEW)
        self.assertEqual(result["fields_needing_attention"], ["deadline"])
        self.assertEqual(result["parsed_deadline"], "")

    def test_source_confirmed_rolling_deadline(self):
        result = check_listing(
            {
                "title": "Synthetic Rolling Opportunity",
                "source_url": "https://example.org/opportunities/rolling",
                "deadline": None,
                "deadline_status": "rolling",
            }
        )
        self.assertEqual(result["status"], COMPLETE)
        self.assertEqual(result["fields_needing_attention"], [])
        self.assertEqual(result["parsed_deadline"], "")

    def test_source_confirmed_no_deadline(self):
        result = check_listing(
            {
                "title": "Synthetic No Deadline Opportunity",
                "source_url": "https://example.org/opportunities/open",
                "deadline": None,
                "deadline_status": "no_deadline",
            }
        )
        self.assertEqual(result["status"], COMPLETE)

    def test_vague_deadline_spring(self):
        # Synthetic rehearsal case, cleared for public use: a vague
        # season word must be flagged, never converted to a date.
        for vague in ("spring", "Spring 2027"):
            listing = complete_listing()
            listing["deadline"] = vague
            result = check_listing(listing)
            self.assertEqual(result["status"], NEEDS_REVIEW, vague)
            self.assertEqual(result["fields_needing_attention"], ["deadline"], vague)
            self.assertEqual(result["parsed_deadline"], "", vague)

    def test_input_is_not_modified(self):
        listing = complete_listing()
        listing["deadline"] = "Spring 2027"
        original = copy.deepcopy(listing)
        check_listing(listing)
        self.assertEqual(listing, original)

    def test_fixtures_file(self):
        listings = json.loads(FIXTURES.read_text(encoding="utf-8"))
        results = [check_listing(item) for item in listings]
        self.assertEqual(results[0]["status"], COMPLETE)
        self.assertEqual(results[1]["status"], NEEDS_REVIEW)
        self.assertEqual(results[2]["status"], NEEDS_REVIEW)
        self.assertIn("deadline", results[2]["fields_needing_attention"])
        self.assertEqual(results[3]["status"], COMPLETE)
        self.assertEqual(results[4]["status"], NEEDS_REVIEW)
        self.assertIn("deadline", results[4]["fields_needing_attention"])
        self.assertEqual(results[4]["parsed_deadline"], "")
        report = format_report(listings)
        self.assertIn(COMPLETE, report)
        self.assertIn(NEEDS_REVIEW, report)


if __name__ == "__main__":
    unittest.main()
