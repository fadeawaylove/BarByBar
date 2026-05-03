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
    bg = "#e7ebef"
    bg_soft = "#f0f3f6"
    surface = "#fcfbf8"
    surface_soft = "#f4f1eb"
    surface_muted = "#ebe5dc"
    surface_elevated = "#fffdf9"
    canvas = "#f7f4ef"
    canvas_gridless = "#f4f1ea"
    border = "#d7d0c5"
    border_strong = "#b6ad9e"
    border_focus = "#24466d"
    text = "#1f2730"
    text_muted = "#66707b"
    text_faint = "#8a928f"
    text_inverse = "#ffffff"
    primary = "#24466d"
    primary_hover = "#1a3859"
    primary_soft = "#dfe7ef"
    primary_tint = "#edf4fb"
    info = "#2d628f"
    success = "#386854"
    success_soft = "#e5f0ea"
    long = "#8f4342"
    long_soft = "#f7e6e4"
    short = "#386854"
    short_soft = "#e5f0ea"
    warning = "#8f6229"
    warning_soft = "#f7eddc"
    danger = "#a84336"
    danger_soft = "#f8e3e0"
    accent = "#f0c36b"
    accent_soft = "#fff3d6"
    radius_sm = 8
    radius_md = 12
    radius_lg = 16
    radius_xl = 18
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
    status_strip_height = 32
    status_button_height = 26
    flat_group_gap = 8
    sidebar_compact_width = 288
    sidebar_width = sidebar_compact_width
    chart_axis = "#b3ab9d"
    chart_preview = "#6e665b"
    chart_measure = "#2f6590"
    chart_marker = "#ded8cf"
    chart_label = "#9a9388"
    chart_label_soft = "#b4ab9c"
    chart_session_end = "#8e8679"
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
QWidget#workspaceTools,
QWidget#workspaceActions,
QWidget#replayUtilityActions,
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
    border-radius: {AppTheme.radius_md}px;
}}
QWidget[card='true'] {{
    background: {rgba(AppTheme.surface_elevated, 168)};
    border: 1px solid {rgba(AppTheme.border, 128)};
    border-radius: {AppTheme.radius_md}px;
}}
ChartWidget[card='true'] {{
    background: {AppTheme.canvas};
    border: 1px solid {rgba(AppTheme.border, 92)};
    border-radius: 6px;
}}
QGroupBox,
QGroupBox[sidebarSection='true'] {{
    background: {rgba(AppTheme.surface_elevated, 172)};
    margin-top: 8px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
    color: {AppTheme.text_faint};
    font-weight: 800;
    letter-spacing: 0.3px;
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
QLabel[role='positionReadout'] {{
    background: {rgba(AppTheme.surface_elevated, 108)};
    border: 1px solid {rgba(AppTheme.border, 168)};
    border-radius: {AppTheme.radius_sm}px;
    color: {AppTheme.text};
    padding: 8px 10px;
    font-weight: 700;
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
    border-radius: 10px;
    color: {AppTheme.text};
    padding: 6px 12px;
    min-height: 24px;
}}
QPushButton:hover {{
    background: {AppTheme.surface_elevated};
    border-color: #9d9384;
}}
QPushButton:pressed {{
    background: {AppTheme.surface_muted};
}}
QPushButton:focus {{
    border-color: {AppTheme.border_focus};
}}
QPushButton:checked {{
    background: {AppTheme.primary_soft};
    border-color: {AppTheme.primary};
    color: #153e91;
    font-weight: 700;
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
    background: {rgba(AppTheme.surface_elevated, 220)};
    border-color: {rgba(AppTheme.border, 180)};
    color: {AppTheme.text};
}}
QPushButton[role='toolbar']:checked {{
    background: {AppTheme.primary_soft};
    border-color: {AppTheme.primary};
    color: #153e91;
    font-weight: 800;
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
    background: {rgba(AppTheme.surface_elevated, 218)};
    border-color: transparent;
    color: {AppTheme.text};
}}
QPushButton[role='timeframe']:checked {{
    background: {AppTheme.primary_tint};
    border-color: transparent;
    color: {AppTheme.primary};
    font-weight: 800;
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
QPushButton[role='long'] {{
    background: {AppTheme.long_soft};
    border-color: #d4b0ac;
    color: {AppTheme.long};
    font-weight: 800;
}}
QPushButton[role='short'] {{
    background: {AppTheme.short_soft};
    border-color: #aac4b6;
    color: {AppTheme.short};
    font-weight: 800;
}}
QPushButton[compactAction='true'] {{
    border-radius: 10px;
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
    background: {rgba(AppTheme.surface_elevated, 214)};
    border-color: {AppTheme.border};
    color: {AppTheme.text};
}}
QPushButton[role='toggle']:checked {{
    background: {AppTheme.primary_soft};
    border-color: {AppTheme.primary};
    color: {AppTheme.primary};
    font-weight: 800;
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
    background: {rgba(AppTheme.surface_elevated, 210)};
    color: {AppTheme.text};
}}
QPushButton[role='sidebarTab']:checked {{
    background: {AppTheme.primary_tint};
    border-color: {rgba(AppTheme.primary, 120)};
    color: {AppTheme.primary};
    font-weight: 900;
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
QPushButton[compactAction='true'][role='quiet']:pressed {{
    background: {AppTheme.surface_muted};
    border-color: {AppTheme.border_strong};
}}
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QTextEdit {{
    background: #fdfcf9;
    border: 1px solid {AppTheme.border_strong};
    border-radius: 8px;
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
    background: #fffefb;
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
    border-radius: 8px;
    padding: 9px 10px;
    color: {AppTheme.text_muted};
}}
QListWidget::item:selected {{
    background: {AppTheme.primary_soft};
    color: #153e91;
    font-weight: 800;
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
