import logging
from PySide6 import QtWidgets, QtCore, QtGui
from qfluentwidgets import (
    BodyLabel,
    CardWidget,
    CheckBox,
    Dialog,
    LineEdit,
    MessageBox,
    PushButton,
    RadioButton,
    SmoothScrollArea,
    StrongBodyLabel,
    isDarkTheme,
)
from omni_trans_core.localization_manager import auto_register, loc_man, translate
from omni_trans_core import settings
from ..constants import LOG_PREFIX
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from omni_trans_core.core import CoreApp

logger = logging.getLogger(f"{LOG_PREFIX}_APP_UI.dialogs")

DIALOG_WIDTH = 660
DIALOG_HEIGHT = 740
NO_LANGUAGES_COLOR = "#ff9800"
LANGUAGE_GRID_COLUMNS = 2


@auto_register(
    ("", "windowTitle", "dialog.export.title"),
    ("name_label", "text", "dialog.export.group.name"),
    ("languages_label", "text", "dialog.export.group.languages"),
    ("options_label", "text", "dialog.export.group.options"),
    ("includeOriginalsCheck", "text", "dialog.export.check.include_originals"),
    ("includeOriginalsCheck", "toolTip", "dialog.export.check.include_originals.tooltip"),
    ("missing_translation_label", "text", "dialog.export.group.missing_translation"),
    ("leaveOriginalRadio", "text", "dialog.export.radio.leave_original"),
    ("skipKeyRadio", "text", "dialog.export.radio.skip_key"),
    ("stats_header", "text", "dialog.export.group.stats"),
)
class ExportSettingsDialog(Dialog):
    def __init__(self, main_window: "CoreApp", default_lore_name: str, parent=None):
        super().__init__(translate("dialog.export.title"), "", parent)
        self.main_window = main_window
        self.all_entries = (
            self.main_window.data_handler.data.get("entries", {})
            if self.main_window.data_handler.data
            else {})
        self.src_lang = settings.current_settings.get("selected_source_language", "")
        self.available_target_langs = settings.current_settings.get( "target_languages", [] )
        self.current_selected_target_lang = settings.current_settings.get( "selected_target_language", "" )
        self.lang_checkboxes = {}
        self.setFixedSize(DIALOG_WIDTH, DIALOG_HEIGHT)
        self._init_window_chrome()
        self._build_ui(default_lore_name)
        for checkbox in self.lang_checkboxes.values():
            checkbox.stateChanged.connect(self.update_stats)
        self.includeOriginalsCheck.stateChanged.connect(self.update_stats)
        self.leaveOriginalRadio.toggled.connect(self.update_stats)
        loc_man.language_changed.connect(self.update_stats)
        self.update_stats()

    def _init_window_chrome(self):
        """Keep the Fluent title bar so the dialog can be moved, drop the inline title."""
        self.titleBar.show()
        self.titleBar.raise_()
        # The stock title bar glyph is black and disappears on the dark background.
        self.titleBar.closeBtn.setNormalColor(
            QtGui.QColor("#ffffff" if isDarkTheme() else "#000000")
        )
        self.titleLabel.hide()
        self.contentLabel.hide()
        self.textLayout.setContentsMargins(0, 8, 0, 0)

    def _build_ui(self, default_lore_name: str):
        self._scroll_area = SmoothScrollArea(self)
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setHorizontalScrollBarPolicy(
            QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._scroll_area.setStyleSheet(
            "QScrollArea{border: none; background: transparent}"
        )
        self._content = QtWidgets.QWidget(self._scroll_area)
        self._content.setObjectName("exportSettingsContent")
        self._content.setStyleSheet(
            "#exportSettingsContent{background: transparent}"
        )
        self._content_layout = QtWidgets.QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(24, 8, 24, 16)
        self._content_layout.setSpacing(12)
        self._scroll_area.setWidget(self._content)
        self.textLayout.addWidget(self._scroll_area, 1)

        self._build_name_card(default_lore_name)
        self._build_languages_card()
        self._build_options_card()
        self._build_stats_card()
        self._content_layout.addStretch(1)

    def _create_card(self) -> tuple[CardWidget, QtWidgets.QVBoxLayout]:
        card = CardWidget(self._content)
        card_layout = QtWidgets.QVBoxLayout(card)
        card_layout.setContentsMargins(16, 12, 16, 12)
        card_layout.setSpacing(8)
        self._content_layout.addWidget(card)
        return card, card_layout

    def _build_name_card(self, default_lore_name: str):
        self.name_card, card_layout = self._create_card()
        self.name_label = StrongBodyLabel(self.name_card)
        self.loreNameEdit = LineEdit(self.name_card)
        self.loreNameEdit.setText(default_lore_name)
        card_layout.addWidget(self.name_label)
        card_layout.addWidget(self.loreNameEdit)

    def _build_languages_card(self):
        self.lang_card, card_layout = self._create_card()
        self.languages_label = StrongBodyLabel(self.lang_card)
        card_layout.addWidget(self.languages_label)

        if not self.available_target_langs:
            no_langs_label = BodyLabel(self.lang_card)
            no_langs_label.setWordWrap(True)
            no_langs_label.setStyleSheet(f"color: {NO_LANGUAGES_COLOR};")
            loc_man.register(no_langs_label, "text", "dialog.export.no_languages")
            card_layout.addWidget(no_langs_label)
            return

        select_buttons_layout = QtWidgets.QHBoxLayout()
        select_buttons_layout.setSpacing(8)
        self.select_all_button = PushButton(self.lang_card)
        self.deselect_all_button = PushButton(self.lang_card)
        loc_man.register(self.select_all_button, "text", "dialog.export.select_all")
        loc_man.register(self.deselect_all_button, "text", "dialog.export.deselect_all")
        self.select_all_button.clicked.connect(self.select_all_langs)
        self.deselect_all_button.clicked.connect(self.deselect_all_langs)
        select_buttons_layout.addWidget(self.select_all_button)
        select_buttons_layout.addWidget(self.deselect_all_button)
        select_buttons_layout.addStretch(1)
        card_layout.addLayout(select_buttons_layout)

        lang_widget_container = QtWidgets.QWidget(self.lang_card)
        lang_widget_container.setObjectName("languageGridContainer")
        lang_widget_container.setStyleSheet(
            "#languageGridContainer{background: transparent}"
        )
        self.lang_grid_layout = QtWidgets.QGridLayout(lang_widget_container)
        self.lang_grid_layout.setContentsMargins(0, 0, 0, 0)
        self.lang_grid_layout.setHorizontalSpacing(24)
        self.lang_grid_layout.setVerticalSpacing(8)

        sorted_langs = sorted(self.available_target_langs)
        for index, lang_name in enumerate(sorted_langs):
            checkbox = CheckBox(lang_widget_container)
            checkbox.setText(lang_name)
            if lang_name == self.current_selected_target_lang:
                checkbox.setChecked(True)
            self.lang_checkboxes[lang_name] = checkbox
            self.lang_grid_layout.addWidget(
                checkbox,
                index // LANGUAGE_GRID_COLUMNS,
                index % LANGUAGE_GRID_COLUMNS,
            )
        rows = (len(sorted_langs) + LANGUAGE_GRID_COLUMNS - 1) // LANGUAGE_GRID_COLUMNS
        self.lang_grid_layout.setRowStretch(rows, 1)
        card_layout.addWidget(lang_widget_container)

    def _build_options_card(self):
        self.options_card, card_layout = self._create_card()
        self.options_label = StrongBodyLabel(self.options_card)
        self.includeOriginalsCheck = CheckBox(self.options_card)
        self.includeOriginalsCheck.setChecked(True)
        self.missing_translation_label = BodyLabel(self.options_card)
        self.leaveOriginalRadio = RadioButton(self.options_card)
        self.leaveOriginalRadio.setChecked(True)
        self.skipKeyRadio = RadioButton(self.options_card)
        card_layout.addWidget(self.options_label)
        card_layout.addWidget(self.includeOriginalsCheck)
        card_layout.addWidget(self.missing_translation_label)
        card_layout.addWidget(self.leaveOriginalRadio)
        card_layout.addWidget(self.skipKeyRadio)

    def _build_stats_card(self):
        self.stats_card, card_layout = self._create_card()
        self.stats_header = StrongBodyLabel(self.stats_card)
        self.stats_label = BodyLabel(self.stats_card)
        self.stats_label.setWordWrap(True)
        card_layout.addWidget(self.stats_header)
        card_layout.addWidget(self.stats_label)

    def update_stats(self):
        self.stats_label.setText(translate("dialog.export.stats.calculating"))
        total_entries = len(self.all_entries)
        _, selected_languages, _, _ = self.get_export_settings()
        total_original_keys = sum(
            len(entry.get("key", [])) for entry in self.all_entries.values())
        if not selected_languages:
            stats_text = translate(
                "dialog.export.stats.no_languages_selected",
                num_entries=total_entries,
                num_keys=total_original_keys,)
            self.stats_label.setText(stats_text)
            return
        translations_found_per_lang = {lang: 0 for lang in selected_languages}
        for entry in self.all_entries.values():
            original_keys = entry.get("key", [])
            if not original_keys:
                continue
            for key_text in original_keys:
                for lang in selected_languages:
                    if self.main_window.cache_manager.get_from_cache( key_text, self.src_lang, lang ):
                        translations_found_per_lang[lang] += 1
        total_translations_found = sum(translations_found_per_lang.values())
        stats_text = translate(
            "dialog.export.stats.template",
            num_entries=total_entries,
            num_translations=total_translations_found,)
        warnings = []
        for lang, found_count in translations_found_per_lang.items():
            missing_count = total_original_keys - found_count
            if missing_count > 0:
                warnings.append(
                    translate(
                        "dialog.export.stats.warning_template",
                        num_missing=missing_count,
                        lang_name=lang,
                    )
                )
        if warnings:
            stats_text += (
                f"\n\n{translate('dialog.export.stats.warnings_header')}\n"
                + "\n".join(warnings))
        self.stats_label.setText(stats_text)

    def select_all_langs(self):
        for checkbox in self.lang_checkboxes.values():
            checkbox.setChecked(True)

    def deselect_all_langs(self):
        for checkbox in self.lang_checkboxes.values():
            checkbox.setChecked(False)

    def accept(self):
        self.accept_settings()

    def accept_settings(self):
        if self.lang_checkboxes and not any( cb.isChecked() for cb in self.lang_checkboxes.values() ):
            box = MessageBox(
                translate("dialog.export.prompt.no_languages_selected.title"),
                translate("dialog.export.prompt.no_languages_selected.text"),
                self,
            )
            if box.exec() != QtWidgets.QDialog.DialogCode.Accepted:
                return
        super().accept()

    def get_export_settings(self):
        lore_name = self.loreNameEdit.text().strip()
        selected_target_languages = [
            lang for lang, cb in self.lang_checkboxes.items() if cb.isChecked()]
        include_originals = self.includeOriginalsCheck.isChecked()
        missing_translation_rule = (
            "leave" if self.leaveOriginalRadio.isChecked() else "skip")
        return (
            lore_name,
            selected_target_languages,
            include_originals,
            missing_translation_rule,)
