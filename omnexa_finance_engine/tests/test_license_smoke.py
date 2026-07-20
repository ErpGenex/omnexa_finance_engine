from frappe.tests.utils import FrappeTestCase

from omnexa_finance_engine import hooks, license_gate


class TestFinanceEngineLicenseSmoke(FrappeTestCase):
	def test_license_gate_is_wired(self):
		self.assertEqual(hooks.before_request, ["omnexa_finance_engine.license_gate.before_request"])
		self.assertEqual(license_gate._APP, "omnexa_finance_engine")
