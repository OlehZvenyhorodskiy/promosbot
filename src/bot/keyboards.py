from typing import Set, Optional, Dict
from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from src.core.constants import SUPERMARKETS, CATEGORIES, SUPPORTED_LANGUAGES
from src.i18n.translations import get_text, get_category_name

def get_main_reply_keyboard(lang: str = "en") -> ReplyKeyboardMarkup:
    keyboard = [
        [
            KeyboardButton(text=get_text("menu_promos", lang)),
            KeyboardButton(text=get_text("menu_search", lang)),
        ],
        [
            KeyboardButton(text=get_text("menu_folders", lang)),
            KeyboardButton(text=get_text("menu_stores", lang)),
        ],
        [
            KeyboardButton(text=get_text("menu_categories", lang)),
            KeyboardButton(text=get_text("menu_favorites", lang)),
        ],
        [
            KeyboardButton(text=get_text("menu_settings", lang)),
            KeyboardButton(text=get_text("menu_test", lang)),
        ],
        [
            KeyboardButton(text=get_text("menu_help", lang)),
        ],
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def get_unified_welcome_keyboard(lang: str = "en") -> InlineKeyboardMarkup:
    rows = []
    # Language picker row
    lang_row = []
    for code, info in SUPPORTED_LANGUAGES.items():
        lang_row.append(
            InlineKeyboardButton(
                text=f"{info['flag']} {info['name']}",
                callback_data=f"lang:{code}",
            )
        )
    rows.append(lang_row[:2])
    rows.append(lang_row[2:])

    # Fast start actions
    rows.append([
        InlineKeyboardButton(text=get_text("menu_promos", lang), callback_data="nav:browse_stores"),
        InlineKeyboardButton(text=get_text("menu_folders", lang), callback_data="nav:folders"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def get_main_hub_keyboard(lang: str = "en") -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=get_text("menu_promos", lang), callback_data="nav:browse_stores")],
        [InlineKeyboardButton(text=get_text("menu_folders", lang), callback_data="nav:folders")],
        [
            InlineKeyboardButton(text=get_text("menu_favorites", lang), callback_data="nav:favs"),
            InlineKeyboardButton(text=get_text("menu_settings", lang), callback_data="nav:settings"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)

def get_language_keyboard() -> InlineKeyboardMarkup:
    buttons = []
    for code, info in SUPPORTED_LANGUAGES.items():
        buttons.append(
            InlineKeyboardButton(
                text=f"{info['flag']} {info['name']}",
                callback_data=f"lang:{code}",
            )
        )
    rows = [buttons[i : i + 2] for i in range(0, len(buttons), 2)]
    rows.append([InlineKeyboardButton(text="⬅️ Back", callback_data="nav:settings")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def get_store_drilldown_keyboard(store_counts: Dict[str, int], total_count: int, lang: str = "en") -> InlineKeyboardMarkup:
    buttons = []
    for store_id, info in SUPERMARKETS.items():
        count = store_counts.get(store_id, 0)
        btn_text = f"{info['emoji']} {info['name']} ({count})"
        buttons.append(
            InlineKeyboardButton(
                text=btn_text,
                callback_data=f"st:{store_id}",
            )
        )

    rows = [buttons[i : i + 2] for i in range(0, len(buttons), 2)]

    # View all stores button
    all_label = get_text("all_stores_btn", lang, count=total_count)
    rows.append([InlineKeyboardButton(text=all_label, callback_data="p:all:0")])
    rows.append([InlineKeyboardButton(text=get_text("btn_back_menu", lang), callback_data="nav:main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def get_store_detail_keyboard(
    store_id: str,
    promo_count: int,
    folder_url: Optional[str],
    cat_counts: Dict[str, int],
    lang: str = "en",
) -> InlineKeyboardMarkup:
    rows = []

    # 1. View all deals in this store
    view_all_text = get_text("view_all_store_deals", lang, count=promo_count)
    rows.append([InlineKeyboardButton(text=view_all_text, callback_data=f"p:s:{store_id}:0")])

    # 2. Official weekly folder link
    if folder_url:
        folder_text = get_text("open_folder_btn", lang)
        rows.append([InlineKeyboardButton(text=folder_text, url=folder_url)])

    # 3. Categories with items in this store (1 category per row so names & numbers never truncate)
    for cat_id, info in CATEGORIES.items():
        c_count = cat_counts.get(cat_id, 0)
        if c_count > 0:
            c_name = get_category_name(cat_id, lang)
            rows.append([
                InlineKeyboardButton(
                    text=f"{info['emoji']} {c_name} ({c_count})",
                    callback_data=f"p:sc:{store_id}:{cat_id}:0",
                )
            ])

    # 4. Navigation: back to all stores
    rows.append([
        InlineKeyboardButton(text=get_text("btn_back_stores", lang), callback_data="nav:browse_stores"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def get_folders_keyboard(lang: str = "en") -> InlineKeyboardMarkup:
    rows = []
    buttons = []
    for store_id, info in SUPERMARKETS.items():
        f_url = info.get("folder_url")
        if f_url:
            buttons.append(
                InlineKeyboardButton(
                    text=f"{info['emoji']} {info['name']}",
                    url=f_url,
                )
            )

    for i in range(0, len(buttons), 2):
        rows.append(buttons[i : i + 2])

    # General Belgian folder aggregator
    rows.append([
        InlineKeyboardButton(
            text=get_text("folder_generic_btn", lang),
            url="https://www.folderbode.be",
        )
    ])
    rows.append([InlineKeyboardButton(text=get_text("btn_back_menu", lang), callback_data="nav:main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def get_stores_keyboard(enabled_stores: Set[str], lang: str = "en") -> InlineKeyboardMarkup:
    buttons = []
    for store_id, info in SUPERMARKETS.items():
        is_on = store_id in enabled_stores
        icon = "✅" if is_on else "⬜"
        text = f"{icon} {info['emoji']} {info['name']}"
        buttons.append(
            InlineKeyboardButton(
                text=text,
                callback_data=f"toggle_store:{store_id}",
            )
        )

    rows = [buttons[i : i + 2] for i in range(0, len(buttons), 2)]
    rows.append(
        [
            InlineKeyboardButton(text=get_text("all_stores_on", lang), callback_data="stores_all:1"),
            InlineKeyboardButton(text=get_text("all_stores_off", lang), callback_data="stores_all:0"),
        ]
    )
    rows.append([InlineKeyboardButton(text=get_text("btn_back_menu", lang), callback_data="nav:main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def get_categories_keyboard(enabled_categories: Set[str], lang: str = "en") -> InlineKeyboardMarkup:
    buttons = []
    for cat_id, info in CATEGORIES.items():
        is_on = cat_id in enabled_categories
        icon = "✅" if is_on else "⬜"
        cat_name = get_category_name(cat_id, lang)
        text = f"{icon} {info['emoji']} {cat_name}"
        buttons.append(
            InlineKeyboardButton(
                text=text,
                callback_data=f"toggle_cat:{cat_id}",
            )
        )

    rows = [buttons[i : i + 2] for i in range(0, len(buttons), 2)]
    rows.append(
        [
            InlineKeyboardButton(text=get_text("all_categories_on", lang), callback_data="cats_all:1"),
            InlineKeyboardButton(text=get_text("all_categories_off", lang), callback_data="cats_all:0"),
        ]
    )
    rows.append([InlineKeyboardButton(text=get_text("btn_back_menu", lang), callback_data="nav:main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def get_settings_keyboard(lang: str = "en") -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=get_text("settings_lang_btn", lang), callback_data="settings:lang")],
        [InlineKeyboardButton(text=get_text("settings_stores_btn", lang), callback_data="nav:stores")],
        [InlineKeyboardButton(text=get_text("settings_categories_btn", lang), callback_data="nav:categories")],
        [InlineKeyboardButton(text=get_text("settings_notif_btn", lang), callback_data="settings:notif")],
        [InlineKeyboardButton(text=get_text("btn_back_menu", lang), callback_data="nav:main")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)

def get_notification_keyboard(current_mode: str, current_hour: int, lang: str = "en") -> InlineKeyboardMarkup:
    check_instant = "✅ " if current_mode == "instant" else "⬜ "
    check_digest = "✅ " if current_mode == "digest" else "⬜ "
    check_off = "✅ " if current_mode == "off" else "⬜ "

    rows = [
        [InlineKeyboardButton(text=f"{check_instant}{get_text('notif_instant', lang)}", callback_data="notif_set:instant")],
        [InlineKeyboardButton(text=f"{check_digest}{get_text('notif_digest', lang)}", callback_data="notif_set:digest")],
    ]

    if current_mode == "digest":
        hour_buttons = []
        for h in [7, 8, 9, 10]:
            h_check = "🎯 " if current_hour == h else ""
            hour_buttons.append(
                InlineKeyboardButton(
                    text=f"{h_check}{h:02d}:00",
                    callback_data=f"digest_hour:{h}",
                )
            )
        rows.append(hour_buttons)

    rows.append([InlineKeyboardButton(text=f"{check_off}{get_text('notif_off', lang)}", callback_data="notif_set:off")])
    rows.append([InlineKeyboardButton(text=get_text("btn_back_settings", lang), callback_data="nav:settings")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def get_new_promos_keyboard(store_counts: Dict[str, int], batch_id: int, lang: str = "en") -> InlineKeyboardMarkup:
    rows = []
    for store_id, count in store_counts.items():
        info = SUPERMARKETS.get(store_id, {"name": store_id.title(), "emoji": "🏪"})
        rows.append([
            InlineKeyboardButton(
                text=f"{info.get('emoji', '🏪')} {info.get('name', store_id)} ({count})",
                callback_data=f"new:{batch_id}:{store_id}",
            )
        ])
    rows.append([InlineKeyboardButton(text=get_text("btn_back_stores", lang), callback_data="nav:browse_stores")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def get_promo_card_keyboard(
    promo_id: str,
    deal_url: Optional[str] = None,
    is_fav: bool = False,
    current_index: int = 0,
    total_count: int = 1,
    lang: str = "en",
    nav_code: str = "all",
    store_id: Optional[str] = None,
    image_url: Optional[str] = None,
    nav_prefix: Optional[str] = None,
    **kwargs,
) -> InlineKeyboardMarkup:
    effective_nav = nav_prefix or nav_code or "all"
    rows = []

    # 1. Action row: Store link
    action_row = []
    store_landing_url = SUPERMARKETS.get(store_id, {}).get("url", "").rstrip("/").casefold()
    specific_deal_url = (deal_url or "").split("?", 1)[0].rstrip("/").casefold()
    if deal_url and deal_url.startswith("http") and specific_deal_url != store_landing_url:
        action_row.append(InlineKeyboardButton(text=get_text("btn_open_deal", lang), url=deal_url))
    if action_row:
        rows.append(action_row)

    # 2. Compact bookmark button (safe under 25 bytes)
    fav_text = get_text("btn_remove_fav" if is_fav else "btn_save_fav", lang)
    rows.append([InlineKeyboardButton(text=fav_text, callback_data=f"fav:{promo_id}")])

    # 3. Compact navigation buttons (prev / count / next)
    if total_count > 1:
        prev_idx = (current_index - 1) % total_count
        next_idx = (current_index + 1) % total_count
        rows.append([
            InlineKeyboardButton(text=get_text("btn_prev", lang), callback_data=f"p:{effective_nav}:{prev_idx}"),
            InlineKeyboardButton(text=f"{current_index + 1}/{total_count}", callback_data="noop"),
            InlineKeyboardButton(text=get_text("btn_next", lang), callback_data=f"p:{effective_nav}:{next_idx}"),
        ])

    # 4. Contextual back button -> directly to store categories or store list!
    if store_id:
        rows.append([
            InlineKeyboardButton(text=get_text("btn_back_categories", lang), callback_data=f"st:{store_id}"),
            InlineKeyboardButton(text=get_text("btn_back_stores", lang), callback_data="nav:browse_stores"),
        ])
    else:
        rows.append([
            InlineKeyboardButton(text=get_text("btn_back_stores", lang), callback_data="nav:browse_stores"),
        ])

    return InlineKeyboardMarkup(inline_keyboard=rows)
