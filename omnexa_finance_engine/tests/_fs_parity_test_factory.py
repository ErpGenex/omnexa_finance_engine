# Copyright (c) 2026, ErpGenEx
"""Reusable test body for FS apps — import in each app's test_sap_parity_gl.py."""

from frappe.tests.utils import FrappeTestCase

from omnexa_finance_engine.fs_parity_bridge import preview_gl_for_vertical


def make_fs_gl_test_class(vertical: str):
	class _Test(FrappeTestCase):
		def test_preview_gl_posting_bridge(self):
			out = preview_gl_for_vertical(vertical, principal="1000")
			self.assertEqual(out["vertical"], vertical)
			self.assertGreaterEqual(len(out["lines"]), 2)

	return _Test
