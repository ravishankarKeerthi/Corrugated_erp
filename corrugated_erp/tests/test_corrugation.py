"""Unit tests for the pure-python corrugation engine.

Run without a bench:   python -m unittest corrugated_erp.tests.test_corrugation
Run inside a bench:    bench --site <site> run-tests --module corrugated_erp.tests.test_corrugation
"""

import unittest

from corrugated_erp.utils import corrugation as c


class TestLayers(unittest.TestCase):
	def test_three_ply(self):
		rows = c.build_layer_template(3, ["B"])
		self.assertEqual([r["layer_name"] for r in rows], ["Top Liner", "Flute 1", "Bottom Liner"])
		self.assertEqual(rows[1]["flute_type"], "B")

	def test_five_ply(self):
		rows = c.build_layer_template(5, ["B", "C"])
		self.assertEqual(
			[r["layer_name"] for r in rows],
			["Top Liner", "Flute 1", "Middle Liner", "Flute 2", "Bottom Liner"],
		)

	def test_seven_ply(self):
		rows = c.build_layer_template(7, ["B", "C", "B"])
		self.assertEqual(len(rows), 7)
		self.assertEqual(rows[2]["layer_name"], "Middle Liner 1")
		self.assertEqual(rows[4]["layer_name"], "Middle Liner 2")

	def test_missing_flute(self):
		with self.assertRaises(ValueError):
			c.build_layer_template(5, ["B"])


class TestSheetSize(unittest.TestCase):
	def test_rsc_outer(self):
		# 300 x 200 x 150 RSC, outer dims, 35 mm glue flap
		length, width = c.sheet_size(300, 200, 150, glue_flap_mm=35)
		self.assertEqual(length, 1035.0)  # 2*(300+200)+35
		self.assertEqual(width, 350.0)  # 150 + 0.5*200 + 0.5*200

	def test_hsc(self):
		_, width = c.sheet_size(300, 200, 150, top_flap_factor=0.5, bottom_flap_factor=0)
		self.assertEqual(width, 250.0)

	def test_manual(self):
		self.assertEqual(c.sheet_size(1, 1, 1, method="Manual", manual_length_mm=500, manual_width_mm=400), (500.0, 400.0))


class TestSpec(unittest.TestCase):
	def setUp(self):
		self.spec = {
			"length_mm": 300,
			"width_mm": 200,
			"height_mm": 150,
			"dimension_basis": "Outer",
			"glue_flap_mm": 35,
			"liner_thickness_mm": 0.2,
			"gum_gsm_per_glue_line": 6,
			"ect_kn_per_m": 5,
			"layers": [
				{"layer_type": "Liner", "gsm": 150, "bf": 18, "take_up_factor": 1},
				{"layer_type": "Flute", "gsm": 120, "bf": 16, "take_up_factor": 1.35, "flute_height_mm": 2.8},
				{"layer_type": "Liner", "gsm": 150, "bf": 18, "take_up_factor": 1},
			],
		}

	def test_weights(self):
		r = c.compute_spec(self.spec)
		self.assertAlmostEqual(r["sheet_area_sqm"], 0.36225, places=5)  # 1.035 x 0.35
		self.assertAlmostEqual(r["board_gsm"], 462.0, places=2)  # 150 + 120*1.35 + 150
		self.assertAlmostEqual(r["box_weight_g"], 167.36, places=1)
		self.assertAlmostEqual(sum(layer["weight_g"] for layer in r["layers"]), r["box_weight_g"], places=1)

	def test_strength(self):
		r = c.compute_spec(self.spec)
		self.assertAlmostEqual(r["theoretical_bs"], 6.36, places=2)  # 2.7+2.7+0.96
		self.assertEqual(r["caliper_mm"], 3.2)
		self.assertGreater(r["estimated_bct_kgf"], 150)
		self.assertLess(r["estimated_bct_kgf"], 200)

	def test_inner_adds_allowance(self):
		outer = c.compute_spec(self.spec)
		self.spec["dimension_basis"] = "Inner"
		inner = c.compute_spec(self.spec)
		self.assertGreater(inner["sheet_length_mm"], outer["sheet_length_mm"])
		self.assertGreater(inner["sheet_width_mm"], outer["sheet_width_mm"])

	def test_gum(self):
		r = c.compute_spec(self.spec)
		self.assertAlmostEqual(r["gum_kg_per_box"], 0.36225 * 1 * 2 * 6 / 1000, places=6)


class TestDeckle(unittest.TestCase):
	def test_auto_outs(self):
		opts = c.deckle_options([{"width_mm": 350, "outs": 0}], [c.inch_to_mm(x) for x in range(28, 74, 2)], 20)
		best = opts[0]
		self.assertGreaterEqual(best["outs"][0], 1)
		self.assertLessEqual(best["used_width_mm"] + 20, best["deckle_mm"])
		# every option respects the minimum trim and is sorted by trim %
		self.assertEqual(opts, sorted(opts, key=lambda o: (o["trim_pct"], o["deckle_mm"])))

	def test_combination(self):
		opts = c.deckle_options([{"width_mm": 350, "outs": 2}, {"width_mm": 400, "outs": 1}], [1100, 1150, 1200], 20)
		self.assertEqual(opts[0]["deckle_mm"], 1150.0)
		self.assertEqual(opts[0]["used_width_mm"], 1100.0)

	def test_no_fit(self):
		self.assertEqual(c.deckle_options([{"width_mm": 2000, "outs": 1}], [1000], 20), [])

	def test_cuts(self):
		self.assertEqual(c.cuts_required(1001, 2), 501)


class TestCosting(unittest.TestCase):
	def test_cost(self):
		r = c.compute_cost(
			{
				"papers": [{"weight_kg": 0.05434, "rate": 40}, {"weight_kg": 0.06520, "rate": 38}, {"weight_kg": 0.05434, "rate": 40}],
				"waste_pct": 3,
				"box_weight_kg": 0.16736,
				"conversion_rate_per_kg": 6,
				"colours": 2,
				"print_rate_per_colour_per_1000": 150,
				"plate_cost": 5000,
				"plate_amortise_qty": 50000,
				"stitches": 4,
				"stitch_rate": 0.05,
				"overhead_pct": 5,
				"margin_pct": 10,
				"quantity": 1000,
			}
		)
		paper = 0.05434 * 40 * 2 + 0.0652 * 38
		self.assertAlmostEqual(r["paper_cost_per_box"], round(paper, 4), places=4)
		mfg = paper * 1.03 + 6 * 0.16736 + 0.3 + 0.1 + 0.2
		self.assertAlmostEqual(r["manufacturing_cost_per_box"], round(mfg, 4), places=3)
		self.assertAlmostEqual(r["total_cost_per_box"], round(mfg * 1.05, 4), places=3)
		self.assertAlmostEqual(r["selling_price_per_box"], round(mfg * 1.05 * 1.1, 4), places=3)
		self.assertAlmostEqual(r["order_value"], round(mfg * 1.05 * 1.1 * 1000, 2), places=0)

	def test_margin(self):
		self.assertEqual(c.achieved_margin_pct(11, 10), 10.0)
		self.assertEqual(c.achieved_margin_pct(5, 0), 0.0)

	def test_ups_per_sheet(self):
		base = {
			"length_mm": 0, "width_mm": 0, "height_mm": 0, "method": "Manual",
			"manual_length_mm": 1000, "manual_width_mm": 500, "dimension_basis": "Outer",
			"gum_gsm_per_glue_line": 6,
			"layers": [
				{"layer_type": "Liner", "gsm": 150, "take_up_factor": 1},
				{"layer_type": "Flute", "gsm": 120, "take_up_factor": 1.5, "flute_height_mm": 2.5},
				{"layer_type": "Liner", "gsm": 150, "take_up_factor": 1},
			],
		}
		one = c.compute_spec(dict(base))
		four = c.compute_spec(dict(base, ups=4))
		self.assertEqual(one["sheet_area_sqm"], 0.5)
		self.assertEqual(four["sheet_area_sqm"], 0.5)
		self.assertAlmostEqual(four["box_weight_g"], one["box_weight_g"] / 4, places=1)
		self.assertAlmostEqual(four["sheet_weight_g"], one["box_weight_g"], places=1)
		self.assertAlmostEqual(four["gum_kg_per_box"], one["gum_kg_per_box"] / 4, places=5)
		self.assertEqual(c.cuts_required(1000, 2, 4), 125)
		self.assertEqual(c.sheets_required(1001, 4), 251)

	def test_split_reel(self):
		r = c.split_reel(500, 1830, [915, 900])
		self.assertEqual(r["child_weights"], [250.0, 245.9])
		self.assertEqual(r["trim_deckle_mm"], 15.0)
		self.assertAlmostEqual(sum(r["child_weights"]) + r["trim_weight_kg"], 500, places=2)
		with self.assertRaises(ValueError):
			c.split_reel(500, 1000, [600, 500])

	def test_planning_and_labour(self):
		self.assertEqual(c.paper_required_kg([100, 50], 2000, 5), [210.0, 105.0])
		d = c.downtime_summary(8, 60, 7000)
		self.assertEqual(d["net_run_hrs"], 7.0)
		self.assertEqual(d["output_per_hour"], 1000.0)
		self.assertEqual(d["availability_pct"], 87.5)
		self.assertEqual(c.piece_amount(2500, 40), 100.0)
		self.assertEqual(c.piece_amount(10, 2, "Per Nos"), 20.0)
		self.assertEqual(c.price_from_kg_rate(52, 0.25), 13.0)


if __name__ == "__main__":
	unittest.main()
