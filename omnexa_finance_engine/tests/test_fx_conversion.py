from decimal import Decimal

from frappe.tests.utils import FrappeTestCase

from omnexa_finance_engine.engine import CurrencyRounding, FXQuote, Money, convert_money


class TestFxConversion(FrappeTestCase):
	def test_convert_money(self):
		usd = Money(amount=Decimal("100"), currency="USD", rounding=CurrencyRounding(2, "HALF_UP"))
		q = FXQuote(source_currency="USD", target_currency="EUR", rate=Decimal("0.925"))
		eur = convert_money(usd, "EUR", q, target_rounding=CurrencyRounding(2, "HALF_UP"))
		self.assertEqual(eur.currency, "EUR")
		self.assertEqual(eur.amount, Decimal("92.50"))
