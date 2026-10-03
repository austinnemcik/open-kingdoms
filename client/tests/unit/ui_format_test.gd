extends TestCase


func test_compact_small_values_are_exact() -> void:
	assert_eq(UiFormat.compact(0), "0")
	assert_eq(UiFormat.compact(950), "950")
	assert_eq(UiFormat.compact(999), "999")


func test_compact_thousands() -> void:
	assert_eq(UiFormat.compact(1000), "1K")
	assert_eq(UiFormat.compact(1200), "1.2K")
	assert_eq(UiFormat.compact(12431), "12.4K")
	assert_eq(UiFormat.compact(99999), "99.9K")
	assert_eq(UiFormat.compact(124500), "124K", "no decimal from 100 of a unit")


func test_compact_truncates_instead_of_rounding_up() -> void:
	assert_eq(UiFormat.compact(1999), "1.9K")
	assert_eq(UiFormat.compact(999999), "999K")


func test_compact_millions_and_beyond() -> void:
	assert_eq(UiFormat.compact(1000000), "1M")
	assert_eq(UiFormat.compact(1250000), "1.2M")
	assert_eq(UiFormat.compact(3400000000), "3.4B")
	assert_eq(UiFormat.compact(7100000000000), "7.1T")
	assert_eq(UiFormat.compact(5000000000000000), "5000T", "largest unit keeps counting")


func test_compact_negative() -> void:
	assert_eq(UiFormat.compact(-12431), "-12.4K")


func test_exact_groups_thousands() -> void:
	assert_eq(UiFormat.exact(0), "0")
	assert_eq(UiFormat.exact(999), "999")
	assert_eq(UiFormat.exact(1000), "1,000")
	assert_eq(UiFormat.exact(12431), "12,431")
	assert_eq(UiFormat.exact(1250000), "1,250,000")
	assert_eq(UiFormat.exact(-4200), "-4,200")


func test_duration_clock() -> void:
	assert_eq(UiFormat.duration(0), "00:00:00")
	assert_eq(UiFormat.duration(59), "00:00:59")
	assert_eq(UiFormat.duration(7985), "02:13:05")
	assert_eq(UiFormat.duration(86399), "23:59:59")
	assert_eq(UiFormat.duration(93785), "1d 02:03:05")


func test_duration_rounds_up_and_clamps() -> void:
	assert_eq(UiFormat.duration(0.2), "00:00:01", "still running until truly done")
	assert_eq(UiFormat.duration(-5), "00:00:00")


func test_duration_short() -> void:
	assert_eq(UiFormat.duration_short(0), "0s")
	assert_eq(UiFormat.duration_short(45), "45s")
	assert_eq(UiFormat.duration_short(95), "1m 35s")
	assert_eq(UiFormat.duration_short(300), "5m")
	assert_eq(UiFormat.duration_short(7985), "2h 13m")
	assert_eq(UiFormat.duration_short(7200), "2h")
	assert_eq(UiFormat.duration_short(93785), "1d 2h")


func test_progress() -> void:
	assert_eq(UiFormat.progress(50.0, 100.0), 0.5)
	assert_eq(UiFormat.progress(0.0, 100.0), 1.0)
	assert_eq(UiFormat.progress(150.0, 100.0), 0.0, "clamped")
	assert_eq(UiFormat.progress(0.0, 0.0), 1.0, "zero-length timer is complete")
