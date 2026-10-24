"""Corrugated ERP calculation engine.

Pure Python (no Frappe imports) so it can be unit tested anywhere and reused by
Box Specification, Box Costing, Deckle Plan and Paper Price Revision.

Conventions
-----------
* All lengths are millimetres, weights grams (g) or kilograms (kg) as named.
* GSM = grams per square metre. BF = bursting factor of kraft paper.
* "Liner" layers are flat; "Flute" layers are corrugated and consume more paper
  than the board area. That extra is the flute take-up factor (e.g. B flute ~1.35).
"""

from math import ceil, floor, sqrt

MM_PER_INCH = 25.4
G_FORCE = 9.80665  # N per kgf


def _f(value):
	try:
		return float(value or 0)
	except (TypeError, ValueError):
		return 0.0


def rnd(value, digits=3):
	return round(_f(value), digits)


def mm_to_inch(mm):
	return rnd(_f(mm) / MM_PER_INCH, 2)


def inch_to_mm(inch):
	return rnd(_f(inch) * MM_PER_INCH, 1)


def is_flute(layer_type):
	return (layer_type or "").strip().lower().startswith("flute")


# ---------------------------------------------------------------------------
# Board build-up
# ---------------------------------------------------------------------------
def flute_count(ply):
	ply = int(_f(ply) or 3)
	if ply not in (2, 3, 5, 7, 9):
		raise ValueError("Ply must be 2, 3, 5, 7 or 9")
	return 1 if ply == 2 else (ply - 1) // 2


def build_layer_template(ply, flutes):
	"""Return the layer rows (top to bottom) for a board.

	ply    : 2, 3, 5, 7 or 9
	flutes : list of flute codes, one per flute layer (e.g. ["B"] or ["B", "C"])
	"""
	ply = int(_f(ply) or 3)
	n = flute_count(ply)
	flutes = [f for f in (flutes or []) if f]
	if len(flutes) < n:
		raise ValueError("{0} flute type(s) required for {1} ply board".format(n, ply))

	rows = [{"layer_name": "Top Liner", "layer_type": "Liner", "flute_type": None}]
	middle = 0
	for i in range(n):
		rows.append({"layer_name": "Flute {0}".format(i + 1), "layer_type": "Flute", "flute_type": flutes[i]})
		if ply == 2:
			break
		if i < n - 1:
			middle += 1
			name = "Middle Liner" if n == 2 else "Middle Liner {0}".format(middle)
			rows.append({"layer_name": name, "layer_type": "Liner", "flute_type": None})
		else:
			rows.append({"layer_name": "Bottom Liner", "layer_type": "Liner", "flute_type": None})
	return rows


def effective_gsm(gsm, layer_type, take_up_factor):
	take_up = _f(take_up_factor) or 1.0
	return _f(gsm) * (take_up if is_flute(layer_type) else 1.0)


def board_caliper(layers, liner_thickness_mm=0.2):
	"""Approximate board thickness = sum of flute heights + liner thickness."""
	cal = 0.0
	for layer in layers:
		if is_flute(layer.get("layer_type")):
			cal += _f(layer.get("flute_height_mm"))
		else:
			cal += _f(liner_thickness_mm)
	return rnd(cal, 2)


def theoretical_bs(layers):
	"""Theoretical bursting strength (kg/cm2) - common Indian plant thumb rule.

	Liners contribute BF x GSM / 1000, flutes contribute half of that.
	It is an estimate for quoting; always confirm with a lab test.
	"""
	total = 0.0
	for layer in layers:
		contribution = _f(layer.get("bf")) * _f(layer.get("gsm")) / 1000.0
		total += contribution * (0.5 if is_flute(layer.get("layer_type")) else 1.0)
	return rnd(total, 2)


def mckee_bct_kgf(ect_kn_per_m, caliper_mm, length_mm, width_mm):
	"""Box compression strength by the simplified McKee formula.

	BCT [N] = 5.87 x ECT [N/m] x sqrt(caliper [m] x perimeter [m])
	Returns kgf. Returns 0 when ECT or caliper is unknown.
	"""
	ect = _f(ect_kn_per_m) * 1000.0
	cal = _f(caliper_mm) / 1000.0
	perimeter = 2.0 * (_f(length_mm) + _f(width_mm)) / 1000.0
	if ect <= 0 or cal <= 0 or perimeter <= 0:
		return 0.0
	newton = 5.87 * ect * sqrt(cal * perimeter)
	return rnd(newton / G_FORCE, 1)


# ---------------------------------------------------------------------------
# Sheet (blank) size
# ---------------------------------------------------------------------------
def sheet_size(
	length_mm,
	width_mm,
	height_mm,
	method="Wrap Around",
	top_flap_factor=0.5,
	bottom_flap_factor=0.5,
	glue_flap_mm=35,
	score_allowance_mm=0,
	length_allowance_mm=0,
	width_allowance_mm=0,
	manual_length_mm=0,
	manual_width_mm=0,
):
	"""Return (sheet_length_mm, sheet_width_mm).

	Wrap-around styles (RSC 0201, HSC 0200, FOL 0203):
	  sheet length = 2L + 2W + glue flap (+ 4 score allowances)
	  sheet width  = H + top flap + bottom flap (+ score allowances)
	  where each flap = flap factor x W (RSC 0.5 / 0.5, HSC 0.5 / 0, FOL 1 / 1)
	The sheet width is the corrugator cut width, i.e. what must fit on the reel deckle.
	"""
	if (method or "").lower().startswith("manual"):
		return rnd(manual_length_mm, 1), rnd(manual_width_mm, 1)

	L, W, H = _f(length_mm), _f(width_mm), _f(height_mm)
	a = _f(score_allowance_mm)
	length = 2 * (L + W) + 4 * a + _f(glue_flap_mm) + _f(length_allowance_mm)
	flaps = (_f(top_flap_factor) + _f(bottom_flap_factor)) * (W + a)
	width = H + 2 * a + flaps + _f(width_allowance_mm)
	return rnd(length, 1), rnd(width, 1)


def sheet_area_sqm(sheet_length_mm, sheet_width_mm):
	return rnd(_f(sheet_length_mm) * _f(sheet_width_mm) / 1_000_000.0, 6)


def gum_kg_per_box(area_sqm, flutes, gum_gsm_per_glue_line):
	"""Starch gum: each flute is glued on both tips (single facer + pasting)."""
	return rnd(_f(area_sqm) * int(_f(flutes)) * 2 * _f(gum_gsm_per_glue_line) / 1000.0, 6)


def compute_spec(spec):
	"""Full technical calculation for a box specification.

	spec keys: length_mm, width_mm, height_mm, dimension_basis ("Inner"/"Outer"),
	method, top_flap_factor, bottom_flap_factor, glue_flap_mm, length_allowance_mm,
	width_allowance_mm, manual_length_mm, manual_width_mm, liner_thickness_mm,
	caliper_override_mm, ect_kn_per_m, gum_gsm_per_glue_line,
	ups (boxes cut from one sheet, default 1),
	layers: [{layer_type, gsm, bf, take_up_factor, flute_height_mm}]

	Sheet figures are for one corrugated sheet; weights, area and gum are per box
	(sheet / ups), so die-cut jobs with 2, 4 ... ups per sheet are costed correctly.
	"""
	layers = spec.get("layers") or []
	ups = max(1, int(_f(spec.get("ups")) or 1))
	caliper = _f(spec.get("caliper_override_mm")) or board_caliper(layers, spec.get("liner_thickness_mm", 0.2))
	score = caliper if (spec.get("dimension_basis") or "Inner") == "Inner" else 0.0

	s_len, s_wid = sheet_size(
		spec.get("length_mm"),
		spec.get("width_mm"),
		spec.get("height_mm"),
		method=spec.get("method") or "Wrap Around",
		top_flap_factor=spec.get("top_flap_factor", 0.5),
		bottom_flap_factor=spec.get("bottom_flap_factor", 0.5),
		glue_flap_mm=spec.get("glue_flap_mm", 35),
		score_allowance_mm=score,
		length_allowance_mm=spec.get("length_allowance_mm", 0),
		width_allowance_mm=spec.get("width_allowance_mm", 0),
		manual_length_mm=spec.get("manual_length_mm", 0),
		manual_width_mm=spec.get("manual_width_mm", 0),
	)
	area = sheet_area_sqm(s_len, s_wid)
	box_area = area / ups

	out_layers = []
	board_gsm = 0.0
	for layer in layers:
		eff = effective_gsm(layer.get("gsm"), layer.get("layer_type"), layer.get("take_up_factor"))
		board_gsm += eff
		out_layers.append({"effective_gsm": rnd(eff, 2), "weight_g": rnd(eff * box_area, 2)})

	box_weight_g = board_gsm * box_area
	flutes = sum(1 for layer in layers if is_flute(layer.get("layer_type")))
	return {
		"caliper_mm": rnd(caliper, 2),
		"sheet_length_mm": s_len,
		"sheet_width_mm": s_wid,
		"sheet_length_inch": mm_to_inch(s_len),
		"sheet_width_inch": mm_to_inch(s_wid),
		"sheet_area_sqm": area,
		"ups": ups,
		"box_area_sqm": rnd(box_area, 6),
		"sheet_weight_g": rnd(board_gsm * area, 2),
		"board_gsm": rnd(board_gsm, 2),
		"box_weight_g": rnd(box_weight_g, 2),
		"box_weight_kg": rnd(box_weight_g / 1000.0, 5),
		"theoretical_bs": theoretical_bs(layers),
		"estimated_bct_kgf": mckee_bct_kgf(
			spec.get("ect_kn_per_m"), caliper, spec.get("length_mm"), spec.get("width_mm")
		),
		"gum_kg_per_box": gum_kg_per_box(box_area, flutes, spec.get("gum_gsm_per_glue_line", 0)),
		"flutes": flutes,
		"layers": out_layers,
	}


# ---------------------------------------------------------------------------
# Deckle (reel width) planning
# ---------------------------------------------------------------------------
def deckle_options(rows, standard_deckles, min_trim_mm=20):
	"""Suggest reel deckles with the least trim waste.

	rows: list of {"width_mm": sheet width, "outs": n}. A single row with outs 0
	      means "find the best number of outs" for that sheet width.
	standard_deckles: list of available reel widths in mm.
	Returns options sorted by trim % (best first).
	"""
	rows = [r for r in (rows or []) if _f(r.get("width_mm")) > 0]
	if not rows:
		return []
	min_trim = _f(min_trim_mm)
	auto = len(rows) == 1 and not int(_f(rows[0].get("outs")))
	options = []
	for d in sorted({_f(x) for x in standard_deckles or [] if _f(x) > 0}):
		if auto:
			w = _f(rows[0]["width_mm"])
			outs = int(floor((d - min_trim) / w)) if d > min_trim else 0
			if outs < 1:
				continue
			used = outs * w
			outs_list = [outs]
		else:
			outs_list = [max(1, int(_f(r.get("outs")) or 1)) for r in rows]
			used = sum(_f(r["width_mm"]) * o for r, o in zip(rows, outs_list))
		if used + min_trim > d + 1e-9:
			continue
		trim = d - used
		options.append(
			{
				"deckle_mm": rnd(d, 1),
				"deckle_inch": mm_to_inch(d),
				"outs": outs_list,
				"used_width_mm": rnd(used, 1),
				"trim_mm": rnd(trim, 1),
				"trim_pct": rnd(trim / d * 100.0, 2),
			}
		)
	options.sort(key=lambda o: (o["trim_pct"], o["deckle_mm"]))
	return options


def cuts_required(qty, outs, ups=1):
	"""Corrugator cuts needed for qty boxes with `outs` sheets across the reel and `ups` boxes per sheet."""
	outs = max(1, int(_f(outs) or 1))
	ups = max(1, int(_f(ups) or 1))
	return int(ceil(_f(qty) / ups / outs))


def sheets_required(qty, ups=1):
	ups = max(1, int(_f(ups) or 1))
	return int(ceil(_f(qty) / ups))


# ---------------------------------------------------------------------------
# Reel slitting (cutting one reel into narrower reels)
# ---------------------------------------------------------------------------
def split_reel(parent_weight_kg, parent_deckle_mm, child_deckles_mm):
	"""Split a reel's weight across narrower child reels in proportion to width.

	Returns {"child_weights": [...], "used_deckle_mm", "trim_deckle_mm", "trim_weight_kg"}.
	Raises ValueError if the children are wider than the parent.
	"""
	weight, parent = _f(parent_weight_kg), _f(parent_deckle_mm)
	children = [_f(c) for c in child_deckles_mm or []]
	if parent <= 0 or weight <= 0:
		raise ValueError("Parent reel deckle and weight must be greater than zero")
	if not children or any(c <= 0 for c in children):
		raise ValueError("Every child reel needs a deckle greater than zero")
	used = sum(children)
	if used > parent + 1e-9:
		raise ValueError("Child reels ({0} mm) are wider than the parent reel ({1} mm)".format(rnd(used, 1), rnd(parent, 1)))
	per_mm = weight / parent
	child_weights = [rnd(c * per_mm, 2) for c in children]
	trim_weight = rnd(weight - sum(child_weights), 2)
	return {
		"child_weights": child_weights,
		"used_deckle_mm": rnd(used, 1),
		"trim_deckle_mm": rnd(parent - used, 1),
		"trim_weight_kg": max(trim_weight, 0.0),
	}


# ---------------------------------------------------------------------------
# Planning
# ---------------------------------------------------------------------------
def paper_required_kg(layer_weights_g, qty, waste_pct=0):
	"""Paper kg per layer for qty boxes including process waste. layer_weights_g are per box."""
	factor = _f(qty) / 1000.0 * (1 + _f(waste_pct) / 100.0)
	return [rnd(_f(w) * factor, 3) for w in layer_weights_g or []]


# ---------------------------------------------------------------------------
# Costing
# ---------------------------------------------------------------------------
def compute_cost(inp):
	"""Per-box cost and price.

	inp keys:
	  papers                      : [{weight_kg, rate}] paper per box by layer
	  waste_pct                   : process + trim waste on paper (%)
	  box_weight_kg               : board weight of one box
	  conversion_rate_per_kg      : corrugation + pasting + power + labour per kg
	  colours, print_rate_per_colour_per_1000
	  plate_cost, plate_amortise_qty, die_cost, die_amortise_qty
	  stitches, stitch_rate, gum_kg, gum_rate, other_cost_per_box
	  overhead_pct, freight_per_box, margin_pct (mark-up on total cost), quantity
	"""
	g = lambda k: _f(inp.get(k))  # noqa: E731

	paper_rows = []
	paper_cost = 0.0
	for p in inp.get("papers") or []:
		cost = _f(p.get("weight_kg")) * _f(p.get("rate"))
		paper_rows.append(rnd(cost, 4))
		paper_cost += cost

	waste_cost = paper_cost * g("waste_pct") / 100.0
	conversion = g("conversion_rate_per_kg") * g("box_weight_kg")
	printing = g("colours") * g("print_rate_per_colour_per_1000") / 1000.0
	tooling = 0.0
	if g("plate_amortise_qty"):
		tooling += g("plate_cost") / g("plate_amortise_qty")
	if g("die_amortise_qty"):
		tooling += g("die_cost") / g("die_amortise_qty")
	stitching = g("stitches") * g("stitch_rate")
	gum = g("gum_kg") * g("gum_rate")
	mfg = paper_cost + waste_cost + conversion + printing + tooling + stitching + gum + g("other_cost_per_box")
	overhead = mfg * g("overhead_pct") / 100.0
	total = mfg + overhead + g("freight_per_box")
	price = total * (1 + g("margin_pct") / 100.0)
	weight = g("box_weight_kg")
	return {
		"paper_rows": paper_rows,
		"paper_cost_per_box": rnd(paper_cost, 4),
		"waste_cost_per_box": rnd(waste_cost, 4),
		"conversion_cost_per_box": rnd(conversion, 4),
		"printing_cost_per_box": rnd(printing, 4),
		"tooling_cost_per_box": rnd(tooling, 4),
		"stitching_cost_per_box": rnd(stitching, 4),
		"gum_cost_per_box": rnd(gum, 4),
		"manufacturing_cost_per_box": rnd(mfg, 4),
		"overhead_cost_per_box": rnd(overhead, 4),
		"total_cost_per_box": rnd(total, 4),
		"selling_price_per_box": rnd(price, 4),
		"cost_per_kg": rnd(total / weight, 2) if weight else 0.0,
		"price_per_kg": rnd(price / weight, 2) if weight else 0.0,
		"margin_per_box": rnd(price - total, 4),
		"order_value": rnd(price * g("quantity"), 2),
	}


def price_from_kg_rate(rate_per_kg, box_weight_kg):
	"""Per-box price when the customer agrees a rate per kg."""
	return rnd(_f(rate_per_kg) * _f(box_weight_kg), 4)


def downtime_summary(duration_hrs, downtime_minutes, output_qty):
	"""Net running hours and output per running hour."""
	gross = _f(duration_hrs)
	down = _f(downtime_minutes) / 60.0
	net = max(gross - down, 0.0)
	return {
		"downtime_hrs": rnd(down, 2),
		"net_run_hrs": rnd(net, 2),
		"output_per_hour": rnd(_f(output_qty) / net, 1) if net else 0.0,
		"availability_pct": rnd(net / gross * 100.0, 1) if gross else 0.0,
	}


def piece_amount(output_qty, rate, basis="Per 1000 Nos"):
	"""Contract labour amount for a stage."""
	q, r = _f(output_qty), _f(rate)
	if basis == "Per Nos":
		return rnd(q * r, 2)
	return rnd(q / 1000.0 * r, 2)


def achieved_margin_pct(price, total_cost):
	price, total_cost = _f(price), _f(total_cost)
	if not total_cost:
		return 0.0
	return rnd((price / total_cost - 1) * 100.0, 2)
