# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""Wave DoD smoke — omnexa_finance_engine."""

from frappe.tests.utils import FrappeTestCase


class TestWaveDoD(FrappeTestCase):
	def test_app_importable(self):
		import importlib

		mod = importlib.import_module("omnexa_finance_engine")
		self.assertTrue(mod.__name__)
