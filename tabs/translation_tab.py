import logging
from PySide6 import QtWidgets, QtCore
from qfluentwidgets import HeaderCardWidget, MessageBox, SmoothScrollArea, TextEdit
from omni_trans_core.interfaces import (
    AbstractTab,
    TranslatableItem,
    IControlWidgetActions,
)
from omni_trans_core.ui.widgets import (
    RPMStatusWidget,
    GenerationParamsWidget,
    SourceLanguageWidget,
    TargetLanguageWidget,
    DataTableWidget,
    MultiConnectionTable,
    TranslationControlWidget,
)
from omni_trans_core import constants as const
from omni_trans_core import settings
from omni_trans_core.localization_manager import auto_register, translate
from ..constants import LOG_PREFIX
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from omni_trans_core.core import CoreApp
    from ..data_handler import LorebookDataHandler

logger = logging.getLogger(f'{LOG_PREFIX}_APP.translation_tab')

@auto_register(
    ("table_widget", "retranslate", None),
    ("content_display_group", "title", "tab.translation.group.full_content"),
)
class TranslationTab(AbstractTab, IControlWidgetActions):
    TAB_NAME = "Translation"
    translation_requested = QtCore.Signal(list, bool)
    generation_params_updated = QtCore.Signal(str, str, dict)
    data_availability_changed = QtCore.Signal(bool)

    def __init__(self, main_window: "CoreApp", data_handler: "LorebookDataHandler"):
        super().__init__(main_window)
        self.main_window = main_window
        self.data_handler = data_handler
        self.table_data = []
        self.data_availability_changed.emit(False)
        self.init_ui()
        self._connect_signals()
        self.connection_table.update_connections(restore_state=False)

    @property
    def tab_name(self) -> str:
        return translate("tab.translation.tab_name")
    
    def init_ui(self):
        translation_layout = QtWidgets.QVBoxLayout(self)
        translation_layout.setContentsMargins(16, 16, 16, 16)
        translation_layout.setSpacing(12)
        language_panel_layout = QtWidgets.QHBoxLayout()
        language_panel_layout.setContentsMargins(0, 0, 0, 0)
        language_panel_layout.setSpacing(12)
        self.source_lang_widget = SourceLanguageWidget()
        self.target_lang_widget = TargetLanguageWidget()
        language_panel_layout.addWidget(self.source_lang_widget, stretch=1)
        language_panel_layout.addWidget(self.target_lang_widget, stretch=1)
        translation_layout.addLayout(language_panel_layout)
        middle_v_splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
        middle_v_splitter.setOpaqueResize(False)
        top_middle_h_splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        top_middle_h_splitter.setOpaqueResize(False)
        self.table_widget = DataTableWidget()
        self.table = self.table_widget.table
        self.table_columns_config = [
            {
                "key": "uid",
                "header_key": "tab.translation.table.header.uid",
                "resize_mode": QtWidgets.QHeaderView.ResizeMode.ResizeToContents,
            },
            {
                "key": "key",
                "header_key": "tab.translation.table.header.key",
                "resize_mode": QtWidgets.QHeaderView.ResizeMode.ResizeToContents,
            },
            {
                "key": "translation",
                "header_key": "tab.translation.table.header.translation",
                "resize_mode": QtWidgets.QHeaderView.ResizeMode.ResizeToContents,
            },
            {
                "key": "content_preview",
                "header_key": "tab.translation.table.header.preview",
                "resize_mode": QtWidgets.QHeaderView.ResizeMode.Stretch,
            },
        ]
        self.table_widget.configure(self.table_columns_config)
        self.table.verticalHeader().setHighlightSections(False)
        self.table.horizontalHeader().setHighlightSections(False)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.setWordWrap(False)
        top_middle_h_splitter.addWidget(self.table_widget)
        right_panel_widget = QtWidgets.QWidget()
        right_panel_layout = QtWidgets.QVBoxLayout(right_panel_widget)
        right_panel_layout.setContentsMargins(0, 0, 0, 0)
        right_panel_layout.setSpacing(8)
        self.control_panel = TranslationControlWidget(actions_handler=self)
        right_panel_layout.addWidget(self.control_panel)
        self.connection_table = MultiConnectionTable(self.main_window)
        right_panel_layout.addWidget(self.connection_table, stretch=1)
        self.gen_params_widget = GenerationParamsWidget()
        right_panel_layout.addWidget(self.gen_params_widget)
        # Disable GenerationParamsWidget initially until user explicitly selects a model
        self.gen_params_widget.setEnabled(False)
        self.rpm_status_widget = RPMStatusWidget(self)
        right_panel_layout.addWidget(self.rpm_status_widget)
        right_panel_layout.addStretch()
        right_panel_scroll = SmoothScrollArea()
        right_panel_scroll.setWidgetResizable(True)
        right_panel_scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        right_panel_scroll.setHorizontalScrollBarPolicy(
            QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        right_panel_scroll.setWidget(right_panel_widget)
        top_middle_h_splitter.addWidget(right_panel_scroll)
        top_middle_h_splitter.setStretchFactor(0, 3)
        top_middle_h_splitter.setStretchFactor(1, 2)
        top_middle_h_splitter.setSizes([705, 470])
        middle_v_splitter.addWidget(top_middle_h_splitter)
        self.content_display_group = HeaderCardWidget()
        content_display_widget = QtWidgets.QWidget(self.content_display_group)
        content_display_layout = QtWidgets.QVBoxLayout(content_display_widget)
        content_display_layout.setContentsMargins(0, 0, 0, 0)
        self.full_content_display = TextEdit(content_display_widget)
        self.full_content_display.setReadOnly(True)
        content_display_layout.addWidget(self.full_content_display)
        self.content_display_group.viewLayout.addWidget(content_display_widget)
        middle_v_splitter.addWidget(self.content_display_group)
        translation_layout.addWidget(middle_v_splitter, stretch=1)

    def _show_warning(self, title: str, content: str):
        box = MessageBox(title, content, self)
        box.hideCancelButton()
        box.exec()

    def _show_info(self, title: str, content: str):
        box = MessageBox(title, content, self)
        box.hideCancelButton()
        box.exec()

    def _confirm(self, title: str, content: str) -> bool:
        box = MessageBox(title, content, self)
        return box.exec() == QtWidgets.QDialog.DialogCode.Accepted

    def _connect_signals(self):
        self.main_window.translation_manager.rpm_status_updated.connect(
            self.rpm_status_widget.update_status
        )
        self.source_lang_widget.language_changed.connect(self.on_source_language_change)
        self.target_lang_widget.language_changed.connect(
            self._on_target_language_changed
        )
        self.data_handler.entry_added.connect(self.populate_table_data)
        self.data_handler.entry_deleted.connect(self.populate_table_data)
        self.data_handler.entry_updated.connect(self.populate_table_data)
        self.connection_table.connections_changed.connect(
            self._on_connections_changed
        )
        self.connection_table.row_clicked.connect(
            self._on_connection_row_clicked
        )
        self.connection_table.model_changed.connect(
            self._on_connection_model_changed
        )
        self.gen_params_widget.params_changed.connect(self._on_gen_params_changed)
        self.table_widget.selection_changed.connect(self._on_table_selection_changed)
        self.control_panel.item_edited.connect(self._on_item_edited)

    @QtCore.Slot(dict)
    def _on_gen_params_changed(self, params: dict):
        active_conn_name = self.main_window.get_active_connection_name()
        if active_conn_name:
            model_name = settings.current_settings.get("active_model_for_connection", {}).get(active_conn_name, "")
            logger.debug(f"_on_gen_params_changed: conn={active_conn_name}, model={model_name}, temp={params.get('temperature')}, max_tokens={params.get('max_output_tokens')}")
            self.generation_params_updated.emit(active_conn_name, model_name, params)
        else:
            logger.debug("_on_gen_params_changed: no active_conn_name, params NOT emitted")

    def handle_model_capability_notice(self, model_id: str, capability: str):
        active_model_full_id = self.main_window.get_active_model_full_id()
        if active_model_full_id and active_model_full_id == model_id:
            self.gen_params_widget.show_capability_notice(capability)

    @QtCore.Slot(str)
    def on_source_language_change(self, lang_name: str):
        if self.main_window.translation_manager.active_translation_jobs > 0:
            self._show_warning(
                translate("tab.translation.dialog.operation_in_progress.title"),
                translate("tab.translation.dialog.cannot_change_source"),
            )
            self.source_lang_widget.update_language_combo()
            return
        logger.info(f"Source language changed to: {lang_name}")
        self.main_window.status_bar.showMessage(
            translate("tab.translation.status.source_changed", lang_name=lang_name)
        )
        if self.data_handler.data:
            self.populate_table_data()

    @QtCore.Slot(str)
    def _on_target_language_changed(self, lang_name: str):
        if self.main_window.translation_manager.active_translation_jobs > 0:
            self._show_warning(
                translate("tab.translation.dialog.operation_in_progress.title"),
                translate("tab.translation.dialog.cannot_change_target"),
            )
            self.target_lang_widget.update_language_combo()
            return
        logger.info(f"Target language changed to: {lang_name or 'None'}")
        self.control_panel.set_active_language(lang_name)

        hdr_text = f"Translated ({lang_name if lang_name else 'N/A'})"
        hdr_item = self.table.horizontalHeaderItem(2)
        if hdr_item:
            hdr_item.setText(hdr_text)

        self.full_content_display.clear()
        self.table.clearSelection()
        self.control_panel.clear_selection()
        if self.data_handler.data:
            self.populate_table_data()
        self.main_window.status_bar.showMessage(
            f"Target language: {lang_name if lang_name else 'None'}"
        )

    @QtCore.Slot(list)
    def _on_connections_changed(self, active_connections: list[tuple[str, str]]):
        """Handle change in selected connections."""
        self.main_window.translation_manager.set_active_connections(active_connections)
        self.gen_params_widget.setEnabled(self.connection_table.is_model_selected())

    @QtCore.Slot(str, str)
    def _on_connection_row_clicked(self, conn_name: str, model_name: str):
        """Update GenerationParamsWidget for clicked connection."""
        self.main_window.set_active_connection_name(conn_name)
        self.gen_params_widget.setEnabled(True)
        self.gen_params_widget.set_connection_type(conn_name, model_name)

    @QtCore.Slot(str, str)
    def _on_connection_model_changed(self, conn_name: str, new_model: str):
        """Handle model change for a connection."""
        # Save to settings
        if "active_model_for_connection" not in settings.current_settings:
            settings.current_settings["active_model_for_connection"] = {}
        settings.current_settings["active_model_for_connection"][conn_name] = new_model
        settings.save_settings()
        
        # Update active_connections in TranslationManager
        active_connections = self.main_window.translation_manager.active_connections
        if active_connections:
            updated_connections = [
                (cn, new_model if cn == conn_name else model)
                for cn, model in active_connections
            ]
            self.main_window.translation_manager.set_active_connections(updated_connections)
        
        # Update GenerationParamsWidget if this is the active connection
        if self.main_window.get_active_connection_name() == conn_name:
            self.gen_params_widget.set_connection_type(conn_name, new_model)
        
        logger.debug(f"Model for connection '{conn_name}' changed to '{new_model}'.")

    @QtCore.Slot()
    def on_data_loaded(self):
        self.populate_table_data()
        self.connection_table.update_connections(restore_state=True)

    def clear_view(self):
        self.table_data = []
        self.table.setRowCount(0)
        self.control_panel.clear_selection()
        self.full_content_display.clear()
        self.table.clearSelection()
        logger.debug("TranslationTab view cleared for new file.")

    def populate_table_data(self):
        sorted_entries = self.data_handler.get_sorted_lore_entries()
        if not sorted_entries:
            self.table_data.clear()
            self.table_widget.set_data([], unique_id_key="id")
            return
        new_table_data = []
        tgt_lang = self.target_lang_widget.combo.currentText()
        src_lang = self.source_lang_widget.combo.currentText()
        if not src_lang:
            self.table_data.clear()
            self.table_widget.set_data([], unique_id_key="id")
            return

        def get_preview(text: str) -> str:
            clean_text = text.replace("\n", " ")
            return (
                (clean_text[:147] + "...") if len(clean_text) > 150 else clean_text
            )

        for entry_id, entry_data in sorted_entries:
            uid = entry_data.get("uid")
            if uid is None:
                continue
            original_keys = entry_data.get("key", [])
            content = entry_data.get("content", "")
            if not isinstance(original_keys, list):
                continue

            if original_keys:
                for orig_key_text in original_keys:
                    orig_key_disp = str(orig_key_text).strip()
                    if not orig_key_disp:
                        continue
                    cached_trans = (
                        self.main_window.cache_manager.get_from_cache(
                            orig_key_disp, src_lang, tgt_lang
                        )
                        or ""
                    )
                    new_table_data.append(
                        {
                            "id": f"{uid}:{orig_key_disp}",
                            "uid": str(uid),
                            "key": orig_key_disp,
                            "translation": cached_trans,
                            "content": content,
                            "content_preview": get_preview(content),
                        }
                    )
            else:
                new_table_data.append(
                    {
                        "id": f"{uid}:",
                        "uid": str(uid),
                        "key": "",
                        "translation": "",
                        "content": content,
                        "content_preview": get_preview(content),
                    }
                )
        self.table_data = new_table_data
        self.data_availability_changed.emit(bool(self.table_data))
        self.table_widget.set_data(self.table_data, unique_id_key="id")

    @QtCore.Slot()
    def _on_table_selection_changed(self, selected_data: list[dict]):
        if not selected_data:
            self.control_panel.clear_selection()
            self.full_content_display.clear()
            return
        if self.main_window.translation_manager.active_translation_jobs > 0:
            self.table.clearSelection()
            return
        first_item = selected_data[0]
        item_id = first_item.get("id", "")
        orig_k = first_item.get("key", "")
        trans_k = first_item.get("translation", "")
        content_k = first_item.get("content", "")
        self.control_panel.set_data(item_id, orig_k, trans_k)
        self.full_content_display.setPlainText(content_k)

    @QtCore.Slot(str, str)
    def _on_item_edited(self, item_id: str, new_text: str):
        if self.main_window.translation_manager.active_translation_jobs > 0:
            self._show_warning(
                translate("tab.translation.dialog.operation_in_progress.title"),
                "Cannot save edits while translations are active.",
            )
            return
        try:
            uid, orig_k = item_id.split(":", 1)
        except ValueError:
            logger.error(f"Could not parse item_id '{item_id}' for editing.")
            return
        tgt_lang = self.target_lang_widget.combo.currentText()
        src_lang = self.source_lang_widget.combo.currentText()
        if not all([tgt_lang, src_lang]):
            self._show_warning(
                translate("manager.language_error.title"),
                translate("manager.language_error.text"),
            )
            return
        self.main_window.cache_manager.update_cache(
            orig_k, new_text, src_lang, tgt_lang
        )
        self.main_window.status_bar.showMessage(
            f"Applied edit for '{orig_k}' (UID {uid}).", 3000
        )
        for row_data in self.table_data:
            if row_data.get("id") == item_id:
                row_data["translation"] = new_text
                break
        self.table_widget.update_row_by_id(item_id, {"translation": new_text})

    def get_selected_items(self) -> list[TranslatableItem]:
        selected_rows_data = self.table_widget.get_selected_rows_data()
        if not selected_rows_data:
            return []
        items_to_translate = []
        for row_data in selected_rows_data:
            uid = row_data.get("uid")
            orig_k = row_data.get("key")
            trans_k = row_data.get("translation")
            content = row_data.get("content")
            dict_key = self.data_handler.find_entry_dict_key_by_uid(str(uid))
            entry_data = (
                self.data_handler.data["entries"].get(dict_key, {})
                if dict_key and self.data_handler.data
                else {}
            )
            item = TranslatableItem(
                id=row_data.get("id", ""),
                source_text=str(orig_k),
                context=str(content),
                original_data=entry_data,
                existing_translation=str(trans_k),
            )
            items_to_translate.append(item)
        return items_to_translate

    def get_all_items(self) -> list[TranslatableItem]:
        return self.data_handler.get_translatable_items()

    def handle_translation_request(
        self, items: list[TranslatableItem], force_regen: bool
    ):
        if not self.data_handler.data:
            self._show_info(
                translate("widget.control.error.no_data.title"),
                "Load or create a LORE-book first.",
            )
            return
        self.translation_requested.emit(items, force_regen)

    def handle_deletion_request(self, items: list[TranslatableItem]):
        if self.main_window.translation_manager.active_translation_jobs > 0:
            self._show_warning(
                translate("tab.translation.dialog.operation_in_progress.title"),
                "Cannot delete translations while other operations are active.",
            )
            return
        tgt_lang = self.target_lang_widget.combo.currentText()
        src_lang = self.source_lang_widget.combo.currentText()
        if not all([tgt_lang, src_lang]):
            self._show_warning(
                translate("manager.language_error.title"),
                translate("manager.language_error.text"),
            )
            return
        title = translate("tab.editor.dialog.confirm_delete.title")
        text = (
            f"Are you sure you want to delete {len(items)} translation(s) "
            f"for language '{tgt_lang}'?"
        )
        if not self._confirm(title, text):
            return
        deleted_count = 0
        deleted_ids = []
        for item in items:
            item_id = item["id"]
            deleted_ids.append(item_id)
            source_text = item["source_text"]
            self.main_window.cache_manager.update_cache(
                source_text, "", src_lang, tgt_lang
            )
            for row_data in self.table_data:
                if row_data.get("id") == item_id:
                    row_data["translation"] = ""
                    break
            self.table_widget.update_row_by_id(item_id, {"translation": ""})
            if self.control_panel.current_item_id == item_id:
                self.control_panel.update_item_display(item_id, "")
            deleted_count += 1
        if deleted_ids:
            self.table_widget.flash_row_by_id(
                deleted_ids, color=const.FLASH_DANGER_COLOR
            )
        if deleted_count > 0:
            self.main_window.status_bar.showMessage(
                f"Deleted {deleted_count} translation(s).", 5000
            )

    def show_info_message(self, title: str, text: str):
        self._show_info(title, text)

    @QtCore.Slot(dict)
    def update_item_display(self, update_data: dict):
        item_id = update_data.get("item_id")
        final_translation = update_data.get("final_translation", "")
        if not item_id:
            return
        self.table_widget.update_row_by_id(item_id, {"translation": final_translation})
        self.control_panel.update_item_display(item_id, final_translation)
        self.table_widget.scroll_to_row_by_id(item_id)

    def flash_items(self, item_ids: list[str]):
        for item_id in item_ids:
            self.table_widget.flash_row_by_id(item_id)

    @QtCore.Slot()
    def on_settings_changed(self):
        self.connection_table.update_connections(restore_state=False)
        self.source_lang_widget.update_language_combo()
        self.target_lang_widget.update_language_combo()
