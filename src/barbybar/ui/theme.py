from __future__ import annotations


def _hex_to_rgb(color: str) -> tuple[int, int, int]:
    value = color.lstrip("#")
    if len(value) == 3:
        value = "".join(char * 2 for char in value)
    if len(value) != 6:
        raise ValueError(f"Unsupported hex color: {color}")
    return tuple(int(value[index : index + 2], 16) for index in (0, 2, 4))


def rgba(color: str, alpha: int) -> str:
    red, green, blue = _hex_to_rgb(color)
    safe_alpha = max(0, min(alpha, 255))
    return f"rgba({red}, {green}, {blue}, {safe_alpha})"


class AppTheme:
    bg = "#e8edf2"
    bg_soft = "#f5f7fa"
    surface = "#ffffff"
    surface_soft = "#f3f6f8"
    surface_muted = "#e6ebf0"
    surface_elevated = "#ffffff"
    canvas = "#f8fafc"
    canvas_gridless = "#f4f7fa"
    border = "#d3dbe3"
    border_strong = "#aab7c4"
    border_focus = "#1d4ed8"
    border_soft = "#e3e9ef"
    text = "#17212b"
    text_muted = "#5f6d7a"
    text_faint = "#8793a0"
    text_inverse = "#ffffff"
    text_disabled = "#a6adb4"
    primary = "#1f4f7a"
    primary_hover = "#173d61"
    primary_soft = "#dbe8f3"
    primary_tint = "#eef6fc"
    focus = border_focus
    hover = surface_elevated
    pressed = surface_muted
    checked = primary_soft
    checked_border = primary
    selected = "#e7f1fb"
    selected_border = primary
    disabled = "#edf0f2"
    disabled_border = "#d8dde2"
    info = "#2d628f"
    success = "#386854"
    success_soft = "#e5f0ea"
    long = "#8f4342"
    long_soft = "#f7e6e4"
    short = "#386854"
    short_soft = "#e5f0ea"
    close = "#52606d"
    close_soft = "#edf1f5"
    reverse = "#6d5dd3"
    reverse_soft = "#ece9ff"
    numeric = "#263445"
    pnl_positive = long
    pnl_negative = short
    active_mode = "#1d4ed8"
    active_mode_soft = "#dbeafe"
    active_mode_border = "#93c5fd"
    focus_soft = "#e4effb"
    warning = "#8f6229"
    warning_soft = "#f7eddc"
    danger = "#a84336"
    danger_soft = "#f8e3e0"
    accent = "#f0c36b"
    accent_soft = "#fff3d6"
    table_header = "#edf2f6"
    table_row_alt = "#f7fafc"
    table_selected = primary_tint
    radius_sm = 6
    radius_md = 8
    radius_lg = 10
    radius_xl = 12
    radius = radius_lg
    space_xs = 4
    space_sm = 8
    space_md = 12
    space_lg = 16
    space_xl = 20
    control_height_sm = 28
    control_height_md = 32
    control_height_lg = 36
    toolbar_strip_height = 34
    toolbar_button_height = 30
    toolbar_icon_button_size = 28
    toolbar_vertical_margin = 3
    toolbar_button_radius = 6
    toolbar_action_width_sm = 50
    toolbar_action_width_md = 64
    toolbar_action_width_lg = 76
    status_strip_height = 32
    status_button_height = 26
    status_button_width_md = 64
    status_button_width_lg = 78
    sidebar_input_width_sm = 58
    sidebar_input_width_md = 82
    flat_group_gap = 8
    sidebar_compact_width = 288
    sidebar_width = sidebar_compact_width
    chart_axis = "#b6c0ca"
    chart_preview = "#4f5d6b"
    chart_measure = "#255f86"
    chart_marker = "#d7dee6"
    chart_label = "#7e8b97"
    chart_label_soft = "#9aa6b2"
    chart_session_end = "#82909e"
    chart_average = "#5f6b7a"
    chart_entry_long = "#2979ff"
    chart_entry_short = "#ff9f1c"
    chart_stop_loss = "#1f8b24"
    chart_take_profit = "#d84a4a"
    chart_trade_win = "#d84a4a"
    chart_trade_loss = "#1f8b24"
    chart_trade_flat = "#5f6b7a"
    chart_trade_exit = "#fff3bf"
    chart_anchor = "#ffd166"
    chart_anchor_idle = "#5f6b7a"
    chart_channel_guide = "#f5b700"
    chart_reverse = "#7a43b6"


def app_stylesheet() -> str:
    return f"""
QMainWindow, QDialog {{
    background: {AppTheme.bg};
    color: {AppTheme.text};
    font-size: 12px;
    font-family: "Segoe UI Variable Text", "Microsoft YaHei UI";
}}
QWidget#appRoot,
QWidget#chartWorkspace,
QWidget#rightPanel,
QWidget#settingsContent,
QWidget#topNavBarContainer {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {AppTheme.bg_soft}, stop:1 {AppTheme.bg});
}}
QWidget#topNavBar,
QWidget#replayControlBar,
QWidget[dialogCard='true'],
QWidget#busyCard,
QWidget[card='true'],
QGroupBox,
QListWidget,
QWidget#settingsSidebar {{
    background: {AppTheme.surface};
    border: 1px solid {AppTheme.border};
    border-radius: {AppTheme.radius_lg}px;
}}
QWidget#topNavBar,
QWidget#replayControlBar {{
    background: {rgba(AppTheme.surface_elevated, 188)};
    border-radius: {AppTheme.radius_sm}px;
}}
QWidget#replayPrimaryActions {{
    background: {rgba(AppTheme.primary_tint, 145)};
    border: 1px solid {rgba(AppTheme.primary, 80)};
    border-radius: {AppTheme.radius_sm}px;
}}
QWidget#replaySecondaryActions {{
    background: transparent;
    border: none;
}}
QWidget#workspaceTools,
QWidget#workspaceActions,
QWidget#workspaceManagementActions,
QWidget#workspaceDiagnosticsActions,
QWidget#replayUtilityActions,
QWidget#replayStatusGroup,
QWidget#rightSidebarTabs,
QWidget#positionSummaryCard,
QWidget#trainingSummaryCard {{
    background: transparent;
    border: none;
}}
QWidget[toolbarGroup='true'] {{
    background: transparent;
    border: none;
    border-right: 1px solid {rgba(AppTheme.border, 170)};
    border-radius: 0px;
}}
QWidget[segmented='true'] {{
    background: {rgba(AppTheme.surface_soft, 228)};
    border: 1px solid {AppTheme.border};
    border-radius: {AppTheme.radius_sm}px;
}}
QWidget[card='true'] {{
    background: {rgba(AppTheme.surface_elevated, 112)};
    border: 1px solid {rgba(AppTheme.border, 82)};
    border-radius: {AppTheme.radius_sm}px;
}}
QWidget#directTradeSection[priority='primary'] {{
    background: {AppTheme.focus_soft};
    border: 1px solid {rgba(AppTheme.primary, 72)};
}}
QWidget#limitTradeSection[priority='secondary'] {{
    background: {rgba(AppTheme.surface_soft, 136)};
    border: 1px solid {rgba(AppTheme.border, 74)};
}}
ChartWidget[card='true'] {{
    background: {AppTheme.canvas};
    border: 1px solid {rgba(AppTheme.border, 72)};
    border-radius: 6px;
}}
QGroupBox,
QGroupBox[sidebarSection='true'] {{
    background: {rgba(AppTheme.surface_elevated, 92)};
    margin-top: 8px;
}}
QGroupBox#quickTradeBox {{
    background: {rgba(AppTheme.focus_soft, 128)};
    border-color: {rgba(AppTheme.primary, 92)};
}}
QGroupBox#orderToolsBox,
QGroupBox#displayBox,
QGroupBox#sessionUtilityBox {{
    background: {rgba(AppTheme.surface_elevated, 72)};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
    color: {AppTheme.text_faint};
    font-weight: 800;
    letter-spacing: 0.3px;
}}
QGroupBox#quickTradeBox::title {{
    color: {AppTheme.primary};
}}
QWidget#settingsSidebar {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {AppTheme.surface_elevated}, stop:1 {AppTheme.surface_soft});
}}
QLabel[role='appTitle'] {{
    color: {AppTheme.text};
    font-size: 16px;
    font-weight: 800;
}}
QLabel[role='toolbarGroupTitle'] {{
    color: {AppTheme.text_faint};
    font-size: 8px;
    font-weight: 700;
    letter-spacing: 0.3px;
    padding: 0px;
}}
QLabel[role='caseTitle'] {{
    color: {AppTheme.text};
    font-size: 12px;
    font-weight: 900;
}}
QLabel[role='caseMeta'],
QLabel[role='toolbarHint'] {{
    color: {AppTheme.text_faint};
    font-size: 10px;
    font-weight: 700;
}}
QLabel[role='caseSaveState'] {{
    background: {AppTheme.surface_soft};
    border: 1px solid {AppTheme.border_soft};
    border-radius: {AppTheme.radius_sm}px;
    color: {AppTheme.text_muted};
    padding: 1px 6px;
    font-size: 10px;
    font-weight: 800;
}}
QLabel[role='caseSaveState'][state='saved'] {{
    background: {AppTheme.success_soft};
    border-color: {rgba(AppTheme.success, 88)};
    color: {AppTheme.success};
}}
QLabel[role='caseSaveState'][state='dirty'] {{
    background: {AppTheme.warning_soft};
    border-color: {rgba(AppTheme.warning, 90)};
    color: {AppTheme.warning};
}}
QLabel[role='caseSaveState'][state='saving'] {{
    background: {AppTheme.active_mode_soft};
    border-color: {AppTheme.active_mode_border};
    color: {AppTheme.active_mode};
}}
QLabel[role='sidebarCardTitle'] {{
    color: {AppTheme.text};
    font-size: 11px;
    font-weight: 800;
}}
QLabel[role='sidebarCardHint'] {{
    color: {AppTheme.text_faint};
    font-size: 10px;
}}
QLabel[role='sectionHint'],
QLabel[role='muted'],
QLabel[role='statusMuted'] {{
    color: {AppTheme.text_muted};
}}
QLabel[role='sectionChip'] {{
    background: transparent;
    border: none;
    color: {AppTheme.text_faint};
    font-weight: 800;
    padding: 2px 0px 4px 0px;
    letter-spacing: 0.5px;
}}
QLabel[role='statusReadout'] {{
    background: transparent;
    border: none;
    border-radius: 0px;
    color: {AppTheme.text_muted};
    padding: 0px;
    font-weight: 700;
}}
QLabel[role='numericReadout'] {{
    color: {AppTheme.numeric};
    font-weight: 800;
}}
QLabel[role='pnlPositive'] {{
    color: {AppTheme.pnl_positive};
    font-weight: 800;
}}
QLabel[role='pnlNegative'] {{
    color: {AppTheme.pnl_negative};
    font-weight: 800;
}}
QLabel[role='positionReadout'] {{
    background: {rgba(AppTheme.surface_elevated, 108)};
    border: 1px solid {rgba(AppTheme.border, 168)};
    border-radius: {AppTheme.radius_sm}px;
    color: {AppTheme.text};
    padding: 8px 10px;
    font-weight: 700;
}}
QLabel[role='positionReadout'][state='flat'] {{
    background: {rgba(AppTheme.surface_elevated, 108)};
    border-color: {rgba(AppTheme.border, 168)};
    color: {AppTheme.text_muted};
}}
QLabel[role='positionReadout'][state='long'] {{
    background: {rgba(AppTheme.long_soft, 210)};
    border-color: {rgba(AppTheme.long, 120)};
    color: {AppTheme.long};
}}
QLabel[role='positionReadout'][state='short'] {{
    background: {rgba(AppTheme.short_soft, 210)};
    border-color: {rgba(AppTheme.short, 120)};
    color: {AppTheme.short};
}}
QLabel[role='positionReadout'][state='completed'] {{
    background: {rgba(AppTheme.success_soft, 224)};
    border-color: {rgba(AppTheme.success, 126)};
    color: {AppTheme.success};
}}
QLabel[role='trainingStats'] {{
    color: {AppTheme.text_muted};
    padding: 1px 1px 0px 1px;
}}
QLabel[role='statsHeadline'] {{
    color: {AppTheme.primary};
    font-size: 12px;
    font-weight: 800;
}}
QLabel[role='statsMeta'] {{
    color: {AppTheme.text_muted};
    font-size: 11px;
}}
QLabel[role='dialogEyebrow'] {{
    color: {AppTheme.text_faint};
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.4px;
}}
QLabel[role='dialogHeading'] {{
    color: {AppTheme.text};
    font-size: 18px;
    font-weight: 800;
}}
QLabel[role='dialogSummary'] {{
    color: {AppTheme.text_muted};
    font-size: 13px;
}}
QLabel[role='dialogSectionTitle'] {{
    color: {AppTheme.primary};
    font-size: 12px;
    font-weight: 800;
}}
QLabel[role='dialogStatus'] {{
    color: {AppTheme.text_muted};
    font-size: 12px;
}}
QLabel[role='errorBanner'] {{
    color: {AppTheme.danger};
    background: {AppTheme.danger_soft};
    border: 1px solid #efc4bc;
    border-radius: {AppTheme.radius_sm}px;
    padding: 8px 10px;
}}
QPushButton {{
    background: {AppTheme.surface_soft};
    border: 1px solid {AppTheme.border_strong};
    border-radius: {AppTheme.radius_sm}px;
    color: {AppTheme.text};
    padding: 6px 12px;
    min-height: 24px;
}}
QPushButton:hover {{
    background: {AppTheme.surface_elevated};
    border-color: {AppTheme.border_strong};
}}
QPushButton:pressed {{
    background: {AppTheme.pressed};
}}
QPushButton:focus {{
    border-color: {AppTheme.focus};
}}
QPushButton:checked {{
    background: {AppTheme.checked};
    border-color: {AppTheme.checked_border};
    color: #153e91;
    font-weight: 700;
}}
QPushButton:disabled {{
    background: {AppTheme.disabled};
    border-color: {AppTheme.disabled_border};
    color: {AppTheme.text_disabled};
}}
QPushButton[role='toolbar'] {{
    background: transparent;
    border-color: transparent;
    border-radius: {AppTheme.toolbar_button_radius}px;
    color: {AppTheme.text_muted};
    font-weight: 700;
    padding: 0px 8px;
    min-height: {AppTheme.toolbar_button_height}px;
}}
QPushButton[role='toolbar']:hover {{
    background: {rgba(AppTheme.hover, 220)};
    border-color: {rgba(AppTheme.border, 180)};
    color: {AppTheme.text};
}}
QPushButton[role='toolbar']:checked {{
    background: {AppTheme.checked};
    border-color: {AppTheme.checked_border};
    color: #153e91;
    font-weight: 800;
}}
QPushButton[role='toolbar']:disabled {{
    background: transparent;
    border-color: transparent;
    color: {AppTheme.text_disabled};
}}
QPushButton[role='toolbar'][tone='workspace'] {{
    color: {AppTheme.text};
    font-weight: 800;
}}
QPushButton[role='toolbar'][tone='workspace']:hover {{
    border-color: {rgba(AppTheme.border, 210)};
}}
QPushButton[role='toolbar'][tone='diagnostic'] {{
    color: {AppTheme.text_faint};
    font-weight: 700;
}}
QPushButton[role='toolbar'][tone='diagnostic']:hover {{
    color: {AppTheme.text_muted};
    border-color: {rgba(AppTheme.border, 136)};
}}
QPushButton[role='toolbar'][tone='diagnostic']:checked {{
    color: {AppTheme.primary};
}}
QPushButton[role='timeframe'] {{
    background: transparent;
    border: 1px solid transparent;
    border-radius: {AppTheme.toolbar_button_radius}px;
    color: {AppTheme.text_muted};
    padding: 0px 8px;
    min-height: {AppTheme.toolbar_button_height}px;
}}
QPushButton[role='timeframe']:hover {{
    background: {rgba(AppTheme.hover, 218)};
    border-color: transparent;
    color: {AppTheme.text};
}}
QPushButton[role='timeframe']:checked {{
    background: {AppTheme.selected};
    border-color: transparent;
    color: {AppTheme.primary};
    font-weight: 800;
}}
QPushButton[role='timeframe']:disabled {{
    background: transparent;
    border-color: transparent;
    color: {AppTheme.text_disabled};
}}
QPushButton[role='workflowMode'] {{
    background: transparent;
    border: 1px solid transparent;
    border-radius: {AppTheme.toolbar_button_radius}px;
    color: {AppTheme.text_muted};
    padding: 0px 9px;
    min-height: {AppTheme.toolbar_button_height}px;
    font-weight: 800;
}}
QPushButton[role='workflowMode']:hover {{
    background: {rgba(AppTheme.hover, 220)};
    border-color: {rgba(AppTheme.active_mode_border, 116)};
    color: {AppTheme.text};
}}
QPushButton[role='workflowMode']:checked {{
    background: {AppTheme.active_mode_soft};
    border-color: {AppTheme.active_mode_border};
    color: {AppTheme.active_mode};
    font-weight: 900;
}}
QPushButton[role='workflowMode']:disabled {{
    background: transparent;
    border-color: transparent;
    color: {AppTheme.text_disabled};
}}
QPushButton[role='primary'] {{
    background: {AppTheme.primary};
    border-color: {AppTheme.primary};
    color: {AppTheme.text_inverse};
    font-weight: 800;
    padding: 7px 14px;
}}
QPushButton[role='primary']:hover {{
    background: {AppTheme.primary_hover};
    border-color: {AppTheme.primary_hover};
}}
QPushButton[role='primary']:disabled {{
    background: {AppTheme.disabled_border};
    border-color: {AppTheme.disabled_border};
    color: {AppTheme.text_disabled};
}}
QPushButton[role='primary'][tone='plain'] {{
    background: transparent;
    border-color: transparent;
    color: {AppTheme.primary};
}}
QPushButton[role='primary'][tone='plain']:hover {{
    background: {rgba(AppTheme.primary_tint, 220)};
    border-color: transparent;
}}
QPushButton[role='secondary'] {{
    background: {AppTheme.primary_tint};
    border-color: {AppTheme.border};
    color: {AppTheme.primary};
    font-weight: 700;
}}
QPushButton[role='utility'],
QPushButton[role='quiet'] {{
    background: {rgba(AppTheme.surface_elevated, 196)};
    color: {AppTheme.text_muted};
    border-color: transparent;
}}
QPushButton[role='utility']:hover,
QPushButton[role='quiet']:hover {{
    color: {AppTheme.text};
    border-color: transparent;
}}
QPushButton[role='utility']:disabled,
QPushButton[role='quiet']:disabled {{
    background: transparent;
    color: {AppTheme.text_disabled};
    border-color: transparent;
}}
QPushButton[role='danger'] {{
    background: {AppTheme.danger};
    border-color: {AppTheme.danger};
    color: {AppTheme.text_inverse};
    font-weight: 800;
}}
QPushButton[role='danger']:hover {{
    background: #92382d;
    border-color: #92382d;
}}
QPushButton[role='danger']:disabled {{
    background: {AppTheme.disabled_border};
    border-color: {AppTheme.disabled_border};
    color: {AppTheme.text_disabled};
}}
QPushButton[role='long'] {{
    background: {AppTheme.long_soft};
    border-color: #d4b0ac;
    color: {AppTheme.long};
    font-weight: 800;
}}
QPushButton[role='long']:disabled {{
    background: {rgba(AppTheme.long_soft, 136)};
    border-color: {rgba("#d4b0ac", 130)};
    color: {AppTheme.text_disabled};
}}
QPushButton[role='short'] {{
    background: {AppTheme.short_soft};
    border-color: #aac4b6;
    color: {AppTheme.short};
    font-weight: 800;
}}
QPushButton[role='short']:disabled {{
    background: {rgba(AppTheme.short_soft, 136)};
    border-color: {rgba("#aac4b6", 130)};
    color: {AppTheme.text_disabled};
}}
QPushButton[role='close'] {{
    background: {AppTheme.close_soft};
    border-color: {rgba(AppTheme.close, 95)};
    color: {AppTheme.close};
    font-weight: 800;
}}
QPushButton[role='reverse'] {{
    background: {AppTheme.reverse_soft};
    border-color: {rgba(AppTheme.reverse, 98)};
    color: {AppTheme.reverse};
    font-weight: 800;
}}
QPushButton[role='close']:disabled,
QPushButton[role='reverse']:disabled {{
    background: {AppTheme.disabled};
    border-color: {AppTheme.disabled_border};
    color: {AppTheme.text_disabled};
}}
QPushButton[compactAction='true'] {{
    border-radius: {AppTheme.radius_sm}px;
    padding: 3px 0px;
    min-height: 18px;
    font-weight: 800;
}}
QPushButton[role='toggle'] {{
    background: transparent;
    color: {AppTheme.text_muted};
    border-color: {rgba(AppTheme.border, 160)};
    border-radius: 6px;
    padding: 3px 8px;
}}
QPushButton[role='toggle']:hover {{
    background: {rgba(AppTheme.hover, 214)};
    border-color: {AppTheme.border};
    color: {AppTheme.text};
}}
QPushButton[role='toggle']:checked {{
    background: {AppTheme.checked};
    border-color: {AppTheme.checked_border};
    color: {AppTheme.primary};
    font-weight: 800;
}}
QPushButton[role='toggle']:disabled {{
    background: transparent;
    border-color: {AppTheme.disabled_border};
    color: {AppTheme.text_disabled};
}}
QPushButton[role='sidebarTab'] {{
    background: transparent;
    border-color: transparent;
    border-radius: {AppTheme.toolbar_button_radius}px;
    color: {AppTheme.text_muted};
    font-weight: 800;
    padding: 0px 8px;
    min-height: 24px;
}}
QPushButton[role='sidebarTab']:hover {{
    background: {rgba(AppTheme.hover, 210)};
    color: {AppTheme.text};
}}
QPushButton[role='sidebarTab']:checked {{
    background: {AppTheme.selected};
    border-color: {rgba(AppTheme.selected_border, 120)};
    color: {AppTheme.primary};
    font-weight: 900;
}}
QPushButton[role='sidebarTab']:disabled {{
    background: transparent;
    border-color: transparent;
    color: {AppTheme.text_disabled};
}}
QPushButton[compactAction='true']:hover {{
    border-color: {AppTheme.primary};
}}
QPushButton[compactAction='true']:pressed {{
    background: {AppTheme.surface_muted};
    border-color: {AppTheme.border_strong};
    padding-top: 4px;
    padding-bottom: 2px;
}}
QPushButton[compactAction='true']:checked {{
    border-color: {AppTheme.primary};
}}
QPushButton[compactAction='true'][role='long']:pressed {{
    background: #f8dede;
    border-color: #d98686;
}}
QPushButton[compactAction='true'][role='short']:pressed {{
    background: #dbf1e4;
    border-color: #7bb493;
}}
QPushButton[compactAction='true'][role='close']:pressed {{
    background: {AppTheme.surface_muted};
    border-color: {rgba(AppTheme.close, 130)};
}}
QPushButton[compactAction='true'][role='reverse']:pressed {{
    background: #ded8ff;
    border-color: {rgba(AppTheme.reverse, 150)};
}}
QPushButton[compactAction='true'][role='quiet']:pressed {{
    background: {AppTheme.surface_muted};
    border-color: {AppTheme.border_strong};
}}
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QTextEdit {{
    background: #fbfdff;
    border: 1px solid {AppTheme.border_strong};
    border-radius: {AppTheme.radius_sm}px;
    color: {AppTheme.text};
    padding: 4px 8px;
    selection-background-color: {AppTheme.primary_soft};
}}
QTextEdit[role='dialogDetail'] {{
    background: {AppTheme.surface};
    border: 1px solid {AppTheme.border};
    border-radius: {AppTheme.radius_md}px;
    padding: 10px 12px;
    font-size: 12px;
    line-height: 1.5;
}}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus, QTextEdit:focus {{
    border-color: {AppTheme.primary};
    background: #ffffff;
}}
QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled, QComboBox:disabled, QTextEdit:disabled {{
    background: {AppTheme.disabled};
    border-color: {AppTheme.disabled_border};
    color: {AppTheme.text_disabled};
}}
QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
    width: 0px;
    height: 0px;
    border: none;
    background: transparent;
}}
QSpinBox::up-arrow, QSpinBox::down-arrow,
QDoubleSpinBox::up-arrow, QDoubleSpinBox::down-arrow {{
    width: 0px;
    height: 0px;
}}
QCheckBox {{
    color: {AppTheme.text};
    spacing: 7px;
}}
QListWidget {{
    padding: 6px;
}}
QListWidget::item {{
    background: {rgba(AppTheme.surface_elevated, 110)};
    border: 1px solid transparent;
    border-radius: {AppTheme.radius_sm}px;
    padding: 9px 10px;
    color: {AppTheme.text_muted};
}}
QListWidget::item:selected {{
    background: {AppTheme.selected};
    border-color: {rgba(AppTheme.selected_border, 124)};
    color: #153e91;
    font-weight: 800;
}}
QTableView {{
    background: {AppTheme.surface};
    alternate-background-color: {AppTheme.table_row_alt};
    border: 1px solid {AppTheme.border_soft};
    border-radius: {AppTheme.radius_sm}px;
    color: {AppTheme.text};
    gridline-color: {rgba(AppTheme.border, 118)};
    selection-background-color: {AppTheme.table_selected};
    selection-color: {AppTheme.text};
}}
QTableView::item {{
    padding: 5px 7px;
    border: none;
}}
QTableView::item:selected {{
    background: {AppTheme.table_selected};
    color: {AppTheme.primary};
}}
QHeaderView::section {{
    background: {AppTheme.table_header};
    border: 0;
    border-right: 1px solid {AppTheme.border_soft};
    border-bottom: 1px solid {AppTheme.border};
    color: {AppTheme.text_muted};
    font-weight: 800;
    padding: 6px 8px;
}}
QScrollBar:vertical, QScrollBar:horizontal {{
    background: transparent;
    border: none;
    margin: 0px;
}}
QScrollBar::handle:vertical, QScrollBar::handle:horizontal {{
    background: {rgba(AppTheme.border_strong, 165)};
    border-radius: 4px;
    min-height: 28px;
    min-width: 28px;
}}
QScrollBar::handle:vertical:hover, QScrollBar::handle:horizontal:hover {{
    background: {rgba(AppTheme.primary, 145)};
}}
QScrollBar::add-line, QScrollBar::sub-line {{
    width: 0px;
    height: 0px;
    border: none;
    background: transparent;
}}
QScrollBar::add-page, QScrollBar::sub-page {{
    background: transparent;
}}
QSplitter::handle {{
    background: transparent;
}}
QStatusBar {{
    background: {AppTheme.bg};
    color: {AppTheme.text_muted};
    border: 0;
    padding: 0px 2px;
}}
QStatusBar::item {{
    border: 0;
    padding: 0px;
    margin: 0px;
}}
QProgressBar {{
    background: {AppTheme.surface_muted};
    border: 0;
    border-radius: 5px;
}}
QProgressBar::chunk {{
    background: {AppTheme.primary};
    border-radius: 5px;
}}
"""


def card_stylesheet() -> str:
    return (
        f"background: {AppTheme.surface}; "
        f"border: 1px solid {AppTheme.border}; "
        f"border-radius: {AppTheme.radius_lg}px;"
    )


def dialog_card_stylesheet() -> str:
    return (
        f"background: {AppTheme.surface_elevated}; "
        f"border: 1px solid {AppTheme.border}; "
        f"border-radius: {AppTheme.radius_xl}px;"
    )


def dialog_stylesheet() -> str:
    return app_stylesheet()


def busy_overlay_stylesheet() -> str:
    return (
        "#busyOverlay { background: transparent; }"
        f"#busyCard {{ background: {rgba(AppTheme.surface_elevated, 248)};"
        f" border: 1px solid {AppTheme.border};"
        f" border-radius: {AppTheme.radius_lg}px; }}"
    )


def progress_bar_stylesheet() -> str:
    return (
        "QProgressBar {"
        f" background: {AppTheme.surface_muted};"
        " border: none;"
        " border-radius: 5px;"
        "}"
        "QProgressBar::chunk {"
        f" background: {AppTheme.primary};"
        " border-radius: 5px;"
        "}"
    )


def color_chip_button_stylesheet(color: str) -> str:
    return (
        f"background: {color};"
        f" border: 1px solid {AppTheme.border_strong};"
        f" border-radius: {AppTheme.radius_sm}px;"
        f" color: {AppTheme.text};"
        " font-weight: 700;"
        " padding: 6px 10px;"
    )


def muted_status_stylesheet() -> str:
    return f"color: {AppTheme.text_muted}; font-size: 12px;"


def emphasized_status_stylesheet() -> str:
    return f"font-size: 13px; font-weight: 700; color: {AppTheme.text};"


def error_banner_stylesheet() -> str:
    return (
        f"color: {AppTheme.danger};"
        f"background: {AppTheme.danger_soft};"
        "border: 1px solid #efc4bc;"
        f"border-radius: {AppTheme.radius_sm}px;"
        "padding: 8px 10px;"
    )


def drawing_tool_button_stylesheet() -> str:
    return f"""
QPushButton {{
    background: {AppTheme.surface_soft};
    border: 1px solid {AppTheme.border};
    border-radius: {AppTheme.toolbar_button_radius}px;
    padding: 0px;
}}
QPushButton:hover {{
    background: {AppTheme.surface_elevated};
    border-color: {AppTheme.border_strong};
}}
QPushButton:pressed {{
    background: {AppTheme.surface_muted};
}}
QPushButton:checked {{
    background: {AppTheme.primary_soft};
    border: 1px solid {AppTheme.primary};
}}
QPushButton:disabled {{
    background: {AppTheme.surface_soft};
    border-color: {AppTheme.border};
}}
"""
