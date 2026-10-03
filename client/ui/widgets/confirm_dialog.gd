class_name ConfirmDialog
extends Control
## Modal yes/no dialog over a dimmed backdrop, optionally listing a cost.
##   var dialog := ConfirmDialog.open(self, "Demolish", "Remove this farm?")
##   dialog.confirmed.connect(_on_demolish)
## Emits exactly one of `confirmed` / `cancelled`, then frees itself.

signal confirmed
signal cancelled

const SCENE := "res://ui/widgets/confirm_dialog.tscn"

## Free the dialog after it is answered. Turn off to reuse one instance.
@export var free_on_close := true

var _frame: PanelFrame
var _message: Label
var _cost: CostRow
var _confirm: Button
var _cancel: Button


func _init() -> void:
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	var scrim := ColorRect.new()
	scrim.color = UiColors.SCRIM
	add_child(scrim)
	scrim.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	var center := CenterContainer.new()
	add_child(center)
	center.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)

	_frame = PanelFrame.new()
	_frame.custom_minimum_size.x = 460
	_frame.close_requested.connect(_answer.bind(false))
	center.add_child(_frame)
	var column := VBoxContainer.new()
	column.add_theme_constant_override(&"separation", 16)
	_frame.add_content(column)
	_message = Label.new()
	_message.theme_type_variation = &"BodyInk"
	_message.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_message.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	column.add_child(_message)
	_cost = CostRow.new()
	_cost.alignment = BoxContainer.ALIGNMENT_CENTER
	_cost.visible = false
	column.add_child(_cost)
	var buttons := HBoxContainer.new()
	buttons.alignment = BoxContainer.ALIGNMENT_CENTER
	buttons.add_theme_constant_override(&"separation", 16)
	column.add_child(buttons)
	_cancel = Button.new()
	_cancel.custom_minimum_size = Vector2(150, 52)
	_cancel.pressed.connect(_answer.bind(false))
	buttons.add_child(_cancel)
	_confirm = Button.new()
	_confirm.theme_type_variation = &"ButtonPrimary"
	_confirm.custom_minimum_size = Vector2(150, 52)
	_confirm.pressed.connect(_answer.bind(true))
	buttons.add_child(_confirm)
	setup("Confirm", "")


func _ready() -> void:
	_confirm.grab_focus.call_deferred()


func setup(title: String, message: String, confirm_text := "Confirm", cancel_text := "Cancel") -> void:
	_frame.title = title
	_message.text = message
	_message.visible = not message.is_empty()
	_confirm.text = confirm_text
	_cancel.text = cancel_text


## Show what the action costs. Confirm is disabled while it is unaffordable.
func set_costs(costs: Dictionary, available: Dictionary = {}, duration_s := -1.0) -> void:
	_cost.set_costs(costs, available, duration_s)
	_cost.visible = true
	_confirm.disabled = not _cost.is_affordable()


## Style the confirm button red for destructive actions.
func set_destructive(destructive: bool) -> void:
	_confirm.theme_type_variation = &"ButtonDanger" if destructive else &"ButtonPrimary"


func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed(&"ui_cancel"):
		get_viewport().set_input_as_handled()
		_answer(false)


static func open(parent: Node, title: String, message: String, confirm_text := "Confirm", cancel_text := "Cancel") -> ConfirmDialog:
	var dialog: ConfirmDialog = (load(SCENE) as PackedScene).instantiate()
	dialog.setup(title, message, confirm_text, cancel_text)
	parent.add_child(dialog)
	return dialog


func _answer(accepted: bool) -> void:
	if accepted:
		confirmed.emit()
	else:
		cancelled.emit()
	if free_on_close:
		queue_free()
	else:
		hide()
