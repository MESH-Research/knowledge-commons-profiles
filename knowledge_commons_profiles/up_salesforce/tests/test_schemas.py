from datetime import UTC
from datetime import datetime

from django.test import SimpleTestCase
from pydantic import TypeAdapter

from knowledge_commons_profiles.up_salesforce.schemas import Contact
from knowledge_commons_profiles.up_salesforce.schemas import QueryResponse
from knowledge_commons_profiles.up_salesforce.schemas import TokenResponse
from knowledge_commons_profiles.up_salesforce.tests.support import TOKEN_BODY


class TokenResponseTests(SimpleTestCase):
    def test_parses_salesforce_token_payload(self):
        token = TokenResponse.model_validate(TOKEN_BODY)
        self.assertEqual(token.access_token, TOKEN_BODY["access_token"])
        self.assertEqual(token.instance_url, TOKEN_BODY["instance_url"])
        self.assertEqual(token.token_type, "Bearer")

    def test_issued_at_is_converted_from_epoch_milliseconds(self):
        token = TokenResponse.model_validate(TOKEN_BODY)
        self.assertEqual(
            token.issued_at_datetime,
            datetime.fromtimestamp(1730000000, tz=UTC),
        )

    def test_issued_at_missing_gives_none(self):
        body = {**TOKEN_BODY}
        del body["issued_at"]
        self.assertIsNone(TokenResponse.model_validate(body).issued_at_datetime)

    def test_masked_token_hides_the_secret(self):
        token = TokenResponse.model_validate(TOKEN_BODY)
        masked = token.masked_token()
        self.assertNotIn(TOKEN_BODY["access_token"], masked)
        self.assertTrue(masked.startswith(TOKEN_BODY["access_token"][:4]))
        self.assertTrue(masked.endswith(TOKEN_BODY["access_token"][-4:]))
        self.assertLess(len(masked), len(TOKEN_BODY["access_token"]))

    def test_masked_token_for_short_token_reveals_nothing(self):
        token = TokenResponse.model_validate(
            {**TOKEN_BODY, "access_token": "abcdefgh"}
        )
        self.assertNotIn("abcdefgh", token.masked_token())


class QueryResponseTests(SimpleTestCase):
    def test_contact_query_parses_with_extra_fields(self):
        payload = {
            "totalSize": 1,
            "done": True,
            "records": [
                {
                    "attributes": {
                        "type": "Contact",
                        "url": "/services/data/v62.0/sobjects/Contact/003",
                    },
                    "Id": "003xx",
                    "Name": "Ada Lovelace",
                    "Email": "ada@example.org",
                    "AccountId": "001xx",
                    "Current_Staff__c": True,
                    "UP_Commons_Eligible__c": True,
                    "SomeOtherField__c": "kept",
                }
            ],
        }
        parsed = TypeAdapter(QueryResponse[Contact]).validate_python(payload)
        self.assertEqual(parsed.totalSize, 1)
        self.assertTrue(parsed.done)
        self.assertIsNone(parsed.nextRecordsUrl)
        self.assertEqual(parsed.records[0].AccountId, "001xx")
        self.assertTrue(parsed.records[0].UP_Commons_Eligible__c)

    def test_next_records_url_is_kept(self):
        payload = {
            "totalSize": 4000,
            "done": False,
            "nextRecordsUrl": "/services/data/v62.0/query/01gxx-2000",
            "records": [],
        }
        parsed = TypeAdapter(QueryResponse[dict]).validate_python(payload)
        self.assertEqual(
            parsed.nextRecordsUrl, "/services/data/v62.0/query/01gxx-2000"
        )
