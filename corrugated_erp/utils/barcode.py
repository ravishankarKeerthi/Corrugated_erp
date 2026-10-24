"""Barcode helpers exposed to print formats (Jinja).

code128_svg  - Code 128-B barcode drawn as inline SVG (works with any handheld scanner,
               no external service or library needed).
qr_svg       - QR code as inline SVG data URI using pyqrcode (a Frappe dependency).
"""

import base64
import io
from html import escape

# Code 128 bar patterns (bar/space module widths) for values 0..106
_PATTERNS = [
	"212222", "222122", "222221", "121223", "121322", "131222", "122213", "122312", "132212", "221213",
	"221312", "231212", "112232", "122132", "122231", "113222", "123122", "123221", "223211", "221132",
	"221231", "213212", "223112", "312131", "311222", "321122", "321221", "312212", "322112", "322211",
	"212123", "212321", "232121", "111323", "131123", "131321", "112313", "132113", "132311", "211313",
	"231113", "231311", "112133", "112331", "132131", "113123", "113321", "133121", "313121", "211331",
	"231131", "213113", "213311", "213131", "311123", "311321", "331121", "312113", "312311", "332111",
	"314111", "221411", "431111", "111224", "111422", "121124", "121421", "141122", "141221", "112214",
	"112412", "122114", "122411", "142112", "142211", "241211", "221114", "413111", "241112", "134111",
	"111242", "121142", "121241", "114212", "124112", "124211", "411212", "421112", "421211", "212141",
	"214121", "412121", "111143", "111341", "131141", "114113", "114311", "411113", "411311", "113141",
	"114131", "311141", "411131", "211412", "211214", "211232", "2331112",
]
_START_B = 104
_STOP = 106


def code128_values(text):
	text = str(text or "")
	values = [_START_B]
	for ch in text:
		code = ord(ch)
		if code < 32 or code > 126:
			raise ValueError("Code128-B supports printable ASCII only")
		values.append(code - 32)
	checksum = values[0] + sum(i * v for i, v in enumerate(values[1:], start=1))
	values.append(checksum % 103)
	values.append(_STOP)
	return values


def code128_svg(text, height=50, module_width=1.6, show_text=True):
	"""Return an inline <svg> Code 128 barcode for the given text."""
	values = code128_values(text)
	x = 10 * module_width  # quiet zone
	bars = []
	for value in values:
		for i, width in enumerate(_PATTERNS[value]):
			w = int(width) * module_width
			if i % 2 == 0:
				bars.append('<rect x="{0:.2f}" y="0" width="{1:.2f}" height="{2}"/>'.format(x, w, height))
			x += w
	total = x + 10 * module_width
	label_h = 14 if show_text else 0
	label = (
		'<text x="{0:.1f}" y="{1}" font-family="monospace" font-size="12" text-anchor="middle">{2}</text>'.format(
			total / 2, height + 12, escape(str(text))
		)
		if show_text
		else ""
	)
	return (
		'<svg xmlns="http://www.w3.org/2000/svg" width="{0:.0f}" height="{1}" viewBox="0 0 {0:.2f} {1}">'
		'<rect width="100%" height="100%" fill="#fff"/><g fill="#000">{2}</g>{3}</svg>'
	).format(total, height + label_h, "".join(bars), label)


def qr_svg(text, scale=3):
	"""Return an <img> tag with a QR code (SVG data URI). Empty string if pyqrcode is missing."""
	try:
		import pyqrcode
	except ImportError:
		return ""
	buffer = io.BytesIO()
	pyqrcode.create(str(text or "")).svg(buffer, scale=scale, background="#fff")
	data = base64.b64encode(buffer.getvalue()).decode()
	return '<img src="data:image/svg+xml;base64,{0}" alt="{1}"/>'.format(data, escape(str(text)))
