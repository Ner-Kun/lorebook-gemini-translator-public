import copy
import logging
from PySide6 import QtWidgets, QtCore, QtGui
from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    CheckBox,
    ComboBox,
    HeaderCardWidget,
    LineEdit,
    MessageBox,
    PrimaryPushButton,
    PushButton,
    SmoothScrollArea,
    StrongBodyLabel,
)
from omni_trans_core.interfaces import AbstractTab
from omni_trans_core.ui.base_widgets import ShakeLineEdit, FocusOutTextEdit
from omni_trans_core.ui.widgets import DataTableWidget
from omni_trans_core.ui.animations import UIAnimator
from omni_trans_core.utils import DebounceTimer
from omni_trans_core.localization_manager import auto_register, loc_man, translate
from ..constants import LOG_PREFIX
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from omni_trans_core.core import CoreApp
    from ..data_handler import LorebookDataHandler

logger = logging.getLogger(f'{LOG_PREFIX}_APP.editor_tab')

EDITOR_LOGIC_KEYS = (
    "tab.editor.logic.and_any",
    "tab.editor.logic.not_all",
    "tab.editor.logic.not_any",
    "tab.editor.logic.and_all",
)
EDITOR_STRATEGY_KEYS = (
    "tab.editor.strategy.normal",
    "tab.editor.strategy.constant",
    "tab.editor.strategy.vectorized",
)
EDITOR_POSITION_KEYS = (
    "tab.editor.position.before_character",
    "tab.editor.position.after_character",
    "tab.editor.position.before_extension",
    "tab.editor.position.after_extension",
    "tab.editor.position.before_authors_note",
    "tab.editor.position.after_authors_note",
    "tab.editor.position.system_directive",
    "tab.editor.position.persona_directive",
    "tab.editor.position.character_directive",
)
EDITOR_TRI_STATE_KEYS = (
    "tab.editor.tri_state.use_global",
    "tab.editor.tri_state.yes",
    "tab.editor.tri_state.no",
)

@auto_register(
    ("lore_entries_label", "text", "tab.editor.label.lore_entries"),
    ("editor_search_input", "placeholderText", "tab.editor.search.placeholder"),
    ("editor_add_btn", "text", "tab.editor.button.add"),
    ("editor_duplicate_btn", "text", "tab.editor.button.duplicate"),
    ("editor_delete_btn", "text", "tab.editor.button.delete"),
    ("table_widget", "retranslate", None),
    ("editor_save_status_label", "text", "tab.editor.status.select_entry"),
    ("basic_info_group", "title", "tab.editor.group.basic_info"),
    ("editor_widgets.enabled_check", "text", "tab.editor.check.entry_enabled"),
    ("comment_label", "text", "tab.editor.label.comment"),
    ("keys_label", "text", "tab.editor.label.primary_keywords"),
    ("keysecondary_label", "text", "tab.editor.label.secondary_keywords"),
    ("content_label", "text", "tab.editor.label.content"),
    ("activation_group", "title", "tab.editor.group.activation"),
    ("logic_label", "text", "tab.editor.label.logic"),
    ("strategy_label", "text", "tab.editor.label.strategy"),
    ("position_label", "text", "tab.editor.label.position"),
    ("order_label", "text", "tab.editor.label.order"),
    ("probability_label", "text", "tab.editor.label.trigger_percent"),
    ("editor_widgets.useProbability_check", "text", "tab.editor.check.use_probability"),
    ("editor_widgets.depth_edit", "placeholderText", "tab.editor.placeholder.depth"),
    ("scan_group", "title", "tab.editor.group.scanning"),
    ("scan_depth_label", "text", "tab.editor.label.scan_depth"),
    ("editor_widgets.scanDepth_edit", "placeholderText", "tab.editor.placeholder.global"),
    ("case_sensitive_label", "text", "tab.editor.label.case_sensitive"),
    ("whole_words_label", "text", "tab.editor.label.whole_words"),
    ("group_scoring_label", "text", "tab.editor.label.group_scoring"),
    ("advanced_group", "title", "tab.editor.group.advanced"),
    ("inclusion_group_label", "text", "tab.editor.label.inclusion_group"),
    ("editor_widgets.groupOverride_check", "text", "tab.editor.check.prioritize"),
    ("group_weight_label", "text", "tab.editor.label.group_weight"),
    ("sticky_label", "text", "tab.editor.label.sticky"),
    ("cooldown_label", "text", "tab.editor.label.cooldown"),
    ("delay_label", "text", "tab.editor.label.delay"),
    ("editor_widgets.addMemo_check", "text", "tab.editor.check.add_memo"),
    ("editor_widgets.preventRecursion_check", "text", "tab.editor.check.prevent_recursion"),
    ("editor_widgets.excludeRecursion_check", "text", "tab.editor.check.exclude_recursion"),
    ("editor_widgets.delayUntilRecursion_check", "text", "tab.editor.check.delay_until_recursion"),
    ("editor_widgets.delayRecursionLevel_edit", "placeholderText", "tab.editor.placeholder.level"),
    ("automation_id_label", "text", "tab.editor.label.automation_id"),
)
class EditorTab(AbstractTab):
    TAB_NAME = "Editor"
    search_term_changed = QtCore.Signal(str)

    def __init__(self, main_window: "CoreApp", data_handler: "LorebookDataHandler"):
        super().__init__(main_window)
        self.main_window = main_window
        self.data_handler = data_handler
        self.selected_editor_entry_id = None
        self.editor_active_entry_copy = None
        self.is_saving_from_editor = False
        self.editor_widgets = {}
        self.editor_logic_keys = EDITOR_LOGIC_KEYS
        self.editor_strategy_keys = EDITOR_STRATEGY_KEYS
        self.editor_position_keys = EDITOR_POSITION_KEYS
        self.editor_tri_state_keys = EDITOR_TRI_STATE_KEYS
        self._init_field_mapping()
        self.init_ui()
        self._connect_signals()
        loc_man.language_changed.connect(self.retranslate)
        self.editor_debounce_timer = DebounceTimer(
            self.editor_save_entry_changes, 1000, self
        )

    def _init_field_mapping(self):
        self.field_mapping = {
            'disable': ('enabled_check', 'checkbox_inverted'),
            'comment': ('comment_edit', 'line_edit'),
            'key': ('keys_edit', 'string_list'),
            'keysecondary': ('keysecondary_edit', 'string_list'),
            'content': ('content_edit', 'plain_text_edit'),
            'selectiveLogic': ('logic_combo', 'combo_index'),
            'position': ('position_combo', 'combo_index'),
            'order': ('order_edit', 'numeric_line_edit', 100),
            'depth': ('depth_edit', 'numeric_line_edit', None),
            'probability': ('probability_edit', 'numeric_line_edit', 100),
            'useProbability': ('useProbability_check', 'checkbox'),
            'scanDepth': ('scanDepth_edit', 'numeric_line_edit', None),
            'caseSensitive': ('caseSensitive_combo', 'tri_state_combo'),
            'matchWholeWords': ('matchWholeWords_combo', 'tri_state_combo'),
            'useGroupScoring': ('useGroupScoring_combo', 'tri_state_combo'),
            'group': ('group_edit', 'line_edit'),
            'groupOverride': ('groupOverride_check', 'checkbox'),
            'groupWeight': ('groupWeight_edit', 'numeric_line_edit', 100),
            'sticky': ('sticky_edit', 'numeric_line_edit', 0),
            'cooldown': ('cooldown_edit', 'numeric_line_edit', 0),
            'delay': ('delay_edit', 'numeric_line_edit', 0),
            'addMemo': ('addMemo_check', 'checkbox'),
            'preventRecursion': ('preventRecursion_check', 'checkbox'),
            'excludeRecursion': ('excludeRecursion_check', 'checkbox'),
            'automationId': ('automationId_edit', 'line_edit'),
        }

    def init_ui(self):
        editor_layout = QtWidgets.QHBoxLayout(self)
        editor_layout.setContentsMargins(16, 16, 16, 16)
        editor_layout.setSpacing(12)
        editor_splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        editor_splitter.setOpaqueResize(False)
        editor_layout.addWidget(editor_splitter)
        editor_left_panel = self._create_left_panel()
        editor_splitter.addWidget(editor_left_panel)
        editor_right_panel = self._create_right_panel()
        editor_splitter.addWidget(editor_right_panel)
        editor_splitter.setStretchFactor(0, 0)
        editor_splitter.setStretchFactor(1, 1)
        editor_splitter.setSizes([380, 800])

    def _create_left_panel(self):
        editor_left_panel = QtWidgets.QWidget()
        editor_left_layout = QtWidgets.QVBoxLayout(editor_left_panel)
        editor_left_layout.setContentsMargins(0, 0, 0, 0)
        editor_left_layout.setSpacing(8)
        editor_left_panel.setMinimumWidth(350)
        editor_left_panel.setMaximumWidth(550)
        self.lore_entries_label = StrongBodyLabel()
        editor_left_layout.addWidget(self.lore_entries_label)
        self.table_widget = DataTableWidget()
        self.editor_search_input = self.table_widget.search_input
        self.editor_entry_table = self.table_widget.table
        self.table_widget_columns_config = [
            {
                "key": "uid",
                "header_key": "tab.editor.table.header.uid",
                "resize_mode": QtWidgets.QHeaderView.ResizeMode.Interactive,
            },
            {
                "key": "keywords",
                "header_key": "tab.editor.table.header.keywords",
                "resize_mode": QtWidgets.QHeaderView.ResizeMode.Stretch,
            },
            {
                "key": "comment",
                "header_key": "tab.editor.table.header.comment",
                "resize_mode": QtWidgets.QHeaderView.ResizeMode.Stretch,
            },
        ]
        self.table_widget.configure(self.table_widget_columns_config)
        self.editor_entry_table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectRows
        )
        self.editor_entry_table.setEditTriggers(
            QtWidgets.QAbstractItemView.NoEditTriggers
        )
        self.editor_entry_table.setWordWrap(False)
        editor_left_layout.addWidget(self.table_widget)
        editor_button_layout = QtWidgets.QHBoxLayout()
        editor_button_layout.setContentsMargins(0, 0, 0, 0)
        editor_button_layout.setSpacing(8)
        self.editor_add_btn = PrimaryPushButton()
        self.editor_duplicate_btn = PushButton()
        self.editor_delete_btn = PushButton()
        editor_button_layout.addWidget(self.editor_add_btn)
        editor_button_layout.addWidget(self.editor_duplicate_btn)
        editor_button_layout.addWidget(self.editor_delete_btn)
        editor_left_layout.addLayout(editor_button_layout)
        return editor_left_panel

    def _create_group(self):
        card = HeaderCardWidget()
        card.viewLayout.setContentsMargins(16, 12, 16, 16)
        content = QtWidgets.QWidget(card)
        content_layout = QtWidgets.QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(10)
        card.viewLayout.addWidget(content)
        return card, content_layout

    @staticmethod
    def _constrain_combo(combo: ComboBox, min_width: int, max_width: int):
        combo.setMinimumWidth(min_width)
        combo.setMaximumWidth(max_width)

    @staticmethod
    def _constrain_numeric(edit: ShakeLineEdit):
        edit.setMinimumWidth(64)
        edit.setMaximumWidth(96)

    def _create_right_panel(self):
        scroll_area = SmoothScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(
            QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.editor_form_widget = QtWidgets.QWidget()
        self.editor_form_widget.setMinimumWidth(0)
        scroll_area.setWidget(self.editor_form_widget)
        editor_right_layout = QtWidgets.QVBoxLayout(self.editor_form_widget)
        editor_right_layout.setContentsMargins(0, 0, 8, 0)
        editor_right_layout.setSpacing(12)
        self.editor_form_widget.setEnabled(False)
        self.basic_info_group, basic_info_content = self._create_group()
        basic_info_layout = QtWidgets.QFormLayout()
        basic_info_layout.setContentsMargins(0, 0, 0, 0)
        basic_info_layout.setSpacing(8)
        self.editor_widgets["enabled_check"] = CheckBox()
        self.editor_widgets["comment_edit"] = LineEdit()
        self.editor_widgets["keys_edit"] = LineEdit()
        self.editor_widgets["keysecondary_edit"] = LineEdit()
        self.editor_widgets["content_edit"] = FocusOutTextEdit()
        self.editor_widgets["content_edit"].setAcceptRichText(False)
        self.editor_save_status_label = CaptionLabel()
        self.editor_save_status_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight)
        first_row_layout = QtWidgets.QHBoxLayout()
        first_row_layout.setContentsMargins(0, 0, 0, 0)
        first_row_layout.addWidget(self.editor_widgets["enabled_check"])
        first_row_layout.addStretch()
        first_row_layout.addWidget(self.editor_save_status_label)
        basic_info_layout.addRow(first_row_layout)
        self.comment_label = BodyLabel()
        self.keys_label = BodyLabel()
        self.keysecondary_label = BodyLabel()
        basic_info_layout.addRow(
            self.comment_label, self.editor_widgets["comment_edit"]
        )
        basic_info_layout.addRow(self.keys_label, self.editor_widgets["keys_edit"])
        basic_info_layout.addRow(
            self.keysecondary_label, self.editor_widgets["keysecondary_edit"]
        )
        basic_info_content.addLayout(basic_info_layout)
        editor_right_layout.addWidget(self.basic_info_group)
        self.content_label = BodyLabel()
        editor_right_layout.addWidget(self.content_label)
        editor_right_layout.addWidget(self.editor_widgets["content_edit"], stretch=1)
        self.activation_group, activation_content = self._create_group()
        activation_first_row = QtWidgets.QHBoxLayout()
        activation_first_row.setContentsMargins(0, 0, 0, 0)
        activation_first_row.setSpacing(8)
        self.editor_widgets["logic_combo"] = ComboBox()
        self._constrain_combo(self.editor_widgets["logic_combo"], 110, 240)
        self._populate_combo("logic_combo", self.editor_logic_keys)
        self.editor_widgets["strategy_combo"] = ComboBox()
        self._constrain_combo(self.editor_widgets["strategy_combo"], 120, 240)
        self._populate_combo("strategy_combo", self.editor_strategy_keys)
        self.logic_label = BodyLabel()
        self.strategy_label = BodyLabel()
        activation_first_row.addWidget(self.logic_label)
        activation_first_row.addWidget(self.editor_widgets["logic_combo"])
        activation_first_row.addWidget(self.strategy_label)
        activation_first_row.addWidget(self.editor_widgets["strategy_combo"])
        activation_first_row.addStretch()
        activation_content.addLayout(activation_first_row)
        activation_second_row = QtWidgets.QHBoxLayout()
        activation_second_row.setContentsMargins(0, 0, 0, 0)
        activation_second_row.setSpacing(8)
        self.editor_widgets["position_combo"] = ComboBox()
        self._constrain_combo(self.editor_widgets["position_combo"], 150, 320)
        self._populate_combo("position_combo", self.editor_position_keys)
        self.editor_widgets["order_edit"] = ShakeLineEdit()
        self.editor_widgets["order_edit"].setValidator(QtGui.QIntValidator())
        self._constrain_numeric(self.editor_widgets["order_edit"])
        self.editor_widgets["probability_edit"] = ShakeLineEdit()
        self.editor_widgets["probability_edit"].setValidator(QtGui.QIntValidator())
        self._constrain_numeric(self.editor_widgets["probability_edit"])
        self.editor_widgets["useProbability_check"] = CheckBox()
        self.editor_widgets["depth_edit"] = ShakeLineEdit()
        self.editor_widgets["depth_edit"].setValidator(QtGui.QIntValidator(0, 999))
        self._constrain_numeric(self.editor_widgets["depth_edit"])
        self.editor_widgets["depth_edit"].hide()
        self.position_label = BodyLabel()
        activation_second_row.addWidget(self.position_label)
        activation_second_row.addWidget(self.editor_widgets["position_combo"])
        activation_second_row.addWidget(self.editor_widgets["depth_edit"])
        activation_second_row.addStretch()
        activation_content.addLayout(activation_second_row)
        activation_third_row = QtWidgets.QHBoxLayout()
        activation_third_row.setContentsMargins(0, 0, 0, 0)
        activation_third_row.setSpacing(8)
        self.order_label = BodyLabel()
        self.probability_label = BodyLabel()
        activation_third_row.addWidget(self.order_label)
        activation_third_row.addWidget(self.editor_widgets["order_edit"])
        activation_third_row.addWidget(self.probability_label)
        activation_third_row.addWidget(self.editor_widgets["probability_edit"])
        activation_third_row.addWidget(self.editor_widgets["useProbability_check"])
        activation_third_row.addStretch()
        activation_content.addLayout(activation_third_row)
        editor_right_layout.addWidget(self.activation_group)
        self.scan_group, scan_content = self._create_group()
        scan_first_row = QtWidgets.QHBoxLayout()
        scan_first_row.setContentsMargins(0, 0, 0, 0)
        scan_first_row.setSpacing(8)
        self.editor_widgets["scanDepth_edit"] = ShakeLineEdit()
        self.editor_widgets["scanDepth_edit"].setValidator(QtGui.QIntValidator(0, 9999))
        self._constrain_numeric(self.editor_widgets["scanDepth_edit"])
        self.editor_widgets["caseSensitive_combo"] = ComboBox()
        self._constrain_combo(self.editor_widgets["caseSensitive_combo"], 110, 220)
        self._populate_combo("caseSensitive_combo", self.editor_tri_state_keys)
        self.scan_depth_label = BodyLabel()
        self.case_sensitive_label = BodyLabel()
        scan_first_row.addWidget(self.scan_depth_label)
        scan_first_row.addWidget(self.editor_widgets["scanDepth_edit"])
        scan_first_row.addWidget(self.case_sensitive_label)
        scan_first_row.addWidget(self.editor_widgets["caseSensitive_combo"])
        scan_first_row.addStretch()
        scan_content.addLayout(scan_first_row)
        scan_second_row = QtWidgets.QHBoxLayout()
        scan_second_row.setContentsMargins(0, 0, 0, 0)
        scan_second_row.setSpacing(8)
        self.editor_widgets["matchWholeWords_combo"] = ComboBox()
        self._constrain_combo(self.editor_widgets["matchWholeWords_combo"], 110, 220)
        self._populate_combo("matchWholeWords_combo", self.editor_tri_state_keys)
        self.whole_words_label = BodyLabel()
        scan_second_row.addWidget(self.whole_words_label)
        scan_second_row.addWidget(self.editor_widgets["matchWholeWords_combo"])
        scan_second_row.addStretch()
        scan_content.addLayout(scan_second_row)
        scan_third_row = QtWidgets.QHBoxLayout()
        scan_third_row.setContentsMargins(0, 0, 0, 0)
        scan_third_row.setSpacing(8)
        self.editor_widgets["useGroupScoring_combo"] = ComboBox()
        self._constrain_combo(self.editor_widgets["useGroupScoring_combo"], 110, 220)
        self._populate_combo("useGroupScoring_combo", self.editor_tri_state_keys)
        self.group_scoring_label = BodyLabel()
        scan_third_row.addWidget(self.group_scoring_label)
        scan_third_row.addWidget(self.editor_widgets["useGroupScoring_combo"])
        scan_third_row.addStretch()
        scan_content.addLayout(scan_third_row)
        editor_right_layout.addWidget(self.scan_group)
        self.advanced_group, advanced_content = self._create_group()
        advanced_layout = QtWidgets.QGridLayout()
        advanced_layout.setContentsMargins(0, 0, 0, 0)
        advanced_layout.setSpacing(8)
        advanced_layout.setColumnStretch(1, 1)
        group_layout = QtWidgets.QHBoxLayout()
        group_layout.setContentsMargins(0, 0, 0, 0)
        group_layout.setSpacing(8)
        self.editor_widgets["group_edit"] = LineEdit()
        self.editor_widgets["groupOverride_check"] = CheckBox()
        group_layout.addWidget(self.editor_widgets["group_edit"], 1)
        group_layout.addWidget(self.editor_widgets["groupOverride_check"])
        self.inclusion_group_label = BodyLabel()
        advanced_layout.addWidget(self.inclusion_group_label, 0, 0)
        advanced_layout.addLayout(group_layout, 0, 1, 1, 3)
        self.editor_widgets["groupWeight_edit"] = ShakeLineEdit()
        self.editor_widgets["groupWeight_edit"].setValidator(QtGui.QIntValidator())
        self._constrain_numeric(self.editor_widgets["groupWeight_edit"])
        self.editor_widgets["sticky_edit"] = ShakeLineEdit()
        self.editor_widgets["sticky_edit"].setValidator(QtGui.QIntValidator())
        self._constrain_numeric(self.editor_widgets["sticky_edit"])
        self.editor_widgets["cooldown_edit"] = ShakeLineEdit()
        self.editor_widgets["cooldown_edit"].setValidator(QtGui.QIntValidator())
        self._constrain_numeric(self.editor_widgets["cooldown_edit"])
        self.editor_widgets["delay_edit"] = ShakeLineEdit()
        self.editor_widgets["delay_edit"].setValidator(QtGui.QIntValidator())
        self._constrain_numeric(self.editor_widgets["delay_edit"])
        numeric_fields_layout = QtWidgets.QVBoxLayout()
        numeric_fields_layout.setContentsMargins(0, 0, 0, 0)
        numeric_fields_layout.setSpacing(8)
        self.group_weight_label = BodyLabel()
        self.sticky_label = BodyLabel()
        self.cooldown_label = BodyLabel()
        self.delay_label = BodyLabel()
        numeric_first_row = QtWidgets.QHBoxLayout()
        numeric_first_row.setContentsMargins(0, 0, 0, 0)
        numeric_first_row.setSpacing(8)
        numeric_first_row.addWidget(self.group_weight_label)
        numeric_first_row.addWidget(self.editor_widgets["groupWeight_edit"])
        numeric_first_row.addWidget(self.sticky_label)
        numeric_first_row.addWidget(self.editor_widgets["sticky_edit"])
        numeric_first_row.addStretch()
        numeric_second_row = QtWidgets.QHBoxLayout()
        numeric_second_row.setContentsMargins(0, 0, 0, 0)
        numeric_second_row.setSpacing(8)
        numeric_second_row.addWidget(self.cooldown_label)
        numeric_second_row.addWidget(self.editor_widgets["cooldown_edit"])
        numeric_second_row.addWidget(self.delay_label)
        numeric_second_row.addWidget(self.editor_widgets["delay_edit"])
        numeric_second_row.addStretch()
        numeric_fields_layout.addLayout(numeric_first_row)
        numeric_fields_layout.addLayout(numeric_second_row)
        advanced_layout.addLayout(numeric_fields_layout, 1, 0, 1, 4)
        separator = QtWidgets.QFrame()
        separator.setFrameShape(QtWidgets.QFrame.HLine)
        separator.setFrameShadow(QtWidgets.QFrame.Sunken)
        advanced_layout.addWidget(separator, 2, 0, 1, 4)
        self.editor_widgets["addMemo_check"] = CheckBox()
        self.editor_widgets["preventRecursion_check"] = CheckBox()
        self.editor_widgets["excludeRecursion_check"] = CheckBox()
        self.editor_widgets["delayUntilRecursion_check"] = CheckBox()
        self.editor_widgets["delayRecursionLevel_edit"] = ShakeLineEdit()
        self.editor_widgets["delayRecursionLevel_edit"].setValidator(
            QtGui.QIntValidator(1, 999)
        )
        self._constrain_numeric(self.editor_widgets["delayRecursionLevel_edit"])
        self.editor_widgets["delayRecursionLevel_edit"].setVisible(False)
        advanced_layout.addWidget(self.editor_widgets["addMemo_check"], 3, 0, 1, 2)
        advanced_layout.addWidget(
            self.editor_widgets["preventRecursion_check"], 4, 0, 1, 2
        )
        advanced_layout.addWidget(
            self.editor_widgets["excludeRecursion_check"], 5, 0, 1, 2
        )
        delay_recursion_layout = QtWidgets.QHBoxLayout()
        delay_recursion_layout.setContentsMargins(0, 0, 0, 0)
        delay_recursion_layout.setSpacing(8)
        delay_recursion_layout.addWidget(
            self.editor_widgets["delayUntilRecursion_check"]
        )
        delay_recursion_layout.addWidget(
            self.editor_widgets["delayRecursionLevel_edit"]
        )
        delay_recursion_layout.addStretch()
        advanced_layout.addLayout(delay_recursion_layout, 6, 0, 1, 4)
        self.editor_widgets["automationId_edit"] = LineEdit()
        self.automation_id_label = BodyLabel()
        advanced_layout.addWidget(self.automation_id_label, 7, 0)
        advanced_layout.addWidget(self.editor_widgets["automationId_edit"], 7, 1, 1, 3)
        advanced_content.addLayout(advanced_layout)
        editor_right_layout.addWidget(self.advanced_group)
        editor_right_layout.addStretch()
        for widget_name in (
            "comment_edit",
            "keys_edit",
            "keysecondary_edit",
            "group_edit",
            "automationId_edit",
        ):
            self.editor_widgets[widget_name].setMinimumWidth(0)
        for widget_name in (
            "enabled_check",
            "useProbability_check",
            "groupOverride_check",
            "addMemo_check",
            "preventRecursion_check",
            "excludeRecursion_check",
            "delayUntilRecursion_check",
        ):
            self.editor_widgets[widget_name].setMinimumWidth(0)
        return scroll_area

    def _populate_combo(self, widget_name: str, keys: tuple[str, ...]):
        combo = self.editor_widgets[widget_name]
        current_index = combo.currentIndex()
        current_data = combo.currentData()
        blocker = QtCore.QSignalBlocker(combo)
        combo.clear()
        for key in keys:
            combo.addItem(translate(key), userData=key)
        restored_index = combo.findData(current_data) if current_data is not None else -1
        if restored_index < 0 and 0 <= current_index < combo.count():
            restored_index = current_index
        combo.setCurrentIndex(restored_index if restored_index >= 0 else 0)
        del blocker

    def retranslate(self):
        self._populate_combo("logic_combo", self.editor_logic_keys)
        self._populate_combo("position_combo", self.editor_position_keys)
        self._populate_combo("strategy_combo", self.editor_strategy_keys)
        self._populate_combo("caseSensitive_combo", self.editor_tri_state_keys)
        self._populate_combo("matchWholeWords_combo", self.editor_tri_state_keys)
        self._populate_combo("useGroupScoring_combo", self.editor_tri_state_keys)

    def _show_warning(self, title: str, content: str):
        box = MessageBox(title, content, self)
        box.hideCancelButton()
        box.exec()

    def _confirm(self, title: str, content: str) -> bool:
        box = MessageBox(title, content, self)
        return box.exec() == QtWidgets.QDialog.DialogCode.Accepted

    def _load_strategy(self, entry_data):
        strategy_idx = 1 if entry_data.get('constant') else 2 if entry_data.get('vectorized') else 0
        self.editor_widgets['strategy_combo'].setCurrentIndex(strategy_idx)

    def _save_strategy(self, entry_data):
        strategy_idx = self.editor_widgets["strategy_combo"].currentIndex()
        entry_data["constant"] = strategy_idx == 1
        entry_data["vectorized"] = strategy_idx == 2

    def _load_delay_recursion(self, entry_data):
        delay_value = entry_data.get("delayUntilRecursion", False)
        is_delayed = bool(delay_value)
        self.editor_widgets["delayUntilRecursion_check"].setChecked(is_delayed)
        self.editor_widgets["delayRecursionLevel_edit"].setVisible(is_delayed)
        if isinstance(delay_value, int) and delay_value > 1:
            self.editor_widgets["delayRecursionLevel_edit"].setText(str(delay_value))
        else:
            self.editor_widgets["delayRecursionLevel_edit"].clear()

    def _save_delay_recursion(self, entry_data):
        if not self.editor_widgets["delayUntilRecursion_check"].isChecked():
            entry_data["delayUntilRecursion"] = False
        else:
            level_text = self.editor_widgets["delayRecursionLevel_edit"].text().strip()
            entry_data["delayUntilRecursion"] = (
                int(level_text) if level_text.isdigit() else True
            )

    def _connect_signals(self):
        self.editor_search_input.textChanged.connect(self.on_global_search_changed)
        self.table_widget.selection_changed.connect(self.editor_load_entry_details)
        self.editor_add_btn.clicked.connect(self.editor_add_entry)
        self.editor_duplicate_btn.clicked.connect(self.editor_duplicate_entry)
        self.editor_delete_btn.clicked.connect(self.editor_delete_entry)
        self.editor_widgets["position_combo"].currentIndexChanged.connect(
            self._update_insertion_depth_visibility
        )
        self.editor_widgets["delayUntilRecursion_check"].toggled.connect(
            self.toggle_recursion_level_field_animated
        )
        for widget_name in [
            "comment_edit",
            "keys_edit",
            "keysecondary_edit",
            "order_edit",
            "probability_edit",
            "scanDepth_edit",
            "group_edit",
            "groupWeight_edit",
            "sticky_edit",
            "cooldown_edit",
            "delay_edit",
            "delayRecursionLevel_edit",
            "automationId_edit",
            "depth_edit",
        ]:
            if widget_name in self.editor_widgets and isinstance(
                self.editor_widgets[widget_name], QtWidgets.QLineEdit
            ):
                self.editor_widgets[widget_name].textChanged.connect(
                    self._trigger_editor_debounce_save
                )
        self.editor_widgets["content_edit"].textChanged.connect(
            self._trigger_editor_debounce_save
        )
        for widget_name in [
            "logic_combo",
            "position_combo",
            "strategy_combo",
            "caseSensitive_combo",
            "matchWholeWords_combo",
            "useGroupScoring_combo",
        ]:
            if widget_name in self.editor_widgets and isinstance(
                self.editor_widgets[widget_name], ComboBox
            ):
                self.editor_widgets[widget_name].currentIndexChanged.connect(
                    self._trigger_editor_debounce_save
                )
        for widget_name in [
            "enabled_check",
            "useProbability_check",
            "groupOverride_check",
            "addMemo_check",
            "preventRecursion_check",
            "excludeRecursion_check",
            "delayUntilRecursion_check",
        ]:
            if widget_name in self.editor_widgets and isinstance(
                self.editor_widgets[widget_name], CheckBox
            ):
                self.editor_widgets[widget_name].toggled.connect(
                    self._trigger_editor_debounce_save
                )
        self.editor_widgets["content_edit"].focus_out.connect(self.on_before_save)
        self.data_handler.entry_deleted.connect(self.editor_refresh_listbox)
        self.data_handler.entry_updated.connect(self._on_entry_updated)

    @QtCore.Slot(bool)
    def toggle_recursion_level_field_animated(self, checked):
        widget = self.editor_widgets.get("delayRecursionLevel_edit")
        UIAnimator.toggle_visibility_animated(widget, show=checked)

    @QtCore.Slot(str, dict)
    def _on_entry_updated(self, entry_id: str, new_data: dict):
        update_dict = {
            "uid": str(new_data.get("uid", "N/A")),
            "keywords": ", ".join(new_data.get("key", [])),
            "comment": new_data.get("comment", ""),
        }
        self.table_widget.update_row_by_id(entry_id, update_dict)

    @QtCore.Slot()
    def on_data_loaded(self):
        self.editor_refresh_listbox()

    def clear_view(self):
        self.editor_clear_form()
        self.editor_form_widget.setEnabled(False)
        self.editor_refresh_listbox()

    @QtCore.Slot()
    def on_before_save(self):
        logger.debug("Forcing editor changes via debounce timer.")
        self.editor_debounce_timer.force_run()

    def editor_clear_form(self):
        for widget in self.editor_widgets.values():
            if isinstance(widget, ComboBox):
                widget.setCurrentIndex(0)
            elif isinstance(widget, QtWidgets.QLineEdit):
                widget.clear()
            elif isinstance(widget, QtWidgets.QTextEdit):
                widget.clear()
            elif isinstance(widget, QtWidgets.QCheckBox):
                widget.setChecked(False)
        self.selected_editor_entry_id = None
        self.editor_active_entry_copy = None

    def editor_refresh_listbox(self):
        selected_id_before_refresh = self.selected_editor_entry_id
        sorted_entries = self.data_handler.get_sorted_lore_entries()
        if not sorted_entries:
            self.table_widget.set_data([], unique_id_key="id")
            return
        table_data = []
        for entry_id, entry_data in sorted_entries:
            uid = str(entry_data.get("uid", "N/A"))
            comment = entry_data.get("comment", "")
            keywords = ", ".join(entry_data.get("key", []))
            full_searchable_text = (
                f"{uid} {keywords} {comment} {entry_data.get('content', '')}"
            )
            table_data.append(
                {
                    "id": entry_id,
                    "uid": uid,
                    "keywords": keywords,
                    "comment": comment,
                    "search_text": full_searchable_text,
                }
            )
        self.table_widget.set_data(table_data, unique_id_key="id")
        if (
            selected_id_before_refresh
            and selected_id_before_refresh in self.table_widget._id_to_row_map
        ):
            self._select_entry_in_list_by_id(selected_id_before_refresh)

    @QtCore.Slot(list)
    def editor_load_entry_details(self, selected_data: list[dict]):
        self.on_before_save()
        if not selected_data:
            self.editor_clear_form()
            self.editor_form_widget.setEnabled(False)
            return
        first_item = selected_data[0]
        entry_id = first_item.get("id")
        
        if (
            not self.data_handler.data
            or "entries" not in self.data_handler.data
            or entry_id not in self.data_handler.data["entries"]
        ):
            return
        self.selected_editor_entry_id = entry_id
        self.editor_active_entry_copy = copy.deepcopy(
            self.data_handler.data["entries"][entry_id]
        )
        entry = self.editor_active_entry_copy
        for widget in self.editor_widgets.values():
            widget.blockSignals(True)
        for key, (widget_name, type, *default) in self.field_mapping.items():
            widget = self.editor_widgets[widget_name]
            default_val = default[0] if default else None
            value = entry.get(key, default_val)
            if type == "line_edit":
                widget.setText(value)
            elif type == "numeric_line_edit":
                set_numeric_field(widget, value, default_val)
            elif type == "plain_text_edit":
                widget.setPlainText(value)
            elif type == "string_list":
                widget.setText(", ".join(value))
            elif type == "checkbox":
                widget.setChecked(bool(value))
            elif type == "checkbox_inverted":
                widget.setChecked(not bool(value))
            elif type == "combo_index":
                widget.setCurrentIndex(value)
            elif type == "tri_state_combo":
                set_tri_state_combo(widget, value)
        self._load_strategy(entry)
        self._load_delay_recursion(entry)
        for widget in self.editor_widgets.values():
            widget.blockSignals(False)
        current_pos_index = self.editor_widgets["position_combo"].currentIndex()
        self._update_insertion_depth_visibility(current_pos_index)
        self.editor_form_widget.setEnabled(True)
        UIAnimator.flash_status_label(self.editor_save_status_label, "<b>Loaded ✅</b>")
        logger.debug(f"Loaded entry '{entry_id}' fully into editor form.")

    @QtCore.Slot()
    def editor_save_entry_changes(self):
        if not self.selected_editor_entry_id or self.editor_active_entry_copy is None:
            return
        self.editor_debounce_timer.cancel()
        entry = self.editor_active_entry_copy
        for key, (widget_name, type, *default) in self.field_mapping.items():
            widget = self.editor_widgets[widget_name]
            default_val = default[0] if default else None
            if type == "line_edit":
                entry[key] = widget.text().strip()
            elif type == "numeric_line_edit":
                entry[key] = get_int_or_default(widget, default_val)
            elif type == "plain_text_edit":
                entry[key] = widget.toPlainText()
            elif type == "string_list":
                entry[key] = [k.strip() for k in widget.text().split(",") if k.strip()]
            elif type == "checkbox":
                entry[key] = widget.isChecked()
            elif type == "checkbox_inverted":
                entry[key] = not widget.isChecked()
            elif type == "combo_index":
                entry[key] = widget.currentIndex()
            elif type == "tri_state_combo":
                entry[key] = get_tri_state_value(widget)
        self._save_strategy(entry)
        self._save_delay_recursion(entry)
        keys_to_remove_if_none = [
            "scanDepth",
            "depth",
            "caseSensitive",
            "matchWholeWords",
            "useGroupScoring",
        ]
        for key in keys_to_remove_if_none:
            if entry.get(key) is None and key in entry:
                del entry[key]
        self.data_handler.update_entry(
            self.selected_editor_entry_id, self.editor_active_entry_copy
        )
        UIAnimator.flash_status_label(
            self.editor_save_status_label, "<b>Applied ✅</b>"
        )

    @QtCore.Slot()
    def editor_add_entry(self):
        if not self.data_handler.data:
            self._show_warning(
                translate("tab.editor.dialog.action_failed.title"),
                translate("tab.editor.dialog.action_failed.no_lorebook_loaded"),
            )
            return
        new_entry_id = self.data_handler.add_new_entry()
        if new_entry_id:
            self.editor_refresh_listbox()
            self._select_entry_in_list_by_id(new_entry_id)
            selected_data = self.table_widget.get_selected_rows_data()
            self.editor_load_entry_details(selected_data)

    @QtCore.Slot()
    def editor_duplicate_entry(self):
        if not self.selected_editor_entry_id:
            self._show_warning(
                translate("tab.editor.dialog.action_failed.title"),
                translate(
                    "tab.editor.dialog.action_failed.no_entry_selected_duplicate"),
            )
            return
        self.on_before_save()
        new_entry_id = self.data_handler.duplicate_entry(self.selected_editor_entry_id)
        if new_entry_id:
            self.editor_refresh_listbox()
            self._select_entry_in_list_by_id(new_entry_id)
            selected_data = self.table_widget.get_selected_rows_data()
            self.editor_load_entry_details(selected_data)

    @QtCore.Slot()
    def editor_delete_entry(self):
        if not self.selected_editor_entry_id:
            self._show_warning(
                translate("tab.editor.dialog.action_failed.title"),
                translate("tab.editor.dialog.action_failed.no_entry_selected_delete"),
            )
            return
        self.on_before_save()
        entry_name = self.data_handler.data["entries"][
            self.selected_editor_entry_id
        ].get("comment", self.selected_editor_entry_id)
        title = translate("tab.editor.dialog.confirm_delete.title")
        text = translate(
            "tab.editor.dialog.confirm_delete.text", entry_name=str(entry_name)
        )
        if not self._confirm(title, text):
            return
        row_to_reselect = self.editor_entry_table.currentRow()
        self.data_handler.delete_entry(self.selected_editor_entry_id)
        self.editor_clear_form()
        self.editor_form_widget.setEnabled(False)
        new_row_count = self.editor_entry_table.rowCount()
        if new_row_count > 0:
            index_to_select = min(row_to_reselect, new_row_count - 1)
            self.editor_entry_table.setCurrentCell(index_to_select, 0)

    @QtCore.Slot(str)
    def on_global_search_changed(self, text):
        self.search_term_changed.emit(text)

    def _select_entry_in_list_by_id(self, entry_id_to_select):
        row_index = self.table_widget._id_to_row_map.get(entry_id_to_select)
        if row_index is not None:
            self.editor_entry_table.blockSignals(True)
            self.editor_entry_table.selectRow(row_index)
            self.editor_entry_table.blockSignals(False)
            item = self.editor_entry_table.item(row_index, 0)
            if item:
                self.editor_entry_table.scrollToItem(
                    item, QtWidgets.QAbstractItemView.ScrollHint.PositionAtCenter
                )

    @QtCore.Slot(int)
    def _update_insertion_depth_visibility(self, index):
        widget = self.editor_widgets.get('depth_edit')
        is_visible = index in [6, 7, 8]
        if widget.isVisible() != is_visible:
            UIAnimator.toggle_visibility_animated(widget, show=is_visible)

    @QtCore.Slot()
    def _trigger_editor_debounce_save(self):
        if self.selected_editor_entry_id is not None:
            UIAnimator.flash_status_label(
                self.editor_save_status_label,
                "⚠️ <i>Changes detected...</i>",
                color="#f1fa8c",
                duration_ms=800,
            )
            self.editor_debounce_timer.trigger()

def get_int_or_default(widget, default_val):
    text = widget.text().strip()
    return int(text) if text.isdigit() else default_val

def set_numeric_field(widget, value, default=0):
    widget.setText(str(value) if value is not None and value != default else "")

def get_tri_state_value(widget):
    idx = widget.currentIndex()
    return None if idx == 0 else idx == 1

def set_tri_state_combo(widget, value):
    if value is None:
        widget.setCurrentIndex(0)
    else:
        widget.setCurrentIndex(1) if value else widget.setCurrentIndex(2)
