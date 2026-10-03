class_name UiFormat
extends RefCounted
## Number and time formatting shared by every widget. Pure functions.

const _UNITS: Array[String] = ["K", "M", "B", "T"]


## Short form for HUD counters: 950 -> "950", 12431 -> "12.4K", 1250000 -> "1.2M".
## Truncates instead of rounding so the display never overstates what a player owns.
static func compact(value: int) -> String:
	if value < 0:
		return "-" + compact(-value)
	if value < 1000:
		return str(value)
	var unit := 0
	var divisor := 1000
	while unit < _UNITS.size() - 1 and value >= divisor * 1000:
		divisor *= 1000
		unit += 1
	@warning_ignore("integer_division")
	var whole := value / divisor
	@warning_ignore("integer_division")
	var tenth := (value % divisor) / (divisor / 10)
	if whole >= 100 or tenth == 0:
		return "%d%s" % [whole, _UNITS[unit]]
	return "%d.%d%s" % [whole, tenth, _UNITS[unit]]


## Exact value with thousands separators: 12431 -> "12,431".
static func exact(value: int) -> String:
	var digits := str(absi(value))
	var out := ""
	var count := 0
	for i in range(digits.length() - 1, -1, -1):
		if count > 0 and count % 3 == 0:
			out = "," + out
		out = digits[i] + out
		count += 1
	return "-" + out if value < 0 else out


## Clock form for running timers: 7985 -> "02:13:05", 93785 -> "1d 02:03:05".
## Rounds up so a timer reads 00:00:01 until it is really done.
static func duration(seconds: float) -> String:
	var total := maxi(ceili(seconds), 0)
	@warning_ignore("integer_division")
	var days := total / 86400
	@warning_ignore("integer_division")
	var hours := (total % 86400) / 3600
	@warning_ignore("integer_division")
	var minutes := (total % 3600) / 60
	var secs := total % 60
	if days > 0:
		return "%dd %02d:%02d:%02d" % [days, hours, minutes, secs]
	return "%02d:%02d:%02d" % [hours, minutes, secs]


## Compact form for costs and summaries, two largest units: "2h 13m", "45s", "1d 2h".
static func duration_short(seconds: float) -> String:
	var total := maxi(ceili(seconds), 0)
	@warning_ignore("integer_division")
	var parts: Array[int] = [total / 86400, (total % 86400) / 3600, (total % 3600) / 60, total % 60]
	var suffixes: Array[String] = ["d", "h", "m", "s"]
	for i in parts.size():
		if parts[i] == 0:
			continue
		var text := "%d%s" % [parts[i], suffixes[i]]
		if i + 1 < parts.size() and parts[i + 1] > 0:
			text += " %d%s" % [parts[i + 1], suffixes[i + 1]]
		return text
	return "0s"


## Fraction complete in 0..1 for a timer with `remaining` of `total` seconds left.
static func progress(remaining: float, total: float) -> float:
	if total <= 0.0:
		return 1.0
	return clampf(1.0 - remaining / total, 0.0, 1.0)
